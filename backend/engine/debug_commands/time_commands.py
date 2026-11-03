"""``/debug time`` sub-commands: inspect and manually change the in-game clock.

Commands that move the clock answer with ``TIME_CHANGED_MARKER`` in front of their message; the
debug route then fires the time events that became due (``game_clock_flow``).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Optional

from sqlalchemy.orm.attributes import flag_modified

from backend.engine.debug_commands.context import DebugContext
from backend.engine.rules.game_clock import (
    TIME_TRIGGER,
    apply_clock_ops,
    effective_minutes_per_tick,
    gm_time_allowed,
    narration_tick,
    read_clock,
    script_key,
    script_threshold,
    to_minutes,
    write_clock,
)
from backend.engine.sessions.memory_manager import MemoryManager

TIME_CHANGED_MARKER = "[TRIGGER_TIME_CHANGED]"
MAX_DEBUG_TICKS = 100
USAGE = (
    "DEBUG ERROR: Usage: /debug time [set T | add T | sub T | tick [N] | pause | resume "
    "| pace T|reset | gm on|off|reset | cancel TIMER_ID]  (T: 90, 2h 30m, 1d, 1:30)"
)


def _formatted(ctx: DebugContext, minutes: int) -> str:
    adventure = ctx.adventure
    return MemoryManager.format_game_time(
        minutes,
        time_system=ctx.state.time_system or getattr(adventure, "time_system", None) or "calendar",
        time_config=ctx.state.time_config or getattr(adventure, "time_config", None) or {},
    )


def _apply(ctx: DebugContext, ops: list[dict[str, Any]]) -> None:
    states = dict(ctx.state.entity_states or {})
    minutes, clock = apply_clock_ops(int(ctx.state.in_game_time or 0), read_clock(states), ops)
    ctx.state.in_game_time = minutes
    write_clock(states, clock)
    ctx.state.entity_states = states
    flag_modified(ctx.state, "entity_states")


def _changed(ctx: DebugContext, what: str) -> str:
    minutes = int(ctx.state.in_game_time or 0)
    return f"{TIME_CHANGED_MARKER} DEBUG: {what} Time is now {_formatted(ctx, minutes)} ({minutes} min)."


def _amount_arg(ctx: DebugContext) -> Optional[int]:
    parts = ctx.args.split(None, 2)
    return to_minutes(parts[2]) if len(parts) > 2 else None


def _time_scripts(ctx: DebugContext) -> list[str]:
    manifest = getattr(ctx.adventure, "original_manifest", None) or {}
    fired = set(read_clock(ctx.state.entity_states)["fired_scripts"])
    lines = []
    for script in manifest.get("scripts") or []:
        threshold = script_threshold(script)
        if threshold is None:
            continue
        status = "fired" if script_key(script) in fired else "armed"
        lines.append(f"  - {script.get('id')} at {threshold} min ({status})")
    return lines


async def status(ctx: DebugContext) -> str:
    clock = read_clock(ctx.state.entity_states)
    minutes = int(ctx.state.in_game_time or 0)
    tick = effective_minutes_per_tick(clock, ctx.adventure)
    override = " (script override)" if clock["minutes_per_tick"] is not None else ""
    lines = [
        "--- DEBUG: IN-GAME CLOCK ---",
        f"Time: {_formatted(ctx, minutes)} ({minutes} min elapsed)",
        f"Ticks: {clock['ticks']} | Paused: {clock['paused']}",
        f"Minutes per tick: {tick}{override}",
        f"GM may change time: {gm_time_allowed(clock, ctx.adventure)}",
        f"Timers ({len(clock['timers'])}):",
    ]
    for timer in clock["timers"]:
        repeat = f", every {timer['every']} min" if timer.get("every") else ""
        lines.append(
            f"  - {timer.get('id')}: {timer.get('handler')}() at {timer.get('at')} min{repeat}"
        )
    scripts = _time_scripts(ctx)
    lines.append(f"{TIME_TRIGGER} scripts ({len(scripts)}):")
    lines.extend(scripts)
    return "\n".join(lines)


async def set_time(ctx: DebugContext) -> str:
    minutes = _amount_arg(ctx)
    if minutes is None:
        return USAGE
    _apply(ctx, [{"op": "set", "minutes": minutes}])
    return _changed(ctx, "Clock set.")


async def add_time(ctx: DebugContext) -> str:
    minutes = _amount_arg(ctx)
    if minutes is None:
        return USAGE
    _apply(ctx, [{"op": "advance", "minutes": minutes}])
    return _changed(ctx, f"Added {minutes} min.")


async def sub_time(ctx: DebugContext) -> str:
    minutes = _amount_arg(ctx)
    if minutes is None:
        return USAGE
    _apply(ctx, [{"op": "advance", "minutes": -minutes}])
    return _changed(ctx, f"Rewound {minutes} min.")


async def tick(ctx: DebugContext) -> str:
    parts = ctx.args.split()
    count = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 1
    count = max(1, min(MAX_DEBUG_TICKS, count))
    states = dict(ctx.state.entity_states or {})
    clock = read_clock(states)
    minutes = int(ctx.state.in_game_time or 0)
    for _ in range(count):
        minutes, _elapsed = narration_tick(minutes, clock, ctx.adventure)
    ctx.state.in_game_time = minutes
    write_clock(states, clock)
    ctx.state.entity_states = states
    flag_modified(ctx.state, "entity_states")
    note = " The clock is paused, so no time passed." if clock["paused"] else ""
    return _changed(ctx, f"Simulated {count} narration tick(s).{note}")


async def pause(ctx: DebugContext) -> str:
    _apply(ctx, [{"op": "pause", "paused": True}])
    return "DEBUG: Clock paused (no narration ticks, no GM time changes)."


async def resume(ctx: DebugContext) -> str:
    _apply(ctx, [{"op": "pause", "paused": False}])
    return "DEBUG: Clock resumed."


async def pace(ctx: DebugContext) -> str:
    parts = ctx.args.split(None, 2)
    if len(parts) > 2 and parts[2].strip().lower() == "reset":
        _apply(ctx, [{"op": "tick_minutes", "minutes": None}])
        return "DEBUG: Minutes per tick reset to the adventure default."
    minutes = _amount_arg(ctx)
    if minutes is None or minutes < 0:
        return USAGE
    _apply(ctx, [{"op": "tick_minutes", "minutes": minutes}])
    return f"DEBUG: Minutes per tick set to {minutes}."


async def gm_control(ctx: DebugContext) -> str:
    parts = ctx.args.split()
    choice = parts[2].lower() if len(parts) > 2 else ""
    values = {"on": True, "off": False, "reset": None}
    if choice not in values:
        return USAGE
    _apply(ctx, [{"op": "gm_control", "allowed": values[choice]}])
    return f"DEBUG: GM time control {choice}."


async def cancel(ctx: DebugContext) -> str:
    parts = ctx.args.split()
    if len(parts) < 3:
        return USAGE
    timer_id = parts[2]
    if not any(t.get("id") == timer_id for t in read_clock(ctx.state.entity_states)["timers"]):
        return f"DEBUG: No timer '{timer_id}'."
    _apply(ctx, [{"op": "cancel_timer", "id": timer_id}])
    return f"DEBUG: Timer '{timer_id}' cancelled."


_SUBCOMMANDS: dict[str, Callable[[DebugContext], Awaitable[str]]] = {
    "": status,
    "status": status,
    "set": set_time,
    "add": add_time,
    "sub": sub_time,
    "tick": tick,
    "pause": pause,
    "resume": resume,
    "pace": pace,
    "gm": gm_control,
    "cancel": cancel,
}


async def time_command(ctx: DebugContext) -> str:
    """``/debug time [sub-command]``."""
    parts = ctx.args.split()
    sub = parts[1].lower() if len(parts) > 1 else ""
    handler = _SUBCOMMANDS.get(sub)
    return await handler(ctx) if handler else USAGE
