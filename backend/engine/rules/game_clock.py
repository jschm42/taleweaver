"""In-game clock: narration ticks, pause state, GM time control and time events.

The elapsed in-game time (minutes, or units for the ``units`` time system) lives in
``SessionState.in_game_time``. Everything else the clock needs at runtime is kept in
``entity_states["__game_clock__"]`` so it is part of every checkpoint and save:

- ``paused``: no narration ticks and no GM time changes while true.
- ``minutes_per_tick``: script override of the adventure's ``time_per_turn`` (None = default).
- ``gm_time_control``: script override of the adventure's ``gm_time_control`` (None = default).
- ``ticks``: number of narration ticks that advanced the clock.
- ``timers``: runtime timers registered with ``tw.time.at/after/every``.
- ``fired_scripts``: keys of ``on_time_reached`` scripts that already fired.

Scripts never write this state directly: ``tw.time`` records ordered operations in
``ScriptChangeset.clock_ops`` and every changeset applier replays them with ``apply_clock_ops``.
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any, Optional

CLOCK_STATE_KEY = "__game_clock__"
# Same key as session_adventure.SESSION_MANIFEST_SNAPSHOT_KEY (API layer, not importable here).
_SNAPSHOT_KEY = "__manifest_snapshot__"
TIME_TRIGGER = "on_time_reached"
DEFAULT_MINUTES_PER_TICK = 5
MAX_TIMERS = 50
MAX_TIME = 10_000_000

_DURATION_UNITS = {"w": 10080, "d": 1440, "h": 60, "m": 1}
_DURATION_TOKEN = re.compile(r"\s*(\d+)\s*([wdhm])", re.IGNORECASE)
_HOURS_MINUTES = re.compile(r"^\s*(\d+):([0-5]\d)\s*$")


def _empty_clock() -> dict[str, Any]:
    return {
        "paused": False,
        "minutes_per_tick": None,
        "gm_time_control": None,
        "ticks": 0,
        "timers": [],
        "fired_scripts": [],
    }


def _clamp_time(value: int) -> int:
    return max(0, min(MAX_TIME, int(value)))


def _parse_time_text(text: str) -> Optional[int]:
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    hours_minutes = _HOURS_MINUTES.match(text)
    if hours_minutes:
        return int(hours_minutes.group(1)) * 60 + int(hours_minutes.group(2))

    idx = 0
    total = 0
    n = len(text)
    matched = False
    while idx < n:
        m = _DURATION_TOKEN.match(text, idx)
        if not m:
            if text[idx:].isspace():
                break
            return None
        matched = True
        num, unit = m.group(1), m.group(2)
        total += int(num) * _DURATION_UNITS[unit.lower()]
        idx = m.end()

    return total if matched else None


def to_minutes(value: Any) -> Optional[int]:
    """Parses a time amount: ``90``, ``"90"``, ``"1h 30m"``, ``"2d"``, ``"1w 2d"`` or ``"1:30"``."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value or "").strip()
    return _parse_time_text(text) if text else None


def _adventure_value(adventure: Any, key: str) -> Any:
    if isinstance(adventure, dict):
        return adventure.get(key)
    return getattr(adventure, key, None)


def _snapshot_adventure(entity_states: Any) -> dict[str, Any]:
    snapshot = entity_states.get(_SNAPSHOT_KEY) if isinstance(entity_states, dict) else None
    adventure = snapshot.get("adventure") if isinstance(snapshot, dict) else None
    return adventure if isinstance(adventure, dict) else {}


def default_minutes_per_tick(adventure: Any) -> int:
    value = _adventure_value(adventure, "time_per_turn")
    return DEFAULT_MINUTES_PER_TICK if value is None else max(0, int(value))


def default_gm_time_control(adventure: Any) -> bool:
    value = _adventure_value(adventure, "gm_time_control")
    return True if value is None else bool(value)


def read_clock(entity_states: Any) -> dict[str, Any]:
    """A normalized, independent copy of the session's clock state."""
    clock = _empty_clock()
    raw = entity_states.get(CLOCK_STATE_KEY) if isinstance(entity_states, dict) else None
    if isinstance(raw, dict):
        clock.update({k: deepcopy(v) for k, v in raw.items() if k in clock})
    clock["timers"] = [t for t in clock["timers"] or [] if isinstance(t, dict)]
    clock["fired_scripts"] = [str(k) for k in clock["fired_scripts"] or []]
    return clock


