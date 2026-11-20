"""Debug inspector data for an NPC's social state: memory, relations, chatter, topics.

Shows what the engine keeps for ``engine/rules/npc_memory.py`` and ``engine/conversations/``
as the game sees it right now (template values merged with script changes), plus the
session-wide conversation counters for the NPC tab of the debug dialog.
"""

from __future__ import annotations

from typing import Any

from backend.engine.conversations.gossip import HEARSAY_PREFIX
from backend.engine.conversations.npc_fields import conversation_fields
from backend.engine.conversations.relations import RELATIONS_KEY, relations_of
from backend.engine.conversations.settings import parse_conversation_settings
from backend.engine.conversations.state import (
    heard_topics,
    player_chatter_enabled,
    read_conversations,
)
from backend.engine.rules.npc_memory import memory_slots, read_memories


def _script_relation_targets(entity_states: Any, npc_id: str) -> set[str]:
    store = read_conversations(entity_states).get(RELATIONS_KEY)
    mine = store.get(npc_id.upper()) if isinstance(store, dict) else None
    return {str(k).upper() for k in mine} if isinstance(mine, dict) else set()


def _relations(ent: Any, entity_states: Any, names: dict[str, str]) -> list[dict[str, Any]]:
    changed = _script_relation_targets(entity_states, str(ent.id))
    return [
        {
            "npc_id": relation["npc_id"],
            "name": names.get(target, relation["npc_id"]),
            "kind": relation["kind"],
            "note": relation.get("note", ""),
            "changed_by_script": target in changed,
        }
        for target, relation in relations_of(ent, entity_states).items()
    ]


def _topics(fields: dict[str, Any], heard: set[str]) -> list[dict[str, Any]]:
    return [
        {
            "id": topic["id"],
            "topic": topic["topic"],
            "with_npc_id": topic.get("with_npc_id", ""),
            "must_convey": topic.get("must_convey", ""),
            "guard_expression": topic.get("guard_expression", ""),
            "repeatable": bool(topic.get("repeatable")),
            "heard": topic["id"] in heard,
        }
        for topic in fields["conversation_topics"]
    ]


def _gossip_log(entity_states: Any) -> list[dict[str, Any]]:
    log = read_conversations(entity_states).get("gossip_log")
    return [e for e in log if isinstance(e, dict)] if isinstance(log, list) else []


def _gossip_of(npc_id: str, entity_states: Any, names: dict[str, str]) -> dict[str, list]:
    """What this NPC passed on (told) and picked up (heard) by gossip, oldest first."""
    me = npc_id.upper()

    def name(other: Any) -> str:
        return names.get(str(other).upper(), str(other))

    log = _gossip_log(entity_states)
    return {
        "told": [
            {"to": name(e.get("listener_id")), "key": e.get("key")}
            for e in log
            if str(e.get("teller_id")).upper() == me
        ],
        "heard": [
            {"from": name(e.get("teller_id")), "key": e.get("key")}
            for e in log
            if str(e.get("listener_id")).upper() == me
        ],
    }


def _fact(raw: dict[str, Any]) -> dict[str, Any]:
    text = str(raw.get("text"))
    return {"key": str(raw.get("key")), "text": text, "hearsay": text.startswith(HEARSAY_PREFIX)}


def npc_social_debug(ent: Any, entity_states: Any, names: dict[str, str]) -> dict[str, Any]:
    """The ``memory`` / ``conversations`` / ``gossip`` blocks of one NPC in the debug payload."""
    metadata = ent.metadata_json if isinstance(ent.metadata_json, dict) else {}
    slots = memory_slots(metadata)
    fields = conversation_fields(metadata)
    stored = read_memories(entity_states, str(ent.id))
    return {
        "memory": {
            "slots": slots,
            # Every stored fact (also beyond the slots), so the debug view shows the raw store.
            "facts": [_fact(f) for f in stored],
        },
        "gossip": _gossip_of(str(ent.id), entity_states, names),
        "conversations": {
            "chatty": fields["chatty"],
            "relations": _relations(ent, entity_states, names),
            "topics": _topics(fields, heard_topics(entity_states)),
        },
    }


def _gossip_log_view(entity_states: Any, names: dict[str, str]) -> list[dict[str, Any]]:
    return [
        {
            "teller": names.get(str(e.get("teller_id")).upper(), str(e.get("teller_id"))),
            "listener": names.get(str(e.get("listener_id")).upper(), str(e.get("listener_id"))),
            "key": e.get("key"),
            "scene_id": e.get("scene_id") or "",
            "minute": e.get("minute") or 0,
        }
        for e in _gossip_log(entity_states)
    ]


def conversation_session_debug(
    adventure: Any, entity_states: Any, names: dict[str, str] | None = None
) -> dict[str, Any]:
    """Session-wide conversation state: settings, player switch, counter, pending beat, gossip."""
    settings = parse_conversation_settings(getattr(adventure, "npc_conversations", None))
    data = read_conversations(entity_states)
    return {
        "gossip_log": _gossip_log_view(entity_states, names or {}),
        "chatter": settings.chatter,
        "gossip": settings.gossip,
        "player_enabled": player_chatter_enabled(entity_states),
        "scene": data.get("scene") or "",
        "quiet": int(data.get("quiet") or 0),
        "last_pair": list(data.get("last_pair") or []),
        "pending_beat": str(data.get("pending_beat") or ""),
        "heard": sorted(heard_topics(entity_states)),
    }
