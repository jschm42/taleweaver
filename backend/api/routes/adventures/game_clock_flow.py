"""Turn-side driver of the in-game clock (see ``engine/rules/game_clock.py``).

- ``tick_after_narration``: one narration tick per player message whose processing ran a Pass 2
  narration (``manager.clock_tick_pending``), then due time events.
- ``run_due_time_events``: fires due ``on_time_reached`` scripts and ``tw.time`` timers. Also
  used after debug time commands and ``/script`` so a changed clock reacts at once.

Time event handlers may change the time or register timers again; the events are therefore
collected in a few rounds, at most ``MAX_EVENT_ROUNDS``.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.orm.attributes import flag_modified

from backend.api.routes.adventures.turn_pass_flow import sse_role_message
from backend.engine.rules.game_clock import (
    collect_due_events,
    narration_tick,
    read_clock,
    time_event_payload,
    write_clock,
)
from backend.engine.rules.rule_engine import GameEvent, GameOverError
from backend.engine.scripting.context import ScriptMessage
from backend.engine.scripting.runner import SCRIPT_ERROR_PREFIX

logger = logging.getLogger(__name__)

MAX_EVENT_ROUNDS = 5


def _store_clock(manager: Any, states: dict[str, Any], clock: dict[str, Any]) -> None:
    write_clock(states, clock)
    manager.state.entity_states = states
    flag_modified(manager.state, "entity_states")


def _take_due_events(manager: Any, scripts: list[Any]) -> list[dict[str, Any]]:
    states = dict(manager.state.entity_states or {})
    clock = read_clock(states)
    events = collect_due_events(int(manager.state.in_game_time or 0), clock, scripts)
    # Also stores re-armed on_time_reached scripts when nothing is due.
    _store_clock(manager, states, clock)
    return events


async def _missing_handler_note(manager: Any, handler: str, timer_id: Any) -> list[Any]:
    note = (
        f"{SCRIPT_ERROR_PREFIX} in 'timer_{timer_id}': the time handler '{handler}' is not "
        "defined in the adventure's init_script, so this time event has no effect."
    )
    await manager._save_chat_message("system", note)
    return [ScriptMessage(note, role="system")]


def _handler_call(handler: Any, name: str) -> str:
    takes_event = int(getattr(handler, "param_count", 1) or 0) > 0
    return f"{name}(time_event)" if takes_event else f"{name}()"


async def _run_event(manager: Any, runner: Any, event: dict[str, Any]) -> list[Any]:
    context = await manager._build_script_context()
    payload = time_event_payload(event, int(manager.state.in_game_time or 0))
    if event["kind"] == "script":
        runner.run_script(event["script"], context, {"time_event": payload})
    else:
        name = str(event["timer"].get("handler") or "")
        definitions: dict[str, Any] = {}
        runner.load_init_definitions(definitions)
        handler = definitions.get(name)
        if not callable(handler):
            return await _missing_handler_note(manager, name, event.get("id"))
        scope = {"tw": context, "game": context, "time_event": payload}
        runner.execute_code(_handler_call(handler, name), scope, script_id=f"timer_{event['id']}")
    messages = await manager._apply_script_changeset(context.changeset)
    if context.is_debug_enabled:
        debug = f"[DEBUG: Time event] {event['kind']} '{event.get('id')}' at {event['at']} min"
        await manager._save_chat_message("system", debug)
    return messages


async def run_due_time_events(manager: Any) -> list[Any]:
    """Fires every due time event; returns the applied script messages. May raise GameOverError."""
    messages: list[Any] = []
    for _ in range(MAX_EVENT_ROUNDS):
        runner = manager._get_script_runner()
        events = _take_due_events(manager, runner.scripts)
        if not events:
            break
        for event in events:
            messages.extend(await _run_event(manager, runner, event))
    return messages


def apply_narration_tick(manager: Any) -> int:
    """Advances the clock by one narration tick; returns the elapsed minutes."""
    states = dict(manager.state.entity_states or {})
    clock = read_clock(states)
    minutes, elapsed = narration_tick(
        int(manager.state.in_game_time or 0), clock, manager.adventure
    )
    manager.state.in_game_time = minutes
    _store_clock(manager, states, clock)
    return elapsed


async def stream_time_events(manager: Any, game_event: Any = None) -> AsyncGenerator[str, None]:
    """Fires due time events and streams their messages; a game over ends the session."""
    try:
        for message in await run_due_time_events(manager):
            yield sse_role_message(message)
    except GameOverError as goe:
        await manager._finalize_session("game_over", str(goe))
        if isinstance(game_event, GameEvent):
            game_event.game_over = True
            game_event.status_note = str(goe)


async def tick_after_narration(manager: Any, game_event: Any = None) -> AsyncGenerator[str, None]:
    """The player message's narration tick plus its time events (once per player message)."""
    if not getattr(manager, "clock_tick_pending", False):
        return
    manager.clock_tick_pending = False
    apply_narration_tick(manager)
    async for event in stream_time_events(manager, game_event):
        yield event