def write_clock(entity_states: dict[str, Any], clock: dict[str, Any]) -> None:
    entity_states[CLOCK_STATE_KEY] = clock


def effective_minutes_per_tick(clock: dict[str, Any], adventure: Any) -> int:
    override = clock.get("minutes_per_tick")
    return default_minutes_per_tick(adventure) if override is None else max(0, int(override))


def gm_time_allowed(clock: dict[str, Any], adventure: Any) -> bool:
    """Whether the GM (Pass 1) may change the time: not while paused, else override/default."""
    if clock.get("paused"):
        return False
    override = clock.get("gm_time_control")
    return default_gm_time_control(adventure) if override is None else bool(override)


def clock_view(state: Any, adventure: Any = None) -> dict[str, Any]:
    """Everything ``tw.time`` reads, resolved for one session."""
    entity_states = getattr(state, "entity_states", None) or {}
    source = adventure if adventure is not None else _snapshot_adventure(entity_states)
    return {
        "minutes": int(getattr(state, "in_game_time", 0) or 0),
        "clock": read_clock(entity_states),
        "default_minutes_per_tick": default_minutes_per_tick(source),
        "default_gm_time_control": default_gm_time_control(source),
        "time_system": getattr(state, "time_system", None)
        or _adventure_value(source, "time_system")
        or "calendar",
        "time_config": getattr(state, "time_config", None)
        or _adventure_value(source, "time_config")
        or {},
    }


# --- Script operations -------------------------------------------------------------------


def _op_set(minutes: int, clock: dict[str, Any], op: dict[str, Any]) -> int:
    return _clamp_time(op.get("minutes", minutes))


def _op_advance(minutes: int, clock: dict[str, Any], op: dict[str, Any]) -> int:
    return _clamp_time(minutes + int(op.get("minutes", 0)))


def _op_pause(minutes: int, clock: dict[str, Any], op: dict[str, Any]) -> int:
    clock["paused"] = bool(op.get("paused", True))
    return minutes


def _op_tick_minutes(minutes: int, clock: dict[str, Any], op: dict[str, Any]) -> int:
    value = op.get("minutes")
    clock["minutes_per_tick"] = None if value is None else max(0, int(value))
    return minutes


def _op_gm_control(minutes: int, clock: dict[str, Any], op: dict[str, Any]) -> int:
    value = op.get("allowed")
    clock["gm_time_control"] = None if value is None else bool(value)
    return minutes


def _op_add_timer(minutes: int, clock: dict[str, Any], op: dict[str, Any]) -> int:
    timer = op.get("timer")
    if not isinstance(timer, dict):
        return minutes
    timers = [t for t in clock["timers"] if t.get("id") != timer.get("id")]
    if len(timers) < MAX_TIMERS:
        timers.append(dict(timer))
    clock["timers"] = timers
    return minutes


def _op_cancel_timer(minutes: int, clock: dict[str, Any], op: dict[str, Any]) -> int:
    clock["timers"] = [t for t in clock["timers"] if t.get("id") != op.get("id")]
    return minutes


_OPS = {
    "set": _op_set,
    "advance": _op_advance,
    "pause": _op_pause,
    "tick_minutes": _op_tick_minutes,
    "gm_control": _op_gm_control,
    "add_timer": _op_add_timer,
    "cancel_timer": _op_cancel_timer,
}


def apply_clock_ops(
    minutes: int, clock: dict[str, Any], ops: list[dict[str, Any]]
) -> tuple[int, dict[str, Any]]:
    """Replays recorded ``tw.time`` operations in order; returns (minutes, clock)."""
    result = deepcopy(clock)
    for op in ops or []:
        handler = _OPS.get(str(op.get("op") or ""))
        if handler is not None:
            minutes = handler(minutes, result, op)
    return _clamp_time(minutes), result


def apply_changeset_clock(state: Any, entity_states: dict[str, Any], ops: list[Any]) -> bool:
    """Applies a changeset's clock operations to a session; returns True when anything ran."""
    if not ops:
        return False
    minutes, clock = apply_clock_ops(int(state.in_game_time or 0), read_clock(entity_states), ops)
    state.in_game_time = minutes
    write_clock(entity_states, clock)
    return True


def is_json_safe(value: Any) -> bool:
    try:
        json.dumps(value)
    except (TypeError, ValueError):
        return False
    return True


# --- Narration ticks and GM requests -----------------------------------------------------


