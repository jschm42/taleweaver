"""Soft stage directions that scripts give the Game Master (``tw.story.direct``).

A script cannot write the narration of a turn itself, but it can ask the GM for something,
e.g. ``tw.story.direct("Let BRAM sing a sailor song")``. The direction is stored in the
session state and handed to the next GM narration (a regular turn, or a choice dialog that
narrates its outcome), which uses it once and drops it.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm.attributes import flag_modified

# Session-state key (inside ``entity_states``) holding directions not yet narrated.
GM_DIRECTIONS_KEY = "__gm_directions__"
MAX_GM_DIRECTIONS = 5
MAX_DIRECTION_LENGTH = 500


def clean_direction(text: Any) -> str:
    """Single-line, length-capped direction text; empty when there is nothing to say."""
    return " ".join(str(text or "").split())[:MAX_DIRECTION_LENGTH]


def pending_gm_directions(entity_states: Any) -> list[str]:
    """Directions waiting for the next GM narration."""
    directions = (entity_states or {}).get(GM_DIRECTIONS_KEY)
    return [str(d) for d in directions] if isinstance(directions, list) else []


def store_gm_directions(entity_states: dict[str, Any], directions: list[str]) -> None:
    """Queues new directions behind the pending ones; only the newest few are kept."""
    if not directions:
        return
    queued = pending_gm_directions(entity_states) + list(directions)
    entity_states[GM_DIRECTIONS_KEY] = queued[-MAX_GM_DIRECTIONS:]


def take_gm_directions(state: Any) -> list[str]:
    """Removes and returns the pending directions of a session state."""
    directions = pending_gm_directions(state.entity_states)
    if not directions:
        return []
    entity_states = dict(state.entity_states or {})
    entity_states.pop(GM_DIRECTIONS_KEY, None)
    state.entity_states = entity_states
    flag_modified(state, "entity_states")
    return directions


def format_gm_directions(directions: list[str]) -> str:
    """Prompt block asking the GM to work the directions into this narration."""
    if not directions:
        return ""
    return (
        "AUTHOR DIRECTIONS (from the adventure's scripts; work them naturally into this "
        "narration, in character and consistent with the scene; they never override game "
        "rules or the technical outcome):\n" + "\n".join(f"- {d}" for d in directions)
    )
