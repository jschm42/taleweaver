"""``/fast_travel <place>``: walk to an unlocked fast travel point in one player message.

Fast travel is automated walking, not a teleport. Every exit on the route is used like
``/traverse_exit`` (``on_leave_scene``, ``on_exit_used``, companion follow, revival and fast
travel points, travel time, map, ``on_enter_scene``, due time events), but without a
narration per step. The trip stops early when anything happens on the way: a hook or time
event wrote a message, a choice opened, a fight started, a script moved the player, the next
exit is locked, or the protagonist went down. One arrival narration follows where the trip
ended, so the message has one in-game turn boundary and one scene checkpoint.

Spec: docs/specs/world_sections.md (6.3).
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy import select

from backend.api.routes.adventures.arrival_narration_flow import narrate_arrival
from backend.api.routes.adventures.dynamic_scene_flow import sync_dynamic_scene_audio
from backend.api.routes.adventures.fast_travel_plan import live_block_reason, load_travel_plan
from backend.api.routes.adventures.game_clock_flow import run_due_time_events
from backend.api.routes.adventures.respawn_flow import end_or_respawn
from backend.api.routes.adventures.scene_scripts import run_global_scene_scripts
from backend.api.routes.adventures.section_triggers import run_section_change_scripts
from backend.engine.interaction.trigger_service import TriggerService
from backend.engine.rules.rule_engine import GameOverError
from backend.engine.rules.travel_time import (
    advance_travel_time,
    format_duration,
    travel_minutes_of,
)
from backend.engine.sessions.scene_entry import enter_scene
from backend.models.chat import ChatMessage
from backend.models.world_entity import WorldScene

FAST_TRAVEL_COMMAND = "/fast_travel"


@dataclass
class _Trip:
    start_label: str
    passed: list[str] = field(default_factory=list)
    minutes: int = 0
    scene: Optional[WorldScene] = None
    stopped: str = ""


def is_fast_travel_command(user_msg: str) -> bool:
    text = (user_msg or "").strip().lower()
    return text == FAST_TRAVEL_COMMAND or text.startswith(f"{FAST_TRAVEL_COMMAND} ")


def _sse(role: str, content: str) -> str:
    return f"event: {role}\ndata: {json.dumps({'role': role, 'content': content})}\n\n"


async def _system(manager: Any, content: str) -> str:
    manager.db.add(ChatMessage(session_id=manager.state.session_id, role="system", content=content))
    return _sse("system", content)


async def _session_scene(manager: Any, scene_id: str) -> Optional[WorldScene]:
    res = await manager.db.execute(
        select(WorldScene).where(
            WorldScene.session_id == manager.state.session_id, WorldScene.id == scene_id
        )
    )
    return res.scalars().first()


async def _on_enter(manager: Any, scene: WorldScene) -> list[Any]:
    messages: list[Any] = []
    if scene.on_enter_scene_script or scene.on_enter_scene_text:
        messages.extend(
            await TriggerService.execute_trigger(
                manager.db,
                manager.state,
                "on_enter_scene",
                scene.id,
                script_code=scene.on_enter_scene_script,
                narrative_text=scene.on_enter_scene_text,
            )
        )
    messages.extend(await run_global_scene_scripts(manager, "on_enter_scene", scene.id))
    return messages


async def _time_events(manager: Any) -> list[Any]:
    try:
        return await run_due_time_events(manager)
    except GameOverError as goe:
        await end_or_respawn(manager, goe, None)
        return ["The journey ends abruptly."]


async def _hop(manager: Any, step: Any, trip: _Trip) -> list[Any]:
    """Uses one exit of the route; returns the messages its hooks and events produced."""
    interactions, state = manager.interactions, manager.state
    world_exit = await interactions._resolve_traversal_exit(step.exit_id)
    scene = await _session_scene(manager, step.target)
    if world_exit is None or world_exit.is_locked or scene is None:
        trip.stopped = "The way ahead is blocked."
        return []
    from_id = str(state.current_scene_id or "")
    messages = list(await interactions._fire_traversal_triggers(from_id, world_exit))
    state.current_scene_id = scene.id
    sync_dynamic_scene_audio(state, scene.id)
    notes = await enter_scene(
        manager.db, state, from_id, world_exit=world_exit, adventure=manager.adventure
    )
    for note in notes:
        manager.db.add(ChatMessage(session_id=state.session_id, role="system", content=note))
    trip.minutes += advance_travel_time(state, travel_minutes_of(world_exit))
    await interactions._record_map_traversal(from_id, scene, world_exit)
    await manager.db.commit()
    trip.scene = scene
    trip.passed.append(scene.label or scene.id)
    messages.extend(await _on_enter(manager, scene))
    messages.extend(await run_section_change_scripts(manager, from_id, scene.id))
    messages.extend(await _time_events(manager))
    return messages


def _stop_reason(manager: Any, trip: _Trip, messages: list[Any]) -> str:
    """Why the trip ends after this step, or "" to go on."""
    if trip.stopped:
        return trip.stopped
    if trip.scene is not None and manager.state.current_scene_id != trip.scene.id:
        return "Something carried you elsewhere."
    if int(getattr(manager.avatar, "hp", 1) or 0) <= 0 or manager._is_input_locked():
        return "The journey ends abruptly."
    blocked = live_block_reason(manager.state.entity_states)
    if blocked:
        return "Something demands your attention."
    return "Something happened on the way." if messages else ""


async def _walk(manager: Any, route: list[Any], trip: _Trip) -> AsyncGenerator[str, None]:
    for step in route:
        messages = await _hop(manager, step, trip)
        for message in messages:
            yield _sse(getattr(message, "role", "system"), str(message))
        trip.stopped = _stop_reason(manager, trip, messages)
        if trip.stopped:
            return


def _summary(trip: _Trip, goal_label: str) -> str:
    duration = f" ({format_duration(trip.minutes)})" if trip.minutes else ""
    where = trip.passed[-1] if trip.passed else trip.start_label
    if trip.stopped and where != goal_label:
        return f"You set out for {goal_label} but stop at {where}{duration}. {trip.stopped}"
    return f"You travel from {trip.start_label} to {goal_label}{duration}."


def _narration_prompt(trip: _Trip, goal_label: str, summary: str) -> str:
    via = ", ".join(trip.passed[:-1])
    passing = f" passing {via}" if via else ""
    return (
        f"[FAST_TRAVEL] The player travels from {trip.start_label} towards {goal_label}{passing}. "
        f"{summary} Tell the journey in one or two sentences, then describe where the player "
        "is now: atmosphere, key details, and anything immediately notable. Do not summarize "
        "earlier events."
    )


async def handle_fast_travel(
    manager: Any, user_msg: str, language: str | None = None
) -> AsyncGenerator[str, None]:
    """Runs ``/fast_travel <place>``: checks, walks the route, then narrates the arrival."""
    ref = user_msg.strip()[len(FAST_TRAVEL_COMMAND) :].strip()
    plan = await load_travel_plan(manager.db, manager.state, manager.adventure)
    point = plan.find(ref)
    refusal = plan.blocked or (
        f"You know no fast travel point called '{ref}'." if point is None else point.reason
    )
    if refusal or point is None:
        yield await _system(manager, refusal or "You cannot travel there.")
        await manager.db.commit()
        return
    start = await _session_scene(manager, str(manager.state.current_scene_id or ""))
    trip = _Trip(start_label=(start.label if start else "") or "here")
    async for chunk in _walk(manager, point.route, trip):
        yield chunk
    if trip.scene is None:
        yield await _system(manager, trip.stopped or "You cannot travel there.")
        await manager.db.commit()
        return
    # The journey replaces the narration tick; its time events already fired on the way.
    manager.clock_tick_pending = manager.clock_tick_pending and not trip.minutes
    summary = _summary(trip, point.label)
    yield await _system(manager, summary)
    await manager.db.commit()
    # A script may have moved the player on: narrate where the player actually is.
    here = await _session_scene(manager, str(manager.state.current_scene_id or "")) or trip.scene
    prompt = _narration_prompt(trip, point.label, summary)
    async for chunk in narrate_arrival(manager.interactions, here, prompt, language):
        yield chunk
