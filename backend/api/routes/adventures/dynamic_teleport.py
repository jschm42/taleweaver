"""Runtime script teleport resolver for static and dynamic scenes."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.dynamic_scene_media import sync_dynamic_scene_audio
from backend.engine.world.dynamic_scene_schemas import normalize_dynamic_zone
from backend.models.adventure_template import AdventureTemplate
from backend.models.session_state import SessionState
from backend.models.world_entity import WorldExit, WorldScene
from backend.models.world_map import WorldMap


async def _find_session_scene(
    db: AsyncSession, session_id: str, scene_id: str
) -> Optional[WorldScene]:
    res = await db.execute(
        select(WorldScene).where(
            WorldScene.session_id == session_id,
            func.lower(WorldScene.id) == str(scene_id).lower(),
        )
    )
    return res.scalars().first()


async def _find_dynamic_exit(db: AsyncSession, session_id: str, ref: str) -> Optional[WorldExit]:
    """Find a session dynamic exit by target scene ID, exit ID, or dynamic zone_id."""
    needle = str(ref or "").strip().lower()
    if not needle:
        return None
    res = await db.execute(select(WorldExit).where(WorldExit.session_id == session_id))
    for exit_row in res.scalars().all():
        zone = exit_row.dynamic_zone if isinstance(exit_row.dynamic_zone, dict) else None
        if not zone or zone.get("enabled") is False:
            continue
        zone_id = str(zone.get("zone_id") or "").strip().lower()
        matches = {
            str(exit_row.to_scene_id or "").strip().lower(),
            str(exit_row.id or "").strip().lower(),
            zone_id,
        }
        if needle in matches:
            return exit_row
    return None


async def _resolve_adventure_for_teleport(
    db: AsyncSession, state: SessionState, adventure: Any
) -> Any:
    if adventure is not None:
        return adventure
    if state.template_id:
        res = await db.execute(
            select(AdventureTemplate).where(AdventureTemplate.id == state.template_id)
        )
        found = res.scalars().first()
        if found is not None:
            return found
    return SimpleNamespace(
        id=state.template_id or "adventure",
        title="Adventure",
        plot="",
        teaser="",
        language="English",
        dynamic_generation={},
    )


async def _update_map_for_teleport(
    db: AsyncSession,
    state: SessionState,
    origin_scene_id: str,
    target_scene: Optional[WorldScene],
    exit_label: str = "Teleporter",
    register_edge: bool = True,
) -> None:
    if not target_scene:
        return
    map_res = await db.execute(select(WorldMap).where(WorldMap.session_id == state.session_id))
    world_map = map_res.scalars().first()
    if not world_map:
        return
    from backend.engine.interaction.map_engine import MapEngine

    if register_edge and origin_scene_id:
        MapEngine.register_exit(
            world_map,
            origin_scene_id,
            target_scene.id,
            exit_label=exit_label,
            exit_type="one_way",
        )
    MapEngine.register_visit(
        world_map,
        target_scene.id,
        label=target_scene.label,
        description=(target_scene.description or "")[:160],
        image_url=target_scene.image_url,
    )


def _merge_dynamic_teleport_zone(
    req: dict[str, Any], matched_exit: Optional[WorldExit]
) -> dict[str, Any]:
    base_zone = (
        dict(matched_exit.dynamic_zone)
        if matched_exit and isinstance(matched_exit.dynamic_zone, dict)
        else {}
    )
    raw_zone: dict[str, Any] = {
        "enabled": True,
        "zone_id": req.get("zone_id")
        or base_zone.get("zone_id")
        or req.get("label")
        or "teleporter",
        "theme": req.get("theme") or base_zone.get("theme") or "An uncharted dimensional chamber",
        "depth": 1,
        "max_depth": req["max_depth"]
        if req.get("max_depth") is not None
        else base_zone.get("max_depth", 3),
        "danger_level": req.get("danger_level") or base_zone.get("danger_level") or "medium",
        "max_npcs": req["max_npcs"]
        if req.get("max_npcs") is not None
        else base_zone.get("max_npcs"),
        "audio_mode": req["audio_mode"]
        if req.get("audio_mode") is not None
        else base_zone.get("audio_mode"),
        "cul_de_sac_on_max_depth": (
            req["cul_de_sac"]
            if req.get("cul_de_sac") is not None
            else base_zone.get("cul_de_sac_on_max_depth", True)
        ),
        "instructions": (
            req["instructions"]
            if req.get("instructions") is not None
            else base_zone.get("instructions")
        ),
        "instructions_scope": (
            req["instructions_scope"]
            if req.get("instructions_scope") is not None
            else base_zone.get("instructions_scope")
        ),
        "cluster_consistency": (
            req["cluster_consistency"]
            if req.get("cluster_consistency") is not None
            else base_zone.get("cluster_consistency", True)
        ),
        "root_theme": base_zone.get("root_theme") or base_zone.get("theme"),
    }
    normalized = normalize_dynamic_zone(raw_zone)
    if normalized:
        return normalized
    return {
        "enabled": True,
        "zone_id": "teleporter",
        "theme": "An uncharted dimensional chamber",
        "depth": 1,
        "max_depth": 3,
        "danger_level": "medium",
        "max_npcs": 2,
        "audio_mode": None,
        "allowed_entity_types": ["NPC", "OBJECT", "CONTAINER", "READABLE", "SWITCH"],
        "cul_de_sac_on_max_depth": True,
    }


async def _move_into_scene(
    *,
    db: AsyncSession,
    state: SessionState,
    changeset: Any,
    scene: WorldScene,
    origin_scene_id: str,
    exit_label: str,
    register_edge: bool,
) -> WorldScene:
    state.current_scene_id = scene.id
    changeset.teleport_scene_id = scene.id
    sync_dynamic_scene_audio(state, scene.id)
    await _update_map_for_teleport(
        db,
        state,
        origin_scene_id,
        scene,
        exit_label=exit_label,
        register_edge=register_edge,
    )
    return scene


async def _maybe_materialize_existing_scene(
    *,
    db: AsyncSession,
    state: SessionState,
    scene: WorldScene,
    origin_scene_id: str,
    exit_label: str,
    adventure: Any,
    user: Any,
) -> WorldScene:
    """Materialize a pre-mapped Dynamic Scene on script teleport if not yet generated."""
    from backend.api.routes.adventures.dynamic_scene_flow import (
        is_unmaterialized_dynamic_scene,
        materialize_existing_dynamic_scene,
    )

    if not is_unmaterialized_dynamic_scene(state, scene):
        return scene
    origin_scene = await _find_session_scene(db, state.session_id, origin_scene_id)
    return (
        await materialize_existing_dynamic_scene(
            db=db,
            state=state,
            adventure=adventure,
            user=user,
            target_scene=scene,
            origin_scene=origin_scene,
            exit_label=exit_label,
            language=getattr(adventure, "language", None) or "English",
        )
        or scene
    )


async def _enter_existing_exit_target(
    *,
    db: AsyncSession,
    state: SessionState,
    changeset: Any,
    matched_exit: WorldExit,
    origin_scene_id: str,
    exit_label: str,
    register_edge: bool,
    adventure: Any,
    user: Any,
) -> WorldScene:
    from backend.api.routes.adventures.dynamic_scene_flow import materialize_dynamic_scene_for_exit

    existing = await _find_session_scene(db, state.session_id, matched_exit.to_scene_id)
    if existing:
        existing = await _maybe_materialize_existing_scene(
            db=db,
            state=state,
            scene=existing,
            origin_scene_id=origin_scene_id,
            exit_label=exit_label or matched_exit.label or "Passage",
            adventure=adventure,
            user=user,
        )
        return await _move_into_scene(
            db=db,
            state=state,
            changeset=changeset,
            scene=existing,
            origin_scene_id=origin_scene_id,
            exit_label=exit_label,
            register_edge=register_edge,
        )

    origin_scene = await _find_session_scene(db, state.session_id, matched_exit.from_scene_id)
    new_scene = await materialize_dynamic_scene_for_exit(
        db=db,
        state=state,
        adventure=adventure,
        user=user,
        world_exit=matched_exit,
        origin_scene=origin_scene,
        language=getattr(adventure, "language", None) or "English",
    )
    return await _move_into_scene(
        db=db,
        state=state,
        changeset=changeset,
        scene=new_scene,
        origin_scene_id=origin_scene_id,
        exit_label=exit_label,
        register_edge=register_edge,
    )


async def _apply_dynamic_teleport_request(
    *,
    db: AsyncSession,
    state: SessionState,
    changeset: Any,
    req: dict[str, Any],
    origin_scene_id: str,
    adventure: Any,
    user: Any,
) -> Optional[WorldScene]:
    from backend.api.routes.adventures.dynamic_scene_flow import materialize_dynamic_scene_for_exit

    ref_key = str(req.get("reference_key") or "").strip()
    matched_exit = await _find_dynamic_exit(db, state.session_id, ref_key) if ref_key else None
    fresh = bool(req.get("fresh", False))
    return_exit = bool(req.get("return_exit", True))
    has_overrides = any(
        req.get(k) is not None
        for k in (
            "max_depth",
            "danger_level",
            "max_npcs",
            "audio_mode",
            "cul_de_sac",
            "instructions",
            "instructions_scope",
            "cluster_consistency",
        )
    )

    if matched_exit and not fresh and not has_overrides:
        return await _enter_existing_exit_target(
            db=db,
            state=state,
            changeset=changeset,
            matched_exit=matched_exit,
            origin_scene_id=origin_scene_id,
            exit_label=matched_exit.label or str(req.get("label") or "Teleporter"),
            register_edge=return_exit,
            adventure=adventure,
            user=user,
        )

    target_id = str(req.get("target_scene_id") or "").strip()
    existing = None if fresh else await _find_session_scene(db, state.session_id, target_id)
    if existing:
        existing = await _maybe_materialize_existing_scene(
            db=db,
            state=state,
            scene=existing,
            origin_scene_id=origin_scene_id,
            exit_label=str(req.get("label") or "Teleporter"),
            adventure=adventure,
            user=user,
        )
        return await _move_into_scene(
            db=db,
            state=state,
            changeset=changeset,
            scene=existing,
            origin_scene_id=origin_scene_id,
            exit_label=str(req.get("label") or "Teleporter"),
            register_edge=return_exit,
        )

    zone_cfg = _merge_dynamic_teleport_zone(req, matched_exit)
    virtual_exit = WorldExit(
        template_id=None,
        session_id=state.session_id,
        from_scene_id=origin_scene_id,
        to_scene_id=target_id,
        label=str(req.get("label") or "Teleporter")[:100],
        exit_type="one_way" if return_exit else "one_way_no_return",
        is_locked=False,
        is_revealed=False,
        dynamic_zone=zone_cfg,
    )
    db.add(virtual_exit)
    origin_scene = await _find_session_scene(db, state.session_id, origin_scene_id)
    new_scene = await materialize_dynamic_scene_for_exit(
        db=db,
        state=state,
        adventure=adventure,
        user=user,
        world_exit=virtual_exit,
        origin_scene=origin_scene,
        language=getattr(adventure, "language", None) or "English",
    )
    return await _move_into_scene(
        db=db,
        state=state,
        changeset=changeset,
        scene=new_scene,
        origin_scene_id=origin_scene_id,
        exit_label=virtual_exit.label,
        register_edge=return_exit,
    )


async def apply_script_teleport(
    db: AsyncSession,
    state: SessionState,
    changeset: Any,
    *,
    adventure: Any = None,
    user: Any = None,
) -> Optional[WorldScene]:
    """Apply a script changeset's teleport or teleport_dynamic request to the session."""
    dyn_req = getattr(changeset, "teleport_dynamic_request", None)
    target_id = str(getattr(changeset, "teleport_scene_id", "") or "").strip()
    if not dyn_req and not target_id:
        return None

    origin_scene_id = str((dyn_req or {}).get("origin_scene_id") or state.current_scene_id or "")
    resolved_adv = await _resolve_adventure_for_teleport(db, state, adventure)

    if isinstance(dyn_req, dict):
        return await _apply_dynamic_teleport_request(
            db=db,
            state=state,
            changeset=changeset,
            req=dyn_req,
            origin_scene_id=origin_scene_id,
            adventure=resolved_adv,
            user=user,
        )

    existing_scene = await _find_session_scene(db, state.session_id, target_id)
    if existing_scene:
        existing_scene = await _maybe_materialize_existing_scene(
            db=db,
            state=state,
            scene=existing_scene,
            origin_scene_id=origin_scene_id,
            exit_label="Teleporter",
            adventure=resolved_adv,
            user=user,
        )
        return await _move_into_scene(
            db=db,
            state=state,
            changeset=changeset,
            scene=existing_scene,
            origin_scene_id=origin_scene_id,
            exit_label="Teleporter",
            register_edge=True,
        )

    dyn_exit = await _find_dynamic_exit(db, state.session_id, target_id)
    if not dyn_exit:
        state.current_scene_id = target_id
        sync_dynamic_scene_audio(state, target_id)
        return None

    return await _enter_existing_exit_target(
        db=db,
        state=state,
        changeset=changeset,
        matched_exit=dyn_exit,
        origin_scene_id=origin_scene_id,
        exit_label=dyn_exit.label or "Teleporter",
        register_edge=True,
        adventure=resolved_adv,
        user=user,
    )
