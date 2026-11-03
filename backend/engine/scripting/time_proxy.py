"""``tw.time``: reads and changes the in-game clock from scripts.

Every change is recorded as an ordered operation in ``changeset.clock_ops`` (replayed by the
changeset appliers, see ``engine/rules/game_clock.py``) and mirrored on a local copy, so a script
reads its own changes back immediately (``tw.time.advance(30); tw.time.now``).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import uuid4

from backend.engine.rules.game_clock import (
    MAX_TIMERS,
    apply_clock_ops,
    is_json_safe,
    read_clock,
    to_minutes,
)
from backend.engine.scripting.dialog import handler_name

_DEFAULT_START_TIME = 8 * 60


def default_clock_view(minutes: int = 0) -> dict[str, Any]:
    return {
        "minutes": int(minutes or 0),
        "clock": read_clock({}),
        "default_minutes_per_tick": 5,
        "default_gm_time_control": True,
        "time_system": "calendar",
        "time_config": {},
    }


def _start_of_day(time_config: dict[str, Any]) -> int:
    try:
        hours, mins = map(int, str(time_config.get("start_time") or "08:00").split(":"))
    except (TypeError, ValueError):
        return _DEFAULT_START_TIME
    return hours * 60 + mins


class TimeProxy:
    """Safe proxy exposed to scripts as ``tw.time``."""

    def __init__(self, changeset: Any, view: Optional[dict[str, Any]], context: Any = None):
        view = view or default_clock_view()
        self._changeset = changeset
        self._context = context
        self._minutes = int(view.get("minutes") or 0)
        self._clock = read_clock({"__game_clock__": view.get("clock") or {}})
        self._default_tick = int(view.get("default_minutes_per_tick", 5))
        self._default_gm = bool(view.get("default_gm_time_control", True))
        self._time_system = str(view.get("time_system") or "calendar")
        self._time_config = dict(view.get("time_config") or {})

    # --- recording -----------------------------------------------------------------------

    def _record(self, op: dict[str, Any]) -> None:
        self._changeset.clock_ops.append(op)
        self._minutes, self._clock = apply_clock_ops(self._minutes, self._clock, [op])

    def _debug(self, message: str) -> None:
        if self._context is not None:
            self._context.debug(message)

    def _amount(self, value: Any, api: str) -> Optional[int]:
        minutes = to_minutes(value)
        if minutes is None:
            self._debug(f"{api} ignored: '{value}' is not a time amount (e.g. 30, '1h 30m').")
        return minutes

    # --- reading -------------------------------------------------------------------------

    @property
    def now(self) -> int:
        """Elapsed in-game minutes (units for the 'units' time system) since the start."""
        return self._minutes

    @property
    def minutes(self) -> int:
        return self._minutes

    @property
    def ticks(self) -> int:
        """How many narration ticks advanced the clock so far."""
        return int(self._clock.get("ticks") or 0)

    @property
    def is_paused(self) -> bool:
        return bool(self._clock.get("paused"))

    @property
    def minutes_per_tick(self) -> int:
        override = self._clock.get("minutes_per_tick")
        return self._default_tick if override is None else int(override)

    @property
    def default_minutes_per_tick(self) -> int:
        return self._default_tick

    @property
    def gm_can_change_time(self) -> bool:
        if self.is_paused:
            return False
        override = self._clock.get("gm_time_control")
        return self._default_gm if override is None else bool(override)

    def _clock_of_day(self) -> tuple[int, int, int]:
        """(day number, hour, minute) of the current time."""
        start = self._time_config.get("start_datetime")
        if start:
            try:
                begin = datetime.fromisoformat(str(start).replace("Z", "+00:00"))
                current = begin + timedelta(minutes=self._minutes)
                return (current - begin).days + 1, current.hour, current.minute
            except (TypeError, ValueError, OverflowError):
                pass
        try:
            first_day = int(self._time_config.get("initial_day", 1))
        except (TypeError, ValueError):
            first_day = 1
        total = _start_of_day(self._time_config) + self._minutes
        return first_day + total // 1440, (total % 1440) // 60, total % 60

    @property
    def day(self) -> int:
        return self._clock_of_day()[0]

    @property
    def hour(self) -> int:
        return self._clock_of_day()[1]

    @property
    def minute(self) -> int:
        return self._clock_of_day()[2]

    def format(self) -> str:
        """The current time as the player sees it (e.g. 'Day 2, 14:30')."""
        # Lazy import: the memory manager pulls in prompt modules the sandbox does not need.
        from backend.engine.sessions.memory_manager import MemoryManager

        return MemoryManager.format_game_time(
            self._minutes, time_system=self._time_system, time_config=self._time_config
        )

    def parse(self, value: Any) -> Optional[int]:
        """Converts '1h 30m', '2d', '1:30' or 90 to minutes; None when it is not a time amount."""
        return to_minutes(value)

    # --- changing the time ---------------------------------------------------------------

    def set(self, value: Any) -> None:
        minutes = self._amount(value, "tw.time.set")
        if minutes is not None:
            self._record({"op": "set", "minutes": minutes})

    def advance(self, value: Any) -> None:
        minutes = self._amount(value, "tw.time.advance")
        if minutes is not None:
            self._record({"op": "advance", "minutes": minutes})

    def rewind(self, value: Any) -> None:
        minutes = self._amount(value, "tw.time.rewind")
        if minutes is not None:
            self._record({"op": "advance", "minutes": -minutes})

    def set_minutes_per_tick(self, value: Any) -> None:
        minutes = self._amount(value, "tw.time.set_minutes_per_tick")
        if minutes is not None:
            self._record({"op": "tick_minutes", "minutes": max(0, minutes)})

    def reset_minutes_per_tick(self) -> None:
        self._record({"op": "tick_minutes", "minutes": None})

    def pause(self) -> None:
        self._record({"op": "pause", "paused": True})

    def resume(self) -> None:
        self._record({"op": "pause", "paused": False})

    def allow_gm_time(self, allowed: bool = True) -> None:
        self._record({"op": "gm_control", "allowed": bool(allowed)})

    def reset_gm_time(self) -> None:
        self._record({"op": "gm_control", "allowed": None})

    # --- timers --------------------------------------------------------------------------

    @property
    def timers(self) -> list[dict[str, Any]]:
        return [dict(t) for t in self._clock["timers"]]

    def has_timer(self, timer_id: str) -> bool:
        return any(t.get("id") == str(timer_id) for t in self._clock["timers"])

    def at(self, when: Any, handler: Any, timer_id: Any = None, data: Any = None) -> Optional[str]:
        """Runs ``handler`` once the clock reaches ``when`` (elapsed minutes since the start)."""
        at = self._amount(when, "tw.time.at")
        return (
            None if at is None else self._add_timer("tw.time.at", at, handler, timer_id, data, None)
        )

    def after(
        self, delay: Any, handler: Any, timer_id: Any = None, data: Any = None
    ) -> Optional[str]:
        """Runs ``handler`` once ``delay`` minutes have passed from now."""
        minutes = self._amount(delay, "tw.time.after")
        if minutes is None:
            return None
        return self._add_timer(
            "tw.time.after", self._minutes + minutes, handler, timer_id, data, None
        )

    def every(
        self,
        interval: Any,
        handler: Any,
        timer_id: Any = None,
        data: Any = None,
        start: Any = None,
    ) -> Optional[str]:
        """Runs ``handler`` each time ``interval`` minutes have passed (first at ``start``)."""
        step = self._amount(interval, "tw.time.every")
        if step is None or step <= 0:
            self._debug("tw.time.every ignored: the interval must be at least 1 minute.")
            return None
        first = self._minutes + step if start is None else self._amount(start, "tw.time.every")
        if first is None:
            return None
        return self._add_timer("tw.time.every", first, handler, timer_id, data, step)

    def cancel(self, timer_id: Any) -> bool:
        if not self.has_timer(timer_id):
            return False
        self._record({"op": "cancel_timer", "id": str(timer_id)})
        return True

    def _add_timer(
        self, api: str, at: int, handler: Any, timer_id: Any, data: Any, every: Optional[int]
    ) -> Optional[str]:
        name = handler_name(handler)
        if name is None:
            self._debug(f"{api} ignored: the handler must name a function of the init script.")
            return None
        if not is_json_safe(data):
            self._debug(f"{api} ignored: data must be plain values (text, numbers, lists, dicts).")
            return None
        new_id = str(timer_id).strip() if timer_id not in (None, "") else uuid4().hex[:8]
        if not self.has_timer(new_id) and len(self._clock["timers"]) >= MAX_TIMERS:
            self._debug(f"{api} ignored: at most {MAX_TIMERS} timers can be active.")
            return None
        timer = {"id": new_id, "at": max(0, at), "handler": name, "every": every, "data": data}
        self._record({"op": "add_timer", "timer": timer})
        return new_id
