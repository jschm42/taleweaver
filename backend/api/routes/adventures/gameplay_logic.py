from __future__ import annotations
import asyncio
import json
import logging
import random
import re
import time
from types import SimpleNamespace
from collections.abc import AsyncGenerator, Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified
from backend.api.routes.adventures.agent_commands import (
    PLAYAGENT_COMMANDS,
    handle_playagent_command,
)
from backend.api.routes.adventures.logic import AdventureLogic
from backend.core.narration_budget import log_narration_budget
from backend.core.narration_styles import (
    narration_max_tokens,
    narration_style_reminder,
    narration_style_rules,
)
from backend.core.voice_tags import vocal_tag_reminder
from backend.engine.dice_command import handle_roll_command, is_roll_command
from backend.api.routes.adventures.turn_helpers import (
    TurnCombatStateHelper,
    TurnProgressionBuilder,
    TurnSessionStateHelper,
)
from backend.api.routes.adventures.turn_llm_pipeline import TurnLlmContextBuilder
from backend.api.routes.adventures.turn_pass_flow import (
    advance_in_game_turn,
    crossed_turn_boundary,
    extract_usage_tokens,
    run_guardrail_chain,
    turn_anchor,
)
from backend.api.routes.adventures.turn_prompt_layout import (
    build_exit_description_task,
    build_narration_messages,
    build_narration_turn_block,
    build_outcome_json,
    build_pass1_user_prompt,
)
from backend.core import prompts
from backend.core.config import settings
from backend.core.llm_logger import log_structured_event
from backend.core.llm_router import GameMasterLLM
from backend.engine.command_parser import CommandParser
from backend.engine.map_engine import MapEngine
from backend.engine.session_checkpoint_service import SessionCheckpointService
from backend.engine.llm_intents import ChatProgressionIntent, MechanicsIntent, to_game_event
from backend.engine.rule_engine import (
    RESOURCE_CAP,
    AdventureGenerationRequest,
    AdventureGeneratorToolIntent,
    AttackResult,
    GameEvent,
    GameOverError,
    SkillCheckResult,
    WorldEntityUpdate,
)
from backend.engine.scripting import GameContext, ScriptChangeset, ScriptRunner, ScriptMessage
from backend.api.routes.adventures.interaction_hooks import fire_interact_triggers
from backend.engine.interaction_targets import interacted_entity_ids
from backend.engine.sequence_scripts import sequence_scripts
from backend.engine.scripting.dialog import store_pending_dialog
from backend.engine.skill_check import roll_attack, roll_skill_check
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.chat import ChatMessage
from backend.models.session_state import SessionState
from backend.models.user import User
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene

logger = logging.getLogger(__name__)

# Public API. `random` is re-exported on purpose: turn_combat uses `gl.random` and tests
# patch `gameplay_logic.random.*`.
__all__ = [
    "WALKTHROUGH_REVEAL_COST",
    "GameTurnManager",
    "random",
]

# Constants
WALKTHROUGH_REVEAL_COST = 150
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


def _is_invalid_llm_payload_error(exc: Exception) -> bool:
    text = str(exc or "").lower()
    patterns = (
        "no content returned from llm for complex task",
        "failed to parse llm response as json",
        "does not match expected schema",
    )
    return any(p in text for p in patterns)


def _friendly_llm_error_message(exc: Exception) -> str | None:
    from backend.core.error_diagnostics import diagnose_provider_error

    lower_text = str(exc or "").lower()

    if _is_token_limit_error(exc):
        return _friendly_token_limit_message()
    if _is_rate_limit_error(exc):
        return "The Game Master is busy right now (rate limit or quota reached). Please check your account credits or try again in a moment."
    if _is_timeout_error(exc):
        return "The Game Master took too long to respond. Please try again."
    if _is_service_unavailable_error(exc):
        return "The Game Master is temporarily unavailable. Please try again shortly."
    if _is_invalid_llm_payload_error(exc):
        return "The selected model returned an invalid response. Please try again or choose a different model."

    # Specific actionable provider errors (Auth, ENCRYPTION_KEY, 404 Model, Connection)
    if any(
        kw in lower_text
        for kw in (
            "encryption_key",
            "invalidtoken",
            "invalidsignature",
            "failed to decrypt",
            "no api key",
            "authenticationerror",
            "invalid_api_key",
            "incorrect api key",
            "unauthorized",
            "notfounderror",
            "no endpoints found",
            "model not found",
            "connection refused",
        )
    ) or getattr(exc, "status_code", None) in (401, 404):
        return diagnose_provider_error(exc)

    return None


def _friendly_llm_unexpected_error_message() -> str:
    return "The Game Master encountered an unexpected issue. Please try again."


def _llm_error_type(exc: Exception) -> str | None:
    lower_text = str(exc or "").lower()
    if any(
        kw in lower_text
        for kw in ("encryption_key", "invalidtoken", "invalidsignature", "failed to decrypt")
    ):
        return "encryption_error"
    if (
        any(kw in lower_text for kw in ("authenticationerror", "invalid_api_key", "unauthorized"))
        or getattr(exc, "status_code", None) == 401
    ):
        return "auth_error"
    if (
        any(kw in lower_text for kw in ("notfounderror", "no endpoints found", "model not found"))
        or getattr(exc, "status_code", None) == 404
    ):
        return "model_not_found"
    if _is_token_limit_error(exc):
        return "token_limit"
    if _is_rate_limit_error(exc):
        return "rate_limit"
    if _is_timeout_error(exc):
        return "timeout"
    if _is_service_unavailable_error(exc):
        return "service_unavailable"
    if _is_invalid_llm_payload_error(exc):
        return "invalid_payload"
    return None


# Imported after the error helpers and constants above on purpose: these modules import
# WALKTHROUGH_REVEAL_COST / _friendly_llm_* from this module at load time (circular import).
from backend.api.routes.adventures.turn_adventure_gen import TurnAdventureGenManager  # noqa: E402
from backend.api.routes.adventures.turn_combat import TurnCombatManager  # noqa: E402
from backend.api.routes.adventures.post_turn_hooks import PostTurnHooks  # noqa: E402
from backend.api.routes.adventures.turn_guardrails import TurnGuardrailsManager  # noqa: E402
from backend.api.routes.adventures.turn_interactions import TurnInteractionsManager  # noqa: E402
from backend.api.routes.adventures.turn_state_applier import TurnStateApplier  # noqa: E402
from backend.api.routes.adventures.turn_suggestions import TurnSuggestionsManager  # noqa: E402


