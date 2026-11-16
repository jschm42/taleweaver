"""``/travel <place>``: the play-agent walks to a place it already visited.

The route is the shortest path over open exits between visited places (``agent_known_map``).
Each agent step goes through one exit as a regular ``/traverse_exit`` turn, so companions
follow, scene scripts run and turn boundaries happen as when the player clicks the exits.
The goal is kept in ``entity_states["__agent__"]["travel_target"]``; while it is set, the next
agent steps continue the trip without asking the LLM (``next_travel_step``). Arriving, a
blocked route, or a new player instruction ends the trip.
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm.attributes import flag_modified

from backend.api.routes.adventures.agent_item_actions import AgentActionOutcome
from backend.api.routes.adventures.agent_known_map import (
    KnownMap,
    find_route,
    load_known_map,
    match_place,
)

TRAVEL_COMMAND = "/travel"
TRAVEL_KEY = "travel_target"


def _agent_state(state: Any) -> dict[str, Any]:
    states = state.entity_states if isinstance(state.entity_states, dict) else {}
    agent = states.get("__agent__")
    return agent if isinstance(agent, dict) else {}


def set_travel_target(state: Any, scene_id: Optional[str]) -> None:
    """Stores (or clears with None) the place the agent is travelling to."""
    states = dict(state.entity_states or {})
    agent = dict(states.get("__agent__") or {})
    if scene_id:
        agent[TRAVEL_KEY] = scene_id
    else:
        agent.pop(TRAVEL_KEY, None)
    states["__agent__"] = agent
    state.entity_states = states
    flag_modified(state, "entity_states")


def _place_ref(known: KnownMap, scene_id: str) -> str:
    """The place's name, or its id when another visited place has the same name."""
    label = known.label(scene_id)
    same = [s for s in known.visited if known.label(s).lower() == label.lower()]
    return label if len(same) == 1 else scene_id


def _known_places(known: KnownMap) -> str:
    return ", ".join(known.label(s) for s in known.visited if s != known.current) or "none"


async def travel(manager: Any, ref: str) -> AgentActionOutcome:
    """Goes through the first exit of the route to ``ref`` and remembers the goal."""
    known = await load_known_map(manager.db, manager.game_id, manager.state)
    goal = match_place(known, ref)
    if goal is None:
        set_travel_target(manager.state, None)
        return AgentActionOutcome(
            message=f"You have not been to a place called '{ref}'. Known places: {_known_places(known)}."
        )
    if goal == known.current:
        set_travel_target(manager.state, None)
        return AgentActionOutcome(message=f"You are already in {known.label(goal)}.")
    route = find_route(known, goal)
    if not route:
        set_travel_target(manager.state, None)
        return AgentActionOutcome(
            message=(
                f"No open way to {known.label(goal)} is known: locked exits or unexplored ways "
                "block it. Unlock an exit or explore with `/go`."
            )
        )
    # The last step arrives; afterwards the agent decides on its own again.
    set_travel_target(manager.state, goal if len(route) > 1 else None)
    return AgentActionOutcome(turn_command=f"/traverse_exit {route[0].exit_id}")


async def next_travel_step(manager: Any) -> Optional[tuple[str, str]]:
    """(thought, action) for the next step of a running trip, or None without one."""
    goal = _agent_state(manager.state).get(TRAVEL_KEY)
    if not goal:
        return None
    known = await load_known_map(manager.db, manager.game_id, manager.state)
    if goal == known.current or not known.is_visited(goal) or not find_route(known, goal):
        set_travel_target(manager.state, None)
        return None
    label = known.label(goal)
    return f"On my way to {label}.", f"{TRAVEL_COMMAND} {_place_ref(known, goal)}"
