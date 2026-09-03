from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from backend.core import prompts
from backend.core.llm_router import GameMasterLLM
from backend.models.chat import ChatMessage
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene

if TYPE_CHECKING:
    from backend.api.routes.adventures.gameplay_logic import GameTurnManager

logger = logging.getLogger(__name__)

PROMPT_SUGGESTIONS_STATE_KEY = "__prompt_suggestions__"
PROMPT_SUGGESTION_MAX_VISIBLE_NPCS = 12
PROMPT_SUGGESTION_MAX_VISIBLE_OBJECTS = 16
PROMPT_SUGGESTION_MAX_UNLOCKED_EXITS = 8
PROMPT_SUGGESTION_MAX_INVENTORY_ITEMS = 16
PROMPT_SUGGESTION_MAX_LAST_RESPONSE_CHARS = 1200


class TurnSuggestionsManager:
    """Manages player prompt suggestions generation, fallback, and state persistence."""

    def __init__(self, manager: GameTurnManager) -> None:
        self.manager = manager

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
    def normalize_prompt_suggestions(cls, values: list[str]) -> list[str]:
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
    def parse_json_string_array(raw: str) -> list[str]:
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

    def build_prompt_suggestions_payload(self) -> dict[str, Any]:
        return {"prompt_suggestions": self.extract_prompt_suggestions(self.manager.state.exit_states or {})}

    def set_prompt_suggestions_state(self, suggestions: list[str]) -> None:
        exit_states = dict(self.manager.state.exit_states or {})
        normalized = self.normalize_prompt_suggestions(suggestions)
        if normalized:
            exit_states[PROMPT_SUGGESTIONS_STATE_KEY] = normalized
        else:
            exit_states.pop(PROMPT_SUGGESTIONS_STATE_KEY, None)
        self.manager.state.exit_states = exit_states
        flag_modified(self.manager.state, "exit_states")

    def fallback_prompt_suggestions(
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
        return self.normalize_prompt_suggestions(fallback)

    async def build_player_only_suggestion_context(self) -> dict[str, Any]:
        """Build a spoiler-safe suggestion context (visible NPCs/objects, unlocked exits, inventory)."""
        scene_res = await self.manager.db.execute(
            select(WorldScene).where(
                WorldScene.id == self.manager.state.current_scene_id,
                WorldScene.session_id == self.manager.game_id,
            )
        )
        current_scene = scene_res.scalars().first()
        scene_label = current_scene.label if current_scene else self.manager.state.current_scene_id or "Current Scene"
        scene_description = current_scene.description if current_scene else ""

        ent_res = await self.manager.db.execute(
            select(WorldEntity).where(
                WorldEntity.session_id == self.manager.game_id,
                WorldEntity.current_scene_id == self.manager.state.current_scene_id,
            )
        )
        entities = list(ent_res.scalars().all())
        states = self.manager.state.entity_states or {}
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

        exits_res = await self.manager.db.execute(
            select(WorldExit).where(
                WorldExit.session_id == self.manager.game_id,
                WorldExit.from_scene_id == self.manager.state.current_scene_id,
            )
        )
        unlocked_exits = [ex.label for ex in exits_res.scalars().all() if not ex.is_locked]

        inventory_items = [
            str(item.get("name") or item.get("id") or "").strip()
            for item in (self.manager.avatar.inventory or [])
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

    async def load_last_assistant_message(self) -> str:
        res = await self.manager.db.execute(
            select(ChatMessage.content)
            .where(
                ChatMessage.session_id == self.manager.state.session_id,
                ChatMessage.role == "assistant",
            )
            .order_by(ChatMessage.created_at.desc())
            .limit(1)
        )
        value = res.scalar_one_or_none()
        return str(value or "").strip()

    async def generate_prompt_suggestions(self, last_response: str) -> list[str]:
        """Generate three short UI prompt suggestions, with deterministic fallback and state persistence."""
        context = await self.build_player_only_suggestion_context()
        fallback = self.fallback_prompt_suggestions(
            scene_label=context["scene_label"],
            visible_objects=context["visible_objects"],
            visible_npcs=context["visible_npcs"],
            inventory_items=context["inventory_items"],
        )
        llm_settings = self.manager.user.llm_settings or {}
        provider = (
            llm_settings.get("small_model_provider")
            or llm_settings.get("complex_model_provider")
            or llm_settings.get("preferred_provider")
            or "openai"
        )
        model = llm_settings.get("small_model") or "gpt-4o-mini"

        suggestions: list[str] = []
        try:
            llm = GameMasterLLM(self.manager.user, provider=provider, model_category="small")
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
                adventure_id=self.manager.state.template_id,
                game_id=self.manager.game_id,
                operation="chat_turn",
                phase="prompt_suggestions",
            )
            suggestions = self.normalize_prompt_suggestions(self.parse_json_string_array(raw))
        except Exception as exc:
            logger.warning("[Turn %s] Prompt suggestion generation failed: %s", self.manager.game_id, exc)

        if len(suggestions) < 3:
            suggestions = self.normalize_prompt_suggestions(suggestions + fallback)
        self.set_prompt_suggestions_state(suggestions[:3])
        return suggestions[:3]
