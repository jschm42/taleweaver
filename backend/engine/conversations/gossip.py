"""Gossip: NPCs with memory pass facts about the protagonist on to related NPCs.

Runs deterministically (no LLM) at every in-game turn boundary when the adventure enables
gossip. Two NPCs in the same scene (with or without the protagonist) exchange facts when

* both have memory slots (``npc_memory.memory_slots``),
* the teller has a sharing relation to the listener (``relations.SHARING_KINDS``: not a
  rival or enemy), and both are conscious.

The listener stores the fact under the same key, prefixed with its source ("Heard from
Bram: ..."), so the narration knows it is hearsay. Facts that were heard themselves are not
passed on again, and a listener never overwrites a fact it already has under that key. The
flow keeps the newest events in ``gossip_log`` for the debug inspector.
At most ``MAX_FACTS_PER_PAIR`` facts travel per pair and turn.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from backend.engine.conversations.relations import shares_with
from backend.engine.rules.npc_memory import memory_slots, read_memories, remember

HEARSAY_PREFIX = "Heard from "
MAX_FACTS_PER_PAIR = 1
# Newest gossip events kept in the conversation state (debug inspector).
MAX_GOSSIP_LOG = 30


@dataclass(frozen=True)
class GossipEvent:
    """One fact that travelled from ``teller_id`` to ``listener_id``."""

    teller_id: str
    listener_id: str
    key: str
    scene_id: str = ""


def _can_gossip(npc: Any) -> bool:
    if getattr(npc, "is_defeated", False):
        return False
    return memory_slots(getattr(npc, "metadata_json", None)) > 0


def _own_facts(states: dict[str, Any], npc: Any) -> list[dict[str, Any]]:
    facts = read_memories(states, str(npc.id), memory_slots(npc.metadata_json))
    return [f for f in facts if not str(f.get("text") or "").startswith(HEARSAY_PREFIX)]


def _tell(
    states: dict[str, Any], teller: Any, listener: Any
) -> tuple[dict[str, Any], list[GossipEvent]]:
    known = {f.get("key") for f in read_memories(states, str(listener.id))}
    events: list[GossipEvent] = []
    for fact in _own_facts(states, teller):
        if len(events) >= MAX_FACTS_PER_PAIR:
            break
        if fact.get("key") in known:
            continue
        text = f"{HEARSAY_PREFIX}{teller.name}: {fact.get('text')}"
        slots = memory_slots(listener.metadata_json)
        states = remember(states, str(listener.id), fact.get("key"), text, slots)
        scene_id = str(getattr(teller, "current_scene_id", "") or "")
        events.append(GossipEvent(str(teller.id), str(listener.id), str(fact.get("key")), scene_id))
    return states, events


def _by_scene(npcs: Iterable[Any]) -> dict[str, list[Any]]:
    groups: dict[str, list[Any]] = defaultdict(list)
    for npc in npcs:
        scene_id = str(getattr(npc, "current_scene_id", "") or "")
        if scene_id and _can_gossip(npc):
            groups[scene_id].append(npc)
    return groups


def spread_gossip(
    entity_states: dict[str, Any], npcs: Iterable[Any]
) -> tuple[dict[str, Any], list[GossipEvent]]:
    """Exchanges facts between co-located related memory NPCs; returns (states, events).

    ``npcs`` are session NPC rows with entity overrides applied (current scene, defeat).
    The returned dict is the given one when nothing travelled.
    """
    states = entity_states
    events: list[GossipEvent] = []
    for group in _by_scene(npcs).values():
        for teller in group:
            for listener in group:
                if teller is listener or not shares_with(teller, listener, states):
                    continue
                states, told = _tell(states, teller, listener)
                events.extend(told)
    return states, events


def append_gossip_log(log: Any, events: list[GossipEvent], state: Any) -> list[dict[str, Any]]:
    """``gossip_log`` of the conversation state with ``events`` added (newest last, bounded)."""
    entries = [e for e in log if isinstance(e, dict)] if isinstance(log, list) else []
    entries.extend(
        {
            "teller_id": event.teller_id,
            "listener_id": event.listener_id,
            "key": event.key,
            "scene_id": event.scene_id,
            "minute": int(getattr(state, "in_game_time", 0) or 0),
        }
        for event in events
    )
    return entries[-MAX_GOSSIP_LOG:]