def narration_tick(minutes: int, clock: dict[str, Any], adventure: Any) -> tuple[int, int]:
    """One narration tick; returns (new minutes, elapsed). Mutates ``clock['ticks']``."""
    if clock.get("paused"):
        return minutes, 0
    step = effective_minutes_per_tick(clock, adventure)
    clock["ticks"] = int(clock.get("ticks") or 0) + 1
    new_minutes = _clamp_time(minutes + step)
    return new_minutes, new_minutes - minutes


def gm_extra_minutes(extra: int, adventure: Any) -> int:
    """GM-requested extra time, capped so a tick plus extra stays within ``max_time_per_turn``."""
    base = default_minutes_per_tick(adventure)
    max_turn = _adventure_value(adventure, "max_time_per_turn")
    time_config = _adventure_value(adventure, "time_config") or {}
    if max_turn is None and isinstance(time_config, dict):
        max_turn = time_config.get("max_time_per_turn")
    total = base + int(extra)
    if max_turn is not None and int(max_turn) > 0:
        total = min(total, int(max_turn))
    return max(0, total) - base


def apply_gm_time_request(state: Any, adventure: Any, event: Any) -> bool:
    """Applies Pass 1 time fields when GM time control is allowed; returns True on change."""
    if not gm_time_allowed(read_clock(state.entity_states), adventure):
        return False
    changed = False
    if getattr(event, "start_datetime_override", None):
        state.start_datetime = event.start_datetime_override
        changed = True
    override = getattr(event, "time_override_minutes", None)
    if override is not None:
        state.in_game_time = _clamp_time(override)
        return True
    extra = int(getattr(event, "extra_time_minutes", 0) or 0)
    delta = gm_extra_minutes(extra, adventure) if extra else 0
    if delta:
        state.in_game_time = _clamp_time(int(state.in_game_time or 0) + delta)
        changed = True
    return changed


# --- Time events ---------------------------------------------------------------------------


def script_key(script: dict[str, Any]) -> str:
    sequence = script.get("sequence_id")
    base = str(script.get("id") or f"{TIME_TRIGGER}:{script.get('target_id') or ''}")
    return f"{sequence}:{base}" if sequence else base


def script_threshold(script: Any) -> Optional[int]:
    if not isinstance(script, dict) or script.get("trigger") != TIME_TRIGGER:
        return None
    if script.get("is_active") is False:
        return None
    return to_minutes(script.get("target_id") or script.get("target"))


def _due_scripts(minutes: int, clock: dict[str, Any], scripts: list[Any]) -> list[dict]:
    """Due ``on_time_reached`` scripts; re-arms those whose threshold lies in the future again."""
    fired = set(clock["fired_scripts"])
    due: list[dict[str, Any]] = []
    for script in scripts or []:
        threshold = script_threshold(script)
        if threshold is None:
            continue
        key = script_key(script)
        if threshold > minutes:
            fired.discard(key)
            continue
        if key in fired:
            continue
        fired.add(key)
        due.append({"kind": "script", "at": threshold, "id": key, "script": script})
    clock["fired_scripts"] = sorted(fired)
    return due


def _next_repeat(timer: dict[str, Any], minutes: int) -> int:
    every = max(1, int(timer["every"]))
    at = int(timer["at"])
    missed = (minutes - at) // every + 1
    return at + missed * every


def _due_timers(minutes: int, clock: dict[str, Any]) -> list[dict]:
    due: list[dict[str, Any]] = []
    remaining: list[dict[str, Any]] = []
    for timer in clock["timers"]:
        if int(timer.get("at", 0)) > minutes:
            remaining.append(timer)
            continue
        due.append({"kind": "timer", "at": int(timer["at"]), "id": timer.get("id"), "timer": timer})
        if timer.get("every"):
            remaining.append({**timer, "at": _next_repeat(timer, minutes)})
    clock["timers"] = remaining
    return due


def collect_due_events(
    minutes: int, clock: dict[str, Any], scripts: list[Any]
) -> list[dict[str, Any]]:
    """Time events that are due at ``minutes``, oldest first. Marks them fired in ``clock``."""
    events = [*_due_scripts(minutes, clock, scripts), *_due_timers(minutes, clock)]
    return sorted(events, key=lambda e: e["at"])


def time_event_payload(event: dict[str, Any], minutes: int) -> dict[str, Any]:
    """The ``time_event`` value a handler or ``on_time_reached`` script receives."""
    timer = event.get("timer") or {}
    return {
        "id": event.get("id"),
        "at": event.get("at"),
        "now": minutes,
        "data": deepcopy(timer.get("data")),
        "repeats": bool(timer.get("every")),
    }
