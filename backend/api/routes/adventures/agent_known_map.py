"""The play-agent's map: the places the player knows, and routes between them.

Built from the same data as the player's map dialog: the scenes visited in this session
(``WorldMap.nodes``, registered by the engine on every scene change) and the session's exits.
Only player-visible facts go in: hidden exits are left out, a place that was never visited
shows up as "unexplored" behind its exit, and lock secrets (codes, key items) never appear.

``find_route`` walks open exits between visited places for the ``/travel`` command.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy import select

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
                MapExit(str(exit_row.id), scene_id, target, name, bool(exit_row.is_locked))
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
    return f"{map_exit.name} -> {target} [{status}]"


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


def find_route(known: KnownMap, goal: str) -> Optional[list[MapExit]]:
    """Shortest path from the current place to ``goal`` over open exits between visited places."""
    if goal == known.current:
        return []
    previous: dict[str, MapExit] = {}
    queue = deque([known.current])
    seen = {known.current}
    while queue:
        scene_id = queue.popleft()
        for map_exit in known.exits.get(scene_id, []):
            target = map_exit.target
            if map_exit.locked or target in seen or not known.is_visited(target):
                continue
            previous[target] = map_exit
            if target == goal:
                return _walk_back(previous, known.current, goal)
            seen.add(target)
            queue.append(target)
    return None


def _walk_back(previous: dict[str, MapExit], start: str, goal: str) -> list[MapExit]:
    route = []
    node = goal
    while node != start:
        step = previous[node]
        route.append(step)
        node = step.source
    return list(reversed(route))
