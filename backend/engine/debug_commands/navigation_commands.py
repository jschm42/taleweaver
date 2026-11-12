"""``/debug`` sub-commands that move the player or open exits (used by the debug world map)."""

from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm.attributes import flag_modified

from backend.engine.debug_commands.context import DebugContext
from backend.engine.interaction.map_engine import MapEngine
from backend.engine.interaction.script_item_apply import sync_exit_rows
from backend.engine.party.follow import bring_companion_along
from backend.engine.scripting.context import ScriptChangeset
from backend.models.world_entity import WorldExit, WorldScene

logger = logging.getLogger(__name__)

# Prefix of a successful ``/debug goto``; the turn stream then fires the arrival hooks.
DEBUG_GOTO_MARKER = "[TRIGGER_DEBUG_GOTO]"


def _session_or_template(model: Any, ctx: DebugContext) -> Any:
    return or_(
        model.session_id == ctx.state.session_id,
        and_(model.template_id == ctx.state.template_id, model.session_id.is_(None)),
    )


async def _find_exit(ctx: DebugContext, exit_id: str) -> Optional[WorldExit]:
    """The exit with this id, preferring the session row of the same route."""
    res = await ctx.db.execute(
        select(WorldExit)
        .where(_session_or_template(WorldExit, ctx), func.lower(WorldExit.id) == exit_id.lower())
        .order_by(WorldExit.session_id.is_(None))
    )
    found = res.scalars().first()
    if found is None or found.session_id is not None:
        return found
    res = await ctx.db.execute(
        select(WorldExit).where(
            WorldExit.session_id == ctx.state.session_id,
            WorldExit.from_scene_id == found.from_scene_id,
            WorldExit.to_scene_id == found.to_scene_id,
        )
    )
    return res.scalars().first() or found


def _clear_lock_overrides(ctx: DebugContext, world_exit: WorldExit) -> None:
    """Every override key the engine reads for this exit must say unlocked."""
    overrides = dict(ctx.state.exit_states or {})
    for key in (f"{world_exit.from_scene_id}:{world_exit.to_scene_id}", str(world_exit.id)):
        entry = dict(overrides.get(key) or {})
        entry["is_locked"] = False
        overrides[key] = entry
    ctx.state.exit_states = overrides
    flag_modified(ctx.state, "exit_states")


async def open_exit(ctx: DebugContext) -> str:
    """``/debug open_exit EXIT_ID``: unlocks the exit like ``tw.exits.unlock`` (no hooks fire)."""
    parts = ctx.parts
    if len(parts) < 2 or not parts[1].strip():
        return "DEBUG ERROR: Usage: /debug open_exit [EXIT_ID]"
    exit_id = parts[1].strip()
    world_exit = await _find_exit(ctx, exit_id)
    if world_exit is None:
        return f"DEBUG ERROR: Exit '{exit_id}' not found."

    _clear_lock_overrides(ctx, world_exit)
    update = {
        "from_scene_id": world_exit.from_scene_id,
        "to_scene_id": world_exit.to_scene_id,
        "is_locked": False,
    }
    # Session rows and the map edge; template rows stay untouched.
    await sync_exit_rows(ctx.db, ctx.state, ScriptChangeset(exit_updates=[update]))
    route = f"{world_exit.from_scene_id} -> {world_exit.to_scene_id}"
    return f"DEBUG: Exit '{world_exit.id}' ({route}) is now unlocked."


async def _find_scene(ctx: DebugContext, scene_id: str) -> Optional[WorldScene]:
    """Accepts the scene id or the map's safe id (upper case, ``-`` as ``_``)."""
    safe_id = MapEngine._safe_id(scene_id)
    res = await ctx.db.execute(
        select(WorldScene)
        .where(
            _session_or_template(WorldScene, ctx),
            or_(
                func.lower(WorldScene.id) == scene_id.lower(),
                func.upper(func.replace(WorldScene.id, "-", "_")) == safe_id,
            ),
        )
        .order_by(WorldScene.session_id.is_(None))
    )
    return res.scalars().first()


async def _record_visit(ctx: DebugContext, scene: WorldScene) -> None:
    from backend.api.routes.adventures.logic import AdventureLogic

    try:
        world_map = await AdventureLogic.get_or_create_map(
            ctx.db, ctx.state.template_id, session_id=ctx.state.session_id
        )
        MapEngine.register_visit(
            world_map,
            scene.id,
            label=scene.label,
            description=scene.description,
            image_url=scene.image_url,
        )
        world_map.current_scene_id = MapEngine._safe_id(scene.id)
    except Exception as exc:
        logger.warning("[Debug] Map update failed for goto %s: %s", scene.id, exc)


async def goto(ctx: DebugContext) -> str:
    """``/debug goto SCENE_ID``: moves the player into the scene, ignoring exits and locks."""
    parts = ctx.parts
    if len(parts) < 2 or not parts[1].strip():
        return "DEBUG ERROR: Usage: /debug goto [SCENE_ID]"
    scene_id = parts[1].strip()
    scene = await _find_scene(ctx, scene_id)
    if scene is None:
        return f"DEBUG ERROR: Scene '{scene_id}' not found."
    if str(ctx.state.current_scene_id or "").lower() == scene.id.lower():
        return f"DEBUG: You are already in '{scene.label or scene.id}'."

    left_scene_id = ctx.state.current_scene_id
    ctx.state.current_scene_id = scene.id
    await bring_companion_along(ctx.db, ctx.state, left_scene_id)
    await _record_visit(ctx, scene)
    return f"{DEBUG_GOTO_MARKER} {scene.id}"
