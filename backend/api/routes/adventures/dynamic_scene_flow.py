"""Session-scoped materialization and runtime flow for Dynamic Scenes."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from backend.api.routes.adventures.dynamic_cluster_context import (
    collect_cluster_context,
    link_generated_container_inventories,
    normalize_match_token,
)
from backend.api.routes.adventures.dynamic_scene_materialize import (
    _DYNAMIC_ZONE_META_KEY,
    _build_npc_entity,
    _build_object_entity,
    _find_session_scene,
    _maybe_emit_interlude_quote,
    _safe_slug,
    is_unmaterialized_dynamic_scene,
    materialize_existing_dynamic_scene,
)
from backend.api.routes.adventures.dynamic_scene_media import (
    configure_scene_audio,
    extract_tone_text,
    generate_dynamic_visuals,
    sync_dynamic_scene_audio,
)
from backend.api.routes.adventures.dynamic_teleport import apply_script_teleport
from backend.engine.blueprint.parser import has_blueprint_tags
from backend.engine.world.dynamic_scene_generator import (
    generate_dynamic_interlude_quote,
    generate_dynamic_scene_payload,
)
from backend.engine.world.dynamic_scene_schemas import (
    DynamicGeneratedScenePayload,
    build_dynamic_placeholder_scene_id,
    normalize_dynamic_generation,
    normalize_dynamic_zone,
    normalize_instructions_scope,
)
from backend.models.adventure_template import AdventureTemplate
from backend.models.session_state import SessionState
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene

logger = logging.getLogger(__name__)


def _persist_generated_scene_entities(
    *,
    db: AsyncSession,
    state: SessionState,
    world_exit: WorldExit,
    origin_scene: Optional[WorldScene],
    target_id: str,
    zone: dict[str, Any],
    payload: DynamicGeneratedScenePayload,
    scene_image: Optional[str],
    npc_images: dict[int, Optional[str]],
    object_images: Optional[dict[int, Optional[str]]] = None,
    scene_audio_track_id: Optional[str],
) -> tuple[WorldScene, dict[str, Any]]:
    new_scene = WorldScene(
        id=target_id,
        template_id=None,
        session_id=state.session_id,
        label=payload.name[:100],
        description=payload.description[:2000],
        image_url=scene_image,
        audio_track_id=scene_audio_track_id,
    )
    db.add(new_scene)

    if (
        str(world_exit.exit_type or "").lower() not in {"bidirectional", "one_way_no_return"}
        and origin_scene
    ):
        db.add(
            WorldExit(
                template_id=None,
                session_id=state.session_id,
                from_scene_id=target_id,
                to_scene_id=origin_scene.id,
                label=f"Return to {origin_scene.label}"[:100],
                exit_type="one_way",
                is_locked=False,
                is_revealed=True,
            )
        )

    spawned_forward_exits: list[dict[str, str]] = []
    if int(zone["depth"]) < int(zone["max_depth"]):
        for idx, child_exit in enumerate(payload.forward_exits[:2], start=1):
            child_target = build_dynamic_placeholder_scene_id(
                zone["zone_id"],
                int(zone["depth"]) + 1,
                idx,
                suffix=target_id[-4:],
            )
            child_scope = normalize_instructions_scope(zone.get("instructions_scope"))
            child_consumed = bool(zone.get("instructions_consumed")) or (
                child_scope in {"once", "first_scene"}
                and not has_blueprint_tags(str(zone.get("instructions") or ""))
            )
            child_zone = {
                **zone,
                "depth": int(zone["depth"]) + 1,
                "root_theme": zone.get("root_theme") or zone["theme"],
                "theme": child_exit.theme_hint or zone["theme"],
                "instructions_consumed": child_consumed,
            }
            db.add(
                WorldExit(
                    template_id=None,
                    session_id=state.session_id,
                    from_scene_id=target_id,
                    to_scene_id=child_target,
                    label=child_exit.label[:100],
                    exit_type="bidirectional",
                    is_locked=False,
                    is_revealed=False,
                    dynamic_zone=child_zone,
                )
            )
            spawned_forward_exits.append(
                {
                    "to_scene_id": child_target,
                    "label": child_exit.label[:100],
                    "theme_hint": child_exit.theme_hint,
                }
            )

    spawned_npcs: list[dict[str, Any]] = []
    max_npcs = max(0, int(zone.get("max_npcs", 2)))
    for idx, npc in enumerate(payload.npcs[:max_npcs]):
        npc_entity = _build_npc_entity(
            session_id=state.session_id,
            target_id=target_id,
            npc=npc,
            image_url=npc_images.get(idx),
            state=state,
        )
        db.add(npc_entity)
        spawned_npcs.append(
            {
                "id": npc_entity.id,
                "name": npc_entity.name,
                "npc_type": npc_entity.npc_type,
                "role": npc.role,
                "attitude": npc.attitude,
                "combat_role": npc.combat_role,
                "description": npc_entity.description,
            }
        )

    spawned_objects: list[dict[str, Any]] = []
    persisted_objects = list(payload.objects[:5])
    raw_id_to_entity: dict[str, WorldEntity] = {}
    for idx, obj in enumerate(persisted_objects):
        obj_entity = _build_object_entity(
            session_id=state.session_id,
            target_id=target_id,
            obj=obj,
            image_url=(object_images or {}).get(idx),
        )
        db.add(obj_entity)
        raw_id_to_entity[normalize_match_token(obj.id)] = obj_entity
        raw_id_to_entity.setdefault(normalize_match_token(obj.name), obj_entity)
        spawned_objects.append(
            {
                "id": obj_entity.id,
                "name": obj_entity.name,
                "item_type": obj_entity.item_type,
                "is_takeable": obj_entity.is_portable,
                "description": obj_entity.description,
                "hp_change": obj.hp_change,
                "stamina_change": obj.stamina_change,
                "mana_change": obj.mana_change,
                "damage_dice": obj.damage_dice,
            }
        )
    link_generated_container_inventories(persisted_objects, raw_id_to_entity)

    entity_states = dict(state.entity_states or {})
    dyn_meta = dict(entity_states.get(_DYNAMIC_ZONE_META_KEY) or {})
    dyn_meta[target_id] = zone
    entity_states[_DYNAMIC_ZONE_META_KEY] = dyn_meta
    state.entity_states = entity_states
    flag_modified(state, "entity_states")

    generated_scene_data = {
        "id": target_id,
        "origin_scene_id": origin_scene.id if origin_scene else world_exit.from_scene_id,
        "zone_id": zone["zone_id"],
        "theme": zone["theme"],
        "depth": int(zone.get("depth") or 1),
        "max_depth": int(zone.get("max_depth") or 3),
        "danger_level": str(zone.get("danger_level") or "medium"),
        "name": new_scene.label,
        "description": new_scene.description,
        "visual_description": payload.visual_description,
        "music_prompt": payload.music_prompt,
        "npcs": spawned_npcs,
        "objects": spawned_objects,
        "forward_exits": spawned_forward_exits,
    }
    return new_scene, generated_scene_data


async def materialize_dynamic_scene_for_exit(
    *,
    db: AsyncSession,
    state: SessionState,
    adventure: AdventureTemplate,
    user: Any,
    world_exit: WorldExit,
    origin_scene: Optional[WorldScene],
    language: str = "English",
    emit_sse: Optional[Callable[[str, dict[str, Any]], Awaitable[None]]] = None,
) -> WorldScene:
    """Create a persistent session WorldScene, exits, and entities on first dynamic exit entry."""
    target_id = (
        world_exit.to_scene_id
        if not origin_scene or world_exit.from_scene_id.lower() == origin_scene.id.lower()
        else world_exit.from_scene_id
    )
    existing = await _find_session_scene(db, state.session_id, target_id)
    if existing:
        if is_unmaterialized_dynamic_scene(state, existing):
            return (
                await materialize_existing_dynamic_scene(
                    db=db,
                    state=state,
                    adventure=adventure,
                    user=user,
                    target_scene=existing,
                    origin_scene=origin_scene,
                    exit_label=world_exit.label or "Passage",
                    language=language,
                    emit_sse=emit_sse,
                    payload_fn=generate_dynamic_scene_payload,
                    interlude_fn=generate_dynamic_interlude_quote,
                )
                or existing
            )
        sync_dynamic_scene_audio(state, existing.id)
        return existing

    zone = normalize_dynamic_zone(world_exit.dynamic_zone)
    if not zone:
        raise ValueError(f"Exit '{world_exit.id}' is not a valid dynamic exit.")

    dyn_cfg = normalize_dynamic_generation(getattr(adventure, "dynamic_generation", None))
    raw_zone = world_exit.dynamic_zone if isinstance(world_exit.dynamic_zone, dict) else {}
    max_npcs = max(
        0,
        int(
            zone["max_npcs"] if raw_zone.get("max_npcs") is not None else dyn_cfg.get("max_npcs", 2)
        ),
    )
    zone["max_npcs"] = max_npcs
    if emit_sse:
        await emit_sse("status", {"content": "Exploring uncharted territory..."})

    tone_text = extract_tone_text(adventure)
    origin_name = origin_scene.label if origin_scene else world_exit.from_scene_id
    origin_desc = origin_scene.description if origin_scene else ""
    cluster_context = (
        await collect_cluster_context(db, state, zone["zone_id"], exclude_scene_id=target_id)
        if zone.get("cluster_consistency", True)
        else None
    )

    scene_task = asyncio.create_task(
        generate_dynamic_scene_payload(
            adventure_title=adventure.title or "Adventure",
            adventure_setting=adventure.plot or adventure.teaser or "",
            adventure_tone=tone_text,
            origin_scene_name=origin_name,
            origin_scene_description=origin_desc,
            exit_label=world_exit.label or "Passage",
            dynamic_zone=zone,
            user=user,
            db=db,
            adventure_id=adventure.id,
            game_id=state.session_id,
            language=language or adventure.language or "English",
            max_npcs_default=int(dyn_cfg.get("max_npcs", 2)),
            generation_config=dyn_cfg,
            cluster_context=cluster_context,
        )
    )

    if dyn_cfg.get("interlude_quote_enabled", True) and emit_sse:
        await _maybe_emit_interlude_quote(
            db=db,
            state=state,
            adventure=adventure,
            user=user,
            world_exit=world_exit,
            origin_name=origin_name,
            tone_text=tone_text,
            zone=zone,
            language=language or adventure.language or "English",
            emit_sse=emit_sse,
            interlude_fn=generate_dynamic_interlude_quote,
        )

    payload = await scene_task
    scene_image, npc_images, object_images = await generate_dynamic_visuals(
        payload=payload,
        dyn_cfg=dyn_cfg,
        origin_scene=origin_scene,
        user=user,
        adventure=adventure,
        session_id=state.session_id,
        target_id=target_id,
        max_npcs=max_npcs,
    )
    scene_audio_track_id = configure_scene_audio(
        state=state,
        dyn_cfg=dyn_cfg,
        origin_scene=origin_scene,
        target_id=target_id,
        zone=zone,
        payload=payload,
        adventure=adventure,
    )
    new_scene, generated_scene_data = _persist_generated_scene_entities(
        db=db,
        state=state,
        world_exit=world_exit,
        origin_scene=origin_scene,
        target_id=target_id,
        zone=zone,
        payload=payload,
        scene_image=scene_image,
        npc_images=npc_images,
        object_images=object_images,
        scene_audio_track_id=scene_audio_track_id,
    )
    await db.flush()

    after_script = str(zone.get("on_after_generated_script") or "").strip()
    if after_script:
        from backend.engine.interaction.trigger_service import TriggerService

        await TriggerService.execute_trigger(
            db,
            state,
            "after_generated",
            target_id,
            script_code=after_script,
            extra_scope={"generated_scene": generated_scene_data},
        )
        await db.flush()

    return new_scene


async def prepare_dynamic_traversal_sse(
    *,
    interactions: Any,
    exit_ref: str,
    language: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """Stream interlude quote and materialize a dynamic exit or scene before traversal."""
    state: SessionState = interactions.state
    db: AsyncSession = interactions.db
    world_exit = await interactions._resolve_traversal_exit(exit_ref)
    if not world_exit or world_exit.is_locked:
        return

    current_scene_id = str(state.current_scene_id or "").strip()
    if world_exit.from_scene_id.lower() == current_scene_id.lower():
        target_id = world_exit.to_scene_id
    elif (
        str(world_exit.exit_type or "").lower() == "bidirectional"
        and world_exit.to_scene_id.lower() == current_scene_id.lower()
    ):
        target_id = world_exit.from_scene_id
    else:
        return

    target_scene = await _find_session_scene(db, state.session_id, target_id)
    target_is_unmaterialized = is_unmaterialized_dynamic_scene(state, target_scene)
    if not world_exit.dynamic_zone and not target_is_unmaterialized:
        return

    if target_scene and not target_is_unmaterialized:
        sync_dynamic_scene_audio(state, target_id)
        return

    origin_scene = await _find_session_scene(db, state.session_id, current_scene_id)
    queue: asyncio.Queue[Optional[str]] = asyncio.Queue()

    async def emit_sse(event_name: str, data: dict[str, Any]) -> None:
        await queue.put(f"event: {event_name}\ndata: {json.dumps(data)}\n\n")

    async def _worker() -> None:
        try:
            await materialize_dynamic_scene_for_exit(
                db=db,
                state=state,
                adventure=interactions.adventure,
                user=interactions.manager.user,
                world_exit=world_exit,
                origin_scene=origin_scene,
                language=language or interactions.adventure.language or "English",
                emit_sse=emit_sse,
            )
            await db.commit()
        finally:
            await queue.put(None)

    task = asyncio.create_task(_worker())
    while True:
        chunk = await queue.get()
        if chunk is None:
            break
        yield chunk
    await task


__all__ = [
    "_build_npc_entity",
    "_build_object_entity",
    "_find_session_scene",
    "_safe_slug",
    "apply_script_teleport",
    "is_unmaterialized_dynamic_scene",
    "materialize_dynamic_scene_for_exit",
    "materialize_existing_dynamic_scene",
    "prepare_dynamic_traversal_sse",
    "sync_dynamic_scene_audio",
]
