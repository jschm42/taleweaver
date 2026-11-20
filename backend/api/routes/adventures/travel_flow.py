"""Turn-side travel time: using an exit with ``travel_minutes`` advances the clock at once.

The clock moves when the player passes the exit, so the arrival narration already sees the
new time. The journey replaces the player message's narration tick
(``manager.clock_tick_pending``); the time events that came due on the road fire after the
narration, where the tick's events would have fired (``game_clock_flow.tick_after_narration``
reads ``manager.travel_events_pending``).

Called by the exit traversal (``/traverse_exit``) and by Game Master scene transitions through
an exit. Script teleports and ``/debug goto`` add no travel time.
"""

from __future__ import annotations

from typing import Any

from backend.engine.rules.travel_time import advance_travel_time, travel_minutes_of, travel_note


def apply_exit_travel(manager: Any, world_exit: Any) -> list[str]:
    """Advances the session clock by the exit's travel time; returns the chat notes."""
    if world_exit is None:
        return []
    minutes = advance_travel_time(manager.state, travel_minutes_of(world_exit))
    if not minutes:
        return []
    manager.clock_tick_pending = False
    manager.travel_events_pending = True
    return [travel_note(world_exit, minutes)]
