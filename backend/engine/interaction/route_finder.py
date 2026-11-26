"""Cheapest route over known, open exits (Dijkstra).

Used by fast travel and by the Play-Agent's ``/travel``. A route step is any object with
``source``, ``target``, ``locked``, ``travel_minutes`` and ``companions_allowed`` (see
``agent_known_map.MapExit``). The cost of a route is compared as a tuple:

1. solo passages (``companions_allowed`` false), only when ``avoid_solo`` is set, so a
   following companion keeps up when another way exists,
2. total travel minutes,
3. number of exits.
"""

from __future__ import annotations

import heapq
import itertools
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Optional

Cost = tuple[int, int, int]


def _step_cost(step: Any, cost: Cost, avoid_solo: bool) -> Cost:
    solo = 1 if avoid_solo and getattr(step, "companions_allowed", True) is False else 0
    minutes = int(getattr(step, "travel_minutes", 0) or 0)
    return cost[0] + solo, cost[1] + minutes, cost[2] + 1


def cheapest_route(
    exits: Mapping[str, Sequence[Any]],
    start: str,
    goal: str,
    can_enter: Callable[[str], bool],
    *,
    avoid_solo: bool = False,
) -> Optional[list[Any]]:
    """The cheapest list of steps from ``start`` to ``goal``; [] when already there, None if none."""
    if start == goal:
        return []
    order = itertools.count()
    best: dict[str, Cost] = {start: (0, 0, 0)}
    previous: dict[str, Any] = {}
    queue: list[tuple[Cost, int, str]] = [((0, 0, 0), next(order), start)]
    while queue:
        cost, _, scene_id = heapq.heappop(queue)
        if scene_id == goal:
            return _walk_back(previous, start, goal)
        if cost > best.get(scene_id, cost):
            continue
        for step in exits.get(scene_id, []):
            target = step.target
            if step.locked or not can_enter(target):
                continue
            new_cost = _step_cost(step, cost, avoid_solo)
            if target in best and best[target] <= new_cost:
                continue
            best[target] = new_cost
            previous[target] = step
            heapq.heappush(queue, (new_cost, next(order), target))
    return None


def _walk_back(previous: dict[str, Any], start: str, goal: str) -> list[Any]:
    route = []
    node = goal
    while node != start:
        step = previous[node]
        route.append(step)
        node = step.source
    return list(reversed(route))


def route_minutes(route: Sequence[Any]) -> int:
    return sum(int(getattr(step, "travel_minutes", 0) or 0) for step in route)
