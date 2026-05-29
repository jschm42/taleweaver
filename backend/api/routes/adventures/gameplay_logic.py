from __future__ import annotations
import asyncio
import json
import logging
import os
import random
import re
import time
import uuid
from types import SimpleNamespace
from collections.abc import AsyncGenerator, Awaitable, Callable
from copy import deepcopy
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from backend.api.routes.adventures.logic import AdventureLogic
from backend.api.routes.adventures.turn_helpers import (
    TurnCombatStateHelper,
    TurnProgressionBuilder,
    TurnSessionStateHelper,
)
from backend.api.routes.adventures.turn_llm_pipeline import TurnLlmContextBuilder
from backend.core import prompts
from backend.core.config import settings
from backend.core.llm_logger import log_structured_event
from backend.core.llm_router import GameMasterLLM
from backend.engine.command_parser import CommandParser
from backend.engine.debug_engine import DebugEngine
from backend.engine.map_engine import MapEngine
from backend.engine.quest_manager import QuestManager
from backend.engine.session_checkpoint_service import SessionCheckpointService
from backend.engine.adventure_generator_service import AdventureGeneratorService
from backend.engine.rule_engine import (
    RESOURCE_CAP,
    AdventureGenerationRequest,
    AdventureGeneratorToolIntent,
    AttackResult,
    GameEvent,
    GameOverException,
    RuleEngine,
    SkillCheckResult,
    ToolResults,
    WorldEntityUpdate,
)
from backend.engine.skill_check import roll_attack, roll_skill_check
from backend.engine.stat_aggregator import calculate_total_stats
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.chat import ChatMessage
from backend.models.session_state import SessionState
from backend.models.user import User
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene
from backend.utils.path_security import ensure_within_data_dir as _ensure_within_data_dir
from backend.utils.path_security import sanitize_path_component as _sanitize_path_component

logger = logging.getLogger(__name__)

# Constants
WALKTHROUGH_REVEAL_COST = 200
WALKTHROUGH_HINT_COST = 50
AG_IMAGE_CONFIRMATION_STATE_KEY = "__ag_image_confirmation__"
AG_LAST_REQUEST_STATE_KEY = "__ag_last_generation_request__"
AG_LAST_ERROR_STATE_KEY = "__ag_last_generation_error__"
GM_NOTES_STATE_KEY = "__gm_notes__"
GM_NOTES_MAX_ITEMS = 20
GM_NOTES_PROMPT_MAX_ITEMS = 12
GM_CHAT_RULE_PASS_NPCS_MAX_ITEMS = 10
TERMINAL_EPILOGUE_STATE_KEY = "__terminal_epilogue__"
PROMPT_SUGGESTIONS_STATE_KEY = "__prompt_suggestions__"
PROMPT_SUGGESTION_MAX_VISIBLE_NPCS = 12
PROMPT_SUGGESTION_MAX_VISIBLE_OBJECTS = 16
PROMPT_SUGGESTION_MAX_UNLOCKED_EXITS = 8
PROMPT_SUGGESTION_MAX_INVENTORY_ITEMS = 16
PROMPT_SUGGESTION_MAX_LAST_RESPONSE_CHARS = 1200
CHECKPOINT_REASON_SCENE_CHANGE = "SCENE_CHANGE"
CHECKPOINT_REASON_QUEST_UPDATE = "QUEST_UPDATE"
CHECKPOINT_REASON_AWARD_GRANTED = "AWARD_GRANTED"
PROMPT_SUGGESTIONS_STATE_KEY = "__prompt_suggestions__"
PROMPT_SUGGESTION_MAX_VISIBLE_NPCS = 12
PROMPT_SUGGESTION_MAX_VISIBLE_OBJECTS = 16
PROMPT_SUGGESTION_MAX_UNLOCKED_EXITS = 8
PROMPT_SUGGESTION_MAX_INVENTORY_ITEMS = 16
PROMPT_SUGGESTION_MAX_LAST_RESPONSE_CHARS = 1200


def _is_token_limit_error(exc: Exception) -> bool:
    text = str(exc or "").lower()
    patterns = (
        "token limit",
        "too many tokens",
        "maximum context length",
        "context length exceeded",
        "context window",
        "prompt is too long",
        "max_tokens",
    )
    return any(p in text for p in patterns)


def _friendly_token_limit_message() -> str:
    return "The Game Master needs a shorter context right now. Please try again with a shorter request."


def _is_rate_limit_error(exc: Exception) -> bool:
    text = str(exc or "").lower()
    patterns = (
        "rate limit",
        "too many requests",
        "quota exceeded",
        "429",
    )
    return any(p in text for p in patterns)


def _is_timeout_error(exc: Exception) -> bool:
    text = str(exc or "").lower()
    patterns = (
        "timeout",
        "timed out",
        "read timeout",
        "request timeout",
        "deadline exceeded",
    )
    return any(p in text for p in patterns)


def _is_service_unavailable_error(exc: Exception) -> bool:
    text = str(exc or "").lower()
    patterns = (
        "service unavailable",
        "temporarily unavailable",
        "overloaded",
        "bad gateway",
        "502",
        "503",
        "504",
    )
    return any(p in text for p in patterns)


def _friendly_llm_error_message(exc: Exception) -> str | None:
    if _is_token_limit_error(exc):
        return _friendly_token_limit_message()
    if _is_rate_limit_error(exc):
        return "The Game Master is busy right now. Please try again in a moment."
    if _is_timeout_error(exc):
        return "The Game Master took too long to respond. Please try again."
    if _is_service_unavailable_error(exc):
        return "The Game Master is temporarily unavailable. Please try again shortly."
    return None


def _friendly_llm_unexpected_error_message() -> str:
    return "The Game Master encountered an unexpected issue. Please try again."


def _llm_error_type(exc: Exception) -> str | None:
    if _is_token_limit_error(exc):
        return "token_limit"
    if _is_rate_limit_error(exc):
        return "rate_limit"
    if _is_timeout_error(exc):
        return "timeout"
    if _is_service_unavailable_error(exc):
        return "service_unavailable"
    return None

