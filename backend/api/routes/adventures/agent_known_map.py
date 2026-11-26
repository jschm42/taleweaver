"""The play-agent's map: the places the player knows, and routes between them.

Built from the same data as the player's map dialog: the scenes visited in this session
(``WorldMap.nodes``, registered by the engine on every scene change) and the session's exits.
Only player-visible facts go in: hidden exits are left out, a place that was never visited
shows up as "unexplored" behind its exit, and lock secrets (codes, key items) never appear.

``find_route`` takes the cheapest route (travel time, then exits) over open exits between
visited places for the ``/travel`` command (``engine/interaction/route_finder.py``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy import select

from backend.engine.interaction.route_finder import cheapest_route
from backend.engine.rules.travel_time import format_duration, travel_minutes_of
from backend.engine.world.exit_labels import exit_display_name
from backend.models.world_entity import WorldExit, WorldScene
from backend.models.world_map import WorldMap

UNEXPLORED = "unexplored"


@dataclass(frozen=True)
class MapExit:
    """One way out of a visited place, oriented away from it."""

    exit_id: str
    source: str
    target: str
    name: str
    locked: bool
    travel_minutes: int = 0
    companions_allowed: bool = True


@dataclass
class KnownMap:
    current: str
    visited: list[str]
    labels: dict[str, str]
    exits: dict[str, list[MapExit]] = field(default_factory=dict)

    def label(self, scene_id: str) -> str:
        return self.labels.get(scene_id, scene_id)

    def is_visited(self, scene_id: str) -> bool:
        return scene_id in self.visited


def _norm(value: Any) -> str:
    return " ".join(str(value or "").lower().split())


def _leaves(exit_row: WorldExit, scene_id: str) -> Optional[str]:
    """The far side when ``exit_row`` leads out of ``scene_id``, else None."""
    if exit_row.from_scene_id == scene_id:
        return exit_row.to_scene_id
    if exit_row.to_scene_id == scene_id and exit_row.exit_type == "bidirectional":
        return exit_row.from_scene_id
    return None


def _visited_ids(world_map: Optional[WorldMap], current: str) -> list[str]:
    nodes = world_map.nodes if world_map and isinstance(world_map.nodes, dict) else {}
    ids = [
        str(node.get("id")) for node in nodes.values() if isinstance(node, dict) and node.get("id")
    ]
    return list(dict.fromkeys([current, *ids])) if current else ids


def build_known_map(
    current: str, visited: list[str], exit_rows: list[WorldExit], labels: dict[str, str]
) -> KnownMap:
    """The known graph: every visible exit that leaves a visited place."""
    known = KnownMap(current=current, visited=visited, labels=labels)
    for scene_id in visited:
        for exit_row in exit_rows:
            target = _leaves(exit_row, scene_id)
            if target is None or getattr(exit_row, "is_hidden", False):
                continue
            name = exit_display_name(exit_row.label, labels.get(target, target))
            known.exits.setdefault(scene_id, []).append(
                MapExit(
                    str(exit_row.id),
                    scene_id,
                    target,
                    name,
                    bool(exit_row.is_locked),
                    travel_minutes_of(exit_row),
                    getattr(exit_row, "companions_allowed", True) is not False,
                )
            )
    return known


async def load_known_map(db: Any, game_id: str, state: Any) -> KnownMap:
    """The player's known map for a session."""
    current = str(state.current_scene_id or "")
    map_res = await db.execute(select(WorldMap).where(WorldMap.session_id == game_id))
    exit_res = await db.execute(select(WorldExit).where(WorldExit.session_id == game_id))
    scene_res = await db.execute(select(WorldScene).where(WorldScene.session_id == game_id))
    labels = {s.id: s.label or s.id for s in scene_res.scalars().all()}
    visited = _visited_ids(map_res.scalars().first(), current)
    return build_known_map(current, visited, list(exit_res.scalars().all()), labels)


def _exit_line(known: KnownMap, map_exit: MapExit) -> str:
    target = known.label(map_exit.target) if known.is_visited(map_exit.target) else UNEXPLORED
    status = "LOCKED" if map_exit.locked else "OPEN"
    journey = (
        f", {format_duration(map_exit.travel_minutes)} journey" if map_exit.travel_minutes else ""
    )
    return f"{map_exit.name} -> {target} [{status}{journey}]"


def format_fast_travel(points: list[Any]) -> str:
    """The FAST TRAVEL block of the agent prompt: unlocked points the agent can travel to."""
    usable = [p for p in points if p.available]
    if not usable:
        return ""
    lines = [
        f"- {p.label}" + (f" ({format_duration(p.minutes)})" if p.minutes else "") for p in usable
    ]
    return (
        "FAST TRAVEL (unlocked places; `/fast_travel <place>` walks the whole known route in one "
        "step, its travel time passes):\n" + "\n".join(lines)
    )


def format_known_map(known: KnownMap) -> str:
    """The KNOWN MAP block of the agent prompt."""
    if len(known.visited) <= 1:
        return "KNOWN MAP: You only know this place so far."
    lines = []
    for scene_id in known.visited:
        here = " (YOU ARE HERE)" if scene_id == known.current else ""
        exits = (
            "; ".join(_exit_line(known, e) for e in known.exits.get(scene_id, []))
            or "no known exits"
        )
        lines.append(f"- {known.label(scene_id)}{here}: {exits}")
    return (
        "KNOWN MAP (places you visited and their exits; 'unexplored' = never entered):\n"
        + "\n".join(lines)
        + "\nWalk to a visited place with `/travel <place>` (open exits only, one exit per step). "
        "Explore 'unexplored' exits with `/go` from the place they leave."
    )


def match_place(known: KnownMap, ref: str) -> Optional[str]:
    """The visited place called ``ref`` (label or id; exact match first, then partial)."""
    wanted = _norm(ref)
    if not wanted:
        return None
    names = {
        scene_id: {_norm(known.label(scene_id)), _norm(scene_id)} for scene_id in known.visited
    }
    exact = next((s for s, n in names.items() if wanted in n), None)
    if exact:
        return exact
    return next((s for s in known.visited if wanted in _norm(known.label(s))), None)


def find_route(known: KnownMap, goal: str, *, avoid_solo: bool = False) -> Optional[list[MapExit]]:
    """Cheapest route from the current place to ``goal`` over open exits between visited places."""
    return cheapest_route(known.exits, known.current, goal, known.is_visited, avoid_solo=avoid_solo)
