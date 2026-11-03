"""Per-chapter walkthrough unlocks: the player can only unlock the current sequence's guide.

Each unlock costs ``WALKTHROUGH_REVEAL_COST`` XP. Unlocked sequence IDs live in
``entity_states["__walkthrough_revealed__"]``, so checkpoints save and restore them. Sessions
from before per-chapter unlocks carry ``is_walkthrough_revealed``; for them every chapter up to
the current one counts as unlocked. Later chapters are never shown.
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm.attributes import flag_modified

from backend.engine.rules.sequence_walkthrough import (
    current_chapter,
    format_walkthrough_steps,
    sequence_walkthrough_steps,
)

WALKTHROUGH_REVEAL_COST = 150
REVEALED_KEY = "__walkthrough_revealed__"


def revealed_sequence_ids(state: Any) -> list[str]:
    raw = (state.entity_states or {}).get(REVEALED_KEY)
    return [str(i) for i in raw] if isinstance(raw, list) else []


def current_step(steps: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    return next((step for step in steps if step.get("is_current")), None)


def _is_revealed(state: Any, step: dict[str, Any], free: bool) -> bool:
    if free or getattr(state, "is_walkthrough_revealed", False):
        return True
    return step.get("sequence_id") in revealed_sequence_ids(state)


def mark_revealed(state: Any, sequence_id: str) -> None:
    states = dict(state.entity_states or {})
    revealed = revealed_sequence_ids(state)
    if sequence_id not in revealed:
        states[REVEALED_KEY] = [*revealed, sequence_id]
    state.entity_states = states
    flag_modified(state, "entity_states")


def walkthrough_status(adventure: Any, state: Any, free: bool = False) -> dict[str, Any]:
    """What the player may see: unlocked chapters reached so far, and the current chapter's state.

    ``free`` (debug mode) treats every reached chapter as unlocked.
    """
    sequences = getattr(adventure, "sequences", None)
    chapter = current_chapter(sequences, state.active_sequence_id)
    steps = sequence_walkthrough_steps(sequences, state.active_sequence_id)
    reached = [step for step in steps if step["chapter"] <= chapter]
    current = current_step(reached)
    visible = [step for step in reached if _is_revealed(state, step, free)]
    return {
        "available": bool(reached),
        "current": current,
        "current_revealed": current is not None and _is_revealed(state, current, free),
        "steps": visible,
        "walkthrough": format_walkthrough_steps(visible),
    }


def _status_message(status: dict[str, Any]) -> str:
    current = status["current"]
    if not status["available"]:
        return "No walkthrough available for this adventure yet."
    if current is None:
        return "There is no walkthrough for the current chapter."
    if status["current_revealed"]:
        return f"Walkthrough for {current['name']} unlocked."
    return (
        f"The walkthrough for the current chapter is sealed. Unlock it for "
        f"{WALKTHROUGH_REVEAL_COST} XP; every chapter is unlocked separately."
    )


def walkthrough_payload(status: dict[str, Any], current_xp: int) -> dict[str, Any]:
    """Response of ``GET /{game_id}/walkthrough``."""
    current = status["current"]
    message = _status_message(status)
    return {
        "available": status["available"],
        "revealed": status["current_revealed"],
        "can_reveal": current is not None and not status["current_revealed"],
        "current_chapter_title": current["name"] if current else None,
        "current_xp": current_xp,
        "reveal_cost": WALKTHROUGH_REVEAL_COST,
        "walkthrough": status["walkthrough"],
        "steps": status["steps"],
        "message": message,
        "preview": message,
    }
