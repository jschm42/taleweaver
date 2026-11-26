"""What follows every scene change of the protagonist, in one place.

Every runtime place that sets ``state.current_scene_id`` (GM transition, exit traversal, script
teleports, ``/debug goto``) calls :func:`enter_scene` right after, before ``on_enter_scene``:

* the following companion comes along (``party.follow.bring_companion_along``),
* a scene marked as revival point becomes the session's respawn point,
* a fast travel point with the unlock mode ``visit`` is unlocked (``rules/fast_travel.py``).
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from backend.engine.party.follow import bring_companion_along
from backend.engine.rules.fast_travel import unlock_on_visit
from backend.engine.rules.respawn import read_respawn, respawn_settings, store_respawn
from backend.models.session_state import SessionState
from backend.models.world_entity import WorldScene


async def enter_scene(
    db: AsyncSession,
    state: SessionState,
    from_scene_id: Optional[str],
    *,
    world_exit: Any = None,
    adventure: Any = None,
) -> list[str]:
    """Runs the scene-entry follow-ups; returns system messages for the chat."""
    messages = await bring_companion_along(
        db, state, from_scene_id, world_exit=world_exit, adventure=adventure
    )
    if from_scene_id != state.current_scene_id:
        current = await _current_scene(db, state)
        messages.extend(await note_respawn_point(db, state, adventure, current))
        messages.extend(note_fast_travel_point(state, current))
    return messages


async def _current_scene(db: AsyncSession, state: SessionState) -> Optional[WorldScene]:
    res = await db.execute(
        select(WorldScene)
        .where(
            WorldScene.id == state.current_scene_id,
            or_(
                WorldScene.session_id == state.session_id,
                and_(WorldScene.template_id == state.template_id, WorldScene.session_id.is_(None)),
            ),
        )
        .order_by(WorldScene.session_id.is_(None))
    )
    return res.scalars().first()


def note_fast_travel_point(state: SessionState, scene: Optional[WorldScene]) -> list[str]:
    """Unlocks a fast travel point on its first visit (unlock mode ``visit``)."""
    states = dict(state.entity_states or {})
    if not unlock_on_visit(states, scene):
        return []
    state.entity_states = states
    flag_modified(state, "entity_states")
    return [f"Fast travel point unlocked: {scene.label}."]


async def note_respawn_point(
    db: AsyncSession,
    state: SessionState,
    adventure: Any = None,
    current: Optional[WorldScene] = None,
) -> list[str]:
    """Makes the current scene the respawn point when it is one; returns the chat notice.

    The point is recorded in every rule mode; the notice only shows in respawn mode.
    """
    scene = current if current is not None else await _current_scene(db, state)
    scene = scene if scene is not None and scene.is_respawn_point else None
    record = read_respawn(state.entity_states)
    if scene is None or record["point"] == scene.id:
        return []
    record["point"] = scene.id
    state.entity_states = store_respawn(state.entity_states, record)
    flag_modified(state, "entity_states")
    if adventure is None:
        # Lazy import: the session adventure loader lives in the API layer.
        from backend.api.routes.adventures.session_adventure import load_session_adventure

        adventure = await load_session_adventure(db, state)
    if not respawn_settings(getattr(adventure, "game_over_rules", None)).enabled:
        return []
    return [f"Revival point reached: {scene.label}."]