class GameTurnManager:
    """Class to manage the complex unified game turn (chat interaction)."""

    def __init__(self, db: AsyncSession, game_id: str, user: User):
        self.db = db
        self.game_id = game_id
        self.user = user
        self.state: SessionState | None = None
        self.adventure: AdventureTemplate | None = None
        self.avatar: Avatar | None = None
        self.stop_requested = False
        self.turn_language: str | None = None
        self._progression = TurnProgressionBuilder(
            self,
            gm_notes_prompt_max_items=GM_NOTES_PROMPT_MAX_ITEMS,
            gm_chat_rule_pass_npcs_max_items=GM_CHAT_RULE_PASS_NPCS_MAX_ITEMS,
            gm_chat_prompt_template=prompts.GM_CHAT_MINIMAL_RULE_PASS_PROMPT,
        )
        self._session_helper = TurnSessionStateHelper(
            self,
            gm_notes_state_key=GM_NOTES_STATE_KEY,
            gm_notes_max_items=GM_NOTES_MAX_ITEMS,
            terminal_epilogue_state_key=TERMINAL_EPILOGUE_STATE_KEY,
        )
        self._combat_state_helper = TurnCombatStateHelper(self)
        self._llm_context_builder = TurnLlmContextBuilder(self)
        self._pending_checkpoint_reasons: set[str] = set()
        self._checkpoint_scene_label: str | None = None

    def _queue_checkpoint(self, reason: str, *, scene_label: str | None = None) -> None:
        self._pending_checkpoint_reasons.add(reason)
        if scene_label:
            self._checkpoint_scene_label = scene_label

    async def _persist_pending_checkpoints(self) -> list[dict[str, Any]]:
        if not self._pending_checkpoint_reasons or not self.state:
            return []

        checkpoint_events: list[dict[str, Any]] = []
        reasons = sorted(self._pending_checkpoint_reasons)
        for reason in reasons:
            checkpoint = await SessionCheckpointService.create_checkpoint(
                self.db,
                self.state.session_id,
                reason,
                scene_label=self._checkpoint_scene_label,
            )
            checkpoint_events.append(
                {
                    "id": checkpoint.id,
                    "trigger_reason": checkpoint.trigger_reason,
                    "created_at": checkpoint.created_at.isoformat() if checkpoint.created_at else None,
                }
            )

        await self.db.commit()
        self._pending_checkpoint_reasons.clear()
        self._checkpoint_scene_label = None
        return checkpoint_events

    async def _unhide_entities_in_text(self, text: str) -> None:
        """Scan text for entity ID tokens like 'ID: TALKING_RAT' and set their
        session override `is_hidden` to False so they appear in the scene.
        """
        if not text:
            return
        ids = set(re.findall(r"ID:\s*([A-Z0-9_]+)", text or ""))
        if not ids or not self.state:
            return
        states = dict(self.state.entity_states or {})
        changed = False
        for eid in ids:
            if eid not in states:
                states[eid] = {}
            if states[eid].get("is_hidden") is not False:
                states[eid]["is_hidden"] = False
                changed = True
        if changed:
            self.state.entity_states = states
            flag_modified(self.state, "entity_states")
            try:
                await self.db.commit()
            except Exception:
                # Don't let unhide failures break the turn; log and continue
                logger.exception("Failed to commit entity unhide changes")

    async def _save_chat_message(self, role: str, content: str) -> ChatMessage:
        """Persist a ChatMessage and run post-save processing (unhide referenced entities).
        Returns the created ChatMessage instance.
        """
        cm = ChatMessage(session_id=self.state.session_id, role=role, content=content)
        self.db.add(cm)
        try:
            await self.db.flush()
        except Exception:
            logger.exception("Failed to flush ChatMessage to DB")
        # Attempt to unhide any referenced entities inside the message text
        try:
            await self._unhide_entities_in_text(content)
        except Exception:
            logger.exception("Failed to unhide entities for message")
        return cm

    @staticmethod
    def _compact_json(payload: object) -> str:
        return TurnProgressionBuilder.compact_json(payload)

    @staticmethod
    def _is_lookaround_request(user_msg: str) -> bool:
        normalized = (user_msg or "").strip().lower()
        if not normalized:
            return False
        return (
            "look around" in normalized
            or normalized in {"[look around]", "/lookaround", "/look", "look"}
        )

    async def _build_scene_exits_context_json(self) -> str:
        exits_res = await self.db.execute(
            select(WorldExit).where(
                WorldExit.from_scene_id == self.state.current_scene_id,
                WorldExit.session_id == self.game_id,
            )
        )
        exits = list(exits_res.scalars().all())
        if not exits:
            return "[]"

        destination_ids = [str(ex.to_scene_id) for ex in exits if ex.to_scene_id]
        destination_label_map: dict[str, str] = {}
        if destination_ids:
            scenes_res = await self.db.execute(
                select(WorldScene).where(
                    WorldScene.session_id == self.game_id,
                    WorldScene.id.in_(destination_ids),
                )
            )
            destination_label_map = {
                str(scene.id): (scene.label or str(scene.id))
                for scene in scenes_res.scalars().all()
            }

        exit_refs: list[dict[str, Any]] = []
        for ex in exits:
            exit_refs.append(
                {
                    "label": (ex.label or "").strip(),
                    "destination_scene_id": str(ex.to_scene_id or "").strip(),
                    "destination_scene_label": destination_label_map.get(str(ex.to_scene_id), str(ex.to_scene_id or "")),
                    "is_locked": bool(ex.is_locked),
                }
            )

        return self._compact_json(exit_refs)

    def _build_mechanics_awards(self) -> list[dict]:
        return self._progression.build_mechanics_awards()

    def _build_chat_progression_quests(self) -> list[dict]:
        return self._progression.build_chat_progression_quests()

    @staticmethod
    def _build_chat_progression_awards(unearned_awards: list[dict]) -> list[dict]:
        return TurnProgressionBuilder.build_chat_progression_awards(unearned_awards)

    @staticmethod
    def _build_chat_progression_npcs(entities: list[WorldEntity]) -> list[dict]:
        reduced_npcs = []
        for entity in entities:
            if (entity.entity_type or "").upper() != "NPC":
                continue
            reduced_npcs.append(
                {
                    "id": entity.id,
                    "name": entity.name,
                    "scene_id": entity.current_scene_id,
                    "position": entity.spatial_position,
                    "inventory": entity.inventory or [],
                }
            )
            if len(reduced_npcs) >= GM_CHAT_RULE_PASS_NPCS_MAX_ITEMS:
                break
        return reduced_npcs

    @staticmethod
    def _build_chat_progression_scenes(session_scenes: list[WorldScene]) -> list[dict]:
        return TurnProgressionBuilder.build_chat_progression_scenes(session_scenes)

    @staticmethod
    def _build_chat_progression_exits(exits: list[WorldExit]) -> list[dict]:
        return TurnProgressionBuilder.build_chat_progression_exits(exits)

    def _build_chat_rule_pass_prompt(self, quests: list[dict], awards: list[dict], npcs: list[dict], scenes: list[dict], exits: list[dict]) -> str:
        prompt = self._progression.build_chat_rule_pass_prompt(quests, awards, npcs, scenes, exits)

        if self.state.allow_dynamic_items:
            prompt += (
                "\n\nDYNAMIC ITEMS IS ENABLED:\n"
                "- You are allowed to create/generate brand new items on-the-fly if contextually appropriate using `new_inventory_items` or `spawned_items`."
            )
        else:
            prompt += (
                "\n\nDYNAMIC ITEMS IS DISABLED:\n"
                "- CRITICAL: You are NOT allowed to create/generate brand new items on-the-fly. You must ONLY move/use pre-defined items that already exist in the world or in NPC inventories."
            )
        return prompt

    def _get_gm_notes(self) -> list[str]:
        return self._session_helper.get_gm_notes()

    def _get_terminal_epilogue_state(self) -> dict[str, bool]:
        return self._session_helper.get_terminal_epilogue_state()

    def _terminal_status_flags(self) -> tuple[bool, bool]:
        return self._session_helper.terminal_status_flags()

    def _is_terminal_epilogue_pending(self) -> bool:
        return self._session_helper.is_terminal_epilogue_pending()

    def _is_input_locked(self) -> bool:
        return self._session_helper.is_input_locked()

    def _set_terminal_epilogue_sent(self, status: str, sent: bool = True) -> None:
        self._session_helper.set_terminal_epilogue_sent(status, sent)

    def _build_terminal_flags_payload(self) -> dict[str, Any]:
        return self._session_helper.build_terminal_flags_payload()

    @staticmethod
    def extract_prompt_suggestions(exit_states: Any) -> list[str]:
        """Return up to three stored prompt suggestions from session exit_state payload."""
        if not isinstance(exit_states, dict):
            return []
        raw = exit_states.get(PROMPT_SUGGESTIONS_STATE_KEY)
        if not isinstance(raw, list):
            return []
        result: list[str] = []
        for entry in raw:
            if not isinstance(entry, str):
                continue
            cleaned = " ".join(entry.strip().split())
            if cleaned:
                result.append(cleaned)
            if len(result) >= 3:
                break
        return result

    @staticmethod
    def _truncate_suggestion_words(text: str, max_words: int = 6) -> str:
        words = [w for w in text.strip().split() if w]
        if not words:
            return ""
        return " ".join(words[:max_words])

    @classmethod
    def _normalize_prompt_suggestions(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for value in values:
            cleaned = cls._truncate_suggestion_words(value)
            if not cleaned:
                continue
            key = cleaned.lower()
            if key in seen:
                continue
            seen.add(key)
            normalized.append(cleaned)
            if len(normalized) >= 3:
                break
        return normalized

    @staticmethod
    def _parse_json_string_array(raw: str) -> list[str]:
        text = (raw or "").strip()
        if not text:
            return []
        parsed: Any = None
        try:
            parsed = json.loads(text)
        except Exception:
            match = re.search(r"\[[\s\S]*\]", text)
            if not match:
                return []
            try:
                parsed = json.loads(match.group(0))
            except Exception:
                return []
        if not isinstance(parsed, list):
            return []
        return [entry for entry in parsed if isinstance(entry, str)]

    def _build_prompt_suggestions_payload(self) -> dict[str, Any]:
        return {"prompt_suggestions": self.extract_prompt_suggestions(self.state.exit_states or {})}

    def _set_prompt_suggestions_state(self, suggestions: list[str]) -> None:
        exit_states = dict(self.state.exit_states or {})
        normalized = self._normalize_prompt_suggestions(suggestions)
        if normalized:
            exit_states[PROMPT_SUGGESTIONS_STATE_KEY] = normalized
        else:
            exit_states.pop(PROMPT_SUGGESTIONS_STATE_KEY, None)
        self.state.exit_states = exit_states
        flag_modified(self.state, "exit_states")

    def _fallback_prompt_suggestions(
        self,
        *,
        scene_label: str,
        visible_objects: list[str],
        visible_npcs: list[str],
        inventory_items: list[str],
    ) -> list[str]:
        sensory_target = visible_objects[0] if visible_objects else scene_label or "the area"
        interaction_target = visible_npcs[0] if visible_npcs else (inventory_items[0] if inventory_items else sensory_target)
        fallback = [
            f"Examine {sensory_target}".strip(),
            f"Ask {interaction_target} carefully".strip(),
            "Pause and read the room",
        ]
        return self._normalize_prompt_suggestions(fallback)

    async def _build_player_only_suggestion_context(self) -> dict[str, Any]:
        """Build a spoiler-safe suggestion context (visible NPCs/objects, unlocked exits, inventory)."""
        scene_res = await self.db.execute(
            select(WorldScene).where(
                WorldScene.id == self.state.current_scene_id,
                WorldScene.session_id == self.game_id,
            )
        )
        current_scene = scene_res.scalars().first()
        scene_label = current_scene.label if current_scene else self.state.current_scene_id or "Current Scene"
        scene_description = current_scene.description if current_scene else ""

        ent_res = await self.db.execute(
            select(WorldEntity).where(
                WorldEntity.session_id == self.game_id,
                WorldEntity.current_scene_id == self.state.current_scene_id,
            )
        )
        entities = list(ent_res.scalars().all())
        states = self.state.entity_states or {}
        visible_npcs: list[str] = []
        visible_objects: list[str] = []
        for ent in entities:
            ov = states.get(ent.id) or {}
            is_hidden = bool(ov.get("is_hidden", ent.is_hidden))
            is_in_inventory = bool(ov.get("is_in_inventory", ent.is_in_inventory))
            if is_hidden or is_in_inventory:
                continue
            if (ent.entity_type or "").upper() == "NPC":
                visible_npcs.append(ent.name)
            elif (ent.entity_type or "").upper() == "OBJECT":
                visible_objects.append(ent.name)

        exits_res = await self.db.execute(
            select(WorldExit).where(
                WorldExit.session_id == self.game_id,
                WorldExit.from_scene_id == self.state.current_scene_id,
            )
        )
        unlocked_exits = [ex.label for ex in exits_res.scalars().all() if not ex.is_locked]

        inventory_items = [
            str(item.get("name") or item.get("id") or "").strip()
            for item in (self.avatar.inventory or [])
            if isinstance(item, dict) and str(item.get("name") or item.get("id") or "").strip()
        ]

        return {
            "scene_label": scene_label,
            "scene_description": scene_description,
            "visible_npcs": visible_npcs[:PROMPT_SUGGESTION_MAX_VISIBLE_NPCS],
            "visible_objects": visible_objects[:PROMPT_SUGGESTION_MAX_VISIBLE_OBJECTS],
            "unlocked_exits": unlocked_exits[:PROMPT_SUGGESTION_MAX_UNLOCKED_EXITS],
            "inventory_items": inventory_items[:PROMPT_SUGGESTION_MAX_INVENTORY_ITEMS],
        }

    async def _load_last_assistant_message(self) -> str:
        res = await self.db.execute(
            select(ChatMessage.content)
            .where(
                ChatMessage.session_id == self.state.session_id,
                ChatMessage.role == "assistant",
            )
            .order_by(ChatMessage.created_at.desc())
            .limit(1)
        )
        value = res.scalar_one_or_none()
        return str(value or "").strip()

    async def _generate_prompt_suggestions(self, last_response: str) -> list[str]:
        """Generate three short UI prompt suggestions, with deterministic fallback and state persistence."""
        context = await self._build_player_only_suggestion_context()
        fallback = self._fallback_prompt_suggestions(
            scene_label=context["scene_label"],
            visible_objects=context["visible_objects"],
            visible_npcs=context["visible_npcs"],
            inventory_items=context["inventory_items"],
        )
        llm_settings = self.user.llm_settings or {}
        provider = (
            llm_settings.get("small_model_provider")
            or llm_settings.get("complex_model_provider")
            or llm_settings.get("preferred_provider")
            or "openai"
        )
        model = llm_settings.get("small_model") or "gpt-4o-mini"

        suggestions: list[str] = []
        try:
            llm = GameMasterLLM(self.user, provider=provider, model_category="small")
            user_prompt = prompts.PROMPT_SUGGESTION_USER_PROMPT_TEMPLATE.format(
                scene_context=f"{context['scene_label']}: {context['scene_description']}".strip(),
                visible_npcs=json.dumps(context["visible_npcs"], ensure_ascii=False),
                visible_objects=json.dumps(context["visible_objects"], ensure_ascii=False),
                unlocked_exits=json.dumps(context["unlocked_exits"], ensure_ascii=False),
                inventory_items=json.dumps(context["inventory_items"], ensure_ascii=False),
                last_response=(last_response or "").strip()[:PROMPT_SUGGESTION_MAX_LAST_RESPONSE_CHARS],
            )
            raw = await llm.aexecute_simple_task(
                prompts.PROMPT_SUGGESTION_SYSTEM_PROMPT,
                user_prompt,
                model,
                adventure_id=self.state.template_id,
                game_id=self.game_id,
                operation="chat_turn",
                phase="prompt_suggestions",
            )
            suggestions = self._normalize_prompt_suggestions(self._parse_json_string_array(raw))
        except Exception as exc:
            logger.warning("[Turn %s] Prompt suggestion generation failed: %s", self.game_id, exc)

        if len(suggestions) < 3:
            suggestions = self._normalize_prompt_suggestions(suggestions + fallback)
        self._set_prompt_suggestions_state(suggestions[:3])
        return suggestions[:3]

    def _apply_gm_notes_update(
        self,
        remember_notes: list[str] | None,
        forget_notes: list[str] | None,
        clear_notes: bool,
    ) -> None:
        self._session_helper.apply_gm_notes_update(remember_notes, forget_notes, clear_notes)

    def _build_gm_notes_prompt_block(self) -> str:
        return self._session_helper.build_gm_notes_prompt_block()

    @staticmethod
    def _build_progression_event(intent: AdventureGeneratorToolIntent) -> GameEvent:
        return TurnProgressionBuilder.build_progression_event(intent)

    async def initialize(self) -> bool:
        """Loads all necessary context for the turn."""
        start = time.perf_counter()
        self.state = await AdventureLogic.resolve_session_state(self.db, self.game_id, user_id=self.user.id)
        if not self.state: 
            logger.warning(f"[Turn {self.game_id}] Initialization failed: Session state not found.")
            return False
            
        adv_res = await self.db.execute(select(AdventureTemplate).where(AdventureTemplate.id == self.state.template_id))
        self.adventure = adv_res.scalars().first()
        av_res = await self.db.execute(select(Avatar).where(Avatar.id == self.state.avatar_id))
        self.avatar = av_res.scalars().first()

        if not self.adventure:
            snapshot = AdventureLogic.extract_manifest_snapshot(self.state)
            snapshot_adventure = snapshot.get("adventure") if isinstance(snapshot.get("adventure"), dict) else {}
            snapshot_manifest = snapshot.get("original_manifest") if isinstance(snapshot.get("original_manifest"), dict) else {}
            if snapshot_adventure or snapshot_manifest:
                self.adventure = SimpleNamespace(
                    id=snapshot_adventure.get("id") or self.state.template_id or "deleted-template",
                    title=snapshot_adventure.get("title") or (self.state.session.adventure_title if self.state.session else None) or "Deleted Adventure",
                    teaser=snapshot_adventure.get("teaser"),
                    version=snapshot_adventure.get("version"),
                    language=snapshot_adventure.get("language"),
                    image_url=snapshot_adventure.get("image_url") or (self.state.session.adventure_image_url if self.state.session else None),
                    strict_rules=bool(snapshot_adventure.get("strict_rules", True)),
                    rule_enforcement_mode=snapshot_adventure.get("rule_enforcement_mode") or "rpg",
                    time_per_turn=int(snapshot_adventure.get("time_per_turn", 5) or 5),
                    pacing_minutes=int(snapshot_adventure.get("pacing_minutes", 5) or 5),
                    clock_enabled=bool(snapshot_adventure.get("clock_enabled", False)),
                    time_system=snapshot_adventure.get("time_system") or "calendar",
                    time_config=snapshot_adventure.get("time_config") or {},
                    selected_tone=snapshot_adventure.get("selected_tone"),
                    selected_image_styles=snapshot_adventure.get("selected_image_styles") or [],
                    quests=snapshot_adventure.get("quests") or self.state.quests or [],
                    awards=snapshot_adventure.get("awards") or [],
                    plot=snapshot_adventure.get("plot") or self.state.plot,
                    rules=snapshot_adventure.get("rules") or self.state.rules,
                    intro_text=snapshot_adventure.get("intro_text"),
                    walkthrough=snapshot_adventure.get("walkthrough") or self.state.walkthrough,
                    completed_condition=snapshot_adventure.get("completed_condition") or self.state.completed_condition,
                    gameover_condition=snapshot_adventure.get("gameover_condition") or self.state.gameover_condition,
                    tts_director_notes=snapshot_adventure.get("tts_director_notes") or self.state.tts_director_notes,
                    original_prompt=snapshot_adventure.get("original_prompt") or "",
                    allow_dynamic_items=bool(snapshot_adventure.get("allow_dynamic_items", True)),
                    can_damage_npcs=bool(snapshot_adventure.get("can_damage_npcs", True)),
                    npcs_can_damage_protagonist=bool(snapshot_adventure.get("npcs_can_damage_protagonist", True)),
                    is_adventure_generator=bool(snapshot_adventure.get("is_adventure_generator", False)),
                    original_manifest=snapshot_manifest,
                )
        
        if not (self.adventure and self.avatar):
            return False

        # Lazy-register initial map visit
        try:
            world_map = await AdventureLogic.get_or_create_map(self.db, self.state.template_id)
            # Use session_id to find the scene (snapshot)
            scene_res = await self.db.execute(
                select(WorldScene).where(
                    WorldScene.id == self.state.current_scene_id,
                    WorldScene.session_id == self.state.session_id,
                )
            )
            cur_scene = scene_res.scalars().first()
            
            # Fallback to template if not found (though it should be there after deep clone)
            if not cur_scene:
                scene_res = await self.db.execute(select(WorldScene).where(WorldScene.id == self.state.current_scene_id, WorldScene.template_id == self.state.template_id))
                cur_scene = scene_res.scalars().first()

            MapEngine.register_visit(
                world_map, 
                self.state.current_scene_id, 
                label=cur_scene.label if cur_scene else None, 
                description=cur_scene.description if cur_scene else None, 
                image_url=cur_scene.image_url if cur_scene else None
            )
        except Exception as e:
            logger.warning(f"Failed to auto-register map visit for {self.game_id}: {e}")

        duration = time.perf_counter() - start
        logger.debug(f"[Turn {self.game_id}] Initialization (DB) took {duration:.4f}s")
        return True

    async def process_turn(self, message: str, auto_visualize: bool = False, language: str | None = None) -> AsyncGenerator[str, None]:
        self.turn_language = language
        if not await self.initialize():
            yield f"event: error\ndata: {json.dumps({'detail': 'Game session not found.'})}\n\n"
            return

        # Pre-emptive sanitization of avatar JSON fields to avoid datetime serialization issues
        self.avatar.inventory = jsonable_encoder(self.avatar.inventory)
        self.avatar.equipment = jsonable_encoder(self.avatar.equipment)

        user_msg = message.strip()
        actual_user_input = user_msg
        if not user_msg:
            user_msg = "[LOOK AROUND]"

        if user_msg.lower() in {"/shuffle", "/suggest", "/suggestions"}:
            last_response = await self._load_last_assistant_message()
            await self._generate_prompt_suggestions(last_response)
            await self.db.commit()
            final_data = jsonable_encoder({
                'sheet': await AdventureLogic.build_sheet_snapshot(self.avatar, self.state, self.db),
                'entities': await AdventureLogic.build_session_entities(self.db, self.state),
                'combat': AdventureLogic.get_combat_snapshot(self.state),
                **self._build_prompt_suggestions_payload(),
                **self._build_terminal_flags_payload(),
                'status': 'success',
            })
            yield f"event: final\ndata: {json.dumps(final_data)}\n\n"
            return

        if user_msg.lower().startswith("/agent"):
            from backend.api.routes.adventures.agent_logic import AgentService
            cmd_args = user_msg[6:].strip().lower()
            if cmd_args == "on":
                llm_settings = self.user.llm_settings or {}
                monkey_mode_default = bool(llm_settings.get("play_agent_monkey_mode", False))
                AgentService.set_agent_active(self.state, True)
                AgentService.set_monkey_mode(self.state, monkey_mode_default)
                await self.db.commit()
                msg = "Autonomous Agent Gameplay Mode enabled. The AI will now play the game on your behalf."
                if monkey_mode_default:
                    msg += " Monkey Mode is active by default from settings."
                await self._save_chat_message("system", msg)
                yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"
            elif cmd_args == "off":
                AgentService.set_agent_active(self.state, False)
                await self.db.commit()
                
                import os
                session_id = self.state.session_id if self.state else self.game_id
                safe_session_id = _sanitize_path_component(session_id)

                agents_hint = "Agent issues log file is unavailable due to an invalid session path."
                if safe_session_id:
                    agents_md_path = _ensure_within_data_dir(
                        os.path.join(settings.DATA_DIR, "adventures", "sessions", safe_session_id, "AGENTS.md")
                    )
                    link_path = agents_md_path.replace("\\", "/")
                    if not link_path.startswith("/"):
                        link_path = "/" + link_path
                    agents_hint = f"Agent issues log file: [AGENTS.md](file://{link_path}) (Path: `{agents_md_path}`)"

                msg = (
                    "Autonomous Agent Gameplay Mode disabled. You are now back in control.\n\n"
                    f"{agents_hint}"
                )
                await self._save_chat_message("system", msg)
                yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"
            elif cmd_args == "monkey on":
                AgentService.set_monkey_mode(self.state, True)
                await self.db.commit()
                msg = (
                    "Play-Agent Monkey Mode enabled. The agent will now deliberately try invalid, chaotic, "
                    "or context-inappropriate actions to stress-test engine robustness."
                )
                await self._save_chat_message("system", msg)
                yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"
            elif cmd_args == "monkey off":
                AgentService.set_monkey_mode(self.state, False)
                await self.db.commit()
                msg = "Play-Agent Monkey Mode disabled. The agent will return to normal walkthrough-driven behavior."
                await self._save_chat_message("system", msg)
                yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"
            else:
                msg = "Usage: /agent on | /agent off | /agent monkey on | /agent monkey off"
                yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"

            final_data = jsonable_encoder({
                'sheet': await AdventureLogic.build_sheet_snapshot(self.avatar, self.state, self.db),
                'entities': await AdventureLogic.build_session_entities(self.db, self.state),
                'combat': AdventureLogic.get_combat_snapshot(self.state),
                **self._build_prompt_suggestions_payload(),
                **self._build_terminal_flags_payload(),
                'status': 'success',
            })
            yield f"event: final\ndata: {json.dumps(final_data)}\n\n"
            return

        if self._is_input_locked():
            lock_message = (
                "This story has reached its final ending. You can still review the map, character sheet, "
                "quests, awards, walkthrough, and chat history, but no further actions can be taken."
            )
            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': lock_message})}\n\n"
            final_data = jsonable_encoder({
                'sheet': await AdventureLogic.build_sheet_snapshot(self.avatar, self.state, self.db),
                'entities': await AdventureLogic.build_session_entities(self.db, self.state),
                'combat': AdventureLogic.get_combat_snapshot(self.state),
                **self._build_prompt_suggestions_payload(),
                **self._build_terminal_flags_payload(),
                'status': 'success',
            })
            yield f"event: final\ndata: {json.dumps(final_data)}\n\n"
            return

        # Unified logic for /debug and / (slash) commands
        if user_msg.startswith("/debug"):
            cmd_args = user_msg[7:].strip().lower()
            is_on_cmd = cmd_args == "on" or cmd_args.startswith("log on")
            # Keep combat-outcome debug shortcuts available for deterministic testing/workflows.
            is_combat_outcome_shortcut = cmd_args in {"win_fight", "loose_fight"}
            
            if settings.TALEWEAVER_DEBUG_ENABLED or self.state.is_debug_enabled or is_on_cmd or is_combat_outcome_shortcut:
                async for chunk in self._handle_debug(user_msg):
                    yield chunk
                return
            else:
                logger.warning(f"[Turn {self.game_id}] Debug command ignored: TALEWEAVER_DEBUG_ENABLED is False and in-game debug is OFF.")
                # If debug is disabled, treat it as an unknown command to the user
                unknown_msg = "Unknown command: /debug. Type /help for a list of commands."
                await self._save_chat_message("system", unknown_msg)
                yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': unknown_msg})}\n\n"
                return

        # 1. Combat & Loot Handling (Active Phase)
        if self._has_combat_phase():
            async for chunk in self._handle_combat_turn(user_msg):
                yield chunk
            return

        # 2. Fight Trigger / Attack
        if user_msg.lower().startswith("/fight") or user_msg.lower().startswith("/attack"):
            async for chunk in self._handle_fight_start(user_msg):
                yield chunk
            return
            
        is_rule_pass = False
        if user_msg.startswith("/"):
            response = CommandParser.parse_command(self.avatar, user_msg, debug_enabled=(settings.TALEWEAVER_DEBUG_ENABLED or bool(self.state.is_debug_enabled)))
            
            if response == "[RULE_PASS]":
                is_rule_pass = True
                user_msg = "[EVALUATE STATE]"
                yield f"event: status\ndata: {json.dumps({'content': 'The Game Master evaluates your situation...'})}\n\n"
            elif response.startswith("[TRIGGER_SAY]"):
                user_msg = f'Say out loud: "{response[13:].strip()}"'
                # Continue turn as normal
            elif response.startswith("[TRIGGER_INSPECT]"):
                user_msg = f"Inspect {response[17:].strip()}"
                # Continue turn as normal
            elif response.startswith("[TRIGGER_OPEN]"):
                open_target = response[14:].strip()
                if open_target:
                    user_msg = (
                        f"Open {open_target}. If this reveals any contents, list those contents explicitly in the chat response "
                        "(not only in UI dialogs), so they are visible in chat history."
                    )
                else:
                    user_msg = "Usage: /open <target>"
                # Continue turn as normal
            elif response.startswith("[TRIGGER_READ]"):
                read_target = response[14:].strip()
                if read_target:
                    user_msg = (
                        f"Read {read_target}. If there is readable text/log content, print the full relevant text in the chat response "
                        "(not only in UI dialogs), so it remains in chat history."
                    )
                else:
                    user_msg = "Usage: /read <target>"
                # Continue turn as normal
            elif response.startswith("[TRIGGER_PUSH]"):
                push_target = response[14:].strip()
                if push_target:
                    user_msg = f"Push {push_target}"
                else:
                    user_msg = "Push the most relevant mechanism in the scene"
                # Continue turn as normal
            elif response.startswith("[TRIGGER_PULL]"):
                pull_target = response[14:].strip()
                if pull_target:
                    user_msg = f"Pull {pull_target}"
                else:
                    user_msg = "Pull the most relevant mechanism in the scene"
                # Continue turn as normal
            elif response.startswith("[TRIGGER_SEARCH]"):
                search_target = response[16:].strip()
                if search_target:
                    user_msg = f"Search {search_target}"
                else:
                    user_msg = "Search the surroundings carefully"
                # Continue turn as normal
            elif response.startswith("[TRIGGER_LOOKAROUND]"):
                user_msg = "Look around and describe all relevant details in the current area"
                # Continue turn as normal
            elif response.startswith("[TRIGGER_REST]"):
                user_msg = "Take a short rest if it is safe and possible"
                # Continue turn as normal
            elif response.startswith("[TRIGGER_TAKE]"):
                take_target = response[14:].strip()
                take_npc = await self._find_scene_npc_by_hint(take_target)
                if take_npc and self._is_npc_defeated(take_npc):
                    msg = f"{take_npc.name} is defeated. Only inspect is available."
                    yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"
                    async for chunk in self._emit_combat_final(msg):
                        yield chunk
                    return
                user_msg = f"Take {take_target}"
                # Continue turn as normal
            elif response.startswith("[TRIGGER_COMBINE]"):
                user_msg = f"Use {response[17:].strip()}"
                # Continue turn as normal
            else:
                # Standard slash command handling (equip, take_direct, etc.)
                async for chunk in self._handle_slash(user_msg, response):
                    yield chunk
                return

        blocked_message = await self._guard_non_visible_inspect_or_search(user_msg)
        if blocked_message:
            if actual_user_input:
                await self._save_chat_message("user", actual_user_input)
                await self.db.flush()

            await self._save_chat_message("system", blocked_message)
            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': blocked_message})}\n\n"

            await self.db.commit()
            final_data = jsonable_encoder({
                'sheet': await AdventureLogic.build_sheet_snapshot(self.avatar, self.state, self.db),
                'entities': await AdventureLogic.build_session_entities(self.db, self.state),
                'combat': AdventureLogic.get_combat_snapshot(self.state),
                **self._build_prompt_suggestions_payload(),
                **self._build_terminal_flags_payload(),
                'status': 'success',
            })
            yield f"event: final\ndata: {json.dumps(final_data)}\n\n"
            return

        # Core Turn Logic
        turn_start = time.perf_counter()
        logger.debug(f"[Turn {self.game_id}] Starting turn for user '{self.user.username}' with input: {user_msg}")
        if not is_rule_pass:
            yield f"event: status\ndata: {json.dumps({'content': 'Considering...'})}\n\n"
        
        # 1. Advance Time & Apply Ticks (Only for normal turns, NOT for rule passes)
        if not is_rule_pass:
            self.state.in_game_time += self.adventure.time_per_turn
            tick_msgs = RuleEngine.apply_ticks(self.avatar)
            for tm in tick_msgs:
                yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': tm})}\n\n"

        # 2. Record User Message
        silent_commands = ['/take_direct', '/rule-pass', '/equip', '/unequip', '/consume']
        is_silent = any(actual_user_input.lower().startswith(cmd) for cmd in silent_commands)

        if actual_user_input and not is_silent:
            await self._save_chat_message("user", actual_user_input)
            await self.db.flush()

        # 3. LLM Processing (Pass 1 & Pass 2)
        async def _run_llm_cycle_with_lang(msg, av):
            async for c in self._run_llm_cycle(msg, av, language=language):
                yield c
        
        try:
            async for chunk in _run_llm_cycle_with_lang(user_msg, auto_visualize):
                yield chunk
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            user_safe_error = _friendly_llm_error_message(exc)
            if not user_safe_error:
                logger.exception("[Turn %s] Turn pipeline aborted unexpectedly", self.game_id)
                user_safe_error = _friendly_llm_unexpected_error_message()
            yield f"event: error\ndata: {json.dumps({'detail': user_safe_error})}\n\n"
            return
            
        turn_end = time.perf_counter()
        log_structured_event(
            "gm.turn.pipeline.total",
            adventure_id=self.adventure.id,
            game_id=self.game_id,
            operation="chat_turn",
            phase="total",
            duration_ms=round((turn_end - turn_start) * 1000, 2),
            strict_rules=bool(self.adventure.strict_rules),
            is_adventure_generator=bool(self.adventure.is_adventure_generator),
            user_input_chars=len(actual_user_input or ""),
        )
        logger.debug(f"[Turn {self.game_id}] Total turn processing took {turn_end - turn_start:.4f}s")

    async def _handle_debug(self, user_msg: str) -> AsyncGenerator[str, None]:
        cmd_args = user_msg[7:].strip()
        debug_info = await DebugEngine.handle_debug_command(self.db, self.state, cmd_args, user=self.user, adventure=self.adventure, avatar=self.avatar)
        
        # Handle status overrides from debug engine
        if debug_info.startswith("[TRIGGER_GAME_OVER]"):
            await self._finalize_session("game_over", debug_info)
            debug_info = "DEBUG: Session forced to GAME OVER."
        elif debug_info.startswith("[TRIGGER_GAME_COMPLETED]"):
            await self._finalize_session("completed", debug_info)
            debug_info = "DEBUG: Session forced to COMPLETED."
        elif debug_info.startswith("[TRIGGER_WALKTHROUGH_REVEAL_FREE]"):
            self.state.is_walkthrough_revealed = True
            debug_info = debug_info[33:].strip()
        elif debug_info.startswith("[TRIGGER_GEN_ITEM]"):
            prompt = debug_info.replace("[TRIGGER_GEN_ITEM]", "").strip()
            async for chunk in self._handle_debug_gen_item(prompt):
                yield chunk
            return
        elif debug_info.startswith("[TRIGGER_NPC_DROP_ITEMS]"):
            dropped_info = await self._debug_drop_npc_items()
            debug_info = f"DEBUG: {dropped_info}"

        
        # New: Combat Debug Commands
        elif cmd_args == "win_fight":
            combat = self._read_combat_state()
            if combat and combat.get("active"):
                combat["active"] = False
                combat["outcome"] = "victory"
                combat["enemy"]["hp"] = 0

                # Mirror normal victory behavior so debug wins can be used for loot testing.
                enemy_id = combat["enemy"]["id"]
                enemy_res = await self.db.execute(
                    select(WorldEntity).where(
                        WorldEntity.id == enemy_id,
                        WorldEntity.session_id == self.game_id,
                    )
                )
                enemy_ent = enemy_res.scalars().first()

                xp_gained = 0
                if enemy_ent:
                    xp_gained = self._award_combat_victory_xp(enemy_ent)
                combat["status_note"] = f"Combat won via debug command. (+{xp_gained} XP)"

                loot_items = await self._normalize_loot_items(
                    list(combat.get("enemy", {}).get("inventory") or (enemy_ent.inventory if enemy_ent else []) or [])
                )
                combat["loot_pending"] = bool(loot_items)
                combat["loot_items"] = loot_items

                states = dict(self.state.entity_states or {})
                if enemy_id not in states:
                    states[enemy_id] = {}
                states[enemy_id]["hp"] = 0
                states[enemy_id]["inventory"] = []
                enemy_is_killable = (states[enemy_id].get("is_killable") if "is_killable" in states[enemy_id] else enemy_ent.is_killable if enemy_ent else True)
                if enemy_is_killable:
                    states[enemy_id]["is_defeated"] = True
                    states[enemy_id]["is_attackable"] = False
                self.state.entity_states = states
                flag_modified(self.state, "entity_states")

                self._append_combat_log(combat, combat["status_note"], "outcome")
                if loot_items:
                    loot_msg = "Victory! Loot available. Use /loot take <item>, /loot leave <item>, /loot done"
                    self._append_combat_log(combat, loot_msg, "loot")
                self._set_combat_state(combat)
                debug_info = f"DEBUG: Combat forced to VICTORY (loot phase enabled). (+{xp_gained} XP)"
        
        elif cmd_args == "loose_fight":
            combat = self._read_combat_state()
            if combat and combat.get("active"):
                combat["active"] = False
                combat["outcome"] = "defeat"
                combat["player"]["hp"] = 0
                combat["status_note"] = "Combat lost via debug command."
                
                # Sync back to avatar
                self.avatar.hp = 0
                
                self._append_combat_log(combat, combat["status_note"], "outcome")
                self._set_combat_state(combat)
                debug_info = "DEBUG: Combat forced to DEFEAT."

        if debug_info.startswith("[DEBUG_LOG_OFF]"):
            await self.db.commit()
            map_payload = await self._build_map_payload()
            final_data = jsonable_encoder({
                **map_payload,
                'sheet': await AdventureLogic.build_sheet_snapshot(self.avatar, self.state, self.db),
                'combat': AdventureLogic.get_combat_snapshot(self.state),
                'awards': self.adventure.awards if self.adventure else [],
                'game_over_reason': self.state.session.status_note if self.state.session else None,
                **self._build_prompt_suggestions_payload(),
                **self._build_terminal_flags_payload(),
                'status': 'success'
            })
            yield f"event: final\ndata: {json.dumps(final_data)}\n\n"
            return

        # Save the user's /debug command to DB so it can be deleted in debug mode.
        user_chat_msg = ChatMessage(session_id=self.state.session_id, role="user", content=user_msg)
        self.db.add(user_chat_msg)
        await self.db.flush()
        user_msg_id = str(user_chat_msg.id)

        # Send debug info as a system message so it appears in chat.
        # Include both IDs so the frontend can attach them for deletion.
        system_chat_msg = ChatMessage(session_id=self.state.session_id, role="system", content=debug_info)
        self.db.add(system_chat_msg)
        await self.db.flush()
        system_msg_id = str(system_chat_msg.id)

        await self.db.commit()
        yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': debug_info, 'is_debug': True, 'id': system_msg_id, 'user_msg_id': user_msg_id})}\n\n"

        final_data = jsonable_encoder({
            'sheet': await AdventureLogic.build_sheet_snapshot(self.avatar, self.state, self.db),
            'entities': await AdventureLogic.build_session_entities(self.db, self.state),
            'combat': AdventureLogic.get_combat_snapshot(self.state),
            **self._build_prompt_suggestions_payload(),
            **self._build_terminal_flags_payload(),
            'status': 'success',
        })
        yield f"event: final\ndata: {json.dumps(final_data)}\n\n"

    async def _handle_debug_gen_item(self, prompt: str) -> AsyncGenerator[str, None]:
        """Debug helper to force-generate an item based on a prompt."""
        instruction = f"DEBUG COMMAND: The user wants you to generate an item now. Instruction: {prompt}"
        # We temporarily set the prompt as if it was the user message
        async for chunk in self._run_llm_cycle(instruction, self.avatar):
            yield chunk

        map_payload = await self._build_map_payload()
        final_data = jsonable_encoder({
            **map_payload,
            'sheet': await AdventureLogic.build_sheet_snapshot(self.avatar, self.state, self.db),
            'combat': AdventureLogic.get_combat_snapshot(self.state),
            'awards': self.adventure.awards,
            'game_over_reason': self.state.session.status_note if self.state.session else None,
            **self._build_prompt_suggestions_payload(),
            **self._build_terminal_flags_payload(),
            'status': 'success'
        })
        yield f"event: final\ndata: {json.dumps(final_data)}\n\n"

    async def _debug_drop_npc_items(self) -> str:
        # Find all NPCs in the current scene
        res = await self.db.execute(
            select(WorldEntity).where(
                WorldEntity.session_id == self.game_id,
                WorldEntity.entity_type == "NPC",
                WorldEntity.current_scene_id == self.state.current_scene_id
            )
        )
        npcs = res.scalars().all()
        if not npcs:
            return "No NPCs found in the current scene."

        overrides = self.state.entity_states or {}
        dropped_items_summary = []

        for npc in npcs:
            # Determine NPC's current inventory
            npc_inv = overrides.get(npc.id, {}).get("inventory")
            if npc_inv is None:
                npc_inv = npc.inventory or []

            if not npc_inv:
                continue

            # Drop each item in scene
            for item in npc_inv:
                await self._spawn_scene_item(item)
                dropped_items_summary.append(f"{item.get('name') or 'Item'} (from {npc.name})")

            # Clear NPC's inventory in DB
            npc.inventory = []
            self.db.add(npc)

            # Clear NPC's inventory in session state overrides
            states = dict(self.state.entity_states or {})
            if npc.id not in states:
                states[npc.id] = {}
            states[npc.id]["inventory"] = []
            self.state.entity_states = states
            flag_modified(self.state, "entity_states")

        if not dropped_items_summary:
            return "No items to drop from NPCs in the current scene."

        return f"Dropped NPC items: {', '.join(dropped_items_summary)}"

    async def _handle_slash(self, user_msg: str, response: str) -> AsyncGenerator[str, None]:
        # Handle /map specifically (doesn't use CommandParser)
        if user_msg.lower() == "/map":
            map_payload = await self._build_map_payload()
            final_data = jsonable_encoder({
                **map_payload,
                'sheet': await AdventureLogic.build_sheet_snapshot(self.avatar, self.state, self.db),
                **self._build_prompt_suggestions_payload(),
                **self._build_terminal_flags_payload(),
            })
            yield f"event: final\ndata: {json.dumps(final_data)}\n\n"
            return
            
        if response.startswith("[TRIGGER_TAKE_DIRECT]"):
            entity_id_or_name = response[21:].strip()
            take_npc = await self._find_scene_npc_by_hint(entity_id_or_name)
            if take_npc and self._is_npc_defeated(take_npc):
                msg = f"{take_npc.name} is defeated. Only inspect is available."
                yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"
                async for chunk in self._emit_combat_final(msg):
                    yield chunk
                return

            # Find portable OBJECT in current scene (snapshot), matching by name or ID (case-insensitive).
            ent_res = await self.db.execute(
                select(WorldEntity).where(
                    WorldEntity.session_id == self.game_id,
                    WorldEntity.current_scene_id == self.state.current_scene_id,
                    WorldEntity.entity_type == "OBJECT",
                    WorldEntity.is_hidden.is_(False),
                    WorldEntity.is_in_inventory.is_(False),
                )
            )
            candidates = ent_res.scalars().all()
            hint_lower = entity_id_or_name.lower()
            ent = None
            for candidate in candidates:
                if candidate.id and candidate.id.lower() == hint_lower:
                    ent = candidate
                    break
                if candidate.name and candidate.name.lower() == hint_lower:
                    ent = candidate
                    break
            if ent and ent.is_portable:
                # Move to inventory
                new_inv = list(self.avatar.inventory)
                item_dict = jsonable_encoder({c.name: getattr(ent, c.name) for c in ent.__table__.columns})
                new_inv.append(item_dict)
                self.avatar.inventory = new_inv
                
                # Update session state instead of global entity
                states = dict(self.state.entity_states or {})
                if ent.id not in states:
                    states[ent.id] = {}
                states[ent.id]["is_in_inventory"] = True
                self.state.entity_states = states
                flag_modified(self.state, "entity_states")
                response = f"Added {ent.name} to your inventory."
            else:
                response = "You cannot take that."
        
        elif response.startswith("[TRIGGER_WALKTHROUGH_REVEAL]"):
            if self.avatar.exp >= WALKTHROUGH_REVEAL_COST:
                self.avatar.exp -= WALKTHROUGH_REVEAL_COST
                self.state.is_walkthrough_revealed = True
                response = f"Walkthrough revealed! You spent {WALKTHROUGH_REVEAL_COST} XP. You can now open it via the menu."
            else:
                response = f"You do not have enough XP to reveal the walkthrough ({self.avatar.exp}/{WALKTHROUGH_REVEAL_COST})."

        elif response.startswith("[TRIGGER_WALKTHROUGH_HINT]"):
            if self.avatar.exp >= WALKTHROUGH_HINT_COST:
                # For now, hint just reveals the whole thing or we could implement a smarter hint system.
                # User specifically asked for walkthrough reveal, so let's stick to that for now.
                self.avatar.exp -= WALKTHROUGH_HINT_COST
                response = f"Hint: Look closer at the surroundings. (Cost: {WALKTHROUGH_HINT_COST} XP)"
            else:
                response = f"You do not have enough XP for a hint ({self.avatar.exp}/{WALKTHROUGH_HINT_COST})."

        if response.startswith("[TRIGGER_DROP]"):
            item_name = response[14:].strip()
            if not item_name:
                response = "Usage: /drop <item name>"
            else:
                # Find item in inventory
                item_idx = -1
                for idx, item in enumerate(self.avatar.inventory or []):
                    if isinstance(item, dict) and item.get("name", "").lower() == item_name.lower():
                        item_idx = idx
                        break
                
                if item_idx == -1:
                    response = f"You don't have '{item_name}' in your inventory."
                else:
                    new_inventory = list(self.avatar.inventory)
                    dropped_item = new_inventory.pop(item_idx)
                    self.avatar.inventory = new_inventory
                    
                    # Spawn in scene
                    await self._spawn_scene_item(dropped_item)
                    response = f"You dropped {dropped_item.get('name')}."

        if response.startswith("[TRIGGER_OPEN]"):
            container_hint = response.replace("[TRIGGER_OPEN]", "").strip()
            if not container_hint:
                response = "Usage: /open <container>"
            else:
                scene_container, inventory_container, _ = await self._resolve_container_target(container_hint)
                container_name = (scene_container.name if scene_container else inventory_container.get("name")) if (scene_container or inventory_container) else None
                if not container_name:
                    response = f"No container named '{container_hint}' was found."
                else:
                    is_locked = self._is_container_locked(scene_container, inventory_container)
                    if is_locked:
                        response = f"{container_name} is locked."
                    else:
                        container_inventory = await self._get_container_inventory(scene_container, inventory_container)
                        response = f"{container_name} contains {len(container_inventory)} item(s)."

        if response.startswith("[TRIGGER_CONTAINER_TAKE_ALL]"):
            container_hint = response.replace("[TRIGGER_CONTAINER_TAKE_ALL]", "").strip()
            if not container_hint:
                response = "Usage: /container_take_all <container>"
            else:
                scene_container, inventory_container, inventory_idx = await self._resolve_container_target(container_hint)
                container_name = (scene_container.name if scene_container else inventory_container.get("name")) if (scene_container or inventory_container) else None
                if not container_name:
                    response = f"No container named '{container_hint}' was found."
                else:
                    is_locked = self._is_container_locked(scene_container, inventory_container)
                    if is_locked:
                        response = f"{container_name} is locked."
                    else:
                        raw_items = await self._get_container_inventory(scene_container, inventory_container)
                        normalized_items = await self._normalize_container_items(raw_items)
                        if not normalized_items:
                            response = f"{container_name} is empty."
                        else:
                            new_inventory = list(self.avatar.inventory or [])
                            for item in normalized_items:
                                new_inventory.append(item)
                                await self._move_container_item_to_inventory(item)
                            self.avatar.inventory = new_inventory
                            await self._clear_container_inventory(scene_container, inventory_container, inventory_idx)
                            response = f"You take all {len(normalized_items)} item(s) from {container_name}."

        if response.startswith("[TRIGGER_CONTAINER_DROP_SCENE]"):
            container_hint = response.replace("[TRIGGER_CONTAINER_DROP_SCENE]", "").strip()
            if not container_hint:
                response = "Usage: /container_drop_scene <container>"
            else:
                scene_container, inventory_container, inventory_idx = await self._resolve_container_target(container_hint)
                container_name = (scene_container.name if scene_container else inventory_container.get("name")) if (scene_container or inventory_container) else None
                if not container_name:
                    response = f"No container named '{container_hint}' was found."
                else:
                    is_locked = self._is_container_locked(scene_container, inventory_container)
                    if is_locked:
                        response = f"{container_name} is locked."
                    else:
                        raw_items = await self._get_container_inventory(scene_container, inventory_container)
                        normalized_items = await self._normalize_container_items(raw_items)
                        if not normalized_items:
                            response = f"{container_name} is empty."
                        else:
                            for item in normalized_items:
                                moved = await self._move_container_item_to_scene(item)
                                if not moved:
                                    await self._spawn_scene_item(item)
                            await self._clear_container_inventory(scene_container, inventory_container, inventory_idx)
                            response = f"You drop {len(normalized_items)} item(s) from {container_name} into the scene."

        if response.startswith("[TRIGGER_CONSUME]"):
            item_name = response.replace("[TRIGGER_CONSUME]", "").strip()
            action_msg = self._consume_item_now(item_name)
            await self._save_chat_message("system", action_msg)
            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': action_msg})}\n\n"
            response = action_msg # Allow it to fall through to persist and yield final state

        # PERSIST AND YIELD RESPONSE (For all commands including equip/unequip)
        if response and not response.startswith("[TRIGGER_"):
            await self._save_chat_message("system", response)
            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': response})}\n\n"

        await self.db.commit()
        final_data = jsonable_encoder({
            'sheet': await AdventureLogic.build_sheet_snapshot(self.avatar, self.state, self.db),
            'entities': await AdventureLogic.build_session_entities(self.db, self.state),
            'combat': AdventureLogic.get_combat_snapshot(self.state),
            **self._build_prompt_suggestions_payload(),
            **self._build_terminal_flags_payload(),
        })
        yield f"event: final\ndata: {json.dumps(final_data)}\n\n"
        self.stop_requested = True # Stop after direct slash response

    @staticmethod
    def _is_container_item(item: Any) -> bool:
        return isinstance(item, dict) and str(item.get("item_type") or "").upper() == "CONTAINER"

    def _is_container_locked(self, scene_container: WorldEntity | None, inventory_container: dict[str, Any] | None) -> bool:
        states = self.state.entity_states or {}

        def _requirements_from_metadata(metadata: dict[str, Any]) -> tuple[str, str]:
            return (
                str(metadata.get("code_to_unlock") or "").strip(),
                str(metadata.get("item_to_unlock") or "").strip().upper(),
            )

        if scene_container:
            state_locked = (states.get(scene_container.id) or {}).get("locked")
            if isinstance(state_locked, bool):
                return state_locked
            metadata_json = dict(getattr(scene_container, "metadata_json", None) or {})
            code_to_unlock, item_to_unlock = _requirements_from_metadata(metadata_json)
            return bool(code_to_unlock or item_to_unlock)

        if inventory_container:
            inv_id = str(inventory_container.get("id") or "").strip()
            if inv_id:
                state_locked = (states.get(inv_id) or {}).get("locked")
                if isinstance(state_locked, bool):
                    return state_locked
            item_locked = inventory_container.get("locked")
            if isinstance(item_locked, bool):
                return item_locked
            metadata_json = inventory_container.get("metadata_json")
            if not isinstance(metadata_json, dict):
                metadata_json = {}
            code_to_unlock, item_to_unlock = _requirements_from_metadata(metadata_json)
            return bool(code_to_unlock or item_to_unlock)

        return False

    @staticmethod
    def _extract_access_code(text: str) -> str | None:
        if not text:
            return None
        quoted = re.search(r"[\"']([A-Za-z0-9]{1,32})[\"']", text)
        if quoted:
            return quoted.group(1)
        match = re.search(r"\b(\d{3,8})\b", text)
        return match.group(1) if match else None

    async def _resolve_container_from_free_text(self, text: str) -> tuple[str, str, str, str, bool] | None:
        lowered = (text or "").strip().lower()
        if not lowered:
            return None

        best_match: tuple[int, str, str, str, str, bool] | None = None

        scene_res = await self.db.execute(
            select(WorldEntity).where(
                WorldEntity.session_id == self.game_id,
                WorldEntity.current_scene_id == self.state.current_scene_id,
                WorldEntity.entity_type == "OBJECT",
                WorldEntity.item_type == "CONTAINER",
                WorldEntity.is_hidden.is_(False),
                WorldEntity.is_in_inventory.is_(False),
            )
        )
        for ent in scene_res.scalars().all():
            cid = str(ent.id or "")
            cname = str(ent.name or "")
            tokens = [cid.lower(), cname.lower()]
            token = next((tok for tok in tokens if tok and tok in lowered), None)
            if not token:
                continue
            locked = self._is_container_locked(ent, None)
            metadata_json = dict(ent.metadata_json or {})
            code_to_unlock = str(metadata_json.get("code_to_unlock") or "").strip()
            item_to_unlock = str(metadata_json.get("item_to_unlock") or "").strip().upper()
            candidate = (len(token), cid, cname or cid, code_to_unlock, item_to_unlock, locked)
            if best_match is None or candidate[0] > best_match[0]:
                best_match = candidate

        for inv_item in (self.avatar.inventory or []):
            if not self._is_container_item(inv_item):
                continue
            cid = str(inv_item.get("id") or "").strip()
            cname = str(inv_item.get("name") or "").strip()
            tokens = [cid.lower(), cname.lower()]
            token = next((tok for tok in tokens if tok and tok in lowered), None)
            if not token:
                continue
            locked = self._is_container_locked(None, inv_item)
            metadata_json = inv_item.get("metadata_json")
            if not isinstance(metadata_json, dict):
                metadata_json = {}
            code_to_unlock = str(metadata_json.get("code_to_unlock") or "").strip()
            item_to_unlock = str(metadata_json.get("item_to_unlock") or "").strip().upper()
            candidate = (len(token), cid or cname, cname or cid or "container", code_to_unlock, item_to_unlock, locked)
            if best_match is None or candidate[0] > best_match[0]:
                best_match = candidate

        if not best_match:
            return None

        _, cid, cname, code_to_unlock, item_to_unlock, locked = best_match
        return cid, cname, code_to_unlock, item_to_unlock, locked

    async def _enforce_container_unlock_guardrails(self, event: GameEvent, user_msg: str) -> list[str]:
        lowered = (user_msg or "").strip().lower()
        if not lowered:
            return []

        resolved = await self._resolve_container_from_free_text(lowered)
        if not resolved:
            return []

        container_id, container_name, required_code, required_item_id, is_locked = resolved
        if not is_locked:
            return []

        unlock_allowed = True
        reason = ""

        if required_code:
            code_match = re.search(r"(?:code|pin|access)\W*([A-Za-z0-9]{1,32})", lowered, re.IGNORECASE)
            attempted_code = code_match.group(1) if code_match else self._extract_access_code(lowered)
            if not attempted_code or attempted_code.lower() != required_code.lower():
                unlock_allowed = False
                reason = f"Access code rejected for {container_name}. The lock remains engaged."

        if unlock_allowed and required_item_id:
            inventory_ids = {
                str(item.get("id") or "").strip().upper()
                for item in (self.avatar.inventory or [])
                if isinstance(item, dict)
            }
            if required_item_id.upper() not in inventory_ids:
                unlock_allowed = False
                reason = f"You need {required_item_id} to unlock {container_name}."

        if unlock_allowed:
            return []

        sanitized_updates: list[WorldEntityUpdate] = []
        for update in (event.updated_entities or []):
            if update.entity_id == container_id and update.locked is False:
                continue
            sanitized_updates.append(update)
        sanitized_updates.append(WorldEntityUpdate(entity_id=container_id, locked=True))
        event.updated_entities = sanitized_updates

        event.completed_quest_ids = []
        event.earned_award_keys = []
        event.new_inventory_items = []
        event.updated_inventory_items = []
        event.removed_inventory_item_ids = []
        event.spawned_items = []

        return [reason or f"{container_name} stays locked."]

    async def _resolve_container_target(self, hint: str) -> tuple[WorldEntity | None, dict[str, Any] | None, int | None]:
        normalized_hint = (hint or "").strip().lower()
        if not normalized_hint:
            return None, None, None

        ent_res = await self.db.execute(
            select(WorldEntity).where(
                WorldEntity.session_id == self.game_id,
                WorldEntity.current_scene_id == self.state.current_scene_id,
                WorldEntity.entity_type == "OBJECT",
                or_(
                    WorldEntity.id == hint,
                    WorldEntity.name == hint,
                ),
            )
        )
        scene_ent = ent_res.scalars().first()
        if scene_ent and str(scene_ent.item_type or "").upper() == "CONTAINER":
            return scene_ent, None, None

        for idx, inv_item in enumerate(self.avatar.inventory or []):
            if not self._is_container_item(inv_item):
                continue
            item_id = str(inv_item.get("id") or "").strip().lower()
            item_name = str(inv_item.get("name") or "").strip().lower()
            if normalized_hint in {item_id, item_name}:
                return None, dict(inv_item), idx

        return None, None, None

    async def _get_container_inventory(self, scene_container: WorldEntity | None, inventory_container: dict[str, Any] | None) -> list[Any]:
        if scene_container:
            states = dict(self.state.entity_states or {})
            state_inv = (states.get(scene_container.id) or {}).get("inventory")
            if isinstance(state_inv, list):
                return list(state_inv)
            return list(scene_container.inventory or [])

        if inventory_container:
            return list(inventory_container.get("inventory") or [])

        return []

    async def _normalize_container_item_ref(self, item_ref: Any) -> dict[str, Any] | None:
        if isinstance(item_ref, dict):
            return dict(item_ref)

        if isinstance(item_ref, str) and item_ref.strip():
            item_id = item_ref.strip()
            ent_res = await self.db.execute(
                select(WorldEntity).where(
                    WorldEntity.session_id == self.game_id,
                    WorldEntity.id == item_id,
                )
            )
            ent = ent_res.scalars().first()
            if ent:
                item_data = jsonable_encoder({c.name: getattr(ent, c.name) for c in ent.__table__.columns})
                metadata = dict(ent.metadata_json or {})
                for key in [
                    "hp_change",
                    "mana_change",
                    "stamina_change",
                    "stat_modifier_strength",
                    "stat_modifier_dexterity",
                    "stat_modifier_intelligence",
                    "stat_modifier_wisdom",
                    "stat_modifier_charisma",
                    "stat_modifier_armor_class",
                ]:
                    if key not in item_data and key in metadata:
                        item_data[key] = metadata[key]
                return item_data

            return {"id": item_id, "name": item_id}

        return None

    async def _normalize_container_items(self, raw_items: list[Any]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for item in raw_items or []:
            normalized_item = await self._normalize_container_item_ref(item)
            if normalized_item:
                normalized.append(normalized_item)
        return normalized

    async def _move_container_item_to_inventory(self, item: dict[str, Any]) -> None:
        item_id = str(item.get("id") or "").strip()
        if not item_id:
            return

        ent_res = await self.db.execute(
            select(WorldEntity).where(
                WorldEntity.session_id == self.game_id,
                WorldEntity.id == item_id,
            )
        )
        ent = ent_res.scalars().first()
        if ent:
            ent.is_in_inventory = True
            ent.current_scene_id = "INVENTORY"
            ent.is_hidden = False

        states = dict(self.state.entity_states or {})
        if item_id not in states:
            states[item_id] = {}
        states[item_id]["is_in_inventory"] = True
        states[item_id]["current_scene_id"] = "INVENTORY"
        states[item_id]["is_hidden"] = False
        self.state.entity_states = states
        flag_modified(self.state, "entity_states")

    async def _move_container_item_to_scene(self, item: dict[str, Any]) -> bool:
        item_id = str(item.get("id") or "").strip()
        if not item_id:
            return False

        ent_res = await self.db.execute(
            select(WorldEntity).where(
                WorldEntity.session_id == self.game_id,
                WorldEntity.id == item_id,
            )
        )
        ent = ent_res.scalars().first()
        if not ent:
            return False

        ent.is_in_inventory = False
        ent.current_scene_id = self.state.current_scene_id
        ent.is_hidden = False

        states = dict(self.state.entity_states or {})
        if item_id not in states:
            states[item_id] = {}
        states[item_id]["is_in_inventory"] = False
        states[item_id]["current_scene_id"] = self.state.current_scene_id
        states[item_id]["is_hidden"] = False
        self.state.entity_states = states
        flag_modified(self.state, "entity_states")
        return True

    async def _clear_container_inventory(
        self,
        scene_container: WorldEntity | None,
        inventory_container: dict[str, Any] | None,
        inventory_idx: int | None,
    ) -> None:
        if scene_container:
            scene_container.inventory = []
            self.db.add(scene_container)

            states = dict(self.state.entity_states or {})
            if scene_container.id not in states:
                states[scene_container.id] = {}
            states[scene_container.id]["inventory"] = []
            self.state.entity_states = states
            flag_modified(self.state, "entity_states")

        if inventory_container is not None and inventory_idx is not None:
            updated_inventory = list(self.avatar.inventory or [])
            if 0 <= inventory_idx < len(updated_inventory) and isinstance(updated_inventory[inventory_idx], dict):
                updated_container = dict(updated_inventory[inventory_idx])
                updated_container["inventory"] = []
                updated_inventory[inventory_idx] = updated_container
                self.avatar.inventory = updated_inventory

    def _read_combat_state(self) -> dict[str, Any]:
        return self._combat_state_helper.read_combat_state()

    def _is_combat_active(self) -> bool:
        return self._combat_state_helper.is_combat_active()

    def _has_combat_phase(self) -> bool:
        return self._combat_state_helper.has_combat_phase()

    def _set_combat_state(self, combat: dict[str, Any]) -> None:
        self._combat_state_helper.set_combat_state(combat)

    async def _find_fight_target(self, target_hint: str) -> WorldEntity | None:
        ent_res = await self.db.execute(
            select(WorldEntity).where(
                WorldEntity.session_id == self.game_id,
                WorldEntity.current_scene_id == self.state.current_scene_id,
                WorldEntity.entity_type.in_(["NPC", "npc"]),
                WorldEntity.is_hidden.is_(False),
                WorldEntity.is_in_inventory.is_(False),
            )
        )
        npcs = ent_res.scalars().all()
        if not npcs:
            return None

        target_hint = (target_hint or "").strip()
        states = self.state.entity_states or {}

        # Filter out NPCs that are defeated in session state (permanent)
        def _is_npc_defeated(npc: WorldEntity) -> bool:
            npc_state = states.get(npc.id, {}) or {}
            if npc_state.get("is_defeated"):
                return True
            # Also respect is_hidden override from entity_states
            if npc_state.get("is_hidden"):
                return True
            return False

        eligible_npcs = [npc for npc in npcs if not _is_npc_defeated(npc)]
        if not eligible_npcs:
            return None

        if target_hint:
            low = target_hint.lower()
            for npc in eligible_npcs:
                if npc.id.lower() == low or npc.name.lower() == low:
                    return npc

        for npc in eligible_npcs:
            hp = (states.get(npc.id, {}) or {}).get("hp")
            if hp is None:
                hp = npc.hp
            if hp is None or hp > 0:
                return npc
        return eligible_npcs[0]

    async def _find_scene_npc_by_hint(self, target_hint: str) -> WorldEntity | None:
        target_hint = (target_hint or "").strip()
        if not target_hint:
            return None

        ent_res = await self.db.execute(
            select(WorldEntity).where(
                WorldEntity.session_id == self.game_id,
                WorldEntity.current_scene_id == self.state.current_scene_id,
                WorldEntity.entity_type.in_(["NPC", "npc"]),
                WorldEntity.is_hidden.is_(False),
                WorldEntity.is_in_inventory.is_(False),
            )
        )
        npcs = ent_res.scalars().all()
        low = target_hint.lower()
        for npc in npcs:
            if npc.id.lower() == low or npc.name.lower() == low:
                return npc
        return None

    def _is_npc_defeated(self, npc: WorldEntity) -> bool:
        states = self.state.entity_states or {}
        npc_state = (states.get(npc.id, {}) or {})
        if npc_state.get("is_defeated"):
            return True
        hp = npc_state.get("hp")
        if hp is None:
            hp = npc.hp
        return isinstance(hp, int) and hp <= 0

    @staticmethod
    def _normalize_target_token(value: str) -> str:
        """Normalize a target hint for resilient matching across spacing and punctuation variants."""
        return re.sub(r"[^a-z0-9]+", "", (value or "").strip().lower())

    @staticmethod
    def _sanitize_inspect_or_search_target(raw_target: str) -> str | None:
        """Normalize extracted inspect/search target and drop generic area references."""
        target = (raw_target or "").strip().strip("\"'")
        target = re.sub(r"^[\s:,-]+|[\s\.,!?:;]+$", "", target)
        if not target:
            return None

        generic_targets = {
            "around",
            "area",
            "surroundings",
            "the surroundings",
            "the area",
            "room",
            "the room",
            "umgebung",
            "bereich",
            "raum",
        }
        if target.lower() in generic_targets:
            return None
        return target

    async def _extract_inspect_or_search_target(self, user_msg: str) -> str | None:
        """Extract inspect/search target via lightweight intent detection without language-specific keyword regex."""
        text = " ".join((user_msg or "").strip().split())
        if not text:
            return None

        lower_text = text.lower()
        if lower_text.startswith("/inspect") or lower_text.startswith("/search"):
            direct_target = text.split(" ", 1)[1].strip() if " " in text else ""
            return self._sanitize_inspect_or_search_target(direct_target)

        llm_settings = self.user.llm_settings or {}
        small_model_provider = (
            llm_settings.get("small_model_provider")
            or llm_settings.get("complex_model_provider")
            or llm_settings.get("preferred_provider")
            or "openai"
        )
        small_model = llm_settings.get("small_model") or "gpt-4o-mini"

        intent_system_prompt = (
            "You classify the player's intent for a text-adventure turn. "
            "Return ONLY strict JSON with schema: "
            "{\"action\":\"inspect\"|\"search\"|\"other\",\"target\":string|null}. "
            "Use action=inspect/search only if the player clearly intends to inspect or search a specific target. "
            "For generic look-around or unrelated actions, return action=other and target=null."
        )

        try:
            llm = GameMasterLLM(self.user, provider=small_model_provider, model_category="small")
            raw_intent = await llm.aexecute_simple_task(
                intent_system_prompt,
                text,
                small_model,
                adventure_id=self.adventure.id,
                game_id=self.game_id,
                operation="chat_turn",
                phase="inspect_search_intent_guard",
            )
            parsed = self._parse_json_object(raw_intent)
            if not parsed:
                return None

            action = str(parsed.get("action") or "").strip().lower()
            if action not in {"inspect", "search"}:
                return None

            raw_target = parsed.get("target")
            if raw_target is None:
                return None
            return self._sanitize_inspect_or_search_target(str(raw_target))
        except Exception as exc:
            logger.debug("[Turn %s] Inspect/search intent guard skipped: %s", self.game_id, exc)
            return None

    async def _collect_inspect_search_visibility_tokens(self) -> tuple[set[str], set[str]]:
        """Collect allowed and disallowed normalized tokens for inspect/search target checks."""
        allowed_tokens: set[str] = set()
        disallowed_tokens: set[str] = set()

        def _add_token(bucket: set[str], raw: Any) -> None:
            token = self._normalize_target_token(str(raw or ""))
            if token:
                bucket.add(token)

        states = self.state.entity_states or {}
        ent_res = await self.db.execute(
            select(WorldEntity).where(
                WorldEntity.session_id == self.game_id,
            )
        )
        entities = list(ent_res.scalars().all())

        for ent in entities:
            ent_state = states.get(ent.id, {}) if isinstance(states, dict) else {}
            current_scene_id = ent_state.get("current_scene_id", ent.current_scene_id)
            is_hidden = bool(ent_state.get("is_hidden", ent.is_hidden))
            is_in_inventory = bool(ent_state.get("is_in_inventory", ent.is_in_inventory))

            is_allowed_entity = current_scene_id == self.state.current_scene_id and not is_hidden and not is_in_inventory
            _add_token(allowed_tokens if is_allowed_entity else disallowed_tokens, ent.id)
            _add_token(allowed_tokens if is_allowed_entity else disallowed_tokens, ent.name)

            if (ent.entity_type or "").upper() != "NPC":
                continue

            npc_inventory = ent_state.get("inventory", ent.inventory or [])
            if not isinstance(npc_inventory, list):
                npc_inventory = []

            inventory_bucket = allowed_tokens if (current_scene_id == self.state.current_scene_id and not is_hidden) else disallowed_tokens
            for item in npc_inventory:
                if not isinstance(item, dict):
                    continue
                _add_token(inventory_bucket, item.get("id"))
                _add_token(inventory_bucket, item.get("name"))

        for item in (self.avatar.inventory or []):
            if not isinstance(item, dict):
                continue
            _add_token(allowed_tokens, item.get("id"))
            _add_token(allowed_tokens, item.get("name"))

        disallowed_tokens.difference_update(allowed_tokens)
        return allowed_tokens, disallowed_tokens

    async def _is_inspect_or_search_target_visible(self, target_hint: str) -> bool:
        """Allow inspect/search targets only from current scene, local NPC inventory, or avatar inventory."""
        normalized_hint = self._normalize_target_token(target_hint)
        if not normalized_hint:
            return True

        allowed_tokens: set[str] = set()

        def _add_token(raw: Any) -> None:
            token = self._normalize_target_token(str(raw or ""))
            if token:
                allowed_tokens.add(token)

        states = self.state.entity_states or {}
        ent_res = await self.db.execute(
            select(WorldEntity).where(
                WorldEntity.session_id == self.game_id,
            )
        )
        entities = list(ent_res.scalars().all())

        for ent in entities:
            ent_state = states.get(ent.id, {}) if isinstance(states, dict) else {}
            current_scene_id = ent_state.get("current_scene_id", ent.current_scene_id)
            is_hidden = bool(ent_state.get("is_hidden", ent.is_hidden))
            is_in_inventory = bool(ent_state.get("is_in_inventory", ent.is_in_inventory))

            if current_scene_id != self.state.current_scene_id or is_hidden:
                continue

            if not is_in_inventory:
                _add_token(ent.id)
                _add_token(ent.name)

            if (ent.entity_type or "").upper() != "NPC":
                continue

            npc_inventory = ent_state.get("inventory", ent.inventory or [])
            if not isinstance(npc_inventory, list):
                npc_inventory = []

            for item in npc_inventory:
                if not isinstance(item, dict):
                    continue
                _add_token(item.get("id"))
                _add_token(item.get("name"))

        for item in (self.avatar.inventory or []):
            if not isinstance(item, dict):
                continue
            _add_token(item.get("id"))
            _add_token(item.get("name"))

        if normalized_hint in allowed_tokens:
            return True

        return any(tok and tok in normalized_hint for tok in allowed_tokens if len(tok) >= 3)

    async def _guard_non_visible_inspect_or_search(self, user_msg: str) -> str | None:
        """Return a blocking system message if the player targets an unseen object for inspect/search."""
        normalized_message = self._normalize_target_token(user_msg)
        if not normalized_message:
            return None

        _allowed_tokens, disallowed_tokens = await self._collect_inspect_search_visibility_tokens()
        if not any(tok in normalized_message for tok in disallowed_tokens if len(tok) >= 3):
            return None

        target_hint = await self._extract_inspect_or_search_target(user_msg)
        if not target_hint:
            return None

        is_visible = await self._is_inspect_or_search_target_visible(target_hint)
        if is_visible:
            return None

        return (
            f"You cannot inspect or search '{target_hint}' right now. "
            "Only objects in the current scene and items from your inventory or local NPC inventories are available."
        )

    def _entity_stat(self, ent: WorldEntity, stat_key: str, fallback: int = 0) -> int:
        states = self.state.entity_states or {}
        override = (states.get(ent.id, {}) or {}).get(stat_key)
        if isinstance(override, int):
            return override
        ent_val = getattr(ent, stat_key, None)
        if isinstance(ent_val, int):
            return ent_val
        return fallback

    def _is_npc_killable(self, npc: WorldEntity) -> bool:
        states = self.state.entity_states or {}
        override = (states.get(npc.id, {}) or {}).get("is_killable")
        if isinstance(override, bool):
            return override
        return bool(getattr(npc, "is_killable", True))

    def _player_damage_dice(self) -> str:
        eq = self.avatar.equipment or {}
        main_hand = eq.get("MainHand")
        if isinstance(main_hand, dict):
            dice = main_hand.get("damage_dice")
            if isinstance(dice, str) and re.match(r"^\d+d\d+([+-]\d+)?$", dice.replace(" ", "").lower()):
                return dice
        return "1d8"

    def _enemy_damage_dice(self, enemy: WorldEntity) -> str:
        if isinstance(enemy.metadata_json, dict):
            dice = enemy.metadata_json.get("damage_dice")
            if isinstance(dice, str) and re.match(r"^\d+d\d+([+-]\d+)?$", dice.replace(" ", "").lower()):
                return dice
        return "1d6"

    def _append_combat_log(self, combat: dict[str, Any], text: str, entry_type: str = "log") -> None:
        self._combat_state_helper.append_combat_log(combat, text, entry_type)

    async def _emit_combat_final(self, status_note: str | None = None) -> AsyncGenerator[str, None]:
        await self.db.commit()
        combat_snap = AdventureLogic.get_combat_snapshot(self.state)
        # Ensure we don't send a zombie combat object that has no active phase
        if combat_snap and not combat_snap.get("active") and not combat_snap.get("loot_pending") and not combat_snap.get("outcome"):
            combat_snap = None

        map_payload = await self._build_map_payload()
        final_data = jsonable_encoder({
            **map_payload,
            'sheet': await AdventureLogic.build_sheet_snapshot(self.avatar, self.state, self.db),
            'entities': await AdventureLogic.build_session_entities(self.db, self.state),
            'combat': combat_snap,
            **self._build_prompt_suggestions_payload(),
            **self._build_terminal_flags_payload(),
            'status_note': status_note or (self.state.session.status_note if self.state.session else None),
            'status': 'success'
        })
        yield f"event: final\ndata: {json.dumps(final_data)}\n\n"

    async def _emit_combat_aftermath_narration(self, combat: dict[str, Any]) -> AsyncGenerator[str, None]:
        outcome = str(combat.get("outcome") or "").lower()
        if outcome not in {"victory", "escaped"}:
            return

        enemy_name = (combat.get("enemy") or {}).get("name") or "the enemy"
        outcome_note = combat.get("status_note") or "The combat has ended."

        llm_settings = self.user.llm_settings or {}
        complex_model_provider = (
            llm_settings.get("complex_model_provider")
            or llm_settings.get("small_model_provider")
            or llm_settings.get("preferred_provider")
            or "openai"
        )
        complex_model = llm_settings.get("complex_model") or "gpt-4o"

        try:
            llm = GameMasterLLM(self.user, provider=complex_model_provider, model_category="complex")
        except ValueError:
            return

        prompt = (
            "You are the Game Master. Write a short aftermath narration after combat ends. "
            "Use 2-4 sentences, stay in-world, no mechanics, no bullet points, no command suggestions."
        )
        if self.turn_language:
            prompt += f" Respond only in {self.turn_language.upper()}."

        user_prompt = (
            f"Protagonist: {self.avatar.name}. "
            f"Enemy: {enemy_name}. "
            f"Combat outcome: {outcome}. "
            f"Outcome note: {outcome_note}. "
            "Narrate the immediate atmosphere and next beat from the Game Master's perspective."
        )

        response_text = ""
        yield f"event: status\ndata: {json.dumps({'content': 'Game Master reflects on the battle outcome...'})}\n\n"
        stream = await llm.stream_simple_task(prompt, user_prompt, complex_model)
        async for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            if delta:
                response_text += delta
                yield f"event: chunk\ndata: {json.dumps({'content': delta})}\n\n"

        response_text = response_text.strip()
        if response_text:
            await self._save_chat_message("assistant", response_text)
            # Only append to combat log if combat is still present in the state
            # Otherwise we'd accidentally resurrect a cleared combat state
            if self._read_combat_state():
                self._append_combat_log(combat, response_text, "aftermath")
                self._set_combat_state(combat)

    async def _handle_fight_start(self, user_msg: str) -> AsyncGenerator[str, None]:
        if (self.adventure.rule_enforcement_mode or "rpg") != "rpg":
            msg = "Turn-based combat is only available in RPG mode."
            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"
            async for chunk in self._emit_combat_final(msg):
                yield chunk
            return

        if not bool(getattr(self.adventure, "can_damage_npcs", True)):
            msg = "Combat is disabled for this adventure: the protagonist cannot damage NPCs."
            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"
            async for chunk in self._emit_combat_final(msg):
                yield chunk
            return

        if self._is_combat_active():
            msg = "A fight is already active. Use Attack, Run, or a consumable."
            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"
            async for chunk in self._emit_combat_final(msg):
                yield chunk
            return

        target_hint = ""
        if " " in user_msg:
            target_hint = user_msg.split(" ", 1)[1].strip()
        
        target = await self._find_fight_target(target_hint)
        if not target:
            msg = "No enemy is available in this scene."
            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"
            async for chunk in self._emit_combat_final(msg):
                yield chunk
            return

        # Check if NPC is already defeated (permanent state)
        states = self.state.entity_states or {}
        is_defeated = (states.get(target.id, {}) or {}).get("is_defeated", False)
        if is_defeated:
            msg = f"{target.name} has already been defeated."
            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"
            async for chunk in self._emit_combat_final(msg):
                yield chunk
            return

        # Check if NPC is attackable
        is_attackable = (states.get(target.id, {}) or {}).get("is_attackable")
        if is_attackable is None:
            is_attackable = target.is_attackable
            
        if is_attackable is False:
            msg = f"You cannot attack {target.name}."
            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"
            async for chunk in self._emit_combat_final(msg):
                yield chunk
            return

        enemy_hp = self._entity_stat(target, "hp", 50)
        if enemy_hp <= 0:
            msg = f"{target.name} is already defeated."
            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"
            async for chunk in self._emit_combat_final(msg):
                yield chunk
            return

        enemy_max_hp = self._entity_stat(target, "max_hp", enemy_hp if enemy_hp > 0 else 50)
        # If no NPC dexterity value is provided, use a neutral baseline so enemies can act reliably.
        enemy_dex = self._entity_stat(target, "stat_modifier_dexterity", 10)
        enemy_ac_mod = self._entity_stat(target, "stat_modifier_armor_class", 0)
        player_stats = calculate_total_stats(self.avatar)
        player_dex = int(player_stats.get("dexterity", self.avatar.dexterity))

        player_init = random.randint(1, 20) + max(0, player_dex // 2)
        enemy_init = random.randint(1, 20) + max(0, enemy_dex // 2)
        player_starts = player_init >= enemy_init

        combat = {
            "active": True,
            "round": 1,
            "turn": "player" if player_starts else "enemy",
            "player": {
                "name": self.avatar.name,
                "image_url": self.avatar.profile_image,
                "hp": self.avatar.hp,
                "max_hp": self.avatar.max_hp,
                "stamina": self.avatar.stamina,
                "max_stamina": self.avatar.max_stamina,
                "ac": int(player_stats.get("armor_class", self.avatar.armor_class)),
            },
            "enemy": {
                "id": target.id,
                "name": target.name,
                "image_url": target.image_url,
                "hp": enemy_hp,
                "max_hp": enemy_max_hp,
                "stamina": self._entity_stat(target, "stamina", 0),
                "max_stamina": self._entity_stat(target, "max_stamina", 0),
                "dexterity_mod": enemy_dex,
                "armor_mod": enemy_ac_mod,
                "inventory": await self._normalize_loot_items(list(target.inventory or [])),
            },
            "loot_pending": False,
            "loot_items": [],
            "outcome": None,
            "status_note": None,
            "log": [],
        }
        self._append_combat_log(combat, f"Initiative: {self.avatar.name} {player_init} vs {target.name} {enemy_init}.", "initiative")
        if player_starts:
            self._append_combat_log(combat, f"{self.avatar.name} starts the fight.", "turn")
        else:
            self._append_combat_log(combat, f"{target.name} is faster and starts.", "turn")
        self._set_combat_state(combat)

        # If enemy starts, immediately resolve one enemy action.
        if not player_starts:
            async for chunk in self._resolve_enemy_turn():
                yield chunk

        msg = f"Combat started against {target.name}."
        yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"
        async for chunk in self._emit_combat_final(msg):
            yield chunk

    async def _auto_trigger_combat_from_gm(self, game_event: GameEvent) -> bool:
        """Starts combat automatically when mechanics pass requests combat attacks."""
        if self._is_combat_active() or self._has_combat_phase():
            return False
        if (self.adventure.rule_enforcement_mode or "rpg") != "rpg":
            return False
        if not bool(getattr(self.adventure, "can_damage_npcs", True)):
            return False
        if not game_event.requested_attacks:
            return False

        target_hint = ""
        for req in game_event.requested_attacks:
            if req.target_id and req.target_id.upper() != "PLAYER":
                target_hint = req.target_id
                break
            if req.attacker_id and req.attacker_id.upper() != "PLAYER":
                target_hint = req.attacker_id
                break

        target = await self._find_fight_target(target_hint)
        if not target:
            return False

        async for _chunk in self._handle_fight_start(f"/fight {target.id}"):
            pass
        return True

    def _find_consumable(self, item_name: str) -> dict[str, Any] | None:
        for item in list(self.avatar.inventory or []):
            if isinstance(item, dict) and item.get("name", "").lower() == item_name.lower() and item.get("item_type") == "CONSUMABLE":
                return item
        return None

    def _sync_combat_player_snapshot(self, combat: dict[str, Any]) -> None:
        player = dict(combat.get("player") or {})
        player_stats = calculate_total_stats(self.avatar)
        player["name"] = self.avatar.name
        player["image_url"] = self.avatar.profile_image
        player["hp"] = int(self.avatar.hp or 0)
        player["max_hp"] = int(self.avatar.max_hp or RESOURCE_CAP)
        player["stamina"] = int(self.avatar.stamina or 0)
        player["max_stamina"] = int(self.avatar.max_stamina or RESOURCE_CAP)
        player["ac"] = int(player_stats.get("armor_class", self.avatar.armor_class))
        combat["player"] = player

    @staticmethod
    def _description_delta(description: str, resource: str) -> int:
        if not description:
            return 0

        aliases = {
            "hp": r"(?:hp|health|lebenspunkte?)",
            "mana": r"(?:mana|magie|magiekraft)",
            "stamina": r"(?:stamina|ausdauer|energie)",
        }
        resource_rx = aliases.get(resource)
        if not resource_rx:
            return 0

        desc = description.lower()
        pos_words = (
            "stellt", "wieder her", "heilt", "regeneriert", "restores", "restore", "heals", "heal", "regains", "regain",
            "replenish", "replenishes", "recover", "recovers", "gain", "gains", "boost"
        )
        neg_words = (
            "kostet", "verliert", "schaden", "schadet", "entzieht", "senkt", "reduziert", "damage", "damages",
            "lose", "loses", "losing", "drain", "drains", "reduces", "reduce", "consumes", "consume"
        )

        total = 0
        for match in re.finditer(rf"([+-]?\d+)\s*{resource_rx}", desc):
            raw = match.group(1)
            magnitude = abs(int(raw))
            start = max(0, match.start() - 40)
            end = min(len(desc), match.end() + 40)
            ctx = desc[start:end]

            if raw.startswith("-"):
                total -= magnitude
            elif raw.startswith("+"):
                total += magnitude
            elif any(word in ctx for word in neg_words):
                total -= magnitude
            elif any(word in ctx for word in pos_words):
                total += magnitude

        return total

    def _resource_delta_from_consumable(self, item: dict[str, Any], resource: str) -> int:
        key_map = {
            "hp": ["hp_change", "health_change", "heal", "heal_amount", "restore_hp", "restore_health", "hp_delta"],
            "mana": ["mana_change", "restore_mana", "mana_restore", "mana_delta"],
            "stamina": ["stamina_change", "restore_stamina", "stamina_restore", "stamina_delta"],
        }
        keys = key_map.get(resource, [])

        for k in keys:
            val = item.get(k)
            if isinstance(val, (int, float)):
                return int(val)

        effects = item.get("effects")
        if isinstance(effects, dict):
            val = effects.get(resource)
            if isinstance(val, (int, float)):
                return int(val)

        metadata_json = item.get("metadata_json")
        if isinstance(metadata_json, dict):
            for k in keys:
                val = metadata_json.get(k)
                if isinstance(val, (int, float)):
                    return int(val)

            meta_effects = metadata_json.get("effects")
            if isinstance(meta_effects, dict):
                val = meta_effects.get(resource)
                if isinstance(val, (int, float)):
                    return int(val)

        description = item.get("description")
        if isinstance(description, str):
            return self._description_delta(description, resource)

        return 0

    @staticmethod
    def _parse_json_object(raw: str) -> dict[str, Any] | None:
        text = (raw or "").strip()
        if not text:
            return None

        try:
            data = json.loads(text)
            return data if isinstance(data, dict) else None
        except Exception:
            pass

        fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.IGNORECASE | re.DOTALL)
        if fence:
            try:
                data = json.loads(fence.group(1))
                return data if isinstance(data, dict) else None
            except Exception:
                pass

        obj_match = re.search(r"(\{.*\})", text, re.DOTALL)
        if obj_match:
            try:
                data = json.loads(obj_match.group(1))
                return data if isinstance(data, dict) else None
            except Exception:
                return None
        return None

    async def _request_llm_combat_special_event(self, combat: dict[str, Any]) -> dict[str, Any] | None:
        llm_settings = self.user.llm_settings or {}
        complex_model_provider = (
            llm_settings.get("complex_model_provider")
            or llm_settings.get("small_model_provider")
            or llm_settings.get("preferred_provider")
            or "openai"
        )
        complex_model = llm_settings.get("complex_model") or "gpt-4o"

        try:
            llm = GameMasterLLM(self.user, provider=complex_model_provider, model_category="complex")
        except ValueError:
            return None

        enemy = combat.get("enemy") or {}
        player = combat.get("player") or {}
        enemy_name = str(enemy.get("name") or "Enemy")
        player_name = str(player.get("name") or self.avatar.name or "Protagonist")
        enemy_hp = int(enemy.get("hp") or 0)
        enemy_max_hp = int(enemy.get("max_hp") or max(enemy_hp, 1))
        player_hp = int(player.get("hp") or self.avatar.hp or 0)
        player_max_hp = int(player.get("max_hp") or self.avatar.max_hp or max(player_hp, 1))

        system_prompt = (
            "You are the Game Master deciding a combat special event. "
            "Return ONLY valid JSON with this schema: "
            "{\"mode\":\"story\"|\"special_attack\",\"text\":string,\"damage\":number}. "
            "Rules: Keep text to 1-2 short in-world sentences. "
            "If mode is story, set damage to 0. "
            "If mode is special_attack, damage must be an integer between 5 and 40. "
            "No markdown, no code fences, no extra keys."
        )
        if self.turn_language:
            system_prompt += f" Text must be in {self.turn_language.upper()}."

        user_prompt = (
            f"Round: {int(combat.get('round') or 1)}. "
            f"Attacker: {enemy_name} HP {enemy_hp}/{enemy_max_hp}. "
            f"Target: {player_name} HP {player_hp}/{player_max_hp}. "
            "Decide if this special event becomes narrative flavor or a special attack. "
            "Return only the JSON object."
        )

        try:
            raw = await llm.aexecute_simple_task(
                system_prompt,
                user_prompt,
                complex_model,
                adventure_id=self.state.template_id,
                game_id=self.game_id,
                operation="combat.special_event",
                phase="decision",
            )
        except Exception as exc:
            logger.warning("[Turn %s] Special-event LLM call failed: %s", self.game_id, exc)
            return None

        data = self._parse_json_object(raw)
        if not data:
            logger.warning("[Turn %s] Special-event LLM returned unparsable payload: %r", self.game_id, raw)
            return None

        mode = str(data.get("mode") or "").strip().lower()
        text = str(data.get("text") or "").strip()
        damage_raw = data.get("damage")
        damage = 0
        if isinstance(damage_raw, (int, float)):
            damage = int(damage_raw)

        if mode not in {"story", "special_attack"}:
            return None

        if mode == "special_attack":
            damage = max(5, min(40, damage))
            if not text:
                text = f"Special Event: {enemy_name} unleashes a sudden devastating strike!"
        else:
            damage = 0
            if not text:
                text = f"Special Event: {enemy_name} alters the tone of battle with a chilling presence."

        return {"mode": mode, "text": text, "damage": damage}

    def _consume_item_now(self, item_name: str) -> str:
        item = self._find_consumable(item_name)
        if not item:
            return f"You do not have the consumable '{item_name}'."

        hp_delta = self._resource_delta_from_consumable(item, "hp")
        mana_delta = self._resource_delta_from_consumable(item, "mana")
        stamina_delta = self._resource_delta_from_consumable(item, "stamina")

        if hp_delta:
            max_hp = self.avatar.max_hp or RESOURCE_CAP
            self.avatar.hp = max(0, min(max_hp, self.avatar.hp + hp_delta))
        if mana_delta:
            max_mana = self.avatar.max_mana or RESOURCE_CAP
            self.avatar.mana = max(0, min(max_mana, self.avatar.mana + mana_delta))
        if stamina_delta:
            max_stamina = self.avatar.max_stamina or RESOURCE_CAP
            self.avatar.stamina = max(0, min(max_stamina, self.avatar.stamina + stamina_delta))

        new_inventory = []
        removed = False
        for inv_item in list(self.avatar.inventory or []):
            if not removed and isinstance(inv_item, dict) and inv_item.get("name", "").lower() == item_name.lower() and inv_item.get("item_type") == "CONSUMABLE":
                removed = True
                continue
            new_inventory.append(inv_item)
        self.avatar.inventory = new_inventory

        gained = []
        lost = []
        if hp_delta > 0: gained.append(f"+{hp_delta} HP")
        elif hp_delta < 0: lost.append(f"{hp_delta} HP")
        
        if mana_delta > 0: gained.append(f"+{mana_delta} Mana")
        elif mana_delta < 0: lost.append(f"{mana_delta} Mana")
        
        if stamina_delta > 0: gained.append(f"+{stamina_delta} Stamina")
        elif stamina_delta < 0: lost.append(f"{stamina_delta} Stamina")

        msg = f"{self.avatar.name} uses {item.get('name', item_name)}."
        stat_parts = []
        if gained:
            stat_parts.append(f"You gain: {', '.join(gained)}.")
        if lost:
            stat_parts.append(f"You lose: {', '.join(lost)}.")
            
        if stat_parts:
            return f"{msg} {' '.join(stat_parts)}"
        return msg

    async def _maybe_trigger_special_event(self, combat: dict[str, Any]) -> str | None:
        if random.random() > 0.25:
            return None

        enemy_name = combat.get("enemy", {}).get("name", "Enemy")
        if not bool(getattr(self.adventure, "npcs_can_damage_protagonist", True)):
            text = f"Special Event: {enemy_name} shifts the pressure of battle, but no direct damage is dealt."
            self._append_combat_log(combat, text, "special")
            return text
        event_data = await self._request_llm_combat_special_event(combat)

        # Safe fallback if LLM is unavailable or returns invalid payload.
        if not event_data:
            if random.random() < 0.5:
                bonus = 20
                self.avatar.hp = max(0, self.avatar.hp - bonus)
                text = f"Special Event: {enemy_name} performs a special attack for {bonus} damage!"
                self._append_combat_log(combat, text, "special")
                if self.avatar.hp <= 0:
                    raise GameOverException(f"{self.avatar.name} has fallen! Game Over.")
                return text

            text = f"Special Event: {enemy_name} bends the battlefield mood to its advantage."
            self._append_combat_log(combat, text, "special")
            return text

        if event_data.get("mode") == "special_attack":
            bonus = int(event_data.get("damage") or 0)
            self.avatar.hp = max(0, self.avatar.hp - bonus)
            text = str(event_data.get("text") or f"Special Event: {enemy_name} performs a special attack for {bonus} damage!")
            self._append_combat_log(combat, text, "special")
            if self.avatar.hp <= 0:
                raise GameOverException(f"{self.avatar.name} has fallen! Game Over.")
            return text

        text = str(event_data.get("text") or f"Special Event: {enemy_name} bends the battlefield mood to its advantage.")
        self._append_combat_log(combat, text, "special")
        return text

    async def _resolve_enemy_turn(self) -> AsyncGenerator[str, None]:
        combat = self._read_combat_state()
        if not combat.get("active"):
            return

        enemy = combat.get("enemy", {})
        enemy_id = enemy.get("id")
        if not enemy_id:
            return

        enemy_res = await self.db.execute(select(WorldEntity).where(WorldEntity.id == enemy_id, WorldEntity.session_id == self.game_id))
        enemy_ent = enemy_res.scalars().first()
        if not enemy_ent:
            combat["active"] = False
            combat["outcome"] = "victory"
            combat["status_note"] = "Enemy vanished from the scene."
            self._append_combat_log(combat, combat["status_note"], "outcome")
            self._set_combat_state(combat)
            return

        enemy_hp = int(combat.get("enemy", {}).get("hp") or 0)
        if enemy_hp <= 0:
            combat["active"] = False
            combat["outcome"] = "victory"
            combat["status_note"] = f"{enemy.get('name', 'Enemy')} was defeated."
            self._set_combat_state(combat)
            return

        player_stats = calculate_total_stats(self.avatar)
        player_ac = int(player_stats.get("armor_class", self.avatar.armor_class))

        enemy_stamina = self._entity_stat(enemy_ent, "stamina", 0)
        enemy_max_stamina = self._entity_stat(enemy_ent, "max_stamina", 0)

        # Enforce stamina logic if NPC has stamina configured
        if enemy_max_stamina > 0:
            # Check if enemy is out of stamina
            if enemy_stamina < 20:
                # Enemy rests
                enemy_stamina = min(enemy_max_stamina, enemy_stamina + 40)
                
                # Save enemy state
                combat["enemy"]["stamina"] = enemy_stamina
                states = dict(self.state.entity_states or {})
                if enemy_id not in states:
                    states[enemy_id] = {}
                states[enemy_id]["stamina"] = enemy_stamina
                self.state.entity_states = states
                flag_modified(self.state, "entity_states")

                text = f"{enemy_ent.name} is exhausted and rests to recover stamina (+40 Stamina)."
                self._sync_combat_player_snapshot(combat)
                self._append_combat_log(combat, text, "enemy_action")
                yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': text})}\n\n"

                # Transition turn back to player
                combat["turn"] = "player"
                combat["round"] = int(combat.get("round", 1)) + 1
                self._append_combat_log(combat, f"Round {combat['round']}: {self.avatar.name}'s turn.", "turn")
                self._set_combat_state(combat)
                return

            # Consume stamina for attacking
            enemy_stamina = max(0, enemy_stamina - 20)
            combat["enemy"]["stamina"] = enemy_stamina
            states = dict(self.state.entity_states or {})
            if enemy_id not in states:
                states[enemy_id] = {}
            states[enemy_id]["stamina"] = enemy_stamina
            self.state.entity_states = states
            flag_modified(self.state, "entity_states")

        enemy_avatar = Avatar(
            name=enemy_ent.name,
            hp=enemy_hp,
            strength=self._entity_stat(enemy_ent, "stat_modifier_strength", 0),
            dexterity=self._entity_stat(enemy_ent, "stat_modifier_dexterity", 10),
            intelligence=self._entity_stat(enemy_ent, "stat_modifier_intelligence", 0),
            wisdom=self._entity_stat(enemy_ent, "stat_modifier_wisdom", 0),
            charisma=self._entity_stat(enemy_ent, "stat_modifier_charisma", 0),
            armor_class=10 + self._entity_stat(enemy_ent, "stat_modifier_armor_class", 0),
            stats={},
            equipment={},
            inventory=[]
        )

        if not bool(getattr(self.adventure, "npcs_can_damage_protagonist", True)):
            text = f"{enemy_ent.name} attacks, but this adventure disables NPC damage to the protagonist."
            self._sync_combat_player_snapshot(combat)
            self._append_combat_log(combat, text, "enemy_action")
            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': text})}\n\n"
            combat["turn"] = "player"
            combat["round"] = int(combat.get("round", 1)) + 1
            self._append_combat_log(combat, f"Round {combat['round']}: {self.avatar.name}'s turn.", "turn")
            self._set_combat_state(combat)
            return

        roll = roll_attack(enemy_avatar, "dexterity", player_ac, self._enemy_damage_dice(enemy_ent))
        if roll["is_hit"]:
            self.avatar.hp = max(0, self.avatar.hp - roll["damage_total"])
            dmg_bonus = int(roll.get("damage_bonus") or 0)
            dmg_bonus_str = f" + {dmg_bonus}" if dmg_bonus > 0 else (f" - {abs(dmg_bonus)}" if dmg_bonus < 0 else "")
            hit_status = "CRITICAL HIT" if roll.get("is_crit") else "HIT"
            text = (
                f"{enemy_ent.name} ATTACK ROLL: {roll['hit_roll']} + {roll['hit_modifier']} = {roll['hit_total']} vs AC {player_ac} -> {hit_status} | "
                f"DMG {roll['damage_dice_str']} ({' + '.join(str(r) for r in roll['damage_rolls'])}"
                f"{dmg_bonus_str})"
                f" = {roll['damage_total']}"
            )
        else:
            text = f"{enemy_ent.name} ATTACK ROLL: {roll['hit_roll']} + {roll['hit_modifier']} = {roll['hit_total']} vs AC {player_ac} -> MISS"
        self._sync_combat_player_snapshot(combat)
        self._append_combat_log(combat, text, "enemy_action")
        yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': text})}\n\n"

        if self.avatar.hp <= 0:
            await self._finalize_session("game_over", f"{self.avatar.name} has fallen in battle.")
            combat["active"] = False
            combat["outcome"] = "defeat"
            combat["status_note"] = "Game Over"
            self._append_combat_log(combat, "The protagonist falls. Game Over.", "outcome")
            self._set_combat_state(combat)
            return

        try:
            special_text = await self._maybe_trigger_special_event(combat)
            self._sync_combat_player_snapshot(combat)
            if special_text:
                yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': special_text})}\n\n"
        except GameOverException as goe:
            await self._finalize_session("game_over", str(goe))
            self._sync_combat_player_snapshot(combat)
            combat["active"] = False
            combat["outcome"] = "defeat"
            combat["status_note"] = str(goe)
            self._set_combat_state(combat)
            return

        combat["turn"] = "player"
        combat["round"] = int(combat.get("round", 1)) + 1
        self._append_combat_log(combat, f"Round {combat['round']}: {self.avatar.name}'s turn.", "turn")
        self._set_combat_state(combat)

    async def _spawn_scene_item(self, item: dict[str, Any]) -> None:
        name = str(item.get("name") or "Unknown Loot")
        raw_id = str(item.get("id") or "")
        
        # If it's an existing entity in this session, just move it back to the scene
        existing_ent = None
        if raw_id:
            ent_res = await self.db.execute(
                select(WorldEntity).where(
                    WorldEntity.session_id == self.game_id,
                    WorldEntity.id == raw_id
                )
            )
            existing_ent = ent_res.scalars().first()
            if existing_ent:
                existing_ent.current_scene_id = self.state.current_scene_id
                existing_ent.is_in_inventory = False

                # Keep session overrides in sync so snapshot filtering cannot hide dropped loot.
                states = dict(self.state.entity_states or {})
                if raw_id not in states:
                    states[raw_id] = {}
                states[raw_id]["is_in_inventory"] = False
                states[raw_id]["current_scene_id"] = self.state.current_scene_id
                states[raw_id]["is_hidden"] = False
                self.state.entity_states = states
                flag_modified(self.state, "entity_states")
                return

        # Fallback: match by name (case-insensitive) to preserve pre-configured items (like keys)
        if not existing_ent and name:
            ent_res = await self.db.execute(
                select(WorldEntity).where(
                    WorldEntity.session_id == self.game_id,
                    WorldEntity.entity_type == "OBJECT"
                )
            )
            all_objs = ent_res.scalars().all()
            for obj in all_objs:
                if (obj.name or "").strip().lower() == name.strip().lower():
                    existing_ent = obj
                    raw_id = obj.id
                    break

        if existing_ent:
            existing_ent.current_scene_id = self.state.current_scene_id
            existing_ent.is_in_inventory = False
            
            # Also update override in session state
            states = dict(self.state.entity_states or {})
            if raw_id not in states:
                states[raw_id] = {}
            states[raw_id]["is_in_inventory"] = False
            states[raw_id]["current_scene_id"] = self.state.current_scene_id
            states[raw_id]["is_hidden"] = False
            self.state.entity_states = states
            flag_modified(self.state, "entity_states")
            return

        # Otherwise create a new one (e.g. for loot or generated items)
        if not raw_id:
            raw_id = f"LOOT_{uuid.uuid4().hex[:8]}"
            
        safe_id = re.sub(r"[^A-Za-z0-9_\-]", "_", raw_id)[:50]
        if not safe_id:
            safe_id = f"LOOT_{uuid.uuid4().hex[:8]}"

        # Prevent duplicate IDs in the same running session by suffixing collisions.
        base_id = safe_id
        counter = 1
        while await self._session_entity_id_exists(safe_id):
            suffix = f"_{counter}"
            safe_id = f"{base_id[: max(1, 50 - len(suffix))]}{suffix}"
            counter += 1

        # Generate high-quality placeholder if image_url is missing
        image_url = item.get("image_url")
        if not image_url:
            try:
                from backend.engine.media_engine import MediaEngine
                from backend.core.config import settings
                import os
                
                item_type = item.get("item_type") or "PICKABLE"
                safe_adventure_id = _sanitize_path_component(self.adventure.id) or "adventure"
                target_dir = _ensure_within_data_dir(
                    os.path.join(settings.DATA_DIR, "adventures", "library", safe_adventure_id, "entities")
                )
                image_url = await MediaEngine.generate_placeholder(
                    adventure_id=self.adventure.id,
                    entity_id=safe_id,
                    target_dir=target_dir,
                    category=f"ITEM_{item_type.upper()}"
                )
            except Exception as e:
                logger.error("Failed to generate spawned item placeholder: %s", e)
                image_url = None
        states = dict(self.state.entity_states or {})
        if safe_id in states:
            states[safe_id]["is_in_inventory"] = False
            states[safe_id]["current_scene_id"] = self.state.current_scene_id
            states[safe_id]["is_hidden"] = False
            self.state.entity_states = states
            flag_modified(self.state, "entity_states")

        entity = WorldEntity(
            id=safe_id,
            session_id=self.game_id,
            template_id=None,
            entity_type="OBJECT",
            name=name,
            description=str(item.get("description") or f"Loot from battle: {name}"),
            current_scene_id=self.state.current_scene_id,
            spatial_position=item.get("spatial_position") or "on the ground",
            image_url=image_url,
            item_type=item.get("item_type") or "PICKABLE",
            wearable_slots=item.get("wearable_slots"),
            is_in_inventory=False,
            is_hidden=False,
            unlock_rule=None,
            is_portable=True,
            stat_modifier_strength=item.get("stat_modifier_strength"),
            stat_modifier_dexterity=item.get("stat_modifier_dexterity"),
            stat_modifier_intelligence=item.get("stat_modifier_intelligence"),
            stat_modifier_wisdom=item.get("stat_modifier_wisdom"),
            stat_modifier_charisma=item.get("stat_modifier_charisma"),
            stat_modifier_armor_class=item.get("stat_modifier_armor_class"),
            metadata_json={
                "hp_change": item.get("hp_change"),
                "mana_change": item.get("mana_change"),
                "stamina_change": item.get("stamina_change"),
                "code_to_unlock": str(item.get("code_to_unlock") or "").strip(),
                "item_to_unlock": str(item.get("item_to_unlock") or "").strip().upper(),
                "locked": bool(item.get("locked")) if item.get("locked") is not None else None,
            }
        )
        self.db.add(entity)

    async def _session_entity_id_exists(self, entity_id: str) -> bool:
        res = await self.db.execute(
            select(WorldEntity.pk).where(
                WorldEntity.session_id == self.game_id,
                WorldEntity.id == entity_id,
            ).limit(1)
        )
        return res.first() is not None

    async def _collect_existing_item_ids(self) -> set[str]:
        existing_ids: set[str] = {
            str(item.get("id"))
            for item in (self.avatar.inventory or [])
            if isinstance(item, dict) and item.get("id")
        }

        res = await self.db.execute(
            select(WorldEntity.id).where(WorldEntity.session_id == self.game_id)
        )
        existing_ids.update({row.id for row in res.all() if row.id})
        return existing_ids

    async def _normalize_loot_items(self, items: list[Any]) -> list[dict[str, Any]]:
        """Normalize various loot representations into dicts with at least `id` and `name`.

        Items can be:
        - dicts already containing item data
        - strings that reference a WorldEntity id (template or session)
        - other types (ignored)
        """
        normalized: list[dict[str, Any]] = []
        if not items:
            return normalized

        for it in items:
            # If already a dict, ensure it has id/name
            if isinstance(it, dict):
                entry = dict(it)
                if not entry.get("id") and entry.get("name"):
                    # generate a synthetic id when missing
                    entry["id"] = f"LOOT_{uuid.uuid4().hex[:8]}"
                normalized.append(entry)
                continue

            # If it's a string, try to resolve WorldEntity by id
            if isinstance(it, str) and it.strip():
                ent_id = it.strip()
                ent_res = await self.db.execute(
                    select(WorldEntity).where(
                        (WorldEntity.session_id == self.game_id) & (WorldEntity.id == ent_id)
                    )
                )
                ent = ent_res.scalars().first()

                # If not found in session, try template entities for this adventure
                if not ent and self.state and self.state.template_id:
                    ent_res = await self.db.execute(
                        select(WorldEntity).where(
                            (WorldEntity.template_id == self.state.template_id) & (WorldEntity.id == ent_id)
                        )
                    )
                    ent = ent_res.scalars().first()

                if ent:
                    normalized.append({
                        "id": ent.id,
                        "name": ent.name,
                        "description": ent.description,
                        "image_url": ent.image_url,
                        "item_type": ent.item_type,
                        "wearable_slots": ent.wearable_slots,
                        **(ent.metadata_json or {}),
                    })
                else:
                    # Unknown reference, keep minimal info
                    normalized.append({"id": ent_id, "name": ent_id})
                continue

            # Fallback: ignore unknown types
        return normalized

    async def _resolve_loot_command(self, user_msg: str, combat: dict[str, Any]) -> str | None:
        low = user_msg.lower().strip()
        if not low.startswith("/loot"):
            return None

        parts = user_msg.split(" ", 2)
        action = parts[1].lower() if len(parts) > 1 else ""
        arg = parts[2].strip() if len(parts) > 2 else ""

        loot_items = list(combat.get("loot_items") or [])

        if action == "take":
            if not arg:
                return "Usage: /loot take <item id or item name>"
            idx = next((i for i, it in enumerate(loot_items) if str(it.get("id", "")).lower() == arg.lower() or str(it.get("name", "")).lower() == arg.lower()), -1)
            if idx < 0:
                return "Item not found in loot."
            picked = loot_items.pop(idx)
            inv = list(self.avatar.inventory or [])
            inv.append(picked)
            self.avatar.inventory = inv
            combat["loot_items"] = loot_items
            self._append_combat_log(combat, f"Loot taken: {picked.get('name', 'Unknown Item')}", "loot")
            self._set_combat_state(combat)
            return f"Added {picked.get('name', 'item')} to your inventory."

        if action in {"leave", "drop"}:
            if not arg:
                return "Usage: /loot leave <item id or item name>"
            idx = next((i for i, it in enumerate(loot_items) if str(it.get("id", "")).lower() == arg.lower() or str(it.get("name", "")).lower() == arg.lower()), -1)
            if idx < 0:
                return "Item not found in loot."
            dropped = loot_items.pop(idx)
            await self._spawn_scene_item(dropped)
            combat["loot_items"] = loot_items
            self._append_combat_log(combat, f"Loot dropped to scene: {dropped.get('name', 'Unknown Item')}", "loot")
            self._set_combat_state(combat)
            return f"{dropped.get('name', 'Item')} dropped to the current scene."

        if action == "done":
            dropped_items = list(loot_items)
            for item in dropped_items:
                await self._spawn_scene_item(item)
            combat["loot_items"] = []
            combat["loot_pending"] = False
            combat.pop("outcome", None)
            combat["status_note"] = "Combat resolved."
            self._append_combat_log(combat, combat["status_note"], "loot")
            
            # If nothing is left to do, clear the combat state entirely from all sources
            if not combat.get("active") and not combat.get("loot_pending") and not combat.get("outcome"):
                self.state.combat_json = None
                # Aggressively clear combat state by creating a new filtered dict
                self.state.entity_states = {k: v for k, v in (self.state.entity_states or {}).items() if k != "__combat__"}
                flag_modified(self.state, "entity_states")
                last_msg = await self._load_last_assistant_message()
                await self._generate_prompt_suggestions(last_msg)
                await self.db.commit()
            else:
                self._set_combat_state(combat)

            if dropped_items:
                dropped_names = [str(item.get("name") or item.get("id") or "Unknown Item") for item in dropped_items]
                dropped_list = "\n".join(f"- {name}" for name in dropped_names)
                return f"Loot dropped to the scene:\n{dropped_list}"

            return "Combat finished. No loot remained to drop."

        return "Loot commands: /loot take <item>, /loot leave <item>, /loot done"

    def _award_combat_victory_xp(self, enemy_ent: WorldEntity) -> int:
        metadata = dict(enemy_ent.metadata_json or {})
        xp_gained = metadata.get("exp_reward") or metadata.get("xp_reward")
        if xp_gained is None:
            xp_gained = max(50, enemy_ent.max_hp or 100)
        self.avatar.exp = (self.avatar.exp or 0) + xp_gained
        return xp_gained

    async def _handle_combat_turn(self, user_msg: str) -> AsyncGenerator[str, None]:
        combat = self._read_combat_state()
        if not combat.get("active") and (combat.get("loot_pending") or combat.get("outcome")):
            pre_resolve_outcome = combat.get("outcome")
            loot_msg = await self._resolve_loot_command(user_msg, combat)
            if loot_msg:
                yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': loot_msg})}\n\n"
                if user_msg.lower().strip().startswith("/loot done"):
                    combat_after_loot = self._read_combat_state()
                    # Re-inject outcome for narration if it was just popped
                    if not combat_after_loot.get("outcome") and pre_resolve_outcome:
                        combat_after_loot["outcome"] = pre_resolve_outcome
                    async for chunk in self._emit_combat_aftermath_narration(combat_after_loot):
                        yield chunk
                async for chunk in self._emit_combat_final(loot_msg):
                    yield chunk
                return
            msg = "Loot phase active. Use /loot take, /loot leave, or /loot done."
            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"
            async for chunk in self._emit_combat_final(msg):
                yield chunk
            return

        if not combat.get("active"):
            msg = "No active combat. Use /fight to start."
            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"
            async for chunk in self._emit_combat_final(msg):
                yield chunk
            return

        if combat.get("turn") != "player":
            msg = "Wait for your turn."
            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"
            async for chunk in self._emit_combat_final(msg):
                yield chunk
            return

        cmd = user_msg.strip().lower()
        enemy = combat.get("enemy", {})
        enemy_id = enemy.get("id")
        enemy_res = await self.db.execute(select(WorldEntity).where(WorldEntity.id == enemy_id, WorldEntity.session_id == self.game_id))
        enemy_ent = enemy_res.scalars().first()
        if not enemy_ent:
            combat["active"] = False
            combat["outcome"] = "victory"
            combat["status_note"] = "Enemy no longer exists."
            self._append_combat_log(combat, combat["status_note"], "outcome")
            self._set_combat_state(combat)
            async for chunk in self._emit_combat_final(combat["status_note"]):
                yield chunk
            return

        enemy_hp = int(combat.get("enemy", {}).get("hp") or 0)
        enemy_ac = 10 + int(combat.get("enemy", {}).get("armor_mod") or 0)

        if enemy_hp <= 0:
            msg = f"{enemy_ent.name} is already defeated."
            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"
            async for chunk in self._emit_combat_final(msg):
                yield chunk
            return

        action_msg = None
        if (cmd == "attack" or cmd == "/attack" or cmd == "a" or cmd.startswith("attack ") or cmd.startswith("/attack ")) and not bool(getattr(self.adventure, "can_damage_npcs", True)):
            msg = "The protagonist cannot damage NPCs in this adventure. Use Run, Rest, or /consume."
            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"
            async for chunk in self._emit_combat_final(msg):
                yield chunk
            return

        if cmd == "attack" or cmd == "/attack" or cmd == "a" or cmd.startswith("attack ") or cmd.startswith("/attack "):
            if self.avatar.stamina < 20:
                msg = f"Not enough stamina to attack! You have {self.avatar.stamina} stamina, but attacks require 20. Use Rest to recover."
                yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"
                async for chunk in self._emit_combat_final(msg):
                    yield chunk
                return
            
            # Deduct stamina
            self.avatar.stamina = max(0, self.avatar.stamina - 20)
            self._sync_combat_player_snapshot(combat)
            
            # Roll attack
            roll = roll_attack(self.avatar, "dexterity", enemy_ac, self._player_damage_dice())
            hit_status = "CRITICAL HIT" if roll.get("is_crit") else "HIT"
            if roll["is_hit"]:
                enemy_hp = max(0, enemy_hp - roll["damage_total"])
                dmg_bonus = int(roll.get("damage_bonus") or 0)
                dmg_bonus_str = f" + {dmg_bonus}" if dmg_bonus > 0 else (f" - {abs(dmg_bonus)}" if dmg_bonus < 0 else "")
                action_msg = (
                    f"{self.avatar.name} ATTACK ROLL: {roll['hit_roll']} + {roll['hit_modifier']} = {roll['hit_total']} vs AC {enemy_ac} -> {hit_status} | "
                    f"DMG {roll['damage_dice_str']} ({' + '.join(str(r) for r in roll['damage_rolls'])}"
                    f"{dmg_bonus_str})"
                    f" = {roll['damage_total']}"
                )
            else:
                action_msg = f"{self.avatar.name} ATTACK ROLL: {roll['hit_roll']} + {roll['hit_modifier']} = {roll['hit_total']} vs AC {enemy_ac} -> MISS"
            self._append_combat_log(combat, action_msg, "player_action")
        elif cmd in {"rest", "/rest", "wait", "/wait", "recover", "/recover", "skip", "/skip"}:
            self.avatar.stamina = min(self.avatar.max_stamina or 100, self.avatar.stamina + 40)
            self._sync_combat_player_snapshot(combat)
            action_msg = f"{self.avatar.name} rests to recover stamina (+40 Stamina)."
            self._append_combat_log(combat, action_msg, "player_action")
        elif cmd in {"run", "/run", "r"}:
            player_stats = calculate_total_stats(self.avatar)
            player_roll = random.randint(1, 20) + int(player_stats.get("dexterity", self.avatar.dexterity))
            enemy_roll = random.randint(1, 20) + int(combat.get("enemy", {}).get("dexterity_mod") or 0)
            if player_roll >= enemy_roll:
                combat["active"] = False
                combat["outcome"] = "escaped"
                combat["status_note"] = f"{self.avatar.name} escapes from combat."
                self._append_combat_log(combat, f"Run check: {player_roll} vs {enemy_roll}. Escape successful.", "run")
                self._set_combat_state(combat)
                yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': combat['status_note']})}\n\n"
                async for chunk in self._emit_combat_aftermath_narration(combat):
                    yield chunk
                async for chunk in self._emit_combat_final(combat["status_note"]):
                    yield chunk
                return
            action_msg = f"Run check failed ({player_roll} vs {enemy_roll}). {enemy_ent.name} keeps you in combat."
            self._append_combat_log(combat, action_msg, "run")
        elif cmd.startswith("/consume "):
            item_name = user_msg.split(" ", 1)[1].strip()
            action_msg = self._consume_item_now(item_name)
            self._sync_combat_player_snapshot(combat)
            self._append_combat_log(combat, action_msg, "consume")
        else:
            msg = "Combat active. Valid actions: Attack, Run, Rest, or /consume <item>."
            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"
            async for chunk in self._emit_combat_final(msg):
                yield chunk
            return

        if action_msg:
            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': action_msg})}\n\n"

        combat["enemy"]["hp"] = enemy_hp
        states = dict(self.state.entity_states or {})
        if enemy_id not in states:
            states[enemy_id] = {}
        states[enemy_id]["hp"] = enemy_hp
        self.state.entity_states = states
        flag_modified(self.state, "entity_states")

        if enemy_hp <= 0:
            combat["active"] = False
            combat["outcome"] = "victory"
            xp_gained = self._award_combat_victory_xp(enemy_ent)
            combat["status_note"] = f"{enemy_ent.name} is defeated. (+{xp_gained} XP)"
            combat["loot_pending"] = True
            combat["loot_items"] = await self._normalize_loot_items(list(enemy.get("inventory") or enemy_ent.inventory or []))
            states = dict(self.state.entity_states or {})
            if enemy_id not in states:
                states[enemy_id] = {}
            states[enemy_id]["inventory"] = []
            if self._is_npc_killable(enemy_ent):
                # Mark NPC as permanently defeated so they cannot be re-engaged
                states[enemy_id]["is_defeated"] = True
                states[enemy_id]["is_attackable"] = False
            self.state.entity_states = states
            flag_modified(self.state, "entity_states")
            self._append_combat_log(combat, combat["status_note"], "outcome")
            
            msg = f"Defeated {enemy_ent.name}!"
            xp_msg = f"you gained {xp_gained} XP"
            await self._save_chat_message("system", msg)
            await self._save_chat_message("system", xp_msg)
            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"
            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': xp_msg})}\n\n"
            
            if combat.get("loot_items"):
                loot_msg = "Victory! Loot available. Use /loot take <item>, /loot leave <item>, /loot done"
                self._append_combat_log(combat, loot_msg, "loot")
                yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': loot_msg})}\n\n"
            self._set_combat_state(combat)
            async for chunk in self._emit_combat_final(combat["status_note"]):
                yield chunk
            return

        # NPC Fleeing logic (Improved: 10% chance if HP < 20%)
        enemy_max_hp_val = int(combat.get("enemy", {}).get("max_hp") or 100)
        if enemy_hp > 0 and enemy_hp <= (enemy_max_hp_val * 0.2):
            if random.random() < 0.10: # 10% chance
                combat["active"] = False
                combat["outcome"] = "victory"
                xp_gained = self._award_combat_victory_xp(enemy_ent)
                combat["status_note"] = f"{enemy_ent.name} flees in panic! You won the battle. (+{xp_gained} XP)"
                # Mark NPC as permanently defeated (fled = no re-engagement)
                states = dict(self.state.entity_states or {})
                if enemy_id not in states:
                    states[enemy_id] = {}
                if self._is_npc_killable(enemy_ent):
                    states[enemy_id]["is_defeated"] = True
                    states[enemy_id]["is_attackable"] = False
                self.state.entity_states = states
                flag_modified(self.state, "entity_states")
                # Spawn any remaining NPC inventory items to the scene automatically
                flee_loot = await self._normalize_loot_items(list(enemy.get("inventory") or enemy_ent.inventory or []))
                for flee_item in flee_loot:
                    await self._spawn_scene_item(flee_item)
                self._append_combat_log(combat, combat["status_note"], "outcome")
                self._set_combat_state(combat)
                msg = f"Defeated {enemy_ent.name}!"
                xp_msg = f"you gained {xp_gained} XP"
                await self._save_chat_message("system", msg)
                await self._save_chat_message("system", xp_msg)
                yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"
                yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': xp_msg})}\n\n"
                yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': combat['status_note']})}\n\n"
                async for chunk in self._emit_combat_aftermath_narration(combat):
                    yield chunk
                async for chunk in self._emit_combat_final(combat["status_note"]):
                    yield chunk
                return

        combat["turn"] = "enemy"
        self._set_combat_state(combat)
        async for chunk in self._resolve_enemy_turn():
            yield chunk
        async for chunk in self._emit_combat_final(None):
            yield chunk
        return

    async def _run_llm_cycle(self, user_msg: str, auto_visualize: bool, language: str | None = None) -> AsyncGenerator[str, None]:
        _ = auto_visualize
        cycle_start = time.perf_counter()
        scene_id_before_turn = self.state.current_scene_id
        ctx = await self._llm_context_builder.build_context(user_msg=user_msg, language=language)
        history = ctx.history
        entities = ctx.entities
        all_entities = ctx.all_entities
        exits = ctx.exits
        all_scenes = ctx.all_scenes
        mechanics_system_prompt = ctx.mechanics_system_prompt
        narration_system_prompt = ctx.narration_system_prompt
        mechanics_awards = ctx.mechanics_awards
        small_model_provider = ctx.small_model_provider
        complex_model_provider = ctx.complex_model_provider
        small_model = ctx.small_model
        complex_model = ctx.complex_model

        game_event = None
        pre_inventory_ids = set()
        response_text = ""

        # Pass 1: Mechanics (strict adventures), chat progression intent (normal chat),
        # or adventure-generator tool-intent pass (generator chat mode).
        run_mechanics_pass = self.adventure.strict_rules
        run_chat_progression_pass = not self.adventure.strict_rules and not self.adventure.is_adventure_generator
        run_generator_tool_intent_pass = self.adventure.is_adventure_generator and not self.adventure.strict_rules
        handled_generator_confirmation = False

        if run_generator_tool_intent_pass:
            pending_confirmation = self._get_pending_ag_image_confirmation()
            if pending_confirmation:
                handled_generator_confirmation = True
                decision = await self._parse_ag_image_confirmation_decision(user_msg)
                pending_request = AdventureGenerationRequest.model_validate(
                    pending_confirmation.get("request") or {}
                )

                if decision == "unknown":
                    game_event = AdventureGeneratorToolIntent(
                        narrative_description=(
                            "Before I start generation, confirm image mode: "
                            "reply with 'yes with images', 'yes without images', or 'cancel'."
                        )
                    )
                elif decision == "cancel":
                    self._clear_pending_ag_image_confirmation()
                    game_event = AdventureGeneratorToolIntent(
                        narrative_description="Understood. Adventure generation was cancelled."
                    )
                else:
                    self._clear_pending_ag_image_confirmation()
                    if decision == "with_images":
                        pending_request.generate_scene_images = True
                    if decision == "without_images":
                        pending_request.generate_scene_images = False
                        msg = "SYSTEM: Image generation disabled by user confirmation. Continuing with text-only world generation."
                        await self._save_chat_message("system", msg)
                        yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"

                    game_event = AdventureGeneratorToolIntent(
                        requested_adventure_generation=pending_request,
                        narrative_description=(
                            "The Architect inclines his head and begins weaving your requested world."
                            if decision == "with_images"
                            else "The Architect inclines his head and begins weaving your world without auto-generated images."
                        ),
                    )
                    async for tool_chunk in self._stream_adventure_generator_tools(game_event):
                        yield tool_chunk

        if run_mechanics_pass:
            yield f"event: status\ndata: {json.dumps({'content': 'Validating rules...'})}\n\n"
            try:
                llm = GameMasterLLM(self.user, provider=small_model_provider, model_category="small")
            except ValueError:
                yield f"event: error\ndata: {json.dumps({'detail': 'Mechanics model configuration is invalid. Please check your settings and try again.'})}\n\n"
                return
            
            mechanics_suffix = prompts.GM_MECHANICS_SUFFIX
            if self.adventure.rule_enforcement_mode == "story":
                mechanics_suffix = prompts.GM_STORY_MECHANICS_SUFFIX
            
            if self.state.allow_dynamic_items:
                dynamic_instr = (
                    "- To add an item directly to the player, use `new_inventory_items`. You are allowed to create/generate brand new items on-the-fly if contextually appropriate.\n"
                    "- To place a new item in the current scene, use `spawned_items`. You are allowed to create/generate brand new items on-the-fly.\n"
                )
            else:
                dynamic_instr = (
                    "- To add an existing pre-defined item to the player, use `new_inventory_items`. CRITICAL: You are NOT allowed to create/generate new items on-the-fly. Only move/use existing items defined in the world or NPC inventories.\n"
                    "- To place an existing pre-defined item in the current scene, use `spawned_items`. CRITICAL: You are NOT allowed to create/generate new items on-the-fly. Only move/use existing items defined in the world or NPC inventories.\n"
                )

            mechanics_prompt = mechanics_system_prompt + "\n\n" + mechanics_suffix.format(
                quests_json=self._compact_json(self.state.quests or []),
                awards_json=self._compact_json(mechanics_awards),
                dynamic_items_instruction=dynamic_instr
            )
            
            pass1_start = time.perf_counter()
            logger.debug(f"[Turn {self.game_id}] [Pass 1] Calling small model: {small_model} via {small_model_provider}")
            try:
                game_event = await llm.aexecute_complex_task(
                    mechanics_prompt,
                    user_msg,
                    response_model=GameEvent,
                    model=small_model,
                    operation="chat_turn",
                    phase="mechanics",
                )
            except Exception as e:
                user_safe_error = _friendly_llm_error_message(e)
                if user_safe_error:
                    yield f"event: error\ndata: {json.dumps({'detail': user_safe_error})}\n\n"
                    return
                logger.exception("[Turn %s] [Pass 1] Mechanics call failed unexpectedly", self.game_id)
                yield f"event: error\ndata: {json.dumps({'detail': _friendly_llm_unexpected_error_message()})}\n\n"
                return
            pass1_duration = time.perf_counter() - pass1_start
            log_structured_event(
                "gm.turn.pipeline.pass",
                adventure_id=self.adventure.id,
                game_id=self.game_id,
                operation="chat_turn",
                phase="mechanics",
                duration_ms=round(pass1_duration * 1000, 2),
                model=small_model,
                provider=small_model_provider,
            )
            logger.debug(f"[Turn {self.game_id}] [Pass 1] Mechanics analysis took {pass1_duration:.4f}s")

            # Auto-trigger turn-based combat dialog when mechanics detect combat start.
            await self._auto_trigger_combat_from_gm(game_event)
            
            # 2. Resolve Skill Checks
            if game_event.requested_skill_checks:
                results = []
                for req in game_event.requested_skill_checks:
                    roll = roll_skill_check(self.avatar, req.stat, req.dc)
                    res = SkillCheckResult(
                        stat=req.stat,
                        dc=req.dc,
                        roll=roll["d20"],
                        modifier=roll["modifier"],
                        total=roll["total"],
                        success=roll["success"],
                        reason=req.reason
                    )
                    results.append(res)
                    
                    # Output as system message for transparency
                    success_label = "SUCCESS" if res.success else "FAILURE"
                    roll_msg = (
                        f"🎲 **{req.stat.upper()} CHECK**: {res.reason}\n"
                        f"Roll: {res.roll} + {res.modifier} = **{res.total}** (vs DC {res.dc}) -> **{success_label}**"
                    )
                    await self._save_chat_message("system", roll_msg)
                    yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': roll_msg})}\n\n"
                
                game_event.skill_check_results = results
            
            # 2.5 Resolve Attack Rolls
            if game_event.requested_attacks:
                attack_results = []
                for req in game_event.requested_attacks:
                    # Fetch target AC
                    target_ac = 10
                    ac_reason = "Base AC 10"
                    target_id = req.target_id
                    
                    # Look in session state entities first
                    entity_states = self.state.entity_states or {}
                    target_state = entity_states.get(target_id, {})
                    
                    if "stat_modifier_armor_class" in target_state and target_state["stat_modifier_armor_class"] is not None:
                        mod = target_state["stat_modifier_armor_class"]
                        target_ac += mod
                        ac_reason = f"Base 10 + {mod} Mod"
                    else:
                        # Fetch from template if not in state
                        target_res = await self.db.execute(select(WorldEntity).where(WorldEntity.id == target_id, WorldEntity.session_id == self.game_id))
                        target_ent = target_res.scalars().first()
                        if target_ent and target_ent.stat_modifier_armor_class is not None:
                            mod = target_ent.stat_modifier_armor_class
                            target_ac += mod
                            ac_reason = f"Base 10 + {mod} Mod"
                    
                    roll = roll_attack(self.avatar, req.hit_stat, target_ac, req.damage_dice)
                    res = AttackResult(
                        attacker_id=req.attacker_id,
                        target_id=req.target_id,
                        hit_roll=roll["hit_roll"],
                        hit_modifier=roll["hit_modifier"],
                        hit_total=roll["hit_total"],
                        target_ac=target_ac,
                        is_hit=roll["is_hit"],
                        damage_dice_str=roll["damage_dice_str"],
                        damage_rolls=roll["damage_rolls"],
                        damage_dice_total=roll["damage_dice_total"],
                        damage_bonus=roll["damage_bonus"],
                        damage_total=roll["damage_total"],
                        reason=req.reason
                    )
                    attack_results.append(res)
                    
                    # Output as system message
                    hit_label = "HIT" if res.is_hit else "MISS"
                    roll_msg = (
                        f"⚔️ **ATTACK**: {res.reason}\n"
                        f"To-Hit: {res.hit_roll} + {res.hit_modifier} = **{res.hit_total}** (vs AC {res.target_ac}, {ac_reason}) -> **{hit_label}**"
                    )
                    if res.is_hit:
                        rolls_str = " + ".join(str(r) for r in res.damage_rolls)
                        bonus_str = f" + {res.damage_bonus}" if res.damage_bonus > 0 else (f" - {abs(res.damage_bonus)}" if res.damage_bonus < 0 else "")
                        roll_msg += f"\nDamage: {res.damage_dice_str} ({rolls_str}{bonus_str}) = **{res.damage_total}** HP dealt to {target_id}."
                        
                        # Apply damage to NPC HP in GameEvent for _apply_game_event to pick up
                        if not game_event.updated_entities:
                            game_event.updated_entities = []
                        
                        # Find current HP
                        current_hp = 50 # Default
                        if "hp" in target_state:
                            current_hp = target_state["hp"]
                        else:
                            # Re-fetch entity to get baseline HP if needed
                            target_res = await self.db.execute(select(WorldEntity).where(WorldEntity.id == target_id, WorldEntity.session_id == self.game_id))
                            target_ent = target_res.scalars().first()
                            if target_ent and target_ent.hp is not None:
                                current_hp = target_ent.hp
                        
                        new_hp = max(0, current_hp - res.damage_total)
                        game_event.updated_entities.append(WorldEntityUpdate(
                            entity_id=target_id,
                            hp=new_hp
                        ))
                    
                    await self._save_chat_message("system", roll_msg)
                    yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': roll_msg})}\n\n"
                
                game_event.attack_results = attack_results

            # 3. Apply Changes
            pre_inventory_ids = {
                item.get("id")
                for item in (self.avatar.inventory or [])
                if isinstance(item, dict) and item.get("id")
            }
            try:
                guardrail_messages = await self._enforce_container_unlock_guardrails(game_event, user_msg)
                for gm in guardrail_messages:
                    await self._save_chat_message("system", gm)
                    yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': gm})}\n\n"

                system_msgs = await self._apply_game_event(game_event)
                for sm in system_msgs:
                    yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': sm})}\n\n"

                if game_event.game_completed:
                    await self._finalize_session("completed", game_event.status_note)
            except GameOverException as goe:
                await self._finalize_session("game_over", str(goe))
                # Ensure the narration knows about the game over
                game_event.game_over = True
                game_event.status_note = str(goe)

        elif run_generator_tool_intent_pass and not handled_generator_confirmation:
            yield f"event: status\ndata: {json.dumps({'content': 'Checking generator tools...'})}\n\n"
            try:
                llm = GameMasterLLM(self.user, provider=small_model_provider, model_category="small")
            except ValueError as e:
                yield f"event: error\ndata: {json.dumps({'detail': str(e)})}\n\n"
                return

            # Provide compact prior chat context so tool parameters can be derived from discussed details.
            history_lines = []
            for msg in history[-12:]:
                role = msg.get("role")
                if role not in ("user", "assistant"):
                    continue
                content = (msg.get("content") or "").strip()
                if not content:
                    continue
                history_lines.append(f"{role.upper()}: {content[:400]}")

            tool_context_block = ""
            if history_lines:
                tool_context_block = (
                    "\n\nRECENT CHAT CONTEXT (use this to infer generation parameters):\n"
                    + "\n".join(history_lines)
                )

            tool_intent_prompt = (
                mechanics_system_prompt
                + "\n\n"
                + prompts.GM_ADVENTURE_GENERATOR_TOOL_INTENT_SUFFIX
                + tool_context_block
            )
            try:
                generator_intent_start = time.perf_counter()
                game_event = await llm.aexecute_complex_task(
                    tool_intent_prompt,
                    user_msg,
                    response_model=AdventureGeneratorToolIntent,
                    model=small_model,
                )
                log_structured_event(
                    "gm.turn.pipeline.pass",
                    adventure_id=self.adventure.id,
                    game_id=self.game_id,
                    operation="chat_turn",
                    phase="generator_tool_intent",
                    duration_ms=round((time.perf_counter() - generator_intent_start) * 1000, 2),
                    model=small_model,
                    provider=small_model_provider,
                )
            except Exception as e:
                user_safe_error = _friendly_llm_error_message(e)
                if user_safe_error:
                    yield f"event: error\ndata: {json.dumps({'detail': user_safe_error})}\n\n"
                    return
                raise

            if (
                not game_event.requested_adventure_generation
                and await self._is_generation_retry_request(user_msg)
            ):
                last_request = self._get_last_ag_generation_request()
                if last_request:
                    if self._get_last_ag_generation_error() == "token_limit":
                        last_request.generate_scene_images = False
                    game_event.requested_adventure_generation = last_request
                    if not game_event.narrative_description:
                        game_event.narrative_description = "Understood. I will retry the last adventure generation now."

            if game_event.requested_adventure_generation:
                self._set_pending_ag_image_confirmation(game_event.requested_adventure_generation)
                confirmation_msg = (
                    "SYSTEM: Before I start generation, please confirm image mode: "
                    "reply with 'yes with images', 'yes without images', or 'cancel'."
                )
                await self._save_chat_message("system", confirmation_msg)
                yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': confirmation_msg})}\n\n"
                game_event.requested_adventure_generation = None
                game_event.narrative_description = "The Architect pauses at the threshold, awaiting your confirmation."

            if (
                game_event.request_available_image_styles
                or game_event.request_available_tones
                or game_event.requested_adventure_generation
            ):
                async for tool_chunk in self._stream_adventure_generator_tools(game_event):
                    yield tool_chunk

        elif run_chat_progression_pass:
            yield f"event: status\ndata: {json.dumps({'content': 'Checking progression...'})}\n\n"
            try:
                llm = GameMasterLLM(self.user, provider=small_model_provider, model_category="small")
            except ValueError as e:
                yield f"event: error\ndata: {json.dumps({'detail': str(e)})}\n\n"
                return

            reduced_quests = self._build_chat_progression_quests()
            reduced_awards = self._build_chat_progression_awards(mechanics_awards)
            reduced_npcs = self._build_chat_progression_npcs(entities)
            reduced_scenes = self._build_chat_progression_scenes(all_scenes)
            reduced_exits = self._build_chat_progression_exits(exits)

            progression_prompt = self._build_chat_rule_pass_prompt(
                quests=reduced_quests,
                awards=reduced_awards,
                npcs=reduced_npcs,
                scenes=reduced_scenes,
                exits=reduced_exits,
            )

            if language:
                progression_prompt += f"\n\nLANGUAGE CONTEXT: Current player language is {language}."

            progression_start = time.perf_counter()
            try:
                progression_intent = await llm.aexecute_complex_task(
                    progression_prompt,
                    user_msg,
                    response_model=AdventureGeneratorToolIntent,
                    model=small_model,
                )
            except Exception as e:
                user_safe_error = _friendly_llm_error_message(e)
                if user_safe_error:
                    yield f"event: error\ndata: {json.dumps({'detail': user_safe_error})}\n\n"
                    return
                raise

            # Guardrail: avoid accidental teleports from hypothetical/planned statements.
            if progression_intent.new_scene_id:
                allowed_open_destinations = {
                    str(ex.get("to_scene_id") or "").strip()
                    for ex in reduced_exits
                    if not bool(ex.get("is_locked")) and str(ex.get("to_scene_id") or "").strip()
                }
                if progression_intent.new_scene_id not in allowed_open_destinations:
                    progression_intent.new_scene_id = None
                    progression_intent.exit_label = None
                elif not await self._is_explicit_scene_transition_request(user_msg):
                    progression_intent.new_scene_id = None
                    progression_intent.exit_label = None

            log_structured_event(
                "gm.turn.pipeline.pass",
                adventure_id=self.adventure.id,
                game_id=self.game_id,
                operation="chat_turn",
                phase="chat_progression",
                duration_ms=round((time.perf_counter() - progression_start) * 1000, 2),
                model=small_model,
                provider=small_model_provider,
                reduced_payload_chars=len(progression_prompt),
                quest_count=len(reduced_quests),
                award_count=len(reduced_awards),
                npc_count=len(reduced_npcs),
                notes_count=min(len(self._get_gm_notes()), GM_NOTES_PROMPT_MAX_ITEMS),
            )

            game_event = self._build_progression_event(progression_intent)

            try:
                guardrail_messages = await self._enforce_container_unlock_guardrails(game_event, user_msg)
                for gm in guardrail_messages:
                    await self._save_chat_message("system", gm)
                    yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': gm})}\n\n"

                system_msgs = await self._apply_game_event(game_event)
                for sm in system_msgs:
                    yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': sm})}\n\n"

                if game_event.game_completed:
                    await self._finalize_session("completed", game_event.status_note)
                elif game_event.game_over:
                    await self._finalize_session("game_over", game_event.status_note or "Game over.")
            except GameOverException as goe:
                await self._finalize_session("game_over", str(goe))
                game_event.game_over = True
                game_event.status_note = str(goe)

        # Pass 2: Narration
        yield f"event: status\ndata: {json.dumps({'content': 'Generating narrative...'})}\n\n"
        try:
            llm = GameMasterLLM(self.user, provider=complex_model_provider, model_category="complex")
        except ValueError as e:
            yield f"event: error\ndata: {json.dumps({'detail': str(e)})}\n\n"
            return
        tts_settings = self.user.tts_settings or {}
        use_vocal_tags = tts_settings.get("use_vocal_tags", True)
        
        narration_prompt = (
            narration_system_prompt + "\n\n" + 
            prompts.GM_NARRATION_TECHNICAL_OUTCOME_PREFIX.format(
                outcome_json=game_event.model_dump_json() if game_event else "{}"
            ) + "\n\n" +
            prompts.GM_NARRATION_MANDATORY_FORMATTING
        )
        
        if use_vocal_tags:
            tts_provider = tts_settings.get("provider", "google")
            narration_prompt += "\n\n" + prompts.get_vocal_direction_prompt(tts_provider)
            # Add a strong reminder at the end if enabled to ensure the LLM doesn't ignore it
            narration_prompt += "\n\nREMINDER: Use emotional vocal tags like [Laughs] or [Sighs] where appropriate to give your narration life."

        scene_changed_this_turn = self.state.current_scene_id != scene_id_before_turn
        if self._is_lookaround_request(user_msg) or scene_changed_this_turn:
            exits_json = await self._build_scene_exits_context_json()
            exit_count = 0
            try:
                parsed_exits = json.loads(exits_json)
                if isinstance(parsed_exits, list):
                    exit_count = len(parsed_exits)
            except Exception:
                exit_count = 0

            sentence_instruction = (
                "Use exactly 1 sentence for the exit paragraph, and do not use contrast/addition connectors like 'on the other side' or 'additionally'."
                if exit_count == 1
                else "Keep it short (max 2 sentences)."
            )
            narration_prompt += (
                "\n\nEXIT DESCRIPTION TASK (MANDATORY): "
                "If exits are available, add exactly one compact paragraph at the end that narratively describes visible exits and where they lead. "
                f"Do not use headers, labels, lists, or bullet points. {sentence_instruction} "
                "If an exit is locked, mention it naturally. Use the same language and tone as the rest of your narration."
                f"\nCURRENT SCENE EXITS: {exits_json}"
            )


        if run_chat_progression_pass:
            narration_prompt += "\n\n" + prompts.GM_CHAT_NARRATION_SUFFIX
            
        if language:
            narration_prompt += f"\n\nREMINDER: Respond in {language.upper()} only."
            
        pass2_start = time.perf_counter()
        logger.debug(f"[Turn {self.game_id}] [Pass 2] Calling complex model: {complex_model} via {complex_model_provider}")
        try:
            stream = await llm.stream_simple_task(
                narration_prompt,
                user_msg,
                complex_model,
            )

            async for chunk in stream:
                delta = chunk.choices[0].delta.content or ""
                if delta:
                    response_text += delta
                    yield f"event: chunk\ndata: {json.dumps({'content': delta})}\n\n"

        except Exception as e:
            user_safe_error = _friendly_llm_error_message(e)
            if user_safe_error:
                yield f"event: error\ndata: {json.dumps({'detail': user_safe_error})}\n\n"
                return
            raise

        try:
            import litellm
            prompt_tokens = litellm.token_counter(model=complex_model, messages=[
                {"role": "system", "content": narration_prompt},
                {"role": "user", "content": user_msg}
            ])
            completion_tokens = litellm.token_counter(model=complex_model, text=response_text)
        except Exception:
            prompt_tokens = int(len(narration_prompt + user_msg) / 4)
            completion_tokens = int(len(response_text) / 4)

        print(
            f"\n>>> [TOKEN USAGE] Phase: narration | Model: {complex_model} | "
            f"Prompt: {prompt_tokens} | Completion: {completion_tokens} | Total: {prompt_tokens + completion_tokens}\n",
            flush=True
        )
        
        pass2_duration = time.perf_counter() - pass2_start
        log_structured_event(
            "gm.turn.pipeline.pass",
            adventure_id=self.adventure.id,
            game_id=self.game_id,
            operation="chat_turn",
            phase="narration",
            duration_ms=round(pass2_duration * 1000, 2),
            model=complex_model,
            provider=complex_model_provider,
        )
        logger.debug(f"[Turn {self.game_id}] [Pass 2] Narration took {pass2_duration:.4f}s")

        log_structured_event(
            "gm.turn.pipeline.cycle_total",
            adventure_id=self.adventure.id,
            game_id=self.game_id,
            operation="chat_turn",
            phase="cycle_total",
            duration_ms=round((time.perf_counter() - cycle_start) * 1000, 2),
        )

        if run_generator_tool_intent_pass and not (response_text or "").strip():
            fallback = "The Architect inclines his head, the Construct awaiting your next directive."
            if game_event and getattr(game_event, "requested_adventure_generation", None):
                tool_results = getattr(game_event, "tool_results", None)
                generation_success = getattr(tool_results, "generation_success", None) if tool_results else None
                if generation_success is True:
                    fallback = "The Architect steps aside as your new world settles into the library archives."
                elif generation_success is False:
                    fallback = "The Architect frowns as unstable code dissipates from the unfinished world."
                else:
                    fallback = "The Architect watches the Construct flare to life as your requested world takes shape."
            elif game_event and (
                getattr(game_event, "request_available_image_styles", False)
                or getattr(game_event, "request_available_tones", False)
            ):
                fallback = "The Architect gestures toward the floating catalogs, inviting your selection."

            response_text = fallback
            yield f"event: chunk\ndata: {json.dumps({'content': fallback})}\n\n"

        # Finalize
        assistant_chat = ChatMessage(session_id=self.state.session_id, role="assistant", content=response_text)
        self.db.add(assistant_chat)
        
        # Add system messages for stat changes and items
        if isinstance(game_event, GameEvent):
            # 1. Protagonist changes
            if game_event.hp_change != 0:
                verb = "gain" if game_event.hp_change > 0 else "lose"
                msg = f"You {verb} {abs(game_event.hp_change)} HP."
                await self._save_chat_message("system", msg)
                yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"
            
            if game_event.stamina_change != 0:
                verb = "gain" if game_event.stamina_change > 0 else "lose"
                msg = f"You {verb} {abs(game_event.stamina_change)} Stamina."
                await self._save_chat_message("system", msg)
                yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"

            if game_event.mana_change != 0:
                verb = "gain" if game_event.mana_change > 0 else "lose"
                msg = f"You {verb} {abs(game_event.mana_change)} Mana."
                await self._save_chat_message("system", msg)
                yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"

            # 2. NPC/Entity changes
            if game_event.updated_entities:
                for update in game_event.updated_entities:
                    eid = update.entity_id
                    # Find name
                    ent_name = "Someone"
                    # Try to find in current entities list (from start of turn)
                    match = next((e for e in entities if e.id == eid), None)
                    if match:
                        ent_name = match.name
                    
                    if update.hp is not None and match and match.hp is not None:
                        diff = update.hp - match.hp
                        if diff != 0:
                            verb = "healed for" if diff > 0 else "takes"
                            msg = f"{ent_name} {verb} {abs(diff)} damage." if diff < 0 else f"{ent_name} {verb} {diff} HP."
                            await self._save_chat_message("system", msg)
                            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"

                    if update.stamina is not None and match and match.stamina is not None:
                        diff = update.stamina - match.stamina
                        if diff != 0:
                            verb = "gains" if diff > 0 else "loses"
                            msg = f"{ent_name} {verb} {abs(diff)} Stamina."
                            await self._save_chat_message("system", msg)
                            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"

                    if update.mana is not None and match and match.mana is not None:
                        diff = update.mana - match.mana
                        if diff != 0:
                            verb = "gains" if diff > 0 else "loses"
                            msg = f"{ent_name} {verb} {abs(diff)} Mana."
                            await self._save_chat_message("system", msg)
                            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"

            # 2b. NPC/Entity movement to different scenes
            if game_event.moved_entities:
                for move in game_event.moved_entities:
                    if not move.to_scene_id:
                        continue
                    eid = move.entity_id
                    ent_name = eid  # fallback: entity id, not the generic "Someone"
                    # Try local entities first, then all entities
                    match = next((e for e in entities if e.id == eid), None)
                    if not match:
                        match = next((e for e in all_entities if e.id == eid), None)
                    if match:
                        ent_name = match.name
                    target_label = move.to_scene_id
                    scene_res = await self.db.execute(
                        select(WorldScene).where(
                            WorldScene.id == move.to_scene_id,
                            WorldScene.session_id == self.game_id
                        )
                    )
                    scene_obj = scene_res.scalars().first()
                    if scene_obj:
                        target_label = scene_obj.label
                    msg = f"{ent_name} moved to {target_label}."
                    await self._save_chat_message("system", msg)
                    yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"

            # 3. Items
            if game_event.new_inventory_items:
                for item in game_event.new_inventory_items:
                    # Only skip if it's a duplicate AND not being removed in the same turn
                    is_replacement = game_event.removed_inventory_item_ids and item.id in game_event.removed_inventory_item_ids
                    if item.id and item.id in pre_inventory_ids and not is_replacement:
                        continue
                        
                    msg_text = f"Added {item.name} to your inventory."
                    await self._save_chat_message("system", msg_text)
                    yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg_text})}\n\n"

            if game_event.updated_inventory_items:
                for update in game_event.updated_inventory_items:
                    # Find old name for the message
                    old_name = update.name
                    match = next(
                        (
                            i
                            for i in (self.avatar.inventory or [])
                            if isinstance(i, dict) and i.get("id") == update.id
                        ),
                        None,
                    )
                    if match:
                        old_name = match.get("name", update.name)
                    
                    msg_text = f"Updated {old_name} in your inventory."
                    if update.name and update.name != old_name:
                        msg_text = f"Your {old_name} is now a {update.name}."
                        
                    await self._save_chat_message("system", msg_text)
                    yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg_text})}\n\n"

            if game_event.spawned_items:
                for item in game_event.spawned_items:
                    msg_text = f"{item.name} appeared in the scene."
                    await self._save_chat_message("system", msg_text)
                    yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg_text})}\n\n"

            if game_event.removed_inventory_item_ids:
                for item_id in game_event.removed_inventory_item_ids:
                    # Resolve item name from pre-turn inventory (where the item actually was)
                    item_name = item_id
                    
                    # 1. Look in avatar's current inventory (which still has items before commit)
                    match = next(
                        (
                            i
                            for i in (self.avatar.inventory or [])
                            if isinstance(i, dict) and i.get("id") == item_id
                        ),
                        None,
                    )
                    if match:
                        item_name = match.get("name", item_id)
                    else:
                        # 2. Fallback: search in template entities if it was a starting object
                        target_res = await self.db.execute(select(WorldEntity).where(WorldEntity.id == item_id, WorldEntity.template_id == self.state.template_id))
                        target_ent = target_res.scalars().first()
                        if target_ent:
                            item_name = target_ent.name
                    
                    msg_text = f"Removed {item_name} from your inventory."
                    await self._save_chat_message("system", msg_text)
                    yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg_text})}\n\n"

        await self.db.commit()

        checkpoint_events = await self._persist_pending_checkpoints()
        if checkpoint_events:
            yield f"event: status\ndata: {json.dumps({'content': 'Saving chronicle...'})}\n\n"
            for checkpoint_event in checkpoint_events:
                yield f"event: checkpoint\ndata: {json.dumps(checkpoint_event)}\n\n"

        map_payload = await self._build_map_payload()
        
        # Fetch adventure for cover image fallback
        adv_res = await self.db.execute(select(AdventureTemplate).where(AdventureTemplate.id == self.state.template_id))
        adventure = adv_res.scalars().first()

        final_data = jsonable_encoder({
            'map_data': map_payload,
            'nodes': await AdventureLogic.get_all_scene_metadata(self.db, self.state.template_id, session_id=self.state.session_id),
            'npc_metadata': await AdventureLogic.get_npc_metadata(self.db, self.state.template_id, session_id=self.state.session_id),
            'image_url': await AdventureLogic.resolve_scene_image(self.db, self.state, self.state.current_scene_id),
            'adventure_image': AdventureLogic.resolve_session_asset(self.state, "cover", adventure.image_url if adventure else None),
            'sheet': await AdventureLogic.build_sheet_snapshot(self.avatar, self.state, self.db), 
            'entities': await AdventureLogic.build_session_entities(self.db, self.state),
            'combat': AdventureLogic.get_combat_snapshot(self.state),
            'quests': self.state.quests,
            'awards': await self._build_awards_payload(adventure),
            **self._build_prompt_suggestions_payload(),
            **self._build_terminal_flags_payload(),
            'status': 'success'
        })
        yield f"event: final\ndata: {json.dumps(final_data)}\n\n"

    async def _build_map_payload(self) -> dict:
        """Helper to build the augmented map payload for the frontend."""
        world_map = await AdventureLogic.get_or_create_map(self.db, self.state.template_id)
        if not world_map:
            return {"nodes": {}, "edges": [], "current_scene_id": None}

        map_dict = MapEngine.to_dict(world_map)
        map_dict["current_scene_id"] = MapEngine._safe_id(self.state.current_scene_id)
        
        # Augment with adjacent unvisited scenes
        # Fetch exits for this session or template
        exit_query = select(WorldExit).where(
            or_(
                WorldExit.session_id == self.state.session_id,
                WorldExit.template_id == self.state.template_id
            )
        )
        exits_res = await self.db.execute(exit_query)
        exits = list(exits_res.scalars().all())
        map_dict = MapEngine.augment_map_data(map_dict, exits, self.state.current_scene_id)

        return map_dict

    async def _build_awards_payload(self, adventure: AdventureTemplate | None) -> list[dict]:
        """Helper to build the awards payload with earned status."""
        if not self.user:
            return []
            
        awards_list = (adventure.awards if adventure else (AdventureLogic.extract_manifest_snapshot(self.state).get("adventure") or {}).get("awards")) or []
        
        return [
            {
                **aw,
                "is_earned": any(
                    ea.get("key") == aw.get("key")
                    and (
                        ea.get("template_id") == (adventure.id if adventure else self.state.template_id)
                        or ea.get("adventure_id") == (adventure.id if adventure else self.state.template_id)
                    )
                    for ea in (self.user.earned_awards or [])
                ),
            }
            for aw in awards_list
        ]

    async def _apply_game_event(self, event: GameEvent) -> list[str]:
        """Applies technical mutations from a GameEvent to the database and session state. Returns messages for the UI."""
        system_messages: list[str] = []
        existing_item_ids = await self._collect_existing_item_ids()

        def _is_consumable(item: Any) -> bool:
            return str(getattr(item, "item_type", "") or "").upper() == "CONSUMABLE"

        def _allocate_copied_item_id(source_id: str | None) -> str:
            base = re.sub(r"[^A-Za-z0-9_\-]", "_", source_id or "CONSUMABLE")[:40] or "CONSUMABLE"
            counter = 1
            candidate = f"{base}_COPY_{counter}"
            while candidate in existing_item_ids:
                counter += 1
                candidate = f"{base}_COPY_{counter}"
            return candidate
        
        # If we are removing items in this event, they don't count as "existing" for duplicate checks
        # if the LLM wants to replace them with an updated version using the same ID.
        if event.removed_inventory_item_ids:
            logger.info("[Turn %s] Removing from duplicate check: %s", self.game_id, event.removed_inventory_item_ids)
            existing_item_ids -= set(event.removed_inventory_item_ids)

        logger.info("[Turn %s] Existing inventory IDs after removals: %s", self.game_id, list(existing_item_ids))

        if event.new_inventory_items:
            filtered_inventory_items = []
            for item in event.new_inventory_items:
                match = (
                    next(
                        (
                            i
                            for i in (self.avatar.inventory or [])
                            if isinstance(i, dict) and i.get("id") == item.id
                        ),
                        None,
                    )
                    if item.id
                    else None
                )

                if item.id and item.id in existing_item_ids and _is_consumable(item):
                    if not item.image_url and isinstance(match, dict) and match.get("image_url"):
                        item.image_url = match.get("image_url")
                    source_id = item.id
                    item.id = _allocate_copied_item_id(source_id)
                    logger.info(
                        "[Turn %s] Cloning duplicate consumable %s as %s",
                        self.game_id,
                        source_id,
                        item.id,
                    )

                if not item.image_url:
                    try:
                        from backend.engine.media_engine import MediaEngine
                        from backend.core.config import settings
                        import os
                        import uuid
                        
                        item_type = item.item_type or "PICKABLE"
                        safe_id = re.sub(r"[^A-Za-z0-9_\-]", "_", item.id or f"LOOT_{uuid.uuid4().hex[:8]}")[:50]
                        safe_adventure_id = _sanitize_path_component(self.adventure.id) or "adventure"
                        target_dir = _ensure_within_data_dir(
                            os.path.join(settings.DATA_DIR, "adventures", "library", safe_adventure_id, "entities")
                        )
                        item.image_url = await MediaEngine.generate_placeholder(
                            adventure_id=self.adventure.id,
                            entity_id=safe_id,
                            target_dir=target_dir,
                            category=f"ITEM_{item_type.upper()}"
                        )
                    except Exception as e:
                        logger.error("Failed to generate new inventory item placeholder: %s", e)

                if item.id and item.id in existing_item_ids:
                    # Check if it's a true duplicate (same name)
                    if match:
                        if match.get("name") == item.name:
                            logger.info(
                                "[Turn %s] Skipping true duplicate inventory item id: %s",
                                self.game_id,
                                item.id,
                            )
                            continue
                        else:
                            logger.info(
                                "[Turn %s] Permitting implied update for item id %s (Name: %s -> %s)",
                                self.game_id,
                                item.id,
                                match.get("name"),
                                item.name
                            )
                    else:
                        logger.info(
                            "[Turn %s] Skipping duplicate inventory item id %s (exists in session but not in inventory)",
                            self.game_id,
                            item.id,
                        )
                        continue
                
                filtered_inventory_items.append(item)
                if item.id:
                    existing_item_ids.add(item.id)
            event.new_inventory_items = filtered_inventory_items

        if event.spawned_items:
            filtered_spawned_items = []
            for item in event.spawned_items:
                match = (
                    next(
                        (
                            i
                            for i in (self.avatar.inventory or [])
                            if isinstance(i, dict) and i.get("id") == item.id
                        ),
                        None,
                    )
                    if item.id
                    else None
                )
                # Allow if it's a replacement for an item being removed
                is_replacement = event.removed_inventory_item_ids and item.id in event.removed_inventory_item_ids
                if item.id and item.id in existing_item_ids and not is_replacement and _is_consumable(item):
                    if not item.image_url and isinstance(match, dict) and match.get("image_url"):
                        item.image_url = match.get("image_url")
                    source_id = item.id
                    item.id = _allocate_copied_item_id(source_id)
                    logger.info(
                        "[Turn %s] Cloning duplicate spawned consumable %s as %s",
                        self.game_id,
                        source_id,
                        item.id,
                    )

                if item.id and item.id in existing_item_ids and not is_replacement:
                     # Check if it's a true duplicate (same name)
                    if match and match.get("name") == item.name:
                        logger.info(
                            "[Turn %s] Skipping true duplicate spawned item id: %s",
                            self.game_id,
                            item.id,
                        )
                        continue
                
                filtered_spawned_items.append(item)
                if item.id:
                    existing_item_ids.add(item.id)
            event.spawned_items = filtered_spawned_items

        if event.new_status_effects:
            for effect in event.new_status_effects:
                msg = f"✨ You are now: {effect}"
                await self._save_chat_message("system", msg)
                system_messages.append(msg)

        RuleEngine.apply_event(self.avatar, event)
        
        state_dirty = False
        if event.new_scene_id and event.new_scene_id != self.state.current_scene_id:
            # Enforce that the target scene is adjacent (connected by a WorldExit from the current scene)
            exit_res = await self.db.execute(
                select(WorldExit).where(
                    WorldExit.session_id == self.state.session_id,
                    WorldExit.from_scene_id == self.state.current_scene_id,
                    WorldExit.to_scene_id == event.new_scene_id,
                )
            )
            valid_exit = exit_res.scalars().first()
            if not valid_exit:
                blocked_msg = f"Movement blocked: The destination '{event.new_scene_id}' is not adjacent to your current location."
                await self._save_chat_message("system", blocked_msg)
                system_messages.append(blocked_msg)

                logger.warning(
                    f"[Turn {self.game_id}] Blocked invalid/non-adjacent scene transition: "
                    f"{self.state.current_scene_id} -> {event.new_scene_id}"
                )
                event.new_scene_id = None
                event.scene_label = None
                event.exit_label = None
            else:
                old_scene_id = self.state.current_scene_id
                self.state.current_scene_id = event.new_scene_id
                state_dirty = True
                
                # Map Update
                try:
                    world_map = await AdventureLogic.get_or_create_map(self.db, self.state.template_id)
                    # 1. Register exit between scenes
                    MapEngine.register_exit(world_map, old_scene_id, event.new_scene_id, exit_label=event.exit_label or "")
                    # 2. Register visit to the new scene
                    # Use session snapshot for scene data
                    scene_res = await self.db.execute(
                        select(WorldScene).where(
                            WorldScene.id == event.new_scene_id,
                            WorldScene.session_id == self.state.session_id,
                        )
                    )
                    new_scene_db = scene_res.scalars().first()
                    
                    # Add system message for scene change
                    scene_name = new_scene_db.label if new_scene_db else (event.scene_label or "a new location")
                    msg = f"📍 You have entered: {scene_name}"
                    await self._save_chat_message("system", msg)
                    system_messages.append(msg)
                    self._queue_checkpoint(CHECKPOINT_REASON_SCENE_CHANGE, scene_label=scene_name)

                    MapEngine.register_visit(
                        world_map, 
                        event.new_scene_id, 
                        label=new_scene_db.label if new_scene_db else event.scene_label,
                        description=new_scene_db.description if new_scene_db else None,
                        image_url=new_scene_db.image_url if new_scene_db else None
                    )
                except Exception as e:
                    logger.error(f"Map update failed during turn: {e}")
            
        # Entity State Overrides (Movement, Stats, Visibility)
        states = dict(self.state.entity_states or {})
        
        if event.moved_entities:
            for move in event.moved_entities:
                eid = move.entity_id
                if eid not in states:
                    states[eid] = {}
                if move.to_scene_id: 
                    states[eid]["current_scene_id"] = move.to_scene_id
                    # If moving to a new scene, clear spatial position unless a new one is provided
                    if not move.to_spatial_position:
                        states[eid]["spatial_position"] = None
                    
                    # Emit system message for NPC movement
                    ent_name = eid
                    ent_res = await self.db.execute(
                        select(WorldEntity).where(
                            WorldEntity.id == eid,
                            WorldEntity.session_id == self.game_id
                        )
                    )
                    ent_obj = ent_res.scalars().first()
                    if ent_obj:
                        ent_name = ent_obj.name
                    scene_label = move.to_scene_id
                    scene_res = await self.db.execute(
                        select(WorldScene).where(
                            WorldScene.id == move.to_scene_id,
                            WorldScene.session_id == self.game_id
                        )
                    )
                    scene_obj = scene_res.scalars().first()
                    if scene_obj:
                        scene_label = scene_obj.label
                    msg = f"{ent_name} moved to {scene_label}."
                    await self._save_chat_message("system", msg)
                    system_messages.append(msg)
                    
                if move.to_spatial_position: 
                    states[eid]["spatial_position"] = move.to_spatial_position
                state_dirty = True

        if event.updated_entities:
            for update in event.updated_entities:
                eid = update.entity_id
                ent_obj = None
                if eid not in states:
                    states[eid] = {}
                if update.name is not None:
                    states[eid]["name"] = update.name
                if update.description is not None:
                    states[eid]["description"] = update.description
                if update.spatial_position is not None:
                    states[eid]["spatial_position"] = update.spatial_position
                if update.is_hidden is not None:
                    states[eid]["is_hidden"] = update.is_hidden
                if update.hp is not None:
                    states[eid]["hp"] = update.hp
                if update.mana is not None:
                    states[eid]["mana"] = update.mana
                if update.stamina is not None:
                    states[eid]["stamina"] = update.stamina
                if update.is_attackable is not None:
                    states[eid]["is_attackable"] = update.is_attackable
                if update.is_killable is not None:
                    states[eid]["is_killable"] = update.is_killable
                if update.is_defeated is not None:
                    was_defeated = self.state.entity_states.get(eid, {}).get("is_defeated", False)
                    if not was_defeated and update.is_defeated is True:
                        ent_res = await self.db.execute(
                            select(WorldEntity).where(
                                WorldEntity.id == eid,
                                WorldEntity.session_id == self.game_id,
                            )
                        )
                        ent_obj = ent_res.scalars().first()
                        if ent_obj and ent_obj.entity_type == "NPC":
                            xp_gained = self._award_combat_victory_xp(ent_obj)
                            msg = f"Defeated {ent_obj.name}!"
                            xp_msg = f"you gained {xp_gained} XP"
                            await self._save_chat_message("system", msg)
                            await self._save_chat_message("system", xp_msg)
                            system_messages.append(msg)
                            system_messages.append(xp_msg)
                    states[eid]["is_defeated"] = update.is_defeated
                if update.locked is not None:
                    was_locked = self.state.entity_states.get(eid, {}).get("locked")
                    if was_locked is None:
                        ent_res = await self.db.execute(
                            select(WorldEntity).where(
                                WorldEntity.id == eid,
                                WorldEntity.session_id == self.game_id,
                            )
                        )
                        ent_obj = ent_res.scalars().first()
                        if ent_obj:
                            metadata_json = dict(ent_obj.metadata_json or {})
                            was_locked = bool(metadata_json.get("code_to_unlock") or metadata_json.get("item_to_unlock"))
                    
                    if was_locked and update.locked is False:
                        if ent_obj is None:
                            ent_res = await self.db.execute(
                                select(WorldEntity).where(
                                    WorldEntity.id == eid,
                                    WorldEntity.session_id == self.game_id,
                                )
                            )
                            ent_obj = ent_res.scalars().first()
                        
                        if ent_obj and ent_obj.entity_type == "OBJECT" and str(ent_obj.item_type or "").upper() == "CONTAINER":
                            metadata_json = dict(ent_obj.metadata_json or {})
                            code_to_unlock = str(metadata_json.get("code_to_unlock") or "").strip()
                            if code_to_unlock:
                                xp_reward = metadata_json.get("exp_reward") or metadata_json.get("xp_reward") or 100
                                self.avatar.exp = (self.avatar.exp or 0) + xp_reward
                                msg = f"Unlocked {ent_obj.name} with the correct code!"
                                xp_msg = f"you gained {xp_reward} XP"
                                await self._save_chat_message("system", msg)
                                await self._save_chat_message("system", xp_msg)
                                system_messages.append(msg)
                                system_messages.append(xp_msg)
                    states[eid]["locked"] = update.locked
                if update.inventory is not None: 
                    states[eid]["inventory"] = [i.model_dump(exclude_none=True) for i in update.inventory]
                state_dirty = True
        
        if event.deleted_entities:
            for eid in event.deleted_entities:
                if eid not in states:
                    states[eid] = {}
                states[eid]["is_hidden"] = True
                state_dirty = True
        
        if event.new_inventory_items:
            for item in event.new_inventory_items:
                if item.id:
                    if item.id not in states:
                        states[item.id] = {}
                    states[item.id]["is_in_inventory"] = True
                    state_dirty = True

        if event.spawned_items:
            for item in event.spawned_items:
                await self._spawn_scene_item(item.model_dump(exclude_none=True))
            state_dirty = True

        if event.remember_notes or event.forget_notes or event.clear_notes:
            self._apply_gm_notes_update(event.remember_notes, event.forget_notes, bool(event.clear_notes))

        # Quest Updates
        newly_completed_quests: list[dict] = []
        if event.completed_quest_ids:
            new_quests = deepcopy(self.state.quests or [])
            modified = False
            for qid in event.completed_quest_ids:
                for q in new_quests:
                    if q.get("id") == qid and q.get("status") != "completed":
                        q["status"] = "completed"
                        newly_completed_quests.append(q)
                        modified = True
            
            if modified:
                self.state.quests = new_quests
                state_dirty = True

        if event.earned_award_keys:
            now = datetime.utcnow().isoformat()
            award_defs = {
                (aw.get("key") or ""): aw
                for aw in (self.adventure.awards or [])
                if aw.get("key")
            }
            user_awards = list(self.user.earned_awards or [])
            modified = False
            for key in event.earned_award_keys:
                if not key:
                    continue
                already_earned = any(
                    ea.get("key") == key
                    and (ea.get("template_id") == self.adventure.id or ea.get("adventure_id") == self.adventure.id)
                    for ea in user_awards
                )
                if already_earned:
                    continue

                aw = award_defs.get(key)
                if not aw:
                    logger.warning("[Turn %s] GM tried to grant non-existent award: %s", self.game_id, key)
                    continue

                user_awards.append(
                    {
                        "key": key,
                        "title": aw.get("title") or key,
                        "description": aw.get("description"),
                        "tier": aw.get("tier"),
                        "template_id": self.adventure.id,
                        "adventure_id": self.adventure.id,
                        "adventure_title": self.adventure.title,
                        "session_id": self.state.session_id,
                        "earned_at": now,
                    }
                )
                award_title = aw.get("title") or key
                msg = f"🏆 Award Achievement: {award_title}"
                await self._save_chat_message("system", msg)
                system_messages.append(msg)
                modified = True

            if modified:
                self.user.earned_awards = user_awards
                flag_modified(self.user, "earned_awards")
                self._queue_checkpoint(CHECKPOINT_REASON_AWARD_GRANTED)

        # Deterministic Quest Sync (Post-LLM check)
        det_completed = QuestManager.evaluate_quests(self.avatar, self.state)
        if det_completed:
            new_quests = deepcopy(self.state.quests or [])
            modified = False
            for qid in det_completed:
                for q in new_quests:
                    if q.get("id") == qid and q.get("status") != "completed":
                        q["status"] = "completed"
                        if not any(nq.get("id") == qid for nq in newly_completed_quests):
                            newly_completed_quests.append(q)
                        logger.info("[Turn %s] Deterministic Quest Completion: %s", self.game_id, qid)
                        modified = True
            if modified:
                self.state.quests = new_quests
                state_dirty = True

        if newly_completed_quests:
            self._queue_checkpoint(CHECKPOINT_REASON_QUEST_UPDATE)
            # Emit one system entry per newly completed quest so players get explicit feedback.
            for q in newly_completed_quests:
                quest_title = q.get("title") or q.get("id")
                xp_reward = int(q.get("exp_reward") or 0)
                msg = f"Quest completed: {quest_title}"
                self.db.add(
                    ChatMessage(
                        session_id=self.state.session_id,
                        role="system",
                        content=msg,
                    )
                )
                system_messages.append(msg)
                
                if xp_reward > 0:
                    self.avatar.exp = (self.avatar.exp or 0) + xp_reward
                    xp_msg = f"you gained {xp_reward} XP"
                    self.db.add(
                        ChatMessage(
                            session_id=self.state.session_id,
                            role="system",
                            content=xp_msg,
                        )
                    )
                    system_messages.append(xp_msg)

        # RPG Completion Logic: Check if all main quests are finished
        if state_dirty:
            all_main_done = True
            main_quest_exists = False
            for q in (self.state.quests or []):
                if q.get("is_main"):
                    main_quest_exists = True
                    if q.get("status") != "completed":
                        all_main_done = False
                        break
            
            if main_quest_exists and all_main_done:
                event.game_completed = True
                if not event.status_note:
                    event.status_note = "Congratulations! You have completed all main objectives."

        # Process Explicit Map Updates (Exits)
        if event.updated_exits:
            try:
                world_map = await AdventureLogic.get_or_create_map(self.db, self.state.template_id)
                for up_exit in event.updated_exits:
                    MapEngine.register_exit(
                        world_map, 
                        up_exit.from_scene_id, 
                        up_exit.to_scene_id, 
                        is_locked=up_exit.is_locked
                    )
            except Exception as e:
                logger.error(f"Manual map exit update failed: {e}")

        # Auto-cleanup: remove items from NPC inventories if they are now in the scene or player inventory
        player_item_ids = {
            item.get("id")
            for item in (self.avatar.inventory or [])
            if isinstance(item, dict) and item.get("id")
        }
        obj_res = await self.db.execute(
            select(WorldEntity).where(
                WorldEntity.session_id == self.game_id,
                WorldEntity.entity_type == "OBJECT"
            )
        )
        all_objs = obj_res.scalars().all()
        spawned_or_player_ids = set(player_item_ids)
        for obj in all_objs:
            is_in_inv = states.get(obj.id, {}).get("is_in_inventory", obj.is_in_inventory)
            if not is_in_inv:
                # Only add objects that are in the scene (not in any inventory).
                # Objects with is_in_inventory=True may belong to NPC inventories and
                # must NOT be added here, otherwise the cleanup loop below would
                # incorrectly strip them from every NPC's inventory.
                spawned_or_player_ids.add(obj.id)

        npc_res = await self.db.execute(
            select(WorldEntity).where(
                WorldEntity.session_id == self.game_id,
                WorldEntity.entity_type == "NPC"
            )
        )
        all_npcs = npc_res.scalars().all()
        for npc in all_npcs:
            npc_inv = states.get(npc.id, {}).get("inventory", npc.inventory)
            if npc_inv and isinstance(npc_inv, list):
                cleaned_inv = []
                npc_inv_modified = False
                for item in npc_inv:
                    if isinstance(item, dict):
                        item_id = item.get("id")
                        if item_id and item_id in spawned_or_player_ids:
                            logger.info(
                                "[Turn %s] Removing item %s from NPC %s inventory during auto-sync cleanup.",
                                self.game_id,
                                item_id,
                                npc.id
                            )
                            npc_inv_modified = True
                            continue
                    cleaned_inv.append(item)
                
                if npc_inv_modified:
                    if npc.id not in states:
                        states[npc.id] = {}
                    states[npc.id]["inventory"] = cleaned_inv
                    state_dirty = True

        if state_dirty:
            self.state.entity_states = states
            flag_modified(self.state, "entity_states")
            
        await self._apply_adventure_generator_tools(event)
        await self.db.flush()
        return system_messages

    async def _emit_system_message(
        self,
        message: str,
        stream_callback: Callable[[str], Awaitable[None] | None] = None,
    ) -> None:
        """Persist a system message and optionally stream it via callback."""
        await self._save_chat_message("system", message)
        await self.db.flush()
        if stream_callback:
            await stream_callback(message)

    def _get_pending_ag_image_confirmation(self) -> dict[str, Any] | None:
        exit_states = dict(self.state.exit_states or {})
        pending = exit_states.get(AG_IMAGE_CONFIRMATION_STATE_KEY)
        if not isinstance(pending, dict):
            return None
        if not isinstance(pending.get("request"), dict):
            return None
        return pending

    def _set_pending_ag_image_confirmation(self, request: AdventureGenerationRequest) -> None:
        exit_states = dict(self.state.exit_states or {})
        exit_states[AG_IMAGE_CONFIRMATION_STATE_KEY] = {
            "request_id": str(uuid.uuid4()),
            "request": request.model_dump(),
        }
        self.state.exit_states = exit_states
        flag_modified(self.state, "exit_states")

    def _clear_pending_ag_image_confirmation(self) -> None:
        exit_states = dict(self.state.exit_states or {})
        if AG_IMAGE_CONFIRMATION_STATE_KEY in exit_states:
            exit_states.pop(AG_IMAGE_CONFIRMATION_STATE_KEY, None)
            self.state.exit_states = exit_states
            flag_modified(self.state, "exit_states")

    async def _classify_short_intent(self, user_msg: str, system_prompt: str, phase: str) -> dict[str, Any] | None:
        """Run a tiny intent classification call and parse a strict JSON object response."""
        text = (user_msg or "").strip()
        if not text:
            return None

        llm_settings = self.user.llm_settings or {}
        small_model_provider = (
            llm_settings.get("small_model_provider")
            or llm_settings.get("complex_model_provider")
            or llm_settings.get("preferred_provider")
            or "openai"
        )
        small_model = llm_settings.get("small_model") or "gpt-4o-mini"

        try:
            llm = GameMasterLLM(self.user, provider=small_model_provider, model_category="small")
            raw = await llm.aexecute_simple_task(
                system_prompt,
                text,
                small_model,
                adventure_id=self.adventure.id,
                game_id=self.game_id,
                operation="chat_turn",
                phase=phase,
            )
            parsed = self._parse_json_object(raw)
            return parsed if isinstance(parsed, dict) else None
        except Exception as exc:
            logger.debug("[Turn %s] Intent classifier skipped (%s): %s", self.game_id, phase, exc)
            return None

    async def _parse_ag_image_confirmation_decision(self, user_msg: str) -> str:
        text = (user_msg or "").strip().lower()
        if not text:
            return "unknown"

        intent_prompt = (
            "Classify the user's response to an image-mode confirmation question. "
            "Return ONLY strict JSON with schema: {\"decision\":\"with_images\"|\"without_images\"|\"cancel\"|\"unknown\"}."
        )
        parsed = await self._classify_short_intent(user_msg, intent_prompt, "ag_image_confirmation_intent")
        decision = str((parsed or {}).get("decision") or "").strip().lower()
        if decision in {"with_images", "without_images", "cancel", "unknown"}:
            return decision

        without_images_patterns = [
            r"\bohne\b",
            r"\bwithout\b",
            r"\bno images?\b",
            r"\bkeine bilder\b",
            r"\bohne bilder?\b",
        ]
        cancel_patterns = [
            r"\bcancel\b",
            r"\babbrechen\b",
            r"\bstop\b",
            r"\bstopp\b",
            r"^nein$",
            r"^no$",
        ]
        with_images_patterns = [
            r"\bja\b",
            r"\byes\b",
            r"\bwith images?\b",
            r"\bmit bilder?\b",
            r"\bmit bild\b",
        ]

        if any(re.search(p, text) for p in without_images_patterns):
            return "without_images"
        if any(re.search(p, text) for p in cancel_patterns):
            return "cancel"
        if any(re.search(p, text) for p in with_images_patterns):
            return "with_images"
        return "unknown"

    async def _is_generation_retry_request(self, user_msg: str) -> bool:
        text = (user_msg or "").strip().lower()
        if not text:
            return False

        intent_prompt = (
            "Determine if the user asks to retry the last generation attempt. "
            "Return ONLY strict JSON with schema: {\"retry\": true|false}."
        )
        parsed = await self._classify_short_intent(user_msg, intent_prompt, "ag_retry_intent")
        retry_val = (parsed or {}).get("retry")
        if isinstance(retry_val, bool):
            return retry_val

        retry_patterns = (
            r"\bnochmal\b",
            r"\bnoch einmal\b",
            r"\berneut\b",
            r"\bwieder\b",
            r"\bagain\b",
            r"\bretry\b",
            r"\btry again\b",
            r"\bplease retry\b",
        )
        return any(re.search(p, text) for p in retry_patterns)

    async def _is_explicit_scene_transition_request(self, user_msg: str) -> bool:
        text = (user_msg or "").strip().lower()
        if not text:
            return False

        intent_prompt = (
            "Decide whether the user is explicitly requesting immediate physical movement to another scene now "
            "(not hypothetical/planning talk). "
            "Return ONLY strict JSON with schema: {\"explicit_transition\": true|false}."
        )
        parsed = await self._classify_short_intent(user_msg, intent_prompt, "scene_transition_intent")
        transition_val = (parsed or {}).get("explicit_transition")
        if isinstance(transition_val, bool):
            return transition_val

        # Ignore hypothetical/planning phrasing that should not immediately move the player.
        hypothetical_patterns = (
            r"\bif\b",
            r"\bwould\b",
            r"\bcould\b",
            r"\bmight\b",
            r"\bmaybe\b",
            r"\bplan\b",
            r"\bint(en)?d\b",
            r"\bwenn\b",
            r"\bfalls\b",
            r"\bvielleicht\b",
            r"\bwürde\b",
            r"\bkönnte\b",
        )
        if any(re.search(p, text) for p in hypothetical_patterns):
            return False

        movement_patterns = (
            r"\b(go|going|move|moving|walk|walking|run|running|head|enter|proceed|travel|leave)\b",
            r"\b(go to|walk to|move to|head to|enter the|step into)\b",
            r"\b(gehe|geh|laufe|renne|betrete|bewege|reise|verlasse)\b",
            r"\b(gehe in|gehe zu|betrete den|betrete die|ins|in den|in die)\b",
        )
        return any(re.search(p, text) for p in movement_patterns)

    def _set_last_ag_generation_request(self, request: AdventureGenerationRequest) -> None:
        exit_states = dict(self.state.exit_states or {})
        exit_states[AG_LAST_REQUEST_STATE_KEY] = request.model_dump()
        self.state.exit_states = exit_states
        flag_modified(self.state, "exit_states")

    def _get_last_ag_generation_request(self) -> AdventureGenerationRequest | None:
        exit_states = dict(self.state.exit_states or {})
        raw = exit_states.get(AG_LAST_REQUEST_STATE_KEY)
        if not isinstance(raw, dict):
            return None
        try:
            return AdventureGenerationRequest.model_validate(raw)
        except Exception:
            return None

    def _set_last_ag_generation_error(self, error_type: str | None) -> None:
        exit_states = dict(self.state.exit_states or {})
        if error_type:
            exit_states[AG_LAST_ERROR_STATE_KEY] = error_type
        else:
            exit_states.pop(AG_LAST_ERROR_STATE_KEY, None)
        self.state.exit_states = exit_states
        flag_modified(self.state, "exit_states")

    def _get_last_ag_generation_error(self) -> str | None:
        exit_states = dict(self.state.exit_states or {})
        value = exit_states.get(AG_LAST_ERROR_STATE_KEY)
        return value if isinstance(value, str) and value else None

    async def _stream_adventure_generator_tools(self, event) -> AsyncGenerator[str, None]:
        progress_queue: asyncio.Queue[str] = asyncio.Queue()

        async def _stream_progress_message(message: str) -> None:
            await progress_queue.put(message)

        tool_task = asyncio.create_task(
            self._apply_adventure_generator_tools(
                event,
                stream_callback=_stream_progress_message,
            )
        )

        while True:
            try:
                msg = await asyncio.wait_for(progress_queue.get(), timeout=0.1)
                yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"
            except asyncio.TimeoutError:
                if tool_task.done():
                    break

        await tool_task
        while not progress_queue.empty():
            msg = progress_queue.get_nowait()
            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"

    async def _apply_adventure_generator_tools(
        self,
        event,
        stream_callback: Callable[[str], Awaitable[None] | None] = None,
    ) -> None:
        """Executes adventure-generator tool requests from a structured event/intent model."""
        if not self.adventure.is_adventure_generator:
            return

        if event.request_available_image_styles:
            styles = await AdventureGeneratorService.get_available_image_styles(self.user)
            if not event.tool_results:
                event.tool_results = ToolResults()
            event.tool_results.available_image_styles = styles

            msg = f"SYSTEM: Available Image Styles: {', '.join(styles)}"
            await self._emit_system_message(msg, stream_callback=stream_callback)

        if event.request_available_tones:
            tones = await AdventureGeneratorService.get_available_tones(self.user)
            if not event.tool_results:
                event.tool_results = ToolResults()
            event.tool_results.available_tones = tones

            msg = f"SYSTEM: Available Tones: {', '.join(tones)}"
            await self._emit_system_message(msg, stream_callback=stream_callback)

        if event.requested_adventure_generation:
            self._set_last_ag_generation_request(event.requested_adventure_generation)

            async def _post_generation_system_message(status: str) -> None:
                msg = f"SYSTEM: Adventure Generator: {status}"
                await self._emit_system_message(msg, stream_callback=stream_callback)

            try:
                await _post_generation_system_message(
                    f"Preparing generation for '{event.requested_adventure_generation.title}'..."
                )

                new_adv_id = await AdventureGeneratorService.generate_adventure(
                    self.db,
                    self.user,
                    event.requested_adventure_generation,
                    progress_callback=_post_generation_system_message,
                )
                if not event.tool_results:
                    event.tool_results = ToolResults()
                event.tool_results.generation_success = True
                event.tool_results.new_adventure_id = new_adv_id
                self._set_last_ag_generation_error(None)

                await _post_generation_system_message("Generation finished successfully.")

                msg = f"SYSTEM: Adventure '{event.requested_adventure_generation.title}' generated successfully and added to library (ID: {new_adv_id})."
                await self._emit_system_message(msg, stream_callback=stream_callback)
            except Exception as e:
                if not event.tool_results:
                    event.tool_results = ToolResults()
                event.tool_results.generation_success = False
                event.tool_results.generation_error = str(e)
                self._set_last_ag_generation_error(_llm_error_type(e))

                await _post_generation_system_message("Generation aborted due to an error.")

                user_safe_error = _friendly_llm_error_message(e)
                if user_safe_error:
                    msg = f"SYSTEM: {user_safe_error}"
                else:
                    msg = f"SYSTEM ERROR: Adventure generation failed: {e}"
                await self._emit_system_message(msg, stream_callback=stream_callback)

    async def _generate_terminal_epilogue_text(self, language: str | None = None) -> str:
        status = self.state.session.status if self.state and self.state.session else None
        status_note = self.state.session.status_note if self.state and self.state.session else None

        quests = list(self.state.quests or []) if self.state else []
        main_quests = [q for q in quests if q.get("is_main")]
        completed_main = [q for q in main_quests if q.get("status") == "completed"]
        side_quests = [q for q in quests if not q.get("is_main")]
        completed_side = [q for q in side_quests if q.get("status") == "completed"]

        adventure_awards = list(self.adventure.awards or []) if self.adventure else []
        earned_awards = list(self.user.earned_awards or []) if self.user else []
        earned_for_adventure = [
            ea
            for ea in earned_awards
            if (ea.get("template_id") == self.adventure.id or ea.get("adventure_id") == self.adventure.id)
        ] if self.adventure else []

        report_payload = {
            "session_id": self.game_id,
            "adventure_title": self.adventure.title if self.adventure else "Adventure",
            "status": status,
            "status_note": status_note,
            "quests": {
                "main_completed": len(completed_main),
                "main_total": len(main_quests),
                "side_completed": len(completed_side),
                "side_total": len(side_quests),
            },
            "awards": {
                "earned": len(earned_for_adventure),
                "total": len(adventure_awards),
            },
            "exp": self.avatar.exp if self.avatar else 0,
            "in_game_time_minutes": self.state.in_game_time if self.state else 0,
        }

        llm_settings = self.user.llm_settings or {}
        model_provider = (
            llm_settings.get("complex_model_provider")
            or llm_settings.get("small_model_provider")
            or llm_settings.get("preferred_provider")
            or "openai"
        )
        model_name = llm_settings.get("complex_model") or llm_settings.get("small_model") or "gpt-4o"

        if status == "completed":
            system_prompt = (
                "You are the Game Master. Write a warm in-world closing message and final report after main quest completion. "
                "Congratulate the player, summarize their journey in 4-7 sentences, mention quest and award progress, "
                "and explicitly state they can keep playing to complete side quests and earn remaining awards. "
                "No bullet points, no markdown headings, no command lists."
            )
            fallback = (
                "The Game Master smiles with quiet pride. Your main quest is complete, and your name now carries weight in this tale. "
                "Final report: your core objectives are fulfilled, but there are still side stories to uncover and awards left to claim. "
                "You may leave this chronicle now, or remain in the world to perfect your legacy."
            )
        else:
            system_prompt = (
                "You are the Game Master. Write a compassionate in-world closing message and final report after a game over. "
                "Use 4-7 sentences, acknowledge the loss respectfully, summarize quest and award progress, "
                "and clearly communicate that the chronicle is now read-only. "
                "No bullet points, no markdown headings, no command lists."
            )
            fallback = (
                "The Game Master lowers their voice with sympathy. This chapter ends here, and your hero can go no further. "
                "Final report: the journey is recorded exactly as it stands, including your completed quests and earned awards. "
                "You can still review the world, but no further actions can alter this fate."
            )

        if language:
            system_prompt += f" Respond only in {language.upper()}."

        user_prompt = "Create the final narrative from this session report JSON:\n" + json.dumps(report_payload)

        try:
            llm = GameMasterLLM(self.user, provider=model_provider, model_category="complex")
            stream = await llm.stream_simple_task(system_prompt, user_prompt, model_name)
            content = ""
            async for chunk in stream:
                content += chunk.choices[0].delta.content or ""
            content = content.strip()
            return content or fallback
        except Exception:
            return fallback

    async def create_terminal_epilogue(self, language: str | None = None) -> dict[str, Any]:
        if not await self.initialize():
            raise HTTPException(status_code=404, detail="Game session not found.")

        if not self.state or not self.state.session:
            raise HTTPException(status_code=404, detail="Session state not found.")

        if self.state.session.status not in {"completed", "game_over"}:
            raise HTTPException(
                status_code=400,
                detail="Terminal epilogue is only available for completed or game-over sessions.",
            )

        if not self._is_terminal_epilogue_pending():
            return {
                "content": None,
                **self._build_terminal_flags_payload(),
            }

        epilogue_text = await self._generate_terminal_epilogue_text(language=language)
        if epilogue_text:
            await self._save_chat_message("assistant", epilogue_text)

        self._set_terminal_epilogue_sent(self.state.session.status, sent=True)
        await self.db.commit()

        return {
            "content": epilogue_text,
            **self._build_terminal_flags_payload(),
        }

    async def _finalize_session(self, status: str, note: str | None = None):
        """Updates the session status and records the outcome in the user's game log."""
        previous_status = self.state.session.status if self.state and self.state.session else None
        if self.state.session:
            self.state.session.status = status
            self.state.session.status_note = note

        if status in {"completed", "game_over"} and previous_status != status:
            self._set_terminal_epilogue_sent(status, sent=False)
        
        if status == "completed":
            self.state.is_completed = True
        
        # Add to User game log
        log_entry = {
            "session_id": self.game_id,
            "adventure_title": (self.state.session.adventure_title if self.state.session else None) or self.adventure.title,
            "status": status,
            "outcome_note": note,
            "completed_at": datetime.utcnow().isoformat()
        }
        
        current_log = list(self.user.game_log or [])
        # Avoid duplicate entries for same session
        current_log = [entry for entry in current_log if entry.get("session_id") != self.game_id]
        current_log.append(log_entry)
        self.user.game_log = current_log
        flag_modified(self.user, "game_log")
        logger.info(f"Session {self.game_id} finalized with status {status}")
