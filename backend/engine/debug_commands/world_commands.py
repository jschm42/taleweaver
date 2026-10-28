"""``/debug`` sub-commands for awards and the world map."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from backend.engine.debug_commands.context import DebugContext
from backend.engine.map_engine import MapEngine
from backend.models.world_entity import WorldExit, WorldScene


def _record_user_award(ctx: DebugContext, award: dict[str, Any], earned_at: str) -> bool:
    """Adds the award to the user's profile; False when it is already recorded."""
    user, adventure = ctx.user, ctx.adventure
    a_key = award.get("key", "")
    title = award.get("title") or a_key or "Unknown Award"
    dedupe_key = a_key or title
    user_awards = list(user.earned_awards or [])
    already_recorded = any(
        (ea.get("key") or ea.get("title")) == dedupe_key and ea.get("adventure_id") == adventure.id
        for ea in user_awards
    )
    if already_recorded:
        return False
    user_awards.append(
        {
            "key": dedupe_key,
            "title": title,
            "description": award.get("description"),
            "tier": award.get("tier"),
            "adventure_id": adventure.id,
            "adventure_title": adventure.title,
            "session_id": ctx.state.id,
            "earned_at": earned_at,
        }
    )
    user.earned_awards = user_awards
    flag_modified(user, "earned_awards")
    return True


async def grant_awards(ctx: DebugContext) -> str:
    """Grants every award of the current adventure to the player instantly."""
    adventure = ctx.adventure
    if adventure is None or ctx.user is None:
        return "DEBUG ERROR: Award command requires adventure and user context."
    if not adventure.awards:
        return "DEBUG: This adventure has no awards defined."

    # Earned awards live on the user profile; the adventure (a session copy) stays untouched.
    granted: list[str] = []
    now = datetime.now(UTC).isoformat()
    for award in adventure.awards:
        if not _record_user_award(ctx, award, now):
            continue
        title = award.get("title", award.get("key", ""))
        granted.append(f"  [{award.get('tier', '?').upper()}] {title}")

    if not granted:
        return "DEBUG: All awards are already earned."
    return "\n".join(["[DEBUG] All adventure awards granted:", *granted])


async def _all(ctx: DebugContext, model: Any, **criteria: Any) -> list[Any]:
    query = select(model).where(*(getattr(model, k) == v for k, v in criteria.items()))
    res = await ctx.db.execute(query)
    return list(res.scalars().all())


async def _map_scenes_and_exits(ctx: DebugContext) -> tuple[list[Any], list[Any]]:
    """Session scenes/exits, completed with template ones the session does not have."""
    session_id, template_id = ctx.state.session_id, ctx.state.template_id
    scenes = await _all(ctx, WorldScene, session_id=session_id)
    exits = await _all(ctx, WorldExit, session_id=session_id)
    if not template_id:
        return scenes, exits

    scene_ids = {s.id for s in scenes}
    scenes += [
        s for s in await _all(ctx, WorldScene, template_id=template_id) if s.id not in scene_ids
    ]
    exit_keys = {(e.from_scene_id, e.to_scene_id, e.label) for e in exits}
    exits += [
        e
        for e in await _all(ctx, WorldExit, template_id=template_id)
        if (e.from_scene_id, e.to_scene_id, e.label) not in exit_keys
    ]
    return scenes, exits


async def reveal_map(ctx: DebugContext) -> str:
    from backend.api.routes.adventures.logic import AdventureLogic

    scenes, exits = await _map_scenes_and_exits(ctx)
    # The template-level map is what the frontend always reads.
    world_map = await AdventureLogic.get_or_create_map(
        ctx.db, ctx.state.template_id, session_id=ctx.state.session_id
    )
    for scene in scenes:
        MapEngine.register_visit(
            world_map,
            scene.id,
            label=scene.label,
            description=scene.description,
            image_url=scene.image_url,
        )
    world_map.current_scene_id = MapEngine._safe_id(ctx.state.scene_id)
    for exit_row in exits:
        MapEngine.register_exit(
            world_map,
            exit_row.from_scene_id,
            exit_row.to_scene_id,
            exit_label=exit_row.label,
            is_locked=exit_row.is_locked,
        )
    return "DEBUG: World Map fully revealed and synchronized."
