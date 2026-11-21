"""Region triggers: ``on_leave_section`` / ``on_enter_section`` when the player changes region.

When a move leads into a scene of another world section, the top-level and active-sequence
scripts with these triggers run: first ``on_leave_section`` with the old region as target, then
``on_enter_section`` with the new one (scripts without a target run for every region). A move
between two scenes of the same region, or of scenes without a region, triggers nothing.

Called next to the global ``on_enter_scene`` scripts of a move: exit traversal, each fast
travel step, Game Master transitions, the respawn and ``/debug goto``. Script teleports do not
fire them (a script that moves the player can run its region logic itself).
Spec: docs/specs/world_sections.md (phase 4).
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import select

from backend.api.routes.adventures.scene_scripts import run_global_scene_scripts
from backend.models.world_entity import WorldScene

LEAVE_TRIGGER = "on_leave_section"
ENTER_TRIGGER = "on_enter_section"


async def _section_of(manager: Any, scene_id: Optional[str]) -> Optional[str]:
    if not scene_id:
        return None
    res = await manager.db.execute(
        select(WorldScene.section_id).where(
            WorldScene.session_id == manager.state.session_id, WorldScene.id == scene_id
        )
    )
    return res.scalars().first()


async def run_section_change_scripts(
    manager: Any, from_scene_id: Optional[str], to_scene_id: Optional[str]
) -> list[Any]:
    """Runs the leave/enter region scripts when the move crosses a region border."""
    before = await _section_of(manager, from_scene_id)
    after = await _section_of(manager, to_scene_id)
    if before == after:
        return []
    messages: list[Any] = []
    if before:
        messages.extend(await run_global_scene_scripts(manager, LEAVE_TRIGGER, before))
    if after:
        messages.extend(await run_global_scene_scripts(manager, ENTER_TRIGGER, after))
    return messages
