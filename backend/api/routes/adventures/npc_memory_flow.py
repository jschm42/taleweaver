"""Applies the NPC memories Pass 1 reported (``GameEvent.npc_memories``).

A fact is kept only when the turn is a player's action (no arrival narration) and the
character stands visible and undefeated in the current scene and has memory slots
(``engine/rules/npc_memory.py``). At most ``MAX_UPDATES_PER_MESSAGE`` facts are stored per
message. Dropped entries are only logged: the Game Master over-reached, the player did
nothing wrong. Runs before a scene change of the same message, so a character the
protagonist talks to while leaving still remembers it.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm.attributes import flag_modified

from backend.engine.rules.npc_memory import MAX_UPDATES_PER_MESSAGE, memory_slots, remember
from backend.engine.rules.rule_engine import GameEvent, NpcMemoryUpdate
from backend.models.world_entity import WorldEntity

logger = logging.getLogger(__name__)


async def _memory_npc(manager: Any, update: NpcMemoryUpdate) -> tuple[WorldEntity, int] | None:
    npc = await manager._find_scene_npc_by_hint(update.npc_id)
    if npc is None or manager._is_npc_defeated(npc):
        return None
    if ((manager.state.entity_states or {}).get(npc.id) or {}).get("is_hidden"):
        return None
    slots = memory_slots(npc.metadata_json)
    return (npc, slots) if slots else None


async def apply_npc_memories(manager: Any, event: GameEvent) -> None:
    """Stores the valid facts in ``entity_states["__npc_memory__"]`` and clears the field."""
    updates = list(event.npc_memories or [])
    event.npc_memories = None
    if not updates or getattr(manager, "arrival_narration", False):
        return
    states = dict(manager.state.entity_states or {})
    original = states
    for update in updates[:MAX_UPDATES_PER_MESSAGE]:
        target = await _memory_npc(manager, update)
        if target is None:
            logger.info(
                "[Turn %s] Dropped NPC memory for '%s': not here or without memory.",
                manager.game_id,
                update.npc_id,
            )
            continue
        npc, slots = target
        states = remember(states, str(npc.id), update.key, update.text, slots)
    if states is original:
        return
    manager.state.entity_states = states
    flag_modified(manager.state, "entity_states")
    logger.info("[Turn %s] NPC memories updated.", manager.game_id)
