"""Travel time of exits: a way between distant places costs in-game time.

An exit may carry ``travel_minutes`` (``WorldExit.travel_minutes``, None/0 = no travel time)
and a ``travel_label`` ("two days by ship"). Using the exit advances the clock by that time,
right when the player passes it, so the arrival narration already sees the new time. Travel
time replaces the message's narration tick and is not capped by ``max_time_per_turn`` (that
cap is for time the Game Master asks for). A paused clock stays put, like for every tick.

Spec: docs/specs/world_sections.md (6.2).
"""

from __future__ import annotations

from typing import Any, Optional

from backend.engine.rules.game_clock import MAX_TIME, read_clock

MAX_TRAVEL_MINUTES = 60 * 24 * 365
MAX_TRAVEL_LABEL_LENGTH = 100


def normalize_travel_minutes(raw: Any) -> Optional[int]:
    """Whole minutes, or None for no travel time (missing, invalid, zero or negative)."""
    if raw is None or isinstance(raw, bool):
        return None
    try:
        minutes = int(float(raw))
    except (TypeError, ValueError):
        return None
    return min(minutes, MAX_TRAVEL_MINUTES) if minutes > 0 else None


def normalize_travel_label(raw: Any) -> Optional[str]:
    text = str(raw or "").strip()[:MAX_TRAVEL_LABEL_LENGTH]
    return text or None


def travel_minutes_of(world_exit: Any) -> int:
    return normalize_travel_minutes(getattr(world_exit, "travel_minutes", None)) or 0


def advance_travel_time(state: Any, minutes: int) -> int:
    """Adds the travel time to the session clock; returns the minutes actually added."""
    if minutes <= 0 or read_clock(getattr(state, "entity_states", None)).get("paused"):
        return 0
    before = int(state.in_game_time or 0)
    state.in_game_time = min(MAX_TIME, before + minutes)
    return int(state.in_game_time) - before


def format_duration(minutes: int) -> str:
    """``45`` -> ``45 min``, ``480`` -> ``8 h``, ``1590`` -> ``1 d 2 h 30 min``."""
    if minutes <= 0:
        return "0 min"
    days, rest = divmod(int(minutes), 24 * 60)
    hours, mins = divmod(rest, 60)
    parts = [
        f"{days} d" if days else "",
        f"{hours} h" if hours else "",
        f"{mins} min" if mins else "",
    ]
    return " ".join(part for part in parts if part)


def travel_note(world_exit: Any, minutes: int) -> str:
    """The chat line for a journey, e.g. ``The journey (a windy cliff path) takes 2 h 30 min.``"""
    label = normalize_travel_label(getattr(world_exit, "travel_label", None))
    way = f" ({label})" if label else ""
    return f"The journey{way} takes {format_duration(minutes)}."
