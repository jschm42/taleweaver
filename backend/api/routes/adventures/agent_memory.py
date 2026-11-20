"""Persistent short-term notebook for the Play-Agent (``entity_states["__agent__"]["memories"]``).

The Play-Agent only sees a sliding window of recent chat turns, so codes, clues, and which
readables it already checked would otherwise be forgotten after a few turns. The agent can
store and prune concise notes here across turns via ``remember`` and ``forget`` on its decision.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy.orm.attributes import flag_modified

from backend.models.session_state import SessionState

MAX_AGENT_MEMORIES = 25
MAX_MEMORY_CHARS = 200


def _clean_note(raw: object) -> str:
    text = " ".join(str(raw or "").split()).strip()
    if not text:
        return ""
    return text[:MAX_MEMORY_CHARS]


def read_memories(agent_state: Mapping[str, Any] | None) -> list[str]:
    """Returns the agent's stored notes as clean strings."""
    if not isinstance(agent_state, Mapping):
        return []
    raw = agent_state.get("memories")
    if not isinstance(raw, list):
        return []
    return [note for item in raw if (note := _clean_note(item))]


def format_memories(agent_state: Mapping[str, Any] | None) -> str:
    """Formats stored notes for inclusion in the Play-Agent prompt."""
    notes = read_memories(agent_state)
    if not notes:
        return "None yet."
    return "\n".join(f"- {note}" for note in notes)


def _should_forget(note: str, forget_terms: list[str]) -> bool:
    lowered = note.lower()
    return any(term in lowered for term in forget_terms)


def apply_memory_updates(
    state: SessionState,
    remember: list[str] | None = None,
    forget: list[str] | None = None,
) -> list[str]:
    """Applies ``forget`` removals and ``remember`` additions to ``state.entity_states``."""
    entity_states = dict(state.entity_states or {})
    agent_state = dict(entity_states.get("__agent__") or {})
    notes = read_memories(agent_state)

    forget_terms = [t.lower() for item in (forget or []) if (t := _clean_note(item))]
    if forget_terms:
        notes = [n for n in notes if not _should_forget(n, forget_terms)]

    seen = {n.lower() for n in notes}
    for item in remember or []:
        note = _clean_note(item)
        if not note or note.lower() in seen:
            continue
        notes.append(note)
        seen.add(note.lower())

    notes = notes[-MAX_AGENT_MEMORIES:]
    agent_state["memories"] = notes
    entity_states["__agent__"] = agent_state
    state.entity_states = entity_states
    flag_modified(state, "entity_states")
    return notes
