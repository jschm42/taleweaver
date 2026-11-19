"""Session state of NPC conversations: ``entity_states["__conversations__"]``.

Keys (all optional):

* ``player_off``: the player switched NPC chatter off in the in-game settings.
* ``scene`` / ``quiet``: the scene of the counter and the player messages since the last
  conversation there.
* ``last_pair``: the two NPC ids of the last conversation (so the next one prefers others).
* ``heard``: ids of conversation topics the protagonist overheard.
* ``pending_beat``: the conversation direction for the next narration (taken once).
* ``relations``: script overrides ``{npc_id: {other_id: {"kind", "note"}}}``; kind "" removes.

Everything lives in ``entity_states``, so it is part of every checkpoint.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm.attributes import flag_modified

CONVERSATIONS_STATE_KEY = "__conversations__"
MAX_HEARD_TOPICS = 200


def read_conversations(entity_states: Any) -> dict[str, Any]:
    """A copy of the conversation state (empty dict when there is none)."""
    raw = (entity_states or {}).get(CONVERSATIONS_STATE_KEY) if entity_states else None
    return dict(raw) if isinstance(raw, dict) else {}


def write_conversations(entity_states: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    """A new ``entity_states`` dict holding ``data`` (callers flag the column as modified)."""
    states = dict(entity_states or {})
    states[CONVERSATIONS_STATE_KEY] = data
    return states


def player_chatter_enabled(entity_states: Any) -> bool:
    """False when the player switched NPC chatter off for this session."""
    return not read_conversations(entity_states).get("player_off")


def set_player_chatter(entity_states: dict[str, Any], enabled: bool) -> dict[str, Any]:
    data = read_conversations(entity_states)
    data["player_off"] = not enabled
    return write_conversations(entity_states, data)


def heard_topics(entity_states: Any) -> set[str]:
    heard = read_conversations(entity_states).get("heard")
    return {str(t) for t in heard} if isinstance(heard, list) else set()


def mark_heard(data: dict[str, Any], topic_id: str) -> None:
    """Adds ``topic_id`` to the heard list of ``data`` (in place)."""
    heard = [str(t) for t in data.get("heard") or [] if str(t) != topic_id]
    data["heard"] = [*heard, topic_id][-MAX_HEARD_TOPICS:]


def take_pending_beat(state: Any) -> str:
    """Removes and returns the conversation direction stored for this narration."""
    states = getattr(state, "entity_states", None) or {}
    data = read_conversations(states)
    beat = str(data.pop("pending_beat", "") or "")
    if not beat:
        return ""
    state.entity_states = write_conversations(states, data)
    flag_modified(state, "entity_states")
    return beat
