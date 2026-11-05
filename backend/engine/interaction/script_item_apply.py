"""Applies the item side of a script changeset to the database.

Shared by the turn manager and the trigger service: cloned items become new ``WorldEntity``
rows, and (for trigger scripts, which have no turn manager) the protagonist's inventory and
the moved or updated entity rows are written back.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from backend.engine.scripting.context import ScriptChangeset
from backend.models.avatar import Avatar
from backend.models.session_state import SessionState
from backend.models.world_entity import WorldEntity, WorldExit

logger = logging.getLogger(__name__)

# Columns a clone never copies: its own key, ID and timestamps.
_NOT_COPIED = {"pk", "id", "created_at", "updated_at"}
# Session-state keys of the original that describe where it is, not what it is.
_PLACEMENT_KEYS = {"current_scene_id", "spatial_position", "is_in_inventory", "inventory"}
# Session-state keys a fresh NPC clone does not inherit: it starts unhurt and undefeated.
_FRESH_NPC_KEYS = {
    "hp",
    "mana",
    "stamina",
    "is_defeated",
    "is_attackable",
    "attack_trigger_fired",
}
_ROW_FIELDS = ("current_scene_id", "spatial_position", "is_hidden", "is_in_inventory", "inventory")


async def _load_entity(db: AsyncSession, session_id: str, entity_id: str) -> WorldEntity | None:
    res = await db.execute(
        select(WorldEntity).where(WorldEntity.session_id == session_id, WorldEntity.id == entity_id)
    )
    return res.scalars().first()


async def insert_cloned_entities(
    db: AsyncSession, state: SessionState, changeset: ScriptChangeset
) -> None:
    """Creates a session entity row for every item or NPC a script cloned."""
    if not changeset.cloned_entities:
        return
    states: dict[str, Any] = dict(state.entity_states or {})
    for clone in changeset.cloned_entities:
        source = await _load_entity(db, state.session_id, clone["source_id"])
        if source is None:
            logger.warning("[Script] Cannot clone '%s': no session entity.", clone["source_id"])
            continue
        columns = {
            c.name: getattr(source, c.name)
            for c in source.__table__.columns
            if c.name not in _NOT_COPIED
        }
        columns.update(
            id=clone["new_id"],
            current_scene_id=clone["current_scene_id"],
            is_hidden=bool(clone["is_hidden"]),
            is_in_inventory=False,
            inventory=[],
        )
        skipped = _PLACEMENT_KEYS
        if clone.get("fresh_npc"):
            columns["hp"] = source.max_hp or source.hp
            skipped = _PLACEMENT_KEYS | _FRESH_NPC_KEYS
        db.add(WorldEntity(**columns))
        inherited = {k: v for k, v in (states.get(source.id) or {}).items() if k not in skipped}
        states[clone["new_id"]] = {
            **inherited,
            "current_scene_id": clone["current_scene_id"],
            "is_hidden": bool(clone["is_hidden"]),
            "cloned_from": source.id,
        }
    await db.flush()
    state.entity_states = states
    flag_modified(state, "entity_states")


def apply_player_inventory(avatar: Avatar | None, changeset: ScriptChangeset) -> None:
    """Adds and removes inventory entries (additions first, like a turn does)."""
    if avatar is None or not (changeset.player_new_items or changeset.player_removed_item_ids):
        return
    removed = set(changeset.player_removed_item_ids)
    inventory = [*(avatar.inventory or []), *changeset.player_new_items]
    avatar.inventory = [
        it for it in inventory if (it.get("id") if isinstance(it, dict) else it) not in removed
    ]


async def sync_entity_rows(
    db: AsyncSession, state: SessionState, changeset: ScriptChangeset
) -> None:
    """Scene and inventory queries read entity rows, so script changes are written to them."""
    touched = {m["entity_id"] for m in changeset.entity_movements if m.get("entity_id")} | {
        u["entity_id"] for u in changeset.entity_updates if u.get("entity_id")
    }
    if not touched:
        return
    res = await db.execute(
        select(WorldEntity).where(
            WorldEntity.session_id == state.session_id, WorldEntity.id.in_(touched)
        )
    )
    states: dict[str, Any] = dict(state.entity_states or {})
    for ent in res.scalars().all():
        st = states.get(str(ent.id), {})
        for field in (f for f in _ROW_FIELDS if f in st):
            setattr(ent, field, st[field])


async def sync_exit_rows(db: AsyncSession, state: SessionState, changeset: ScriptChangeset) -> None:
    """Synchronizes database WorldExit rows and world_map edges from exit updates."""
    if not changeset.exit_updates:
        return

    for eu in changeset.exit_updates:
        from_scene = str(eu.get("from_scene_id") or "").strip().upper()
        to_scene = str(eu.get("to_scene_id") or "").strip().upper()
        if not from_scene or not to_scene:
            continue

        is_locked = bool(eu.get("is_locked", False))
        lock_description = eu.get("lock_description")

        res = await db.execute(
            select(WorldExit).where(
                WorldExit.session_id == state.session_id,
                or_(
                    and_(
                        func.upper(WorldExit.from_scene_id) == from_scene,
                        func.upper(WorldExit.to_scene_id) == to_scene,
                    ),
                    and_(
                        func.upper(WorldExit.from_scene_id) == to_scene,
                        func.upper(WorldExit.to_scene_id) == from_scene,
                        WorldExit.exit_type == "bidirectional",
                    ),
                ),
            )
        )
        for exit_row in res.scalars().all():
            exit_row.is_locked = is_locked
            if lock_description is not None:
                exit_row.lock_description = lock_description

        try:
            from backend.api.routes.adventures.adventure_logic import AdventureLogic
            from backend.engine.interaction.map_engine import MapEngine

            world_map = await AdventureLogic.get_or_create_map(
                db, state.template_id, session_id=state.session_id
            )
            if world_map:
                MapEngine.register_exit(
                    world_map,
                    from_scene,
                    to_scene,
                    is_locked=is_locked,
                )
        except Exception as exc:
            logger.warning(
                "[Script] Could not sync world_map edge for %s -> %s: %s", from_scene, to_scene, exc
            )
