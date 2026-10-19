"""Shared accessors and persistence helpers for the combat mixins."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from backend.api.routes.adventures.logic import AdventureLogic
from backend.models.world_entity import WorldEntity

if TYPE_CHECKING:
    from backend.api.routes.adventures.gameplay_logic import GameTurnManager

ENEMY_STATE_KEYS = ("hp", "mana", "stamina")


def system_event(text: str) -> str:
    return f"event: system\ndata: {json.dumps({'role': 'system', 'content': text})}\n\n"


class CombatContextMixin:
    """Proxies the turn manager state and offers combat state persistence helpers."""

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

    @property
    def _combat_state_helper(self):
        return self.manager._combat_state_helper

    def _build_map_payload(self, *args, **kwargs):
        return self.manager._build_map_payload(*args, **kwargs)

    def _build_prompt_suggestions_payload(self, *args, **kwargs):
        return self.manager._build_prompt_suggestions_payload(*args, **kwargs)

    def _build_terminal_flags_payload(self, *args, **kwargs):
        return self.manager._build_terminal_flags_payload(*args, **kwargs)

    async def _finalize_session(self, *args, **kwargs):
        return await self.manager._finalize_session(*args, **kwargs)

    async def _generate_prompt_suggestions(self, *args, **kwargs):
        return await self.manager._generate_prompt_suggestions(*args, **kwargs)

    async def _load_last_assistant_message(self, *args, **kwargs):
        return await self.manager._load_last_assistant_message(*args, **kwargs)

    async def _save_chat_message(self, *args, **kwargs):
        return await self.manager._save_chat_message(*args, **kwargs)

    # --- Combat state -------------------------------------------------------------

    def _read_combat_state(self) -> dict[str, Any]:
        return self._combat_state_helper.read_combat_state()

    def _is_combat_active(self) -> bool:
        return self._combat_state_helper.is_combat_active()

    def _has_combat_phase(self) -> bool:
        return self._combat_state_helper.has_combat_phase()

    def _set_combat_state(self, combat: dict[str, Any]) -> None:
        sync_legacy_enemy(combat)
        self._combat_state_helper.set_combat_state(combat)

    def _append_combat_log(
        self,
        combat: dict[str, Any],
        text: str,
        entry_type: str = "log",
        data: dict[str, Any] | None = None,
    ) -> None:
        self._combat_state_helper.append_combat_log(combat, text, entry_type, data)

    def _update_entity_state(self, entity_id: str, **values: Any) -> None:
        states = dict(self.state.entity_states or {})
        entry = dict(states.get(entity_id) or {})
        entry.update(values)
        states[entity_id] = entry
        self.state.entity_states = states
        flag_modified(self.state, "entity_states")

    def _persist_enemy_resources(self, enemy: dict[str, Any]) -> None:
        self._update_entity_state(enemy["id"], **{k: enemy.get(k, 0) for k in ENEMY_STATE_KEYS})

    async def _load_session_entity(self, entity_id: str | None) -> WorldEntity | None:
        if not entity_id:
            return None
        res = await self.db.execute(
            select(WorldEntity).where(
                WorldEntity.session_id == self.game_id, WorldEntity.id == entity_id
            )
        )
        return res.scalars().first()

    # --- Entity helpers -----------------------------------------------------------

    def _entity_override(self, entity_id: str, key: str) -> Any:
        states = self.state.entity_states or {}
        return (states.get(entity_id, {}) or {}).get(key)

    def _entity_stat(self, ent: WorldEntity, stat_key: str, fallback: int = 0) -> int:
        override = self._entity_override(ent.id, stat_key)
        if isinstance(override, int):
            return override
        ent_val = getattr(ent, stat_key, None)
        if isinstance(ent_val, int):
            return ent_val
        return fallback

    def _is_npc_defeated(self, npc: WorldEntity) -> bool:
        if self._entity_override(npc.id, "is_defeated"):
            return True
        hp = self._entity_override(npc.id, "hp")
        if hp is None:
            hp = npc.hp
        return isinstance(hp, int) and hp <= 0

    def _is_npc_killable(self, npc: WorldEntity) -> bool:
        override = self._entity_override(npc.id, "is_killable")
        if isinstance(override, bool):
            return override
        return bool(getattr(npc, "is_killable", True))

    def _is_npc_attackable(self, npc: WorldEntity) -> bool:
        override = self._entity_override(npc.id, "is_attackable")
        if override is None:
            override = npc.is_attackable
        return override is not False

    # --- Stream helpers -----------------------------------------------------------

    async def _emit_combat_final(self, status_note: str | None = None) -> AsyncGenerator[str, None]:
        await self.db.commit()
        combat_snap = AdventureLogic.get_combat_snapshot(self.state)
        # Never send a zombie combat object that has no active phase.
        if combat_snap and not any(
            combat_snap.get(k) for k in ("active", "loot_pending", "outcome")
        ):
            combat_snap = None

        map_payload = await self._build_map_payload()
        session_note = self.state.session.status_note if self.state.session else None
        final_data = jsonable_encoder(
            {
                **map_payload,
                "sheet": await AdventureLogic.build_sheet_snapshot(
                    self.avatar, self.state, self.db
                ),
                "entities": await AdventureLogic.build_session_entities(self.db, self.state),
                "combat": combat_snap,
                **self._build_prompt_suggestions_payload(),
                **self._build_terminal_flags_payload(),
                "status_note": status_note or session_note,
                "status": "success",
            }
        )
        yield f"event: final\ndata: {json.dumps(final_data)}\n\n"

    async def _reply(self, text: str) -> AsyncGenerator[str, None]:
        """Emits a system message followed by the final combat payload."""
        yield system_event(text)
        async for chunk in self._emit_combat_final(text):
            yield chunk


def find_enemy(combat: dict[str, Any], enemy_id: str | None) -> dict[str, Any] | None:
    if not enemy_id:
        return None
    low = str(enemy_id).lower()
    for enemy in combat.get("enemies") or []:
        if str(enemy.get("id", "")).lower() == low or str(enemy.get("name", "")).lower() == low:
            return enemy
    return None


def is_enemy_alive(enemy: dict[str, Any]) -> bool:
    return not enemy.get("defeated") and not enemy.get("fled") and int(enemy.get("hp") or 0) > 0


def engaged_enemies(combat: dict[str, Any]) -> list[dict[str, Any]]:
    return [e for e in combat.get("enemies") or [] if e.get("engaged") and is_enemy_alive(e)]


def sync_legacy_enemy(combat: dict[str, Any]) -> None:
    """Keeps the single-enemy ``combat["enemy"]`` field pointing at the current target."""
    enemies = combat.get("enemies")
    if not enemies:
        return
    target = find_enemy(combat, combat.get("target_id"))
    if not target or not is_enemy_alive(target):
        alive = engaged_enemies(combat) or [e for e in enemies if is_enemy_alive(e)]
        target = alive[0] if alive else target or enemies[0]
        combat["target_id"] = target.get("id")
    combat["enemy"] = dict(target)
