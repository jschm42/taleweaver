"""Replay of the ``tw.npcs`` conversation operations (``ScriptChangeset.conversation_ops``).

Ops (ordered):

* ``{"op": "set_relation", "npc_id", "other_id", "kind", "note"}``: kind "" removes it.
* ``{"op": "mark_heard", "topic_id"}`` / ``{"op": "unmark_heard", "topic_id"}``.

Every changeset applier calls ``apply_conversation_ops``, like ``apply_npc_memory_ops``.
"""

from __future__ import annotations

from typing import Any

from backend.engine.conversations.relations import RELATIONS_KEY
from backend.engine.conversations.state import (
    CONVERSATIONS_STATE_KEY,
    mark_heard,
    read_conversations,
)


def _set_relation(data: dict[str, Any], op: dict[str, Any]) -> None:
    npc_id = str(op.get("npc_id") or "").upper()
    other_id = str(op.get("other_id") or "").upper()
    if not npc_id or not other_id:
        return
    store = {k: dict(v) for k, v in (data.get(RELATIONS_KEY) or {}).items() if isinstance(v, dict)}
    mine = store.setdefault(npc_id, {})
    mine[other_id] = {
        "npc_id": other_id,
        "kind": str(op.get("kind") or "").upper(),
        "note": str(op.get("note") or ""),
    }
    data[RELATIONS_KEY] = store


def _unmark_heard(data: dict[str, Any], topic_id: str) -> None:
    data["heard"] = [str(t) for t in data.get("heard") or [] if str(t) != topic_id]


def apply_conversation_op(data: dict[str, Any], op: dict[str, Any]) -> None:
    """Applies one op to a conversation state dict (in place)."""
    kind = op.get("op")
    topic_id = str(op.get("topic_id") or "")
    if kind == "set_relation":
        _set_relation(data, op)
    elif kind == "mark_heard" and topic_id:
        mark_heard(data, topic_id)
    elif kind == "unmark_heard" and topic_id:
        _unmark_heard(data, topic_id)


def apply_conversation_ops(entity_states: dict[str, Any], ops: Any) -> None:
    """Replays the ordered ops into ``entity_states`` in place."""
    valid = [op for op in ops or [] if isinstance(op, dict)]
    if not valid:
        return
    data = read_conversations(entity_states)
    for op in valid:
        apply_conversation_op(data, op)
    entity_states[CONVERSATIONS_STATE_KEY] = data
