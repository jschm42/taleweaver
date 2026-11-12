"""Moves the active companion along when the protagonist changes scenes.

Every place that sets ``SessionState.current_scene_id`` during play calls
``bring_companion_along`` right after it, before ``on_enter_scene`` runs, so scene scripts
already see the companion in the new scene.

The companion only follows when it is in the scene the protagonist just left, the party is
``following``, it is not defeated, and neither the used exit nor the active sequence forbids
companions (``companions_allowed: false``). Otherwise it stays where it is; once the
protagonist comes back, it follows again from there.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from backend.engine.party.party_state import read_party
from backend.models.session_state import SessionState
from backend.models.world_entity import WorldEntity

logger = logging.getLogger(__name__)


def companions_allowed(world_exit: Any = None, sequence: Optional[dict[str, Any]] = None) -> bool:
    """False when the used exit or the active sequence is a solo section."""
    if world_exit is not None and getattr(world_exit, "companions_allowed", True) is False:
        return False
    return not (isinstance(sequence, dict) and sequence.get("companions_allowed") is False)


def companion_scene_id(entity_states: dict[str, Any], row: WorldEntity) -> str:
    """The companion's effective scene: session override first, then its session row."""
    entry = entity_states.get(row.id) if isinstance(entity_states.get(row.id), dict) else {}
    return str(entry.get("current_scene_id") or row.current_scene_id or "")


def is_out_of_action(entity_states: dict[str, Any], row: WorldEntity) -> bool:
    entry = entity_states.get(row.id) if isinstance(entity_states.get(row.id), dict) else {}
    meta = row.metadata_json if isinstance(row.metadata_json, dict) else {}
    return bool(entry.get("is_defeated", meta.get("is_defeated", False)))


def place_entity(
    entity_states: dict[str, Any], row: Optional[WorldEntity], npc_id: str, scene_id: str
) -> None:
    """Moves an NPC in the session override and (if given) its session row."""
    entry = dict(entity_states.get(npc_id) or {})
    entry["current_scene_id"] = scene_id
    entry["spatial_position"] = None
    entity_states[npc_id] = entry
    if row is not None:
        row.current_scene_id = scene_id
        row.spatial_position = None


async def session_npc(db: AsyncSession, session_id: str, npc_id: str) -> Optional[WorldEntity]:
    res = await db.execute(
        select(WorldEntity).where(WorldEntity.session_id == session_id, WorldEntity.id == npc_id)
    )
    return res.scalars().first()


async def _active_sequence(
    db: AsyncSession, state: SessionState, adventure: Any = None
) -> Optional[dict[str, Any]]:
    # Lazy imports: the session adventure loader lives in the API layer.
    from backend.api.routes.adventures.logic import AdventureLogic
    from backend.api.routes.adventures.session_adventure import load_session_adventure

    if adventure is None:
        adventure = await load_session_adventure(db, state)
    if adventure is None:
        return None
    return AdventureLogic.resolve_active_sequence(adventure, state)


async def bring_companion_along(
    db: AsyncSession,
    state: SessionState,
    from_scene_id: Optional[str],
    *,
    world_exit: Any = None,
    adventure: Any = None,
) -> list[str]:
    """Moves the following companion into ``state.current_scene_id``.

    ``adventure`` (the session adventure) is loaded when the caller does not have it yet.
    Returns system messages for the chat (only when the companion has to stay behind).
    """
    to_scene_id = str(state.current_scene_id or "")
    npc_id = read_party(state.entity_states).follower_id()
    if not npc_id or not from_scene_id or not to_scene_id or to_scene_id == from_scene_id:
        return []
    row = await session_npc(db, state.session_id, npc_id)
    states = dict(state.entity_states or {})
    if row is None or companion_scene_id(states, row) != from_scene_id:
        return []
    if is_out_of_action(states, row):
        return []
    if not companions_allowed(world_exit, await _active_sequence(db, state, adventure)):
        logger.info("[Party %s] %s stays behind in %s", state.session_id, npc_id, from_scene_id)
        return [f"{row.name} cannot follow you here and stays behind."]
    place_entity(states, row, npc_id, to_scene_id)
    state.entity_states = states
    flag_modified(state, "entity_states")
    return []
