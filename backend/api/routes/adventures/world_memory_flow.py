"""Stores the world memories Pass 1 reported (``GameEvent.new_world_memories``).

Each one goes through ``engine/rules/world_memories.add_world_memory`` (clipped, no duplicates,
bounded list). A local memory belongs to the scene it happened in. The player sees a short
system note for every stored memory.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm.attributes import flag_modified

from backend.engine.rules.rule_engine import GameEvent
from backend.engine.rules.world_memories import add_world_memory, make_world_memory

logger = logging.getLogger(__name__)


async def apply_world_memories(applier: Any, event: GameEvent) -> list[str]:
    """Adds the event's world memories to the session; returns the system notes it saved."""
    updates = list(event.new_world_memories or [])
    event.new_world_memories = None
    if not updates:
        return []
    state = applier.state
    memories = list(state.world_memories or [])
    notes: list[str] = []
    for mem in updates:
        entry = make_world_memory(
            mem.description,
            scope=mem.scope,
            emotion=mem.emotion,
            npc_id=mem.npc_id,
            scene_id=mem.scene_id or state.current_scene_id,
        )
        memories, added = add_world_memory(memories, entry)
        if not added:
            logger.info("[Turn %s] Skipped world memory: %s", applier.game_id, mem.description)
            continue
        note = f"Memory saved ({entry['scope']}, {entry['emotion']}): {entry['description']}"
        await applier._save_chat_message("system", note)
        notes.append(note)
    if not notes:
        return []
    state.world_memories = memories
    flag_modified(state, "world_memories")
    applier._queue_checkpoint("world_memories_updated")
    return notes