class GameTurnManager:
    """Class to manage the complex unified game turn (chat interaction)."""

    def __init__(
        self,
        db: AsyncSession,
        game_id: str,
        user: User,
        state: SessionState | None = None,
        adventure: AdventureTemplate | None = None,
        avatar: Avatar | None = None,
    ):
        self.db = db
        self.game_id = game_id
        self.user = user
        self.state: SessionState | None = state
        self.adventure: AdventureTemplate | None = adventure
        self.avatar: Avatar | None = avatar
        self.stop_requested = False
        self.turn_language: str | None = None
        self._progression = TurnProgressionBuilder(
            self,
            gm_notes_prompt_max_items=GM_NOTES_PROMPT_MAX_ITEMS,
            gm_chat_rule_pass_npcs_max_items=GM_CHAT_RULE_PASS_NPCS_MAX_ITEMS,
            gm_chat_prompt_template=prompts.GM_CHAT_PROGRESSION_STATE_TEMPLATE,
        )
        self._session_helper = TurnSessionStateHelper(
            self,
            gm_notes_state_key=GM_NOTES_STATE_KEY,
            gm_notes_max_items=GM_NOTES_MAX_ITEMS,
            terminal_epilogue_state_key=TERMINAL_EPILOGUE_STATE_KEY,
        )
        self._combat_state_helper = TurnCombatStateHelper(self)
        self._llm_context_builder = TurnLlmContextBuilder(self)
        self.combat = TurnCombatManager(self)
        self.pending_npc_attacks: list[str] = []
        self.guardrails = TurnGuardrailsManager(self)
        self.interactions = TurnInteractionsManager(self)
        self.state_applier = TurnStateApplier(self)
        self.adventure_gen = TurnAdventureGenManager(self)
        self.suggestions = TurnSuggestionsManager(self)
        self._pending_checkpoint_reasons: set[str] = set()
        self._checkpoint_scene_label: str | None = None
        # (scene, sequence) at the start of the player's message; an in-game turn only
        # advances when this changes (see turn_pass_flow.advance_in_game_turn).
        self._turn_anchor: tuple[Any, Any] | None = None

    def _queue_checkpoint(self, reason: str, *, scene_label: str | None = None) -> None:
        self._pending_checkpoint_reasons.add(reason)
        if scene_label:
            self._checkpoint_scene_label = scene_label

    @staticmethod
    def _normalize_technical_action_input(user_msg: str) -> str:
        text = str(user_msg or "").strip()
        if not text:
            return text

        text_lower = text.lower()
        for prefix in ("[open_container]", "open_container]", "[open_container", "open_container"):
            if text_lower.startswith(prefix):
                rest = text[len(prefix) :]
                if rest and rest[0].isspace():
                    target = rest.strip()
                    if target:
                        return f"/open {target}"
                break

        for prefix in ("[open_text_log]", "open_text_log]", "[open_text_log", "open_text_log"):
            if text_lower.startswith(prefix):
                rest = text[len(prefix) :]
                if rest and rest[0].isspace():
                    target = rest.strip()
                    if target:
                        return f"/read {target}"
                break

        return text

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
                    "created_at": checkpoint.created_at.isoformat()
                    if checkpoint.created_at
                    else None,
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

    async def _build_narration_messages(
        self, narration_prompt: str, user_msg: str, turn_context: str = ""
    ) -> tuple[list[dict[str, str]], int]:
        """Builds the multi-turn messages array for Pass 2 (narration).

        See turn_prompt_layout.build_narration_messages. Returns (messages, max_turns_configured).
        """
        return await build_narration_messages(
            self.db, self.state, self.adventure, narration_prompt, user_msg, turn_context
        )

    @staticmethod
    def _compact_json(payload: object) -> str:
        return TurnProgressionBuilder.compact_json(payload)

    @staticmethod
    def _is_lookaround_request(user_msg: str) -> bool:
        normalized = (user_msg or "").strip().lower()
        if not normalized:
            return False
        return "look around" in normalized or normalized in {
            "[look around]",
            "/lookaround",
            "/look",
            "look",
        }

    @staticmethod
    def _replace_entity_ids_with_names(text: str, id_to_name: dict[str, str]) -> str:
        """Replace leaked entity-id tokens (e.g. FREEZER_KEY) with display names."""
        if not text or not id_to_name:
            return text

        valid_pairs: dict[str, str] = {}
        for raw_id, raw_name in (id_to_name or {}).items():
            entity_id = str(raw_id or "").strip()
            entity_name = str(raw_name or "").strip()
            if not entity_id or not entity_name:
                continue
            if entity_id == entity_name:
                continue
            valid_pairs[entity_id] = entity_name

        if not valid_pairs:
            return text

        pattern = re.compile(
            r"(?<![A-Za-z0-9_])("
            + "|".join(re.escape(k) for k in sorted(valid_pairs.keys(), key=len, reverse=True))
            + r")(?![A-Za-z0-9_])"
        )

        def _replace(match: re.Match[str]) -> str:
            token = match.group(1)
            prefix = text[max(0, match.start() - 4) : match.start()]
            # Preserve explicit technical markers used by debug/unhide logic.
            if prefix.upper().endswith("ID: "):
                return token
            return valid_pairs.get(token, token)

        return pattern.sub(_replace, text)

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
                    "destination_scene_label": destination_label_map.get(
                        str(ex.to_scene_id), str(ex.to_scene_id or "")
                    ),
                    "is_locked": bool(ex.is_locked),
                }
            )

        return self._compact_json(exit_refs)

    def _build_mechanics_awards(self) -> list[dict]:
        return self._progression.build_mechanics_awards()

    def _build_mechanics_quests(self) -> list[dict]:
        return self._progression.build_mechanics_quests()

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

    @staticmethod
    def _build_chat_progression_locked_containers(
        all_entities: list[WorldEntity],
        entity_states: dict[str, Any],
    ) -> list[dict]:
        """Returns a compact list of currently-locked containers for the chat rule pass.

        Includes only containers that are locked (by code, item, or rule) so the
        small LLM can emit the correct unlock event when the player provides the
        right code or item in natural language.
        """
        result: list[dict] = []
        for ent in all_entities:
            if str(getattr(ent, "entity_type", "") or "").upper() != "OBJECT":
                continue
            if str(getattr(ent, "item_type", "") or "").upper() != "CONTAINER":
                continue

            # Honour session-state override for locked flag
            state_locked = (entity_states.get(ent.id) or {}).get("locked")
            if isinstance(state_locked, bool) and not state_locked:
                continue  # explicitly unlocked in session state

            meta = dict(ent.metadata_json or {})
            code_to_unlock = str(meta.get("code_to_unlock") or "").strip()
            item_to_unlock = str(meta.get("item_to_unlock") or "").strip()
            rule_to_unlock = str(meta.get("rule_to_unlock") or "").strip()

            # Skip if no lock requirements (open container)
            if not (code_to_unlock or item_to_unlock or rule_to_unlock):
                continue

            entry: dict[str, Any] = {
                "id": str(ent.id or "").strip(),
                "name": str(ent.name or ent.id or "container").strip(),
                "scene_id": str(ent.current_scene_id or "").strip(),
            }
            if code_to_unlock:
                entry["code_to_unlock"] = code_to_unlock
            if item_to_unlock:
                entry["item_to_unlock"] = item_to_unlock
            if rule_to_unlock:
                entry["rule_to_unlock"] = rule_to_unlock
            result.append(entry)
        return result

    def _build_chat_rule_pass_prompt(
        self,
        quests: list[dict],
        awards: list[dict],
        npcs: list[dict],
        scenes: list[dict],
        exits: list[dict],
        locked_containers: list[dict] | None = None,
    ) -> str:
        """Builds the per-turn CURRENT STATE block for the chat-mode rule pass.

        The static instructions (incl. the disabled dynamic items rule) live in
        prompts.GM_CHAT_PROGRESSION_RULES_PROMPT, which is sent as system prompt.
        """
        state_block = self._progression.build_chat_rule_pass_prompt(
            quests, awards, npcs, scenes, exits
        )
        if not locked_containers:
            return state_block
        return state_block + (
            "LOCKED CONTAINERS (unlock via `updated_entities` with `locked=false` for the matching "
            "`entity_id` when the player provides the correct code or carries the required item): "
            + json.dumps(locked_containers, ensure_ascii=False, separators=(",", ":"))
            + "\n"
        )

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

    def _apply_gm_notes_update(
        self,
        remember_notes: list[str] | None,
        forget_notes: list[str] | None,
        clear_notes: bool,
    ) -> None:
        self._session_helper.apply_gm_notes_update(remember_notes, forget_notes, clear_notes)

    def _build_gm_notes_prompt_block(self) -> str:
        return self._session_helper.build_gm_notes_prompt_block()

    def _build_world_memories_prompt_block(self) -> str:
        current_scene_id = self.state.current_scene_id if self.state else "START"
        return self._session_helper.build_world_memories_prompt_block(current_scene_id)

    def _build_compressed_history_prompt_block(self) -> str:
        return self._session_helper.build_compressed_history_prompt_block()

    @staticmethod
    def _build_progression_event(intent: AdventureGeneratorToolIntent) -> GameEvent:
        return TurnProgressionBuilder.build_progression_event(intent)

    async def initialize(self) -> bool:
        """Loads all necessary context for the turn."""
        start = time.perf_counter()
        if not self.state:
            self.state = await AdventureLogic.resolve_session_state(
                self.db, self.game_id, user_id=self.user.id
            )
        elif "session" in inspect(self.state).unloaded:
            # Refreshing state can expire this relationship between turns.
            await self.db.refresh(self.state, attribute_names=["session"])
        if not self.state:
            logger.warning(f"[Turn {self.game_id}] Initialization failed: Session state not found.")
            return False

        if not self.adventure and self.state.template_id:
            adv_res = await self.db.execute(
                select(AdventureTemplate).where(AdventureTemplate.id == self.state.template_id)
            )
            self.adventure = adv_res.scalars().first()
        if not self.avatar and self.state.avatar_id:
            av_res = await self.db.execute(select(Avatar).where(Avatar.id == self.state.avatar_id))
            self.avatar = av_res.scalars().first()

        if not self.adventure:
            snapshot = AdventureLogic.extract_manifest_snapshot(self.state)
            snapshot_adventure = (
                snapshot.get("adventure") if isinstance(snapshot.get("adventure"), dict) else {}
            )
            snapshot_manifest = (
                snapshot.get("original_manifest")
                if isinstance(snapshot.get("original_manifest"), dict)
                else {}
            )
            if snapshot_adventure or snapshot_manifest:
                self.adventure = SimpleNamespace(
                    id=snapshot_adventure.get("id") or self.state.template_id or "deleted-template",
                    title=snapshot_adventure.get("title")
                    or (self.state.session.adventure_title if self.state.session else None)
                    or "Deleted Adventure",
                    teaser=snapshot_adventure.get("teaser"),
                    version=snapshot_adventure.get("version"),
                    language=snapshot_adventure.get("language"),
                    image_url=snapshot_adventure.get("image_url")
                    or (self.state.session.adventure_image_url if self.state.session else None),
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
                    completed_condition=snapshot_adventure.get("completed_condition")
                    or self.state.completed_condition,
                    gameover_condition=snapshot_adventure.get("gameover_condition")
                    or self.state.gameover_condition,
                    tts_director_notes=snapshot_adventure.get("tts_director_notes")
                    or self.state.tts_director_notes,
                    original_prompt=snapshot_adventure.get("original_prompt") or "",
                    allow_dynamic_items=False,
                    can_damage_npcs=bool(snapshot_adventure.get("can_damage_npcs", True)),
                    npcs_can_damage_protagonist=bool(
                        snapshot_adventure.get("npcs_can_damage_protagonist", True)
                    ),
                    is_adventure_generator=bool(
                        snapshot_adventure.get("is_adventure_generator", False)
                    ),
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
                scene_res = await self.db.execute(
                    select(WorldScene).where(
                        WorldScene.id == self.state.current_scene_id,
                        WorldScene.template_id == self.state.template_id,
                    )
                )
                cur_scene = scene_res.scalars().first()

            MapEngine.register_visit(
                world_map,
                self.state.current_scene_id,
                label=cur_scene.label if cur_scene else None,
                description=cur_scene.description if cur_scene else None,
                image_url=cur_scene.image_url if cur_scene else None,
            )
        except Exception as e:
            logger.warning(f"Failed to auto-register map visit for {self.game_id}: {e}")

        duration = time.perf_counter() - start
        logger.debug(f"[Turn {self.game_id}] Initialization (DB) took {duration:.4f}s")
        return True

    async def process_turn(
        self, message: str, auto_visualize: bool = False, language: str | None = None
    ) -> AsyncGenerator[str, None]:
        """Runs one turn and applies post-turn hooks (special unlocks, NPC attacks) before its final event."""
        hooks = PostTurnHooks(self)
        async for chunk in self._process_turn_inner(message, auto_visualize, language):
            if not chunk.startswith("event: final"):
                yield chunk
                continue
            async for hooked in hooks.process_final(chunk):
                yield hooked

    async def _command_final_event(self) -> str:
        """Final SSE event for commands that skip the narration pass (state snapshot only)."""
        final_data = jsonable_encoder(
            {
                "sheet": await AdventureLogic.build_sheet_snapshot(
                    self.avatar, self.state, self.db
                ),
                "entities": await AdventureLogic.build_session_entities(self.db, self.state),
                "combat": AdventureLogic.get_combat_snapshot(self.state),
                **self._build_prompt_suggestions_payload(),
                **self._build_terminal_flags_payload(),
                "status": "success",
            }
        )
        return f"event: final\ndata: {json.dumps(final_data)}\n\n"

    async def _process_turn_inner(
        self, message: str, auto_visualize: bool = False, language: str | None = None
    ) -> AsyncGenerator[str, None]:
        self.turn_language = language
        if not await self.initialize():
            yield f"event: error\ndata: {json.dumps({'detail': 'Game session not found.'})}\n\n"
            return

        # Pre-emptive sanitization of avatar JSON fields to avoid datetime serialization issues
        self.avatar.inventory = jsonable_encoder(self.avatar.inventory)
        self.avatar.equipment = jsonable_encoder(self.avatar.equipment)

        self._turn_anchor = turn_anchor(self.state)
        user_msg = message.strip()
        actual_user_input = user_msg
        if not user_msg:
            user_msg = "[LOOK AROUND]"
        else:
            normalized_user_msg = self._normalize_technical_action_input(user_msg)
            if normalized_user_msg != user_msg:
                user_msg = normalized_user_msg
                actual_user_input = normalized_user_msg

        if user_msg.lower() in {"/shuffle", "/suggest", "/suggestions"}:
            last_response = await self._load_last_assistant_message()
            await self._generate_prompt_suggestions(last_response)
            await self.db.commit()
            yield await self._command_final_event()
            return

        cmd_parts = user_msg.strip().split(None, 1)
        if cmd_parts and cmd_parts[0].lower() in PLAYAGENT_COMMANDS:
            cmd_args = cmd_parts[1].strip() if len(cmd_parts) > 1 else ""
            async for chunk in handle_playagent_command(self, cmd_args):
                yield chunk

            yield await self._command_final_event()
            return

        if self._is_input_locked():
            lock_message = (
                "This story has reached its final ending. You can still review the map, character sheet, "
                "quests, awards, walkthrough, and chat history, but no further actions can be taken."
            )
            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': lock_message})}\n\n"
            yield await self._command_final_event()
            return

        # /roll [sides]: a single die roll, no narration pass
        if is_roll_command(user_msg):
            async for chunk in handle_roll_command(self, user_msg):
                yield chunk
            yield await self._command_final_event()
            return

        # traverse_exit internal command: move scene, then run LLM narration pass
        if user_msg.lower().startswith("/traverse_exit "):
            exit_ref = user_msg[15:].strip()
            async for chunk in self._handle_traverse_exit(exit_ref, language=language):
                yield chunk
            return

        # Unified logic for /debug and / (slash) commands
        if user_msg.startswith("/debug"):
            cmd_args = user_msg[7:].strip().lower()
            is_on_cmd = cmd_args == "on" or cmd_args.startswith("log on")
            # Keep combat-outcome debug shortcuts available for deterministic testing/workflows.
            is_combat_outcome_shortcut = cmd_args in {"win_fight", "loose_fight"}

            if cmd_args == "win_fight":
                async for chunk in self.combat.handle_debug_victory():
                    yield chunk
                return

            if (
                settings.TALEWEAVER_DEBUG_ENABLED
                or self.state.is_debug_enabled
                or is_on_cmd
                or is_combat_outcome_shortcut
            ):
                async for chunk in self._handle_debug(user_msg):
                    yield chunk
                return
            else:
                logger.warning(
                    f"[Turn {self.game_id}] Debug command ignored: TALEWEAVER_DEBUG_ENABLED is False and in-game debug is OFF."
                )
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
            response = CommandParser.parse_command(
                self.avatar,
                user_msg,
                debug_enabled=(
                    settings.TALEWEAVER_DEBUG_ENABLED or bool(self.state.is_debug_enabled)
                ),
            )

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
                    await self._handle_read_action_unlock(read_target)
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

                pickup = getattr(self.interactions, "pending_pickup_trigger", None)
                self.interactions.pending_pickup_trigger = None
                seq_intro = getattr(self.interactions, "pending_sequence_intro", None)
                self.interactions.pending_sequence_intro = None
                if pickup or seq_intro:
                    reaction_prompt = ""
                    narration_only = True
                    status_text = "The Game Master reacts..."
                    if pickup:
                        item_name = pickup.get("item_name") or "the item"
                        cue = pickup.get("cue") or ""
                        narration_only = pickup.get("mode") == "narration"
                        if narration_only:
                            reaction_prompt = (
                                f"[ITEM_PICKUP] The player just picked up {item_name}. "
                                "Narrate ONLY the immediate reaction to this action in one or two short paragraphs. "
                                "Do NOT change world state, award items, move the player, or advance the plot beyond this reaction."
                            )
                        else:
                            reaction_prompt = (
                                f"[ITEM_PICKUP] The player just picked up {item_name}. "
                                "React to this action as the Game Master: let present NPCs respond in character and "
                                "apply any rules or consequences that now trigger."
                            )
                        if cue:
                            reaction_prompt += f" Author's cue for this moment: {cue}"
                    if seq_intro:
                        reaction_prompt = f"{reaction_prompt} {seq_intro['prompt']}".strip()
                        status_text = f"Opening {seq_intro['title']}..."
                    yield f"event: status\ndata: {json.dumps({'content': status_text})}\n\n"
                    try:
                        async for chunk in self._run_llm_cycle(
                            reaction_prompt,
                            False,
                            language=language,
                            narration_only=narration_only,
                        ):
                            yield chunk
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:
                        user_safe_error = (
                            _friendly_llm_error_message(exc)
                            or _friendly_llm_unexpected_error_message()
                        )
                        yield f"event: error\ndata: {json.dumps({'detail': user_safe_error, 'retryable': True})}\n\n"
                return

        blocked_message = await self._guard_non_visible_inspect_or_search(user_msg)
        if blocked_message:
            if actual_user_input:
                await self._save_chat_message("user", actual_user_input)
                await self.db.flush()

            await self._save_chat_message("system", blocked_message)
            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': blocked_message})}\n\n"

            await self.db.commit()
            final_data = jsonable_encoder(
                {
                    "sheet": await AdventureLogic.build_sheet_snapshot(
                        self.avatar, self.state, self.db
                    ),
                    "entities": await AdventureLogic.build_session_entities(self.db, self.state),
                    "combat": AdventureLogic.get_combat_snapshot(self.state),
                    **self._build_prompt_suggestions_payload(),
                    **self._build_terminal_flags_payload(),
                    "status": "success",
                }
            )
            yield f"event: final\ndata: {json.dumps(final_data)}\n\n"
            return

        # Core Turn Logic
        turn_start = time.perf_counter()
        logger.debug(
            f"[Turn {self.game_id}] Starting turn for user '{self.user.username}' with input: {user_msg}"
        )
        if not is_rule_pass:
            yield f"event: status\ndata: {json.dumps({'content': 'Considering...'})}\n\n"

        # Base time and status ticks no longer advance per message: an in-game turn only
        # advances on scene/sequence changes (handled inside _run_llm_cycle).

        # Record User Message
        silent_commands = ["/take_direct", "/rule-pass", "/equip", "/unequip", "/consume"]
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
            yield f"event: error\ndata: {json.dumps({'detail': user_safe_error, 'retryable': True})}\n\n"
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
        logger.debug(
            f"[Turn {self.game_id}] Total turn processing took {turn_end - turn_start:.4f}s"
        )
        if settings.TALEWEAVER_DEBUG_ENABLED or bool(self.state and self.state.is_debug_enabled):
            duration_ms = round((turn_end - turn_start) * 1000, 1)
            dbg_msg = (
                f"[DEBUG LOG] Turn completed in {duration_ms}ms | Scene: {self.state.current_scene_id} | "
                f"Hero HP: {self.avatar.hp}/{self.avatar.max_hp} | In-Game Time: {self.state.in_game_time}m"
            )
            dbg_cm = await self._save_chat_message("system", dbg_msg)
            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': dbg_msg, 'is_debug': True, 'id': str(dbg_cm.id)})}\n\n"

    async def _run_llm_cycle(
        self,
        user_msg: str,
        auto_visualize: bool,
        language: str | None = None,
        narration_only: bool = False,
    ) -> AsyncGenerator[str, None]:
        """Runs Pass 1 (mechanics/progression), Pass 1.5 (guardrails), and Pass 2 (narration).

        `narration_only` skips Pass 1 for pure reaction narrations that must not change state.
        """
        _ = auto_visualize
        cycle_start = time.perf_counter()
        scene_id_before_turn = self.state.current_scene_id
        if self._turn_anchor is None:
            self._turn_anchor = turn_anchor(self.state)
        ctx = await self._llm_context_builder.build_context(user_msg=user_msg, language=language)
        history = ctx.history
        entities = ctx.entities
        all_entities = ctx.all_entities
        exits = ctx.exits
        all_scenes = ctx.all_scenes
        mechanics_awards = ctx.mechanics_awards
        small_model_provider = ctx.small_model_provider
        complex_model_provider = ctx.complex_model_provider
        small_model = ctx.small_model
        complex_model = ctx.complex_model
        global_unlock_rules_prompt_block = ctx.global_unlock_rules_prompt_block

        game_event = None
        pre_inventory_ids = set()
        response_text = ""
        rule_violations = []
        pending_generator_proposal: dict[str, Any] | None = None
        script_runner = self._get_script_runner()
        script_ctx = None

        # Pass 1: Mechanics (strict adventures), chat progression intent (normal chat),
        # or adventure-generator tool-intent pass (generator chat mode).
        is_chat_mode = not self.adventure.strict_rules and not self.adventure.is_adventure_generator
        run_mechanics_pass = self.adventure.strict_rules and not narration_only
        run_chat_progression_pass = is_chat_mode and not narration_only
        run_generator_tool_intent_pass = (
            self.adventure.is_adventure_generator
            and not self.adventure.strict_rules
            and not narration_only
        )
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
                llm = GameMasterLLM(
                    self.user, provider=small_model_provider, model_category="small"
                )
            except ValueError:
                yield f"event: error\ndata: {json.dumps({'detail': 'Mechanics model configuration is invalid. Please check your settings and try again.'})}\n\n"
                return

            mechanics_suffix = prompts.GM_MECHANICS_SUFFIX
            if self.adventure.rule_enforcement_mode == "story":
                mechanics_suffix = prompts.GM_STORY_MECHANICS_SUFFIX

            # Static system prompt (cacheable); quests, awards and live state go to the user message.
            mechanics_prompt = ctx.mechanics_static_prompt + "\n\n" + mechanics_suffix
            mechanics_user_prompt = build_pass1_user_prompt(
                ctx.mechanics_state_block,
                user_msg,
                history,
                extra_blocks=(
                    f"OPEN QUESTS: {self._compact_json(self._build_mechanics_quests())}",
                    f"AVAILABLE AWARDS: {self._compact_json(mechanics_awards)}",
                ),
            )

            pass1_start = time.perf_counter()
            logger.debug(
                f"[Turn {self.game_id}] [Pass 1] Calling small model: {small_model} via {small_model_provider}"
            )
            try:
                mechanics_intent = await llm.aexecute_complex_task(
                    mechanics_prompt,
                    mechanics_user_prompt,
                    response_model=MechanicsIntent,
                    model=small_model,
                    operation="chat_turn",
                    phase="mechanics",
                )
                game_event = to_game_event(mechanics_intent)
            except Exception as e:
                user_safe_error = _friendly_llm_error_message(e)
                if user_safe_error:
                    yield f"event: error\ndata: {json.dumps({'detail': user_safe_error})}\n\n"
                    return
                logger.exception(
                    "[Turn %s] [Pass 1] Mechanics call failed unexpectedly", self.game_id
                )
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
            logger.debug(
                f"[Turn {self.game_id}] [Pass 1] Mechanics analysis took {pass1_duration:.4f}s"
            )

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
                        reason=req.reason,
                    )
                    results.append(res)

                    # Output as system message for transparency
                    success_label = "SUCCESS" if res.success else "FAILURE"
                    roll_msg = (
                        f"**{req.stat.upper()} CHECK**: {res.reason}\n"
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

                    if (
                        "stat_modifier_armor_class" in target_state
                        and target_state["stat_modifier_armor_class"] is not None
                    ):
                        mod = target_state["stat_modifier_armor_class"]
                        target_ac += mod
                        ac_reason = f"Base 10 + {mod} Mod"
                    else:
                        # Fetch from template if not in state
                        target_res = await self.db.execute(
                            select(WorldEntity).where(
                                WorldEntity.id == target_id, WorldEntity.session_id == self.game_id
                            )
                        )
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
                        reason=req.reason,
                    )
                    attack_results.append(res)

                    # Output as system message
                    hit_label = "HIT" if res.is_hit else "MISS"
                    roll_msg = (
                        f"**ATTACK**: {res.reason}\n"
                        f"To-Hit: {res.hit_roll} + {res.hit_modifier} = **{res.hit_total}** (vs AC {res.target_ac}, {ac_reason}) -> **{hit_label}**"
                    )
                    if res.is_hit:
                        rolls_str = " + ".join(str(r) for r in res.damage_rolls)
                        bonus_str = (
                            f" + {res.damage_bonus}"
                            if res.damage_bonus > 0
                            else (f" - {abs(res.damage_bonus)}" if res.damage_bonus < 0 else "")
                        )
                        roll_msg += f"\nDamage: {res.damage_dice_str} ({rolls_str}{bonus_str}) = **{res.damage_total}** HP dealt to {target_id}."

                        # Apply damage to NPC HP in GameEvent for _apply_game_event to pick up
                        if not game_event.updated_entities:
                            game_event.updated_entities = []

                        # Find current HP
                        current_hp = 50  # Default
                        if "hp" in target_state:
                            current_hp = target_state["hp"]
                        else:
                            # Re-fetch entity to get baseline HP if needed
                            target_res = await self.db.execute(
                                select(WorldEntity).where(
                                    WorldEntity.id == target_id,
                                    WorldEntity.session_id == self.game_id,
                                )
                            )
                            target_ent = target_res.scalars().first()
                            if target_ent and target_ent.hp is not None:
                                current_hp = target_ent.hp

                        new_hp = max(0, current_hp - res.damage_total)
                        game_event.updated_entities.append(
                            WorldEntityUpdate(entity_id=target_id, hp=new_hp)
                        )

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
                if script_runner.scripts:
                    script_ctx = await self._build_script_context()
                async for guardrail_event in run_guardrail_chain(
                    self, game_event, user_msg, rule_violations, script_ctx
                ):
                    yield guardrail_event

                # Trigger scripts for scene entry and entity interactions
                if script_runner.scripts:
                    script_ctx = await self._build_script_context()
                    if (
                        game_event.new_scene_id
                        and game_event.new_scene_id != self.state.current_scene_id
                    ):
                        cs_scene = script_runner.run_trigger(
                            "on_enter_scene", script_ctx, target_id=game_event.new_scene_id
                        )
                        rule_violations.extend(cs_scene.rejected_actions)
                        sys_msgs = await self._apply_script_changeset(cs_scene, game_event)
                        for sm in sys_msgs:
                            role = getattr(sm, "role", "system")
                            yield f"event: {role}\ndata: {json.dumps({'role': role, 'content': str(sm)})}\n\n"

                if game_event.game_completed:
                    await self._finalize_session("completed", game_event.status_note)
            except GameOverError as goe:
                await self._finalize_session("game_over", str(goe))
                # Ensure the narration knows about the game over
                game_event.game_over = True
                game_event.status_note = str(goe)

        elif run_generator_tool_intent_pass and not handled_generator_confirmation:
            yield f"event: status\ndata: {json.dumps({'content': 'Checking generator tools...'})}\n\n"
            try:
                llm = GameMasterLLM(
                    self.user, provider=small_model_provider, model_category="small"
                )
            except ValueError:
                logger.exception(
                    "Generator tool model configuration is invalid for user %s", self.user.id
                )
                yield f"event: error\ndata: {json.dumps({'detail': 'Generator tool model configuration is invalid. Please check your settings and try again.'})}\n\n"
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
                ctx.mechanics_system_prompt
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
                    # An explicit retry request counts as confirmation.
                    game_event.generation_confirmed = True
                    if not game_event.narrative_description:
                        game_event.narrative_description = (
                            "Understood. I will retry the last adventure generation now."
                        )

            if game_event.requested_adventure_generation:
                req = game_event.requested_adventure_generation
                self._set_last_ag_generation_request(req)
                pending_generator_proposal = self.adventure_gen.build_generator_proposal(
                    req, auto_start=game_event.generation_confirmed
                )
                if not game_event.narrative_description:
                    game_event.narrative_description = self.adventure_gen.proposal_narrative(
                        auto_start=game_event.generation_confirmed
                    )
                game_event.requested_adventure_generation = None

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
                llm = GameMasterLLM(
                    self.user, provider=small_model_provider, model_category="small"
                )
            except ValueError:
                logger.exception(
                    "Progression model configuration is invalid for user %s", self.user.id
                )
                yield f"event: error\ndata: {json.dumps({'detail': 'Progression model configuration is invalid. Please check your settings and try again.'})}\n\n"
                return

            reduced_quests = self._build_chat_progression_quests()
            reduced_awards = self._build_chat_progression_awards(mechanics_awards)
            reduced_npcs = self._build_chat_progression_npcs(entities)
            reduced_scenes = self._build_chat_progression_scenes(all_scenes)
            reduced_exits = self._build_chat_progression_exits(exits)
            locked_containers = self._build_chat_progression_locked_containers(
                entities, self.state.entity_states or {}
            )

            progression_state = self._build_chat_rule_pass_prompt(
                quests=reduced_quests,
                awards=reduced_awards,
                npcs=reduced_npcs,
                scenes=reduced_scenes,
                exits=reduced_exits,
                locked_containers=locked_containers or None,
            )
            progression_user_prompt = build_pass1_user_prompt(
                progression_state,
                user_msg,
                history,
                extra_blocks=(global_unlock_rules_prompt_block,),
            )

            progression_start = time.perf_counter()
            try:
                progression_intent = await llm.aexecute_complex_task(
                    prompts.GM_CHAT_PROGRESSION_RULES_PROMPT,
                    progression_user_prompt,
                    response_model=ChatProgressionIntent,
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
                    if (
                        not bool(ex.get("is_locked"))
                        or any(
                            up.to_scene_id == ex.get("to_scene_id") and not up.is_locked
                            for up in (getattr(progression_intent, "updated_exits", None) or [])
                        )
                    )
                    and str(ex.get("to_scene_id") or "").strip()
                }
                move_is_valid = (
                    progression_intent.new_scene_id in allowed_open_destinations
                    and await self._is_explicit_scene_transition_request(user_msg)
                    and self._message_mentions_transition_target(
                        user_msg=user_msg,
                        target_scene_id=progression_intent.new_scene_id,
                        exit_label=progression_intent.exit_label,
                        reduced_scenes=reduced_scenes,
                        reduced_exits=reduced_exits,
                    )
                )
                if not move_is_valid:
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
                reduced_payload_chars=len(progression_user_prompt),
                quest_count=len(reduced_quests),
                award_count=len(reduced_awards),
                npc_count=len(reduced_npcs),
                notes_count=min(len(self._get_gm_notes()), GM_NOTES_PROMPT_MAX_ITEMS),
            )

            game_event = self._build_progression_event(progression_intent)

            try:
                if script_runner.scripts:
                    script_ctx = await self._build_script_context()
                async for guardrail_event in run_guardrail_chain(
                    self, game_event, user_msg, rule_violations, script_ctx
                ):
                    yield guardrail_event

                if game_event.game_completed:
                    await self._finalize_session("completed", game_event.status_note)
                elif game_event.game_over:
                    await self._finalize_session(
                        "game_over", game_event.status_note or "Game over."
                    )
            except GameOverError as goe:
                await self._finalize_session("game_over", str(goe))
                game_event.game_over = True
                game_event.status_note = str(goe)

        # Entity interactions: scripted and inline on_interact triggers. Runs in every rule
        # mode; without the mechanics pass only entities named in the message count.
        try:
            interacted_ids = await interacted_entity_ids(
                self.db,
                self.state,
                user_msg,
                [ue.entity_id for ue in getattr(game_event, "updated_entities", None) or []],
            )
            for entity_id in interacted_ids:
                sys_msgs, rejected = await fire_interact_triggers(
                    self, script_runner, entity_id, game_event
                )
                rule_violations.extend(rejected)
                for sm in sys_msgs:
                    role = getattr(sm, "role", "system")
                    yield f"event: {role}\ndata: {json.dumps({'role': role, 'content': str(sm)})}\n\n"
        except GameOverError as goe:
            await self._finalize_session("game_over", str(goe))
            if isinstance(game_event, GameEvent):
                game_event.game_over = True
                game_event.status_note = str(goe)

        # Logic-pass completion scripts (on_logic_pass_done)
        if script_runner.scripts:
            try:
                script_ctx = await self._build_script_context()
                cs_logic = script_runner.run_trigger("on_logic_pass_done", script_ctx)
                if cs_logic.has_changes:
                    rule_violations.extend(cs_logic.rejected_actions)
                    sys_msgs = await self._apply_script_changeset(cs_logic, game_event)
                    for sm in sys_msgs:
                        role = getattr(sm, "role", "system")
                        yield f"event: {role}\ndata: {json.dumps({'role': role, 'content': str(sm)})}\n\n"
            except GameOverError as goe:
                await self._finalize_session("game_over", str(goe))
                if isinstance(game_event, GameEvent):
                    game_event.game_over = True
                    game_event.status_note = str(goe)

        # In-game turn: only a scene or sequence change advances time, ticks, and turn scripts.
        turn_advanced = crossed_turn_boundary(self.state, self._turn_anchor)
        if turn_advanced:
            async for turn_event in advance_in_game_turn(self, script_runner, game_event):
                yield turn_event
            self._turn_anchor = turn_anchor(self.state)
            # Narrate from the new location/sequence instead of the pre-turn snapshot.
            ctx = await self._llm_context_builder.build_context(
                user_msg=user_msg, language=language
            )

        # Push a state snapshot before narration so scene/entity images can update immediately on scene changes.
        await self.db.flush()
        pre_narration_state = jsonable_encoder(
            {
                "map_data": await self._build_map_payload(),
                "nodes": await AdventureLogic.get_all_scene_metadata(
                    self.db, self.state.template_id, session_id=self.state.session_id
                ),
                "npc_metadata": await AdventureLogic.get_npc_metadata(
                    self.db, self.state.template_id, session_id=self.state.session_id
                ),
                "image_url": await AdventureLogic.resolve_scene_image(
                    self.db, self.state, self.state.current_scene_id
                ),
                "sheet": await AdventureLogic.build_sheet_snapshot(
                    self.avatar, self.state, self.db
                ),
                "entities": await AdventureLogic.build_session_entities(self.db, self.state),
                "combat": AdventureLogic.get_combat_snapshot(self.state),
                "quests": self.state.quests,
                "world_memories": self.state.world_memories or [],
                "world_rumors": self.state.world_rumors or [],
                "scene_id": self.state.current_scene_id,
                "sequence_id": self.state.active_sequence_id,
                **self._build_prompt_suggestions_payload(),
                **self._build_terminal_flags_payload(),
                "status": "success",
            }
        )
        yield f"event: state\ndata: {json.dumps(pre_narration_state)}\n\n"

        # Pass 2: Narration
        yield f"event: status\ndata: {json.dumps({'content': 'Generating narrative...'})}\n\n"
        try:
            llm = GameMasterLLM(
                self.user, provider=complex_model_provider, model_category="complex"
            )
        except ValueError:
            logger.exception("Narration model configuration is invalid for user %s", self.user.id)
            yield f"event: error\ndata: {json.dumps({'detail': 'Narration model configuration is invalid. Please check your settings and try again.'})}\n\n"
            return
        tts_settings = self.user.tts_settings or {}
        use_vocal_tags = tts_settings.get("use_vocal_tags", True)

        if rule_violations and game_event:
            game_event.narrative_description = (
                "The attempted action failed and was reverted due to the following rule violations: "
                + "; ".join(rule_violations)
            )
        draft_narration, outcome_json = build_outcome_json(game_event)

        # Static system prompt (cacheable across turns); everything per-turn goes into the
        # latest user message via the TURN RESOLUTION block.
        tts_provider = tts_settings.get("provider", "google")
        narration_prompt_parts = [
            ctx.narration_static_prompt,
            prompts.GM_NARRATION_TURN_CONTRACT,
            prompts.GM_NARRATION_MANDATORY_FORMATTING,
            narration_style_rules(getattr(self.state, "narration_style", None)),
            prompts.get_vocal_direction_prompt(tts_provider) if use_vocal_tags else "",
            prompts.GM_CHAT_NARRATION_SUFFIX if is_chat_mode else "",
        ]
        narration_prompt = "\n\n".join(part for part in narration_prompt_parts if part)

        reminders: list[str] = [
            narration_style_reminder(getattr(self.state, "narration_style", None))
        ]
        if use_vocal_tags:
            reminders.append(vocal_tag_reminder())
        if language:
            reminders.append(
                f"Respond in {language.upper()} only (except voice tags like [curious], which MUST always remain in English)."
            )

        exits_task = ""
        scene_changed_this_turn = self.state.current_scene_id != scene_id_before_turn
        if self._is_lookaround_request(user_msg) or scene_changed_this_turn:
            exits_task = build_exit_description_task(await self._build_scene_exits_context_json())

        turn_context = build_narration_turn_block(
            ctx.narration_state_block,
            draft_narration,
            outcome_json,
            rule_violations,
            exits_task=exits_task,
            reminders=tuple(reminders),
        )

        pass2_start = time.perf_counter()
        narration_messages, memory_turns = await self._build_narration_messages(
            narration_prompt, user_msg, turn_context=turn_context
        )
        logger.debug(
            f"[Turn {self.game_id}] [Pass 2] Calling complex model: {complex_model} via {complex_model_provider} "
            f"(memory_turns={memory_turns}, messages={len(narration_messages)})"
        )
        stream_usage: Any = None
        try:
            stream = await llm.stream_simple_task(
                narration_prompt,
                user_msg,
                complex_model,
                messages=narration_messages,
                max_tokens=narration_max_tokens(getattr(self.state, "narration_style", None)),
            )

            async for chunk in stream:
                stream_usage = getattr(chunk, "usage", None) or stream_usage
                choices = getattr(chunk, "choices", None)
                if not choices:
                    continue
                delta = choices[0].delta.content or ""
                if delta:
                    response_text += delta
                    yield f"event: chunk\ndata: {json.dumps({'content': delta})}\n\n"

        except Exception as e:
            if (response_text or "").strip():
                logger.warning(
                    "[Turn %s] Stream ended with exception (%s) after receiving %d chars of narrative; keeping content and completing turn.",
                    self.game_id,
                    type(e).__name__,
                    len(response_text),
                )
            else:
                user_safe_error = _friendly_llm_error_message(e)
                if user_safe_error:
                    yield f"event: error\ndata: {json.dumps({'detail': user_safe_error})}\n\n"
                    return
                raise

        token_usage = extract_usage_tokens(stream_usage) or {
            # Rough estimate when the provider reports no usage (avoids re-tokenizing the prompt).
            "prompt_tokens": int(sum(len(m.get("content", "")) for m in narration_messages) / 4),
            "completion_tokens": int(len(response_text) / 4),
            "cached_prompt_tokens": 0,
            "estimated": True,
        }
        log_structured_event(
            "gm.turn.pipeline.tokens",
            adventure_id=self.adventure.id,
            game_id=self.game_id,
            operation="chat_turn",
            phase="narration",
            model=complex_model,
            memory_turns=memory_turns,
            history_messages_count=len(narration_messages),
            **token_usage,
        )

        log_narration_budget(
            response_text,
            getattr(self.state, "narration_style", None),
            adventure_id=self.adventure.id,
            game_id=self.game_id,
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
            memory_turns=memory_turns,
            history_messages_count=len(narration_messages),
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

        if not (response_text or "").strip():
            if run_generator_tool_intent_pass:
                fallback = (
                    "The Architect inclines his head, the Construct awaiting your next directive."
                )
                if game_event and getattr(game_event, "requested_adventure_generation", None):
                    tool_results = getattr(game_event, "tool_results", None)
                    generation_success = (
                        getattr(tool_results, "generation_success", None) if tool_results else None
                    )
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
            else:
                fallback = (
                    getattr(game_event, "draft_narration", None)
                    or "The world reacts subtly, but nothing immediately obvious occurs."
                )

            response_text = fallback
            yield f"event: chunk\ndata: {json.dumps({'content': fallback})}\n\n"

        id_to_name: dict[str, str] = {}
        for entity in all_entities:
            entity_id = str(getattr(entity, "id", "") or "").strip()
            entity_name = str(getattr(entity, "name", "") or "").strip()
            if entity_id and entity_name:
                id_to_name[entity_id] = entity_name

        if isinstance(game_event, GameEvent) and game_event.updated_entities:
            for update in game_event.updated_entities:
                update_id = str(getattr(update, "entity_id", "") or "").strip()
                update_name = str(getattr(update, "name", "") or "").strip()
                if update_id and update_name:
                    id_to_name[update_id] = update_name

        # Post-narration check: If the narration described uncovering any hidden entities in the scene
        if isinstance(game_event, GameEvent):
            reveal_event = GameEvent()
            post_reveal_messages = await self._enforce_hidden_entity_reveal(
                reveal_event, user_msg, draft_narration=response_text
            )
            if post_reveal_messages and reveal_event.updated_entities:
                await self._apply_game_event(reveal_event)
                if game_event.updated_entities is None:
                    game_event.updated_entities = []
                game_event.updated_entities.extend(reveal_event.updated_entities)
                for gm in post_reveal_messages:
                    await self._save_chat_message("system", gm)
                    yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': gm})}\n\n"

        # Finalize
        assistant_chat = ChatMessage(
            session_id=self.state.session_id, role="assistant", content=response_text
        )
        self.db.add(assistant_chat)

        # Post-narration scripts (on_narration_done)
        if script_runner.scripts:
            try:
                script_ctx = await self._build_script_context()
                cs_narr = script_runner.run_trigger("on_narration_done", script_ctx)
                if cs_narr.has_changes:
                    sys_msgs = await self._apply_script_changeset(cs_narr, game_event)
                    for sm in sys_msgs:
                        role = getattr(sm, "role", "system")
                        yield f"event: {role}\ndata: {json.dumps({'role': role, 'content': str(sm)})}\n\n"
            except GameOverError as goe:
                await self._finalize_session("game_over", str(goe))
                if isinstance(game_event, GameEvent):
                    game_event.game_over = True
                    game_event.status_note = str(goe)

        # Add system messages for stat changes and items
        if isinstance(game_event, GameEvent):
            # 1. Protagonist changes
            if game_event.hp_change != 0:
                verb = "gain" if game_event.hp_change > 0 else "lose"
                msg = f"You {verb} {abs(game_event.hp_change)} HP."
                await self._save_chat_message("system", msg)
                yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg}, ensure_ascii=False)}\n\n"

            if game_event.stamina_change != 0:
                verb = "gain" if game_event.stamina_change > 0 else "lose"
                msg = f"You {verb} {abs(game_event.stamina_change)} Stamina."
                await self._save_chat_message("system", msg)
                yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg}, ensure_ascii=False)}\n\n"

            if game_event.mana_change != 0:
                verb = "gain" if game_event.mana_change > 0 else "lose"
                msg = f"You {verb} {abs(game_event.mana_change)} Mana."
                await self._save_chat_message("system", msg)
                yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg}, ensure_ascii=False)}\n\n"

            # 2. NPC/Entity changes
            if game_event.updated_entities:
                for update in game_event.updated_entities:
                    eid = update.entity_id
                    # Find name
                    ent_name = "Someone"
                    # Try to find in current entities list (from start of turn) or all entities
                    match = next((e for e in entities if e.id == eid), None)
                    if not match:
                        match = next((e for e in all_entities if e.id == eid), None)
                    if match:
                        ent_name = match.name

                    if update.is_hidden is False:
                        was_hidden = (self.state.entity_states or {}).get(eid, {}).get("is_hidden")
                        if was_hidden is None and match:
                            was_hidden = bool(getattr(match, "is_hidden", False))
                        if was_hidden:
                            msg = f"Discovered {ent_name}."
                            await self._save_chat_message("system", msg)
                            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"

                    if update.hp is not None and match and match.hp is not None:
                        diff = update.hp - match.hp
                        if diff != 0:
                            verb = "healed for" if diff > 0 else "takes"
                            msg = (
                                f"{ent_name} {verb} {abs(diff)} damage."
                                if diff < 0
                                else f"{ent_name} {verb} {diff} HP."
                            )
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
                            WorldScene.id == move.to_scene_id, WorldScene.session_id == self.game_id
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
                    is_replacement = (
                        game_event.removed_inventory_item_ids
                        and item.id in game_event.removed_inventory_item_ids
                    )
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
                        target_res = await self.db.execute(
                            select(WorldEntity).where(
                                WorldEntity.id == item_id,
                                WorldEntity.template_id == self.state.template_id,
                            )
                        )
                        target_ent = target_res.scalars().first()
                        if target_ent:
                            item_name = target_ent.name

                    msg_text = f"Removed {item_name} from your inventory."
                    await self._save_chat_message("system", msg_text)
                    yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg_text})}\n\n"

        # on_turn_end / on_turn_start run at the in-game turn boundary (scene/sequence change),
        # see advance_in_game_turn above.

        await self.db.commit()

        async for comp_event in self._compress_history_if_needed():
            yield comp_event

        checkpoint_events = await self._persist_pending_checkpoints()
        if checkpoint_events:
            yield f"event: status\ndata: {json.dumps({'content': 'Saving chronicle...'})}\n\n"
            for checkpoint_event in checkpoint_events:
                yield f"event: checkpoint\ndata: {json.dumps(checkpoint_event)}\n\n"

        map_payload = await self._build_map_payload()

        # Fetch adventure for cover image fallback
        adv_res = await self.db.execute(
            select(AdventureTemplate).where(AdventureTemplate.id == self.state.template_id)
        )
        adventure = adv_res.scalars().first()

        final_data = jsonable_encoder(
            {
                "map_data": map_payload,
                "nodes": await AdventureLogic.get_all_scene_metadata(
                    self.db, self.state.template_id, session_id=self.state.session_id
                ),
                "npc_metadata": await AdventureLogic.get_npc_metadata(
                    self.db, self.state.template_id, session_id=self.state.session_id
                ),
                "image_url": await AdventureLogic.resolve_scene_image(
                    self.db, self.state, self.state.current_scene_id
                ),
                "adventure_image": AdventureLogic.resolve_session_asset(
                    self.state, "cover", adventure.image_url if adventure else None
                ),
                "sheet": await AdventureLogic.build_sheet_snapshot(
                    self.avatar, self.state, self.db
                ),
                "entities": await AdventureLogic.build_session_entities(self.db, self.state),
                "combat": AdventureLogic.get_combat_snapshot(self.state),
                "quests": self.state.quests,
                "active_sequence": AdventureLogic.resolve_active_sequence(adventure, self.state),
                "awards": await self._build_awards_payload(adventure),
                "world_memories": self.state.world_memories or [],
                "world_rumors": self.state.world_rumors or [],
                "compressed_history": self.state.compressed_history,
                "scene_id": self.state.current_scene_id,
                "sequence_id": self.state.active_sequence_id,
                **self._build_prompt_suggestions_payload(),
                **self._build_terminal_flags_payload(),
                "status": "success",
            }
        )
        yield f"event: final\ndata: {json.dumps(final_data)}\n\n"
        if pending_generator_proposal:
            yield f"event: adventure_generator_proposal\ndata: {json.dumps(pending_generator_proposal)}\n\n"

    async def _compress_history_if_needed(self) -> AsyncGenerator[str, None]:
        """
        Automatically compresses turns that have fallen outside max_memory_turns
        into self.state.compressed_history using the configured compression model.
        Emits a system message into the chat and stream when compression occurs.
        """
        if not bool(getattr(self.state, "enable_history_compression", True)):
            return

        max_turns = getattr(self.state, "max_memory_turns", None)
        if max_turns is None and self.adventure:
            max_turns = getattr(self.adventure, "max_memory_turns", 10)
        if max_turns is None:
            max_turns = 10
        max_turns = max(1, int(max_turns))

        from backend.models.chat import ChatMessage

        res = await self.db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == self.state.session_id)
            .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        )
        all_msgs = list(res.scalars().all())
        user_indices = [i for i, m in enumerate(all_msgs) if m.role == "user"]

        if len(user_indices) <= max_turns:
            return

        cutoff_user_idx = len(user_indices) - max_turns
        cutoff_msg_idx = user_indices[cutoff_user_idx]

        msgs_outside_memory = all_msgs[:cutoff_msg_idx]
        if not msgs_outside_memory:
            return

        compressed_data = self.state.compressed_history
        current_summary = ""
        last_compressed_msg_id = None
        if isinstance(compressed_data, dict):
            current_summary = str(compressed_data.get("summary") or "")
            last_compressed_msg_id = compressed_data.get("last_compressed_msg_id")
        elif isinstance(compressed_data, str):
            current_summary = compressed_data

        start_idx = 0
        if last_compressed_msg_id:
            for idx, msg in enumerate(msgs_outside_memory):
                if msg.id == last_compressed_msg_id:
                    start_idx = idx + 1
                    break

        new_msgs_to_compress = msgs_outside_memory[start_idx:]
        if not new_msgs_to_compress:
            return

        formatted_lines = []
        for m in new_msgs_to_compress:
            if m.role not in ("user", "assistant"):
                continue
            role_label = "Player" if m.role == "user" else "Game Master"
            content = (m.content or "").strip()
            if content:
                formatted_lines.append(f"[{role_label}]: {content}")

        if not formatted_lines:
            return

        formatted_events = "\n\n".join(formatted_lines)

        llm_settings = self.user.llm_settings or {}
        compression_provider = (
            llm_settings.get("compression_model_provider")
            or llm_settings.get("small_model_provider")
            or "openai"
        )
        compression_model = (
            llm_settings.get("compression_model")
            or llm_settings.get("small_model")
            or "gpt-4o-mini"
        )

        compression_system_prompt = (
            "You are an expert narrative archivist for an interactive RPG adventure. "
            "Your task is to maintain a concise, chronological, and coherent summary of past events that have fallen outside the active memory window.\n\n"
            "CRITICAL INSTRUCTIONS:\n"
            "1. Output MUST be entirely in English, regardless of the language used in the adventure or player messages.\n"
            "2. Preserve essential facts: key plot discoveries, quests started or completed, major player decisions, important NPC relationships or grudges, major injuries/curses, and significant items acquired or lost.\n"
            "3. Omit routine turn-by-turn mechanics, repeated dice rolls, minor room transitions, or small talk.\n"
            "4. Keep the summary dense, factual, and strictly in narrative past tense."
        )

        if current_summary.strip():
            compression_user_prompt = (
                f"Existing Chronicle Summary (English):\n{current_summary.strip()}\n\n"
                f"New Past Events to Integrate (chronologically subsequent):\n{formatted_events}\n\n"
                "Provide an updated, comprehensive English chronicle summary incorporating both the existing summary and the new events."
            )
        else:
            compression_user_prompt = (
                f"Past Events to Summarize:\n{formatted_events}\n\n"
                "Provide a concise, comprehensive English chronicle summary of these past events."
            )

        try:
            router = GameMasterLLM(
                self.user,
                provider=compression_provider,
                model_category="compression",
            )
            updated_summary = await router.aexecute_simple_task(
                system_prompt=compression_system_prompt,
                user_prompt=compression_user_prompt,
                model=compression_model,
                adventure_id=self.state.template_id,
                game_id=self.game_id,
                operation="history_compression",
            )
            if updated_summary and updated_summary.strip():
                last_msg = msgs_outside_memory[-1]

                self.state.compressed_history = {
                    "summary": updated_summary.strip(),
                    "last_compressed_msg_id": last_msg.id,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
                flag_modified(self.state, "compressed_history")
                await self.db.commit()

                notify_msg = "Past turns exceeding the memory limit were automatically compressed into the chronicle memory."
                await self._save_chat_message("system", notify_msg)
                yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': notify_msg})}\n\n"
                logger.info(
                    "[Turn %s] History compression successful (%d msgs compressed, summary length %d chars)",
                    self.game_id,
                    len(new_msgs_to_compress),
                    len(updated_summary),
                )
        except Exception as e:
            logger.warning("[Turn %s] Failed to compress history: %s", self.game_id, e)

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
            "adventure_title": (self.state.session.adventure_title if self.state.session else None)
            or self.adventure.title,
            "status": status,
            "outcome_note": note,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }

        current_log = list(self.user.game_log or [])
        # Avoid duplicate entries for same session
        current_log = [entry for entry in current_log if entry.get("session_id") != self.game_id]
        current_log.append(log_entry)
        self.user.game_log = current_log
        flag_modified(self.user, "game_log")
        logger.info(f"Session {self.game_id} finalized with status {status}")

    # =========================================================================
    # DELEGATIONS TO SPECIALIZED DOMAIN MANAGERS (SRP & BACKWARD COMPATIBILITY)
    # =========================================================================

    # --- Suggestions ---
    @staticmethod
    def extract_prompt_suggestions(exit_states: Any) -> list[str]:
        return TurnSuggestionsManager.extract_prompt_suggestions(exit_states)

    @staticmethod
    def _truncate_suggestion_words(text: str, max_words: int = 6) -> str:
        return TurnSuggestionsManager._truncate_suggestion_words(text, max_words)

    @classmethod
    def _normalize_prompt_suggestions(cls, values: list[str]) -> list[str]:
        return TurnSuggestionsManager.normalize_prompt_suggestions(values)

    @staticmethod
    def _parse_json_string_array(raw: str) -> list[str]:
        return TurnSuggestionsManager.parse_json_string_array(raw)

    def _build_prompt_suggestions_payload(self, *args, **kwargs) -> dict[str, Any]:
        return self.suggestions.build_prompt_suggestions_payload(*args, **kwargs)

    def _set_prompt_suggestions_state(self, *args, **kwargs) -> None:
        self.suggestions.set_prompt_suggestions_state(*args, **kwargs)

    def _fallback_prompt_suggestions(self, *args, **kwargs) -> list[str]:
        return self.suggestions.fallback_prompt_suggestions(*args, **kwargs)

    async def _build_player_only_suggestion_context(self, *args, **kwargs) -> dict[str, Any]:
        return await self.suggestions.build_player_only_suggestion_context(*args, **kwargs)

    async def _load_last_assistant_message(self, *args, **kwargs) -> str:
        return await self.suggestions.load_last_assistant_message(*args, **kwargs)

    async def _generate_prompt_suggestions(self, *args, **kwargs) -> list[str]:
        return await self.suggestions.generate_prompt_suggestions(*args, **kwargs)

    # --- Adventure Generation & Terminal Epilogue ---
    def _get_pending_ag_image_confirmation(self, *args, **kwargs) -> dict[str, Any] | None:
        return self.adventure_gen.get_pending_ag_image_confirmation(*args, **kwargs)

    def _set_pending_ag_image_confirmation(self, *args, **kwargs) -> None:
        self.adventure_gen.set_pending_ag_image_confirmation(*args, **kwargs)

    def _clear_pending_ag_image_confirmation(self, *args, **kwargs) -> None:
        self.adventure_gen.clear_pending_ag_image_confirmation(*args, **kwargs)

    async def _classify_short_intent(self, *args, **kwargs) -> dict[str, Any] | None:
        return await self.adventure_gen.classify_short_intent(*args, **kwargs)

    async def _parse_ag_image_confirmation_decision(self, *args, **kwargs) -> str:
        return await self.adventure_gen.parse_ag_image_confirmation_decision(*args, **kwargs)

    async def _is_generation_retry_request(self, *args, **kwargs) -> bool:
        return await self.adventure_gen.is_generation_retry_request(*args, **kwargs)

    @staticmethod
    def _contains_transition_movement_cue(text: str) -> bool:
        return TurnAdventureGenManager.contains_transition_movement_cue(text)

    def _message_mentions_transition_target(self, *args, **kwargs) -> bool:
        return self.adventure_gen.message_mentions_transition_target(*args, **kwargs)

    async def _is_explicit_scene_transition_request(self, *args, **kwargs) -> bool:
        return await self.adventure_gen.is_explicit_scene_transition_request(*args, **kwargs)

    def _set_last_ag_generation_request(self, *args, **kwargs) -> None:
        self.adventure_gen.set_last_ag_generation_request(*args, **kwargs)

    def _get_last_ag_generation_request(self, *args, **kwargs) -> Any:
        return self.adventure_gen.get_last_ag_generation_request(*args, **kwargs)

    def _set_last_ag_generation_error(self, *args, **kwargs) -> None:
        self.adventure_gen.set_last_ag_generation_error(*args, **kwargs)

    def _get_last_ag_generation_error(self, *args, **kwargs) -> str | None:
        return self.adventure_gen.get_last_ag_generation_error(*args, **kwargs)

    async def _stream_adventure_generator_tools(self, *args, **kwargs) -> AsyncGenerator[str, None]:
        async for item in self.adventure_gen.stream_adventure_generator_tools(*args, **kwargs):
            yield item

    async def _apply_adventure_generator_tools(self, *args, **kwargs) -> None:
        return await self.adventure_gen.apply_adventure_generator_tools(*args, **kwargs)

    async def _generate_terminal_epilogue_text(self, *args, **kwargs) -> str:
        return await self.adventure_gen.generate_terminal_epilogue_text(*args, **kwargs)

    async def create_terminal_epilogue(self, *args, **kwargs) -> dict[str, Any]:
        return await self.adventure_gen.create_terminal_epilogue(*args, **kwargs)

    # --- Combat ---
    def _read_combat_state(self, *args, **kwargs) -> dict[str, Any]:
        return self.combat._read_combat_state(*args, **kwargs)

    def _is_combat_active(self, *args, **kwargs) -> bool:
        return self.combat._is_combat_active(*args, **kwargs)

    def _has_combat_phase(self, *args, **kwargs) -> bool:
        return self.combat._has_combat_phase(*args, **kwargs)

    def _set_combat_state(self, *args, **kwargs) -> None:
        self.combat._set_combat_state(*args, **kwargs)

    async def _find_fight_target(self, *args, **kwargs) -> WorldEntity | None:
        return await self.combat._find_fight_target(*args, **kwargs)

    async def _find_scene_npc_by_hint(self, *args, **kwargs) -> WorldEntity | None:
        return await self.combat._find_scene_npc_by_hint(*args, **kwargs)

    def _is_npc_defeated(self, *args, **kwargs) -> bool:
        return self.combat._is_npc_defeated(*args, **kwargs)

    def _entity_stat(self, *args, **kwargs) -> int:
        return self.combat._entity_stat(*args, **kwargs)

    def _is_npc_killable(self, *args, **kwargs) -> bool:
        return self.combat._is_npc_killable(*args, **kwargs)

    def _player_damage_dice(self, *args, **kwargs) -> str:
        return self.combat._player_damage_dice(*args, **kwargs)

    def _enemy_damage_dice(self, *args, **kwargs) -> str:
        return self.combat._enemy_damage_dice(*args, **kwargs)

    def _append_combat_log(self, *args, **kwargs) -> None:
        self.combat._append_combat_log(*args, **kwargs)

    def _emit_combat_final(self, *args, **kwargs) -> Any:
        return self.combat._emit_combat_final(*args, **kwargs)

    async def _emit_combat_aftermath_narration(self, *args, **kwargs) -> AsyncGenerator[str, None]:
        async for item in self.combat._emit_combat_aftermath_narration(*args, **kwargs):
            yield item

    def _calculate_npc_total_stats(self, *args, **kwargs) -> dict[str, int]:
        return self.combat._calculate_npc_total_stats(*args, **kwargs)

    async def _handle_fight_start(self, *args, **kwargs) -> AsyncGenerator[str, None]:
        async for item in self.combat._handle_fight_start(*args, **kwargs):
            yield item

    def _auto_trigger_combat_from_gm(self, *args, **kwargs) -> Any:
        return self.combat._auto_trigger_combat_from_gm(*args, **kwargs)

    def _find_consumable(self, *args, **kwargs) -> dict[str, Any] | None:
        return self.combat._find_consumable(*args, **kwargs)

    def _sync_combat_player_snapshot(self, *args, **kwargs) -> None:
        self.combat._sync_combat_player_snapshot(*args, **kwargs)

    def _description_delta(self, *args, **kwargs) -> dict[str, int]:
        return self.combat._description_delta(*args, **kwargs)

    def _resource_delta_from_consumable(self, *args, **kwargs) -> dict[str, int]:
        return self.combat._resource_delta_from_consumable(*args, **kwargs)

    @staticmethod
    def _parse_json_object(text: str) -> dict[str, Any] | None:
        return TurnGuardrailsManager._parse_json_object(text)

    async def _request_llm_combat_special_event(self, *args, **kwargs) -> dict[str, Any] | None:
        return await self.combat._request_llm_combat_special_event(*args, **kwargs)

    def _consume_item_now(self, *args, **kwargs) -> dict[str, Any]:
        return self.combat._consume_item_now(*args, **kwargs)

    async def _maybe_trigger_special_event(
        self, *args, **kwargs
    ) -> tuple[dict[str, Any] | None, list[str]]:
        return await self.combat._maybe_trigger_special_event(*args, **kwargs)

    async def _resolve_enemy_turn(self, *args, **kwargs) -> Any:
        return self.combat._resolve_enemy_turn(*args, **kwargs)

    async def _spawn_scene_item(self, *args, **kwargs) -> WorldEntity:
        return await self.combat._spawn_scene_item(*args, **kwargs)

    async def _session_entity_id_exists(self, *args, **kwargs) -> bool:
        return await self.combat._session_entity_id_exists(*args, **kwargs)

    async def _collect_existing_item_ids(self, *args, **kwargs) -> set[str]:
        return await self.combat._collect_existing_item_ids(*args, **kwargs)

    def _normalize_loot_items(self, *args, **kwargs) -> list[dict[str, Any]]:
        return self.combat._normalize_loot_items(*args, **kwargs)

    def _resolve_loot_command(self, *args, **kwargs) -> tuple[bool, list[str], bool]:
        return self.combat._resolve_loot_command(*args, **kwargs)

    def _award_combat_victory_xp(self, *args, **kwargs) -> int:
        return self.combat._award_combat_victory_xp(*args, **kwargs)

    async def _handle_combat_turn(self, *args, **kwargs) -> AsyncGenerator[str, None]:
        async for item in self.combat._handle_combat_turn(*args, **kwargs):
            yield item

    # --- Guardrails ---
    @staticmethod
    def _normalize_target_token(value: str) -> str:
        return TurnGuardrailsManager._normalize_target_token(value)

    @staticmethod
    def _sanitize_inspect_or_search_target(raw_target: str) -> str | None:
        return TurnGuardrailsManager._sanitize_inspect_or_search_target(raw_target)

    async def _extract_inspect_or_search_target(self, *args, **kwargs) -> str | None:
        return await self.guardrails._extract_inspect_or_search_target(*args, **kwargs)

    async def _collect_inspect_search_visibility_tokens(self, *args, **kwargs) -> set[str]:
        return await self.guardrails._collect_inspect_search_visibility_tokens(*args, **kwargs)

    async def _is_inspect_or_search_target_visible(self, *args, **kwargs) -> bool:
        return await self.guardrails._is_inspect_or_search_target_visible(*args, **kwargs)

    async def _guard_non_visible_inspect_or_search(self, *args, **kwargs) -> str | None:
        return await self.guardrails._guard_non_visible_inspect_or_search(*args, **kwargs)

    def _is_container_item(self, *args, **kwargs) -> bool:
        return self.guardrails._is_container_item(*args, **kwargs)

    def _is_container_locked(self, *args, **kwargs) -> bool:
        return self.guardrails._is_container_locked(*args, **kwargs)

    def _extract_access_code(self, *args, **kwargs) -> str | None:
        return self.guardrails._extract_access_code(*args, **kwargs)

    async def _resolve_container_from_free_text(self, *args, **kwargs) -> WorldEntity | None:
        return await self.guardrails._resolve_container_from_free_text(*args, **kwargs)

    async def _enforce_no_dynamic_item_generation(self, *args, **kwargs) -> list[str]:
        return await self.guardrails._enforce_no_dynamic_item_generation(*args, **kwargs)

    async def _enforce_constructable_combination(self, *args, **kwargs) -> list[str]:
        return await self.guardrails._enforce_constructable_combination(*args, **kwargs)

    async def _enforce_hidden_entity_reveal(self, *args, **kwargs) -> list[str]:
        return await self.guardrails._enforce_hidden_entity_reveal(*args, **kwargs)

    def _is_key_item_referenced(self, *args, **kwargs) -> bool:
        return self.guardrails._is_key_item_referenced(*args, **kwargs)

    def _get_switch_story_flags(self, *args, **kwargs) -> dict[str, bool]:
        return self.guardrails._get_switch_story_flags(*args, **kwargs)

    async def _enforce_container_unlock_guardrails(self, *args, **kwargs) -> list[str]:
        return await self.guardrails._enforce_container_unlock_guardrails(*args, **kwargs)

    async def _enforce_exit_unlock_guardrails(self, *args, **kwargs) -> list[str]:
        return await self.guardrails._enforce_exit_unlock_guardrails(*args, **kwargs)

    async def _enforce_switch_transition_guardrails(self, *args, **kwargs) -> list[str]:
        return await self.guardrails._enforce_switch_transition_guardrails(*args, **kwargs)

    async def _enforce_npc_movement_guardrails(self, *args, **kwargs) -> list[str]:
        return await self.guardrails._enforce_npc_movement_guardrails(*args, **kwargs)

    async def _enforce_quest_and_award_guardrails(self, *args, **kwargs) -> list[str]:
        return await self.guardrails._enforce_quest_and_award_guardrails(*args, **kwargs)

    async def _enforce_win_and_loss_guardrails(self, *args, **kwargs) -> list[str]:
        return await self.guardrails._enforce_win_and_loss_guardrails(*args, **kwargs)

    async def _handle_read_action_unlock(self, *args, **kwargs) -> list[str]:
        return await self.guardrails._handle_read_action_unlock(*args, **kwargs)

    async def _check_special_action_unlocks(self, *args, **kwargs) -> list[str]:
        return await self.guardrails._check_special_action_unlocks(*args, **kwargs)

    # --- Interactions ---
    async def _handle_traverse_exit(self, *args, **kwargs) -> AsyncGenerator[str, None]:
        async for item in self.interactions._handle_traverse_exit(*args, **kwargs):
            yield item

    async def _handle_debug(self, *args, **kwargs) -> AsyncGenerator[str, None]:
        async for item in self.interactions._handle_debug(*args, **kwargs):
            yield item

    async def _handle_debug_gen_item(self, *args, **kwargs) -> AsyncGenerator[str, None]:
        async for item in self.interactions._handle_debug_gen_item(*args, **kwargs):
            yield item

    async def _debug_drop_npc_items(self, *args, **kwargs) -> Any:
        return await self.interactions._debug_drop_npc_items(*args, **kwargs)

    def _is_switch_entity(self, *args, **kwargs) -> bool:
        return self.interactions._is_switch_entity(*args, **kwargs)

    def _switch_config(self, *args, **kwargs) -> dict[str, Any]:
        return self.interactions._switch_config(*args, **kwargs)

    def _parse_switch_args(self, *args, **kwargs) -> Any:
        return self.interactions._parse_switch_args(*args, **kwargs)

    async def _resolve_scene_switch(self, *args, **kwargs) -> WorldEntity | None:
        return await self.interactions._resolve_scene_switch(*args, **kwargs)

    def _switch_story_flags(self, *args, **kwargs) -> dict[str, bool]:
        return self.interactions._switch_story_flags(*args, **kwargs)

    def _set_switch_story_flag(self, *args, **kwargs) -> None:
        self.interactions._set_switch_story_flag(*args, **kwargs)

    def _avatar_inventory_ids(self, *args, **kwargs) -> set[str]:
        return self.interactions._avatar_inventory_ids(*args, **kwargs)

    async def _apply_switch_outcomes(self, *args, **kwargs) -> list[str]:
        return await self.interactions._apply_switch_outcomes(*args, **kwargs)

    async def _execute_switch_command(self, *args, **kwargs) -> AsyncGenerator[str, None]:
        async for item in self.interactions._execute_switch_command(*args, **kwargs):
            yield item

    async def _handle_slash(self, *args, **kwargs) -> AsyncGenerator[str, None]:
        async for item in self.interactions._handle_slash(*args, **kwargs):
            yield item

    async def _resolve_container_target(
        self, *args, **kwargs
    ) -> tuple[WorldEntity | None, int | None]:
        return await self.interactions._resolve_container_target(*args, **kwargs)

    def _get_container_inventory(self, *args, **kwargs) -> list[dict[str, Any]]:
        return self.interactions._get_container_inventory(*args, **kwargs)

    def _normalize_container_item_ref(
        self, *args, **kwargs
    ) -> tuple[dict[str, Any] | None, int | None]:
        return self.interactions._normalize_container_item_ref(*args, **kwargs)

    def _normalize_container_items(self, *args, **kwargs) -> list[dict[str, Any]]:
        return self.interactions._normalize_container_items(*args, **kwargs)

    async def _move_container_item_to_inventory(self, *args, **kwargs) -> tuple[bool, str]:
        return await self.interactions._move_container_item_to_inventory(*args, **kwargs)

    async def _move_container_item_to_scene(self, *args, **kwargs) -> tuple[bool, str]:
        return await self.interactions._move_container_item_to_scene(*args, **kwargs)

    async def _clear_container_inventory(self, *args, **kwargs) -> list[dict[str, Any]]:
        return await self.interactions._clear_container_inventory(*args, **kwargs)

    # --- State Applier ---
    def _upsert_entity_update(self, *args, **kwargs) -> None:
        applier = getattr(self, "state_applier", None)
        if applier is None or not hasattr(applier, "_upsert_entity_update"):
            applier = TurnStateApplier(self)
        applier._upsert_entity_update(*args, **kwargs)

    def _upsert_entity_movement(self, *args, **kwargs) -> None:
        applier = getattr(self, "state_applier", None)
        if applier is None or not hasattr(applier, "_upsert_entity_movement"):
            applier = TurnStateApplier(self)
        applier._upsert_entity_movement(*args, **kwargs)

    async def _build_map_payload(self, *args, **kwargs) -> dict[str, Any]:
        applier = getattr(self, "state_applier", None)
        if applier is None or not hasattr(applier, "_build_map_payload"):
            applier = TurnStateApplier(self)
        return await applier._build_map_payload(*args, **kwargs)

    async def _build_awards_payload(self, *args, **kwargs) -> dict[str, Any]:
        applier = getattr(self, "state_applier", None)
        if applier is None or not hasattr(applier, "_build_awards_payload"):
            applier = TurnStateApplier(self)
        return await applier._build_awards_payload(*args, **kwargs)

    async def _apply_game_event(self, *args, **kwargs) -> list[str]:
        applier = getattr(self, "state_applier", None)
        if applier is None or not hasattr(applier, "_apply_game_event"):
            applier = TurnStateApplier(self)
        return await applier._apply_game_event(*args, **kwargs)

    async def _build_script_context(self) -> GameContext:
        """Builds an isolated GameContext for the scripting sandbox, covering all entities in the session."""
        ent_res = await self.db.execute(
            select(WorldEntity).where(WorldEntity.session_id == self.state.session_id)
        )
        base_entities = [
            {c.name: getattr(e, c.name) for c in e.__table__.columns}
            for e in ent_res.scalars().all()
        ]
        session_overrides = self.state.entity_states or {}
        norm_overrides_by_id = {
            str(k).strip().upper(): v for k, v in session_overrides.items() if isinstance(v, dict)
        }

        entities_map: dict[str, dict[str, Any]] = {}
        for ent in base_entities:
            eid = ent.get("id")
            if not eid:
                continue
            eid_upper = str(eid).strip().upper()
            if eid in session_overrides:
                ent.update(session_overrides[eid])
            elif eid_upper in norm_overrides_by_id:
                ent.update(norm_overrides_by_id[eid_upper])
            entities_map[eid] = ent

        manifest = getattr(self.adventure, "original_manifest", None) or {}
        template_entities = (
            manifest.get("entities") or getattr(self.adventure, "entities", None) or []
        )
        for tent in template_entities:
            if isinstance(tent, dict) and tent.get("id") and tent.get("id") not in entities_map:
                eid = tent.get("id")
                ent_copy = dict(tent)
                eid_upper = str(eid).strip().upper()
                if eid in session_overrides:
                    ent_copy.update(session_overrides[eid])
                elif eid_upper in norm_overrides_by_id:
                    ent_copy.update(norm_overrides_by_id[eid_upper])
                entities_map[eid] = ent_copy

        script_vars = dict(session_overrides.get("__script_vars__", {}))
        story_flags = dict(session_overrides.get("__switch_story_flags__", {}))

        avatar_dict = {
            "name": self.avatar.name,
            "hp": self.avatar.hp,
            "mana": self.avatar.mana,
            "stamina": self.avatar.stamina,
            "inventory": list(self.avatar.inventory or []),
            "status_effects": list(self.avatar.status_effects or []),
        }

        is_debug = bool(
            settings.TALEWEAVER_DEBUG_ENABLED
            or (self.state and getattr(self.state, "is_debug_enabled", False))
        )
        return GameContext(
            avatar_data=avatar_dict,
            current_scene_id=self.state.current_scene_id,
            entities=entities_map,
            exit_states=self.state.exit_states or {},
            quests=self.state.quests or [],
            script_vars=script_vars,
            in_game_time=self.state.in_game_time,
            story_flags=story_flags,
            is_debug_enabled=is_debug,
        )

    def _get_script_runner(self) -> ScriptRunner:
        """Instantiates ScriptRunner with the top-level and active-sequence scripts and init_script."""
        manifest = getattr(self.adventure, "original_manifest", None) or {}
        active_sequence = AdventureLogic.resolve_active_sequence(self.adventure, self.state)
        scripts = [*manifest.get("scripts", []), *sequence_scripts(active_sequence)]
        init_script = manifest.get("init_script") or getattr(self.adventure, "init_script", None)
        return ScriptRunner(scripts, init_script=init_script)

    async def _execute_inline_script(
        self,
        code: str,
        trigger_name: str,
        target_id: str,
        extra_scope: dict[str, Any] | None = None,
    ) -> list[str]:
        if not code or not code.strip():
            return []
        context = await self._build_script_context()
        runner = self._get_script_runner()
        scope = {**(extra_scope or {}), "tw": context, "game": context}
        runner.execute_code(code, scope, script_id=f"inline_{trigger_name}_{target_id}")
        applied_messages = await self._apply_script_changeset(context.changeset)
        if context.is_debug_enabled:
            debug_msg = f"[DEBUG: Trigger fired] {trigger_name} on {target_id}"
            await self._save_chat_message("system", debug_msg)
        return [
            str(m)
            for m in applied_messages
            if not str(getattr(m, "content", m)).strip().startswith("[DEBUG")
        ]

    async def _apply_script_changeset(
        self, changeset: ScriptChangeset, game_event: Any = None
    ) -> list[str]:
        """Applies mutations from ScriptChangeset to models and returns narrative messages."""
        system_messages: list[str] = []

        if changeset.player_hp_change:
            self.avatar.hp = max(0, min(RESOURCE_CAP, self.avatar.hp + changeset.player_hp_change))
            verb = "gain" if changeset.player_hp_change > 0 else "lose"
            system_messages.append(
                ScriptMessage(
                    f"You {verb} {abs(changeset.player_hp_change)} HP (Script).", role="system"
                )
            )
            if not getattr(self, "_in_protagonist_hp_trigger", False):
                self._in_protagonist_hp_trigger = True
                try:
                    prot_meta = getattr(self.avatar, "stats", None) or {}
                    if prot_meta.get("on_hp_change_script"):
                        hp_msgs = await self._execute_inline_script(
                            prot_meta["on_hp_change_script"], "on_hp_change", "protagonist"
                        )
                        system_messages.extend(hp_msgs)
                    if prot_meta.get("on_hp_change_text"):
                        await self._save_chat_message("system", prot_meta["on_hp_change_text"])
                        system_messages.append(
                            ScriptMessage(prot_meta["on_hp_change_text"], role="system")
                        )
                finally:
                    self._in_protagonist_hp_trigger = False
            if self.avatar.hp <= 0:
                raise GameOverError(f"{self.avatar.name} has fallen! Game Over.")

        if changeset.player_mana_change:
            self.avatar.mana = max(
                0, min(RESOURCE_CAP, self.avatar.mana + changeset.player_mana_change)
            )
            verb = "gain" if changeset.player_mana_change > 0 else "lose"
            system_messages.append(
                ScriptMessage(
                    f"You {verb} {abs(changeset.player_mana_change)} Mana (Script).", role="system"
                )
            )

        if changeset.player_stamina_change:
            self.avatar.stamina = max(
                0, min(RESOURCE_CAP, self.avatar.stamina + changeset.player_stamina_change)
            )
            verb = "gain" if changeset.player_stamina_change > 0 else "lose"
            system_messages.append(
                ScriptMessage(
                    f"You {verb} {abs(changeset.player_stamina_change)} Stamina (Script).",
                    role="system",
                )
            )

        if changeset.player_new_items:
            inv = list(self.avatar.inventory or [])
            for it in changeset.player_new_items:
                inv.append(it)
                system_messages.append(
                    ScriptMessage(f"Acquired: {it.get('name', it.get('id'))}", role="system")
                )
            self.avatar.inventory = inv

        if changeset.player_removed_item_ids:
            inv = [
                it
                for it in (self.avatar.inventory or [])
                if (it.get("id") if isinstance(it, dict) else it)
                not in changeset.player_removed_item_ids
            ]
            self.avatar.inventory = inv

        if changeset.player_status_effects_add or changeset.player_status_effects_remove:
            effs = set(self.avatar.status_effects or [])
            effs.update(changeset.player_status_effects_add)
            effs.difference_update(changeset.player_status_effects_remove)
            self.avatar.status_effects = list(effs)
            if not getattr(self, "_in_protagonist_status_trigger", False):
                self._in_protagonist_status_trigger = True
                try:
                    prot_meta = getattr(self.avatar, "stats", None) or {}
                    if prot_meta.get("on_status_change_script"):
                        st_msgs = await self._execute_inline_script(
                            prot_meta["on_status_change_script"], "on_status_change", "protagonist"
                        )
                        system_messages.extend(st_msgs)
                    if prot_meta.get("on_status_change_text"):
                        await self._save_chat_message("system", prot_meta["on_status_change_text"])
                        system_messages.append(
                            ScriptMessage(prot_meta["on_status_change_text"], role="system")
                        )
                finally:
                    self._in_protagonist_status_trigger = False

        if changeset.teleport_scene_id:
            self.state.current_scene_id = changeset.teleport_scene_id

        entity_states = dict(self.state.entity_states or {})
        for move in changeset.entity_movements:
            eid = move["entity_id"]
            st = dict(entity_states.get(eid, {}))
            st["current_scene_id"] = move["to_scene_id"]
            if move.get("to_spatial_position"):
                st["spatial_position"] = move["to_spatial_position"]
            entity_states[eid] = st

        for upd in changeset.entity_updates:
            eid = upd["entity_id"]
            st = dict(entity_states.get(eid, {}))
            for k, v in upd.items():
                if k != "entity_id":
                    st[k] = v
            entity_states[eid] = st

        if changeset.var_updates:
            script_vars = dict(entity_states.get("__script_vars__", {}))
            script_vars.update(changeset.var_updates)
            entity_states["__script_vars__"] = script_vars

        if changeset.story_flag_updates:
            story_flags = dict(entity_states.get("__switch_story_flags__", {}))
            story_flags.update(changeset.story_flag_updates)
            entity_states["__switch_story_flags__"] = story_flags

        store_pending_dialog(entity_states, changeset.pending_dialog)
        self.state.entity_states = entity_states
        flag_modified(self.state, "entity_states")

        # Sync modified fields to WorldEntity DB records if present
        if changeset.entity_movements or changeset.entity_updates:
            affected_ids = {m["entity_id"] for m in changeset.entity_movements} | {
                u["entity_id"] for u in changeset.entity_updates
            }
            for aid in affected_ids:
                st = entity_states.get(aid, {})
                db_ent_res = await self.db.execute(
                    select(WorldEntity).where(
                        WorldEntity.session_id == self.state.session_id, WorldEntity.id == aid
                    )
                )
                db_ent = db_ent_res.scalar_one_or_none()
                if db_ent:
                    if "current_scene_id" in st:
                        db_ent.current_scene_id = st["current_scene_id"]
                    if "spatial_position" in st:
                        db_ent.spatial_position = st["spatial_position"]
                    if "hp" in st and hasattr(db_ent, "hp"):
                        db_ent.hp = st["hp"]
                    if "is_defeated" in st:
                        if hasattr(db_ent, "is_defeated"):
                            db_ent.is_defeated = st["is_defeated"]
                        elif hasattr(db_ent, "metadata_json") and isinstance(
                            db_ent.metadata_json, dict
                        ):
                            meta = dict(db_ent.metadata_json)
                            meta["is_defeated"] = st["is_defeated"]
                            db_ent.metadata_json = meta
                    if "inventory" in st and hasattr(db_ent, "inventory"):
                        db_ent.inventory = st["inventory"]
                    if "is_hidden" in st and hasattr(db_ent, "is_hidden"):
                        db_ent.is_hidden = st["is_hidden"]
                    if "is_in_inventory" in st and hasattr(db_ent, "is_in_inventory"):
                        db_ent.is_in_inventory = st["is_in_inventory"]

        for npc_id in changeset.npc_attack_requests:
            if npc_id not in self.pending_npc_attacks:
                self.pending_npc_attacks.append(npc_id)

        if changeset.exit_updates:
            exit_states = dict(self.state.exit_states or {})
            for eu in changeset.exit_updates:
                k = f"{eu['from_scene_id']}:{eu['to_scene_id']}"
                st = dict(exit_states.get(k, {}))
                st["is_locked"] = eu["is_locked"]
                if "lock_description" in eu:
                    st["lock_description"] = eu["lock_description"]
                exit_states[k] = st
            self.state.exit_states = exit_states
            flag_modified(self.state, "exit_states")

        for msg in changeset.narrative_messages:
            system_messages.append(ScriptMessage(msg, role="assistant"))
            await self._save_chat_message("assistant", msg)

        for msg in getattr(changeset, "system_messages", []):
            system_messages.append(ScriptMessage(msg, role="system"))
            await self._save_chat_message("system", msg)

        if changeset.new_memories:
            memories = list(self.state.world_memories or [])
            for m in changeset.new_memories:
                is_dup = any(
                    (em.get("description") or "").strip().lower()
                    == (m.get("description") or "").strip().lower()
                    and em.get("scope") == m.get("scope")
                    and (m.get("scope") == "global" or em.get("scene_id") == m.get("scene_id"))
                    for em in memories
                )
                if not is_dup:
                    memories.append(m)
            self.state.world_memories = memories

        for qid in changeset.completed_quest_ids:
            quests = list(self.state.quests or [])
            for q in quests:
                if isinstance(q, dict) and q.get("id") == qid:
                    q["status"] = "completed"
            self.state.quests = quests

        if changeset.completed_condition_override:
            self.state.completed_condition = changeset.completed_condition_override
        if changeset.gameover_condition_override:
            self.state.gameover_condition = changeset.gameover_condition_override
        if changeset.completed_guard_expression_override:
            self.state.completed_guard_expression = changeset.completed_guard_expression_override
        if changeset.gameover_guard_expression_override:
            self.state.gameover_guard_expression = changeset.gameover_guard_expression_override

        if changeset.game_completed:
            await self._finalize_session("completed", changeset.status_note)
        elif changeset.game_over:
            raise GameOverError(changeset.status_note or f"{self.avatar.name} has met their end.")

        if (
            changeset.sequence_completed
            and hasattr(self.adventure, "sequences")
            and self.adventure.sequences
        ):
            sequences = sorted(self.adventure.sequences, key=lambda x: x.get("order", 1))
            current_seq_idx = -1

            for i, seq in enumerate(sequences):
                if seq.get("id") == self.state.active_sequence_id or (
                    not self.state.active_sequence_id and i == 0
                ):
                    current_seq_idx = i
                    break

            if current_seq_idx >= 0:
                completed_seq = sequences[current_seq_idx]
                seq_title = (
                    completed_seq.get("title")
                    or completed_seq.get("id")
                    or f"Chapter {current_seq_idx + 1}"
                )

                if completed_seq.get("on_end_sequence_script"):
                    end_msgs = await self._execute_inline_script(
                        completed_seq["on_end_sequence_script"],
                        "on_end_sequence",
                        completed_seq.get("id", f"seq_{current_seq_idx}"),
                    )
                    system_messages.extend(end_msgs)
                if completed_seq.get("on_end_sequence_text"):
                    await self._save_chat_message("system", completed_seq["on_end_sequence_text"])
                    system_messages.append(completed_seq["on_end_sequence_text"])

                xp_reward = int(completed_seq.get("exp_reward") or 0)
                if xp_reward > 0:
                    self.avatar.exp = (self.avatar.exp or 0) + xp_reward
                    xp_msg = f"Sequence completed: {seq_title} (+{xp_reward} XP)"
                else:
                    xp_msg = f"Sequence completed: {seq_title}"
                await self._save_chat_message("system", xp_msg)
                system_messages.append(xp_msg)

                next_seq_idx = current_seq_idx + 1
                if next_seq_idx < len(sequences):
                    next_seq = sequences[next_seq_idx]
                    self.state.active_sequence_id = next_seq.get("id")
                    self.state.active_sequence_order = next_seq.get("order", next_seq_idx + 1)

                    next_title = next_seq.get("title") or next_seq.get("id")
                    next_msg = f"New Sequence unlocked: {next_title}"
                    await self._save_chat_message("system", next_msg)
                    system_messages.append(next_msg)

                    if next_seq.get("on_start_sequence_script"):
                        start_msgs = await self._execute_inline_script(
                            next_seq["on_start_sequence_script"],
                            "on_start_sequence",
                            next_seq.get("id", f"seq_{next_seq_idx}"),
                        )
                        system_messages.extend(start_msgs)
                    if next_seq.get("on_start_sequence_text"):
                        await self._save_chat_message("system", next_seq["on_start_sequence_text"])
                        system_messages.append(next_seq["on_start_sequence_text"])
                else:
                    await self._finalize_session(
                        "completed", "Congratulations! You have completed the final sequence."
                    )

        return [
            m
            for m in system_messages
            if not str(getattr(m, "content", m)).strip().startswith("[DEBUG")
        ]
