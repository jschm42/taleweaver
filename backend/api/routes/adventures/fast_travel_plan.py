"""Where the player can fast travel to right now, and the route to each place.

A destination is an unlocked fast travel point (``rules/fast_travel.py``) that is still marked
as one in the session. The route is the cheapest one over open, known exits between visited
scenes (``interaction/route_finder.py``); the destination itself may be unvisited when a
script unlocked it. With a following companion, routes through solo passages are avoided
when another way exists.

Used by ``GET /{game_id}/travel/options`` (the player's map) and by ``/fast_travel``.
Spec: docs/specs/world_sections.md (6.3).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.agent_known_map import KnownMap, MapExit, load_known_map
from backend.api.routes.adventures.logic import AdventureLogic
from backend.engine.interaction.route_finder import cheapest_route, route_minutes
from backend.engine.party.party_state import read_party
from backend.engine.rules.fast_travel import block_reason, read_travel
from backend.engine.scripting.dialog import pending_dialog
from backend.models.world_entity import WorldScene

COMBAT_KEY = "__combat__"


@dataclass
class TravelPoint:
    scene_id: str
    label: str
    section_id: Optional[str]
    available: bool
    reason: str = ""
    minutes: int = 0
    route: list[MapExit] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "scene_id": self.scene_id,
            "label": self.label,
            "section_id": self.section_id,
            "available": self.available,
            "reason": self.reason,
            "minutes": self.minutes,
            "hops": len(self.route),
            "solo_passage": any(not step.companions_allowed for step in self.route),
        }


@dataclass
class TravelPlan:
    blocked: str
    points: list[TravelPoint]

    def find(self, ref: str) -> Optional[TravelPoint]:
        """The point called ``ref`` (scene id or name; exact first, then partial)."""
        wanted = " ".join(str(ref or "").lower().split())
        if not wanted:
            return None
        exact = [p for p in self.points if wanted in {p.scene_id.lower(), p.label.lower()}]
        if exact:
            return exact[0]
        return next((p for p in self.points if wanted in p.label.lower()), None)

    def as_dict(self) -> dict[str, Any]:
        return {"blocked": self.blocked, "points": [p.as_dict() for p in self.points]}


def live_block_reason(entity_states: Any) -> str:
    """Situations that stop every journey: a fight or an open choice."""
    states = entity_states if isinstance(entity_states, dict) else {}
    combat = states.get(COMBAT_KEY)
    if isinstance(combat, dict) and combat.get("active"):
        return "You cannot travel during a fight."
    if pending_dialog(states):
        return "Answer the open choice first."
    return ""


async def _session_points(db: AsyncSession, session_id: str) -> dict[str, WorldScene]:
    res = await db.execute(
        select(WorldScene).where(
            WorldScene.session_id == session_id, WorldScene.is_fast_travel_point.is_(True)
        )
    )
    return {scene.id: scene for scene in res.scalars().all()}


def _point(known: KnownMap, scene: WorldScene, avoid_solo: bool) -> TravelPoint:
    base = {"scene_id": scene.id, "label": scene.label or scene.id, "section_id": scene.section_id}
    if scene.id == known.current:
        return TravelPoint(**base, available=False, reason="You are here.")
    route = cheapest_route(
        known.exits,
        known.current,
        scene.id,
        lambda target: known.is_visited(target) or target == scene.id,
        avoid_solo=avoid_solo,
    )
    if route is None:
        return TravelPoint(**base, available=False, reason="No open way there is known.")
    return TravelPoint(**base, available=True, minutes=route_minutes(route), route=route)


async def load_travel_plan(db: AsyncSession, state: Any, adventure: Any) -> TravelPlan:
    """Every unlocked fast travel point with its route, plus why travel is blocked (or "")."""
    states = state.entity_states if isinstance(state.entity_states, dict) else {}
    record = read_travel(states)
    sequence = AdventureLogic.resolve_active_sequence(adventure, state)
    blocked = block_reason(adventure, sequence, record) or live_block_reason(states)
    scenes = await _session_points(db, state.session_id)
    known = await load_known_map(db, state.session_id, state)
    party = read_party(states)
    avoid_solo = bool(party.active_id and party.following)
    points = [
        _point(known, scenes[scene_id], avoid_solo)
        for scene_id in record["unlocked"]
        if scene_id in scenes
    ]
    points.sort(key=lambda p: (p.label.lower(), p.scene_id))
    return TravelPlan(blocked=blocked, points=points)
