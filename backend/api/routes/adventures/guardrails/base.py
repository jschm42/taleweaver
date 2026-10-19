"""Shared accessors and helpers for the Pass 1.5 guardrail mixins."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from backend.engine.rule_engine import EntityMovement, GameEvent, WorldEntityUpdate
from backend.models.world_entity import WorldEntity

if TYPE_CHECKING:
    from backend.api.routes.adventures.gameplay_logic import GameTurnManager

DEFAULT_SMALL_MODEL = "gpt-4o-mini"


@dataclass(frozen=True)
class EntityView:
    """Where an entity effectively is right now (session overrides applied)."""

    scene_id: str | None
    hidden: bool
    in_inventory: bool


def entity_view(ent: WorldEntity, states: dict[str, Any]) -> EntityView:
    override = states.get(ent.id, {}) if isinstance(states, dict) else {}
    return EntityView(
        scene_id=override.get("current_scene_id", ent.current_scene_id),
        hidden=bool(override.get("is_hidden", ent.is_hidden)),
        in_inventory=bool(override.get("is_in_inventory", ent.is_in_inventory)),
    )


def item_id_upper(item: Any) -> str:
    return str(getattr(item, "id", None) or getattr(item, "entity_id", None) or "").strip().upper()


def inventory_ids_upper(inventory: list[Any] | None) -> set[str]:
    return {str(i.get("id") or "").strip().upper() for i in inventory or [] if isinstance(i, dict)}


class GuardrailBase:
    """Proxies the turn manager and offers helpers shared by every guardrail."""

    manager: GameTurnManager

    @property
    def db(self):
        return self.manager.db

    @property
    def game_id(self):
        return self.manager.game_id

    @property
    def user(self):
        return self.manager.user

    @property
    def state(self):
        return self.manager.state

    @property
    def avatar(self):
        return self.manager.avatar

    @property
    def adventure(self):
        return self.manager.adventure

    @property
    def turn_language(self):
        return self.manager.turn_language

    def _switch_story_flags(self, *args, **kwargs):
        return self.manager._switch_story_flags(*args, **kwargs)

    async def _save_chat_message(self, *args, **kwargs):
        return await self.manager._save_chat_message(*args, **kwargs)

    @staticmethod
    def _parse_json_object(text: str) -> dict[str, Any] | None:
        raw = (text or "").strip()
        if not raw:
            return None
        for candidate in (raw, *re.findall(r"\{[\s\S]*\}", raw)[:1]):
            try:
                value = json.loads(candidate)
            except ValueError:
                continue
            return value if isinstance(value, dict) else None
        return None

    @staticmethod
    def _normalize_target_token(value: str) -> str:
        """Normalize a target hint for resilient matching across spacing and punctuation variants."""
        return re.sub(r"[^a-z0-9]+", "", (value or "").strip().lower())

    async def _session_entities(self) -> list[WorldEntity]:
        res = await self.db.execute(
            select(WorldEntity).where(WorldEntity.session_id == self.game_id)
        )
        return list(res.scalars().all())

    def _small_llm(self) -> tuple[Any, str]:
        """Returns (client, model) for quick classification calls.

        ``GameMasterLLM`` is resolved through gameplay_logic so tests can patch it there.
        """
        import backend.api.routes.adventures.gameplay_logic as gl

        cfg = self.user.llm_settings or {}
        provider = (
            cfg.get("small_model_provider")
            or cfg.get("complex_model_provider")
            or cfg.get("preferred_provider")
            or cfg.get("provider")
            or "openai"
        )
        fallback = (
            f"openai/{DEFAULT_SMALL_MODEL}" if provider == "openrouter" else DEFAULT_SMALL_MODEL
        )
        model = (
            cfg.get("small_model") or cfg.get("small_model_name") or cfg.get("model") or fallback
        )
        return gl.GameMasterLLM(self.user, provider=provider, model_category="small"), model

    @staticmethod
    def _revoke_turn_rewards(event: GameEvent) -> None:
        """A blocked interaction must not grant quests, awards or items."""
        event.completed_quest_ids = []
        event.earned_award_keys = []
        event.new_inventory_items = []
        event.updated_inventory_items = []
        event.removed_inventory_item_ids = []
        event.spawned_items = []

    def _upsert_entity_update(self, event: GameEvent, entity_id: str, **fields: object) -> None:
        """Insert or merge a WorldEntityUpdate for ``entity_id`` into the event."""
        if not entity_id:
            return
        if event.updated_entities is None:
            event.updated_entities = []
        existing = next((up for up in event.updated_entities if up.entity_id == entity_id), None)
        if existing is None:
            event.updated_entities.append(WorldEntityUpdate(entity_id=entity_id, **fields))  # type: ignore[arg-type]
            return
        for key, value in fields.items():
            setattr(existing, key, value)

    def _upsert_entity_movement(self, event: GameEvent, entity_id: str, to_scene_id: str) -> None:
        """Insert or merge an EntityMovement for ``entity_id`` into the event."""
        if not entity_id or not to_scene_id:
            return
        if event.moved_entities is None:
            event.moved_entities = []
        existing = next((m for m in event.moved_entities if m.entity_id == entity_id), None)
        if existing is None:
            event.moved_entities.append(
                EntityMovement(entity_id=entity_id, to_scene_id=to_scene_id)
            )
            return
        existing.to_scene_id = to_scene_id
