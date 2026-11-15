"""In-place materialization and shared entity builders for Dynamic Scenes."""

from __future__ import annotations

import asyncio
import contextlib
import re
from collections.abc import Awaitable, Callable
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from backend.api.routes.adventures.dynamic_challenge_helper import (
    apply_cluster_key_and_climax_progression,
    apply_dynamic_scripts_and_locks,
    build_dynamic_npc_clones,
    compute_party_hp_budget,
    link_dynamic_npc_inventories,
    resolve_fallback_zone_key_prompt,
    scale_dynamic_object_stats,
)
from backend.api.routes.adventures.dynamic_cluster_context import (
    collect_cluster_context,
    link_generated_container_inventories,
    normalize_match_token,
)
from backend.api.routes.adventures.dynamic_scene_media import (
    PendingDynamicVisuals,
    extract_tone_text,
    prepare_scene_audio_and_visuals,
    register_pending_dynamic_visuals,
    sync_dynamic_scene_audio,
)
from backend.engine.world.dynamic_scene_generator import (
    generate_dynamic_interlude_quote,
    generate_dynamic_scene_payload,
)
from backend.engine.world.dynamic_scene_schemas import (
    DynamicGeneratedNpc,
    DynamicGeneratedObject,
    DynamicGeneratedScenePayload,
    normalize_dynamic_generation,
    normalize_dynamic_zone,
)
from backend.models.adventure_template import AdventureTemplate
from backend.models.session_state import SessionState
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene

_DYNAMIC_ZONE_META_KEY = "__dynamic_zones__"

_COMBAT_ROLE_DEFAULTS: dict[str, dict[str, int]] = {
    "minion": {"hp": 45, "ac": 11},
    "standard": {"hp": 85, "ac": 13},
    "elite": {"hp": 140, "ac": 15},
    "boss": {"hp": 220, "ac": 16},
}


def _safe_slug(raw: str, max_len: int = 24) -> str:
    """Normalize a raw entity identifier into an uppercase alphanumeric underscore slug."""
    cleaned = re.sub(r"[^A-Z0-9]+", "_", str(raw or "").upper()).strip("_")
    return (cleaned or "ITEM")[:max_len]


async def _find_session_scene(
    db: AsyncSession, session_id: str, scene_id: str
) -> Optional[WorldScene]:
    """Look up a session-scoped WorldScene case-insensitively by ID."""
    res = await db.execute(
        select(WorldScene).where(
            WorldScene.session_id == session_id,
            func.lower(WorldScene.id) == str(scene_id).lower(),
        )
    )
    return res.scalars().first()


def _build_npc_entity(
    *,
    session_id: str,
    target_id: str,
    npc: DynamicGeneratedNpc,
    image_url: Optional[str],
    state: SessionState,
) -> WorldEntity:
    """Construct a session WorldEntity for a dynamically generated NPC."""
    entity_id = f"{target_id}_{_safe_slug(npc.id, 16)}"[:50]
    npc_type = str(getattr(npc, "npc_type", "HUMANOID") or "HUMANOID").upper()
    dialogue_style = str(npc.dialogue_style or "").strip()
    if npc_type in {"HUMANOID", "BEING"}:
        speech_note = "Speaks in plain, intelligible full sentences."
        if "full sentences" not in dialogue_style.lower():
            dialogue_style = f"{dialogue_style} ({speech_note})" if dialogue_style else speech_note

    is_hostile = npc.attitude == "hostile"
    stats = _COMBAT_ROLE_DEFAULTS.get(npc.combat_role, {"hp": 80, "ac": 12}) if is_hostile else None
    hp_val = stats["hp"] if stats else 100
    entity = WorldEntity(
        id=entity_id,
        template_id=None,
        session_id=session_id,
        entity_type="NPC",
        name=npc.name[:100],
        description=npc.description[:1000],
        appearance=npc.visual_description[:100] if npc.visual_description else None,
        current_scene_id=target_id,
        image_url=image_url,
        npc_type=npc_type,
        movement_type="STATIONARY",
        moveable=False,
        goal=npc.role[:1000] if npc.role else None,
        character=dialogue_style[:1000] if dialogue_style else None,
        hp=hp_val,
        max_hp=hp_val,
        mana=100,
        max_mana=100,
        stamina=100,
        max_stamina=100,
        is_attackable=is_hostile,
        is_killable=is_hostile,
        inventory=[],
        metadata_json={
            "dynamic_generated": True,
            "attitude": npc.attitude,
            "combat_role": npc.combat_role,
        },
    )
    if is_hostile:
        states = dict(state.entity_states or {})
        states[entity_id] = {"hp": hp_val, "max_hp": hp_val, "attitude": "hostile"}
        state.entity_states = states
        flag_modified(state, "entity_states")
    return entity


def _apply_item_type_metadata(obj: DynamicGeneratedObject, metadata: dict[str, Any]) -> None:
    if obj.item_type == "SWITCH":
        metadata["switch_states"] = ["OFF", "ON"]
        metadata["switch_initial_state"] = "OFF"
        metadata["switch"] = {"states": ["OFF", "ON"], "initial_state": "OFF"}
    elif obj.item_type == "READABLE" and obj.text_log_content:
        metadata["text_log_content"] = obj.text_log_content[:1000]
        metadata["text_log_format"] = "DOCUMENT"
    elif obj.item_type == "WEAPON" and obj.damage_dice:
        metadata["damage_dice"] = obj.damage_dice[:20]


def _build_object_metadata(obj: DynamicGeneratedObject) -> dict[str, Any]:
    metadata: dict[str, Any] = {"dynamic_generated": True}
    _apply_item_type_metadata(obj, metadata)
    for key in ("effect_type", "effect_value"):
        if (val := getattr(obj, key, None)) is not None:
            metadata[key] = val
    for key in ("hp_change", "stamina_change", "mana_change"):
        if val := getattr(obj, key, None):
            metadata[key] = int(val)
    for attr, meta_key in (("is_locked", "locked"), ("is_zone_key", "is_zone_key")):
        if getattr(obj, attr, False):
            metadata[meta_key] = True
    if getattr(obj, "lock_description", None):
        metadata["lock_description"] = str(obj.lock_description)[:255]
    return metadata


def _build_object_entity(
    *,
    session_id: str,
    target_id: str,
    obj: DynamicGeneratedObject,
    image_url: Optional[str] = None,
) -> WorldEntity:
    """Construct a session WorldEntity for a dynamically generated item, container, or switch."""
    entity_id = f"{target_id}_{_safe_slug(obj.id, 16)}"[:50]
    metadata = _build_object_metadata(obj)

    return WorldEntity(
        id=entity_id,
        template_id=None,
        session_id=session_id,
        entity_type="OBJECT",
        name=obj.name[:100],
        description=obj.description[:1000],
        appearance=obj.visual_description[:100] if obj.visual_description else None,
        current_scene_id=target_id,
        image_url=image_url,
        item_type=obj.item_type,
        wearable_slots=obj.wearable_slots or None,
        stat_modifier_strength=obj.stat_modifier_strength or None,
        stat_modifier_dexterity=obj.stat_modifier_dexterity or None,
        stat_modifier_intelligence=obj.stat_modifier_intelligence or None,
        stat_modifier_wisdom=obj.stat_modifier_wisdom or None,
        stat_modifier_charisma=obj.stat_modifier_charisma or None,
        stat_modifier_armor_class=obj.stat_modifier_armor_class or None,
        is_portable=bool(
            obj.is_takeable
            and obj.item_type in {"STANDARD", "CONSUMABLE", "WEARABLE", "WEAPON", "READABLE"}
        ),
        is_hidden=bool(getattr(obj, "is_hidden", False)),
        inventory=[],
        metadata_json=metadata,
    )


async def load_interlude_candidates(db: AsyncSession, state: SessionState) -> list[dict[str, Any]]:
    """Preload humanoid/being NPC candidates on ``db`` before starting concurrent tasks."""
    npc_rows = (
        await db.execute(
            select(WorldEntity).where(
                WorldEntity.session_id == state.session_id,
                WorldEntity.entity_type == "NPC",
            )
        )
    ).scalars()
    return [
        {
            "id": n.id,
            "name": n.name,
            "npc_type": str(n.npc_type or "HUMANOID").strip().upper(),
            "goal": n.goal or "",
            "role": str(n.npc_type or "HUMANOID").strip().upper(),
            "character": n.character or "",
            "description": n.description or "",
            "image_url": n.image_url,
            "voice": n.voice,
            "is_defeated": bool((state.entity_states or {}).get(n.id, {}).get("is_defeated")),
        }
        for n in npc_rows
        if str(n.npc_type or "HUMANOID").strip().upper() in {"HUMANOID", "BEING"}
    ]


async def _maybe_emit_interlude_quote(
    *,
    db: AsyncSession,
    state: SessionState,
    adventure: AdventureTemplate,
    user: Any,
    origin_name: str,
    tone_text: str,
    zone: dict[str, Any],
    language: str,
    emit_sse: Callable[[str, dict[str, Any]], Awaitable[None]],
    world_exit: Optional[WorldExit] = None,
    exit_label: str = "Passage",
    interlude_fn: Optional[Callable[..., Awaitable[Optional[dict[str, Any]]]]] = None,
    candidates: Optional[list[dict[str, Any]]] = None,
) -> None:
    """Emit a brief NPC interlude quote SSE event while dynamic generation completes."""
    resolved_label = (world_exit.label if world_exit else None) or exit_label or "Passage"
    quote_fn = interlude_fn or generate_dynamic_interlude_quote
    npc_candidates = (
        candidates if candidates is not None else await load_interlude_candidates(db, state)
    )
    if not npc_candidates:
        return
    quote_data = await quote_fn(
        adventure_title=adventure.title or "Adventure",
        adventure_setting=adventure.plot or adventure.teaser or "",
        adventure_tone=tone_text,
        origin_scene_name=origin_name,
        exit_label=resolved_label,
        zone_theme=zone["theme"],
        candidate_npcs=npc_candidates,
        user=user,
        db=db,
        adventure_id=adventure.id,
        game_id=state.session_id,
        language=language or adventure.language or "English",
    )
    if quote_data:
        await emit_sse(
            "dynamic_interlude",
            {**quote_data, "target_scene_name": resolved_label or "Uncharted Area"},
        )


async def start_interlude_task(
    *,
    dyn_cfg: dict[str, Any],
    emit_sse: Optional[Callable[[str, dict[str, Any]], Awaitable[None]]],
    db: AsyncSession,
    state: SessionState,
    adventure: AdventureTemplate,
    user: Any,
    origin_name: str,
    tone_text: str,
    zone: dict[str, Any],
    language: str,
    world_exit: Optional[WorldExit] = None,
    exit_label: str = "Passage",
    interlude_fn: Optional[Callable[..., Awaitable[Optional[dict[str, Any]]]]] = None,
) -> Optional[asyncio.Task[None]]:
    """Preload NPCs and launch interlude quote generation concurrently with scene LLM calls."""
    if not (dyn_cfg.get("interlude_quote_enabled", True) and emit_sse):
        return None
    candidates = await load_interlude_candidates(db, state)
    if not candidates:
        return None
    return asyncio.create_task(
        _maybe_emit_interlude_quote(
            db=db,
            state=state,
            adventure=adventure,
            user=user,
            origin_name=origin_name,
            tone_text=tone_text,
            zone=zone,
            language=language,
            emit_sse=emit_sse,
            world_exit=world_exit,
            exit_label=exit_label,
            interlude_fn=interlude_fn,
            candidates=candidates,
        )
    )


async def finish_interlude_task(interlude_task: Optional[asyncio.Task[None]]) -> None:
    """Await a background interlude quote task without surfacing secondary errors."""
    if interlude_task is not None:
        with contextlib.suppress(Exception):
            await interlude_task


def is_unmaterialized_dynamic_scene(state: SessionState, scene: Optional[WorldScene]) -> bool:
    """Return True when a session WorldScene carries a dynamic profile not yet generated."""
    if scene is None or not isinstance(getattr(scene, "dynamic_zone", None), dict):
        return False
    zone = normalize_dynamic_zone(scene.dynamic_zone)
    if not zone:
        return False
    if scene.dynamic_zone.get("materialized") is True:
        return False
    entity_states = state.entity_states if isinstance(state.entity_states, dict) else {}
    zones_meta = entity_states.get(_DYNAMIC_ZONE_META_KEY)
    if isinstance(zones_meta, dict):
        scene_meta = zones_meta.get(scene.id)
        if isinstance(scene_meta, dict) and scene_meta.get("materialized") is True:
            return False
    return True


async def _collect_existing_scene_hint(
    db: AsyncSession, session_id: str, scene: WorldScene
) -> dict[str, Any]:
    """Collect author-defined exits and pre-placed static entities for a pre-mapped scene."""
    exit_rows = (
        await db.execute(
            select(WorldExit).where(
                WorldExit.session_id == session_id,
                WorldExit.from_scene_id == scene.id,
            )
        )
    ).scalars()
    entity_rows = (
        await db.execute(
            select(WorldEntity).where(
                WorldEntity.session_id == session_id,
                WorldEntity.current_scene_id == scene.id,
            )
        )
    ).scalars()
    return {
        "id": scene.id,
        "label": scene.label,
        "author_notes": scene.description or "",
        "exits": [f"{e.label} (-> {e.to_scene_id})" for e in exit_rows],
        "entities": [f"{ent.name} ({ent.entity_type})" for ent in entity_rows],
    }


async def _existing_entity_ids(db: AsyncSession, session_id: str) -> set[str]:
    """Return all entity IDs already persisted for the session."""
    rows = (
        await db.execute(select(WorldEntity.id).where(WorldEntity.session_id == session_id))
    ).scalars()
    return set(rows)


def _apply_existing_scene_header_and_meta(
    *,
    state: SessionState,
    existing_scene: WorldScene,
    origin_scene: Optional[WorldScene],
    zone: dict[str, Any],
    payload: DynamicGeneratedScenePayload,
    scene_image: Optional[str],
    scene_audio_track_id: Optional[str],
) -> None:
    target_id = existing_scene.id
    if isinstance(zone.get("cluster_node"), dict):
        existing_scene.label = (payload.name or existing_scene.label)[:100]
    else:
        existing_scene.label = (existing_scene.label or payload.name)[:100]
    existing_scene.description = payload.description
    if scene_image and not existing_scene.image_url:
        existing_scene.image_url = scene_image
    if scene_audio_track_id and not existing_scene.audio_track_id:
        existing_scene.audio_track_id = scene_audio_track_id

    materialized_zone = {**zone, "materialized": True}
    existing_scene.dynamic_zone = materialized_zone
    flag_modified(existing_scene, "dynamic_zone")

    entity_states = dict(state.entity_states or {})
    dyn_meta = dict(entity_states.get(_DYNAMIC_ZONE_META_KEY) or {})
    dyn_meta[target_id] = {
        **materialized_zone,
        "origin_scene_id": origin_scene.id if origin_scene else target_id,
    }
    entity_states[_DYNAMIC_ZONE_META_KEY] = dyn_meta
    state.entity_states = entity_states
    flag_modified(state, "entity_states")


async def _persist_existing_scene_contents(
    *,
    db: AsyncSession,
    state: SessionState,
    existing_scene: WorldScene,
    existing_ids: set[str],
    origin_scene: Optional[WorldScene],
    zone: dict[str, Any],
    payload: DynamicGeneratedScenePayload,
    scene_image: Optional[str],
    npc_images: dict[int, Optional[str]],
    object_images: dict[int, Optional[str]],
    scene_audio_track_id: Optional[str],
    dyn_cfg: Optional[dict[str, Any]] = None,
    user: Any = None,
    adventure: Any = None,
    visuals_task: Optional[
        asyncio.Task[tuple[Optional[str], dict[int, Optional[str]], dict[int, Optional[str]]]]
    ] = None,
    pending_visuals: Optional[list[PendingDynamicVisuals]] = None,
) -> tuple[WorldScene, dict[str, Any]]:
    """Populate a pre-mapped Dynamic Scene with generated narrative, media, and entities."""
    target_id = existing_scene.id
    _apply_existing_scene_header_and_meta(
        state=state,
        existing_scene=existing_scene,
        origin_scene=origin_scene,
        zone=zone,
        payload=payload,
        scene_image=scene_image,
        scene_audio_track_id=scene_audio_track_id,
    )

    spawned_npcs: list[dict[str, Any]] = []
    npc_entries: list[tuple[DynamicGeneratedNpc, WorldEntity, bool]] = []
    npc_idx_by_id: dict[str, int] = {}
    party_hp = await compute_party_hp_budget(db, state)
    danger = str(zone.get("danger_level") or "medium")
    max_npcs = max(0, int(zone.get("max_npcs", 2)))
    for idx, npc in enumerate(payload.npcs[:max_npcs]):
        for npc_entity, is_primary in build_dynamic_npc_clones(
            session_id=state.session_id,
            target_id=target_id,
            npc=npc,
            image_url=npc_images.get(idx),
            state=state,
            existing_ids=existing_ids,
            party_hp=party_hp,
            danger=danger,
        ):
            db.add(npc_entity)
            npc_idx_by_id[npc_entity.id] = idx
            npc_entries.append((npc, npc_entity, is_primary))
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
    persisted_objects: list[DynamicGeneratedObject] = []
    object_entities: list[WorldEntity] = []
    object_idx_by_id: dict[str, int] = {}
    raw_id_to_entity: dict[str, WorldEntity] = {}
    enemy_hps = [int(ent.max_hp or ent.hp or 0) for _, ent, _ in npc_entries if ent.is_attackable]
    is_climax = int(zone.get("depth") or 1) >= int(zone.get("max_depth") or 3) and bool(
        zone.get("cul_de_sac_on_max_depth", True)
    )
    for idx, obj in enumerate(list(payload.objects[:5])):
        scale_dynamic_object_stats(
            obj,
            party_hp=party_hp,
            enemy_hps=enemy_hps,
            danger=danger,
            is_climax=is_climax,
            instructions=str(zone.get("instructions") or ""),
        )
        obj_entity = _build_object_entity(
            session_id=state.session_id,
            target_id=target_id,
            obj=obj,
            image_url=(object_images or {}).get(idx),
        )
        if obj_entity.id in existing_ids:
            continue
        existing_ids.add(obj_entity.id)
        db.add(obj_entity)
        object_idx_by_id[obj_entity.id] = idx
        persisted_objects.append(obj)
        object_entities.append(obj_entity)
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
    link_dynamic_npc_inventories(npc_entries, raw_id_to_entity)
    apply_dynamic_scripts_and_locks(persisted_objects, npc_entries, raw_id_to_entity)
    zone_key_entity = await apply_cluster_key_and_climax_progression(
        db=db,
        state=state,
        zone=zone,
        target_id=target_id,
        npc_entities=[ent for _, ent, _ in npc_entries],
        object_entities=object_entities,
        dyn_cfg=dyn_cfg,
        user=user,
        adventure=adventure,
        pregenerated_key_image=(object_images or {}).get(-1),
        key_image_pregenerated=True,
    )
    register_pending_dynamic_visuals(
        pending_visuals,
        scene_id=target_id,
        npc_idx_by_id=npc_idx_by_id,
        object_idx_by_id=object_idx_by_id,
        zone_key_entity=zone_key_entity,
        visuals_task=visuals_task,
    )

    generated_scene_data = {
        "id": target_id,
        "origin_scene_id": origin_scene.id if origin_scene else target_id,
        "zone_id": zone["zone_id"],
        "theme": zone["theme"],
        "depth": int(zone.get("depth") or 1),
        "max_depth": int(zone.get("max_depth") or 3),
        "danger_level": str(zone.get("danger_level") or "medium"),
        "name": existing_scene.label,
        "description": existing_scene.description,
        "visual_description": payload.visual_description,
        "music_prompt": payload.music_prompt,
        "npcs": spawned_npcs,
        "objects": spawned_objects,
        "forward_exits": [],
    }
    return existing_scene, generated_scene_data


async def materialize_existing_dynamic_scene(
    *,
    db: AsyncSession,
    state: SessionState,
    adventure: AdventureTemplate,
    user: Any,
    target_scene: WorldScene,
    origin_scene: Optional[WorldScene] = None,
    exit_label: str = "Passage",
    language: str = "English",
    emit_sse: Optional[Callable[[str, dict[str, Any]], Awaitable[None]]] = None,
    payload_fn: Optional[Callable[..., Awaitable[DynamicGeneratedScenePayload]]] = None,
    interlude_fn: Optional[Callable[..., Awaitable[Optional[dict[str, Any]]]]] = None,
    pending_visuals: Optional[list[PendingDynamicVisuals]] = None,
) -> Optional[WorldScene]:
    """Materialize a pre-mapped dynamic WorldScene in-place while preserving authored exits."""
    if not is_unmaterialized_dynamic_scene(state, target_scene):
        sync_dynamic_scene_audio(state, target_scene.id)
        return target_scene

    dyn_cfg = normalize_dynamic_generation(getattr(adventure, "dynamic_generation", None))
    raw_zone = (
        dict(target_scene.dynamic_zone) if isinstance(target_scene.dynamic_zone, dict) else {}
    )
    if not str(raw_zone.get("theme") or "").strip():
        raw_zone["theme"] = str(target_scene.description or target_scene.label or "Uncharted area")
    raw_zone.setdefault("depth", 1)
    zone = normalize_dynamic_zone(raw_zone)
    if not zone:
        return target_scene

    if emit_sse:
        await emit_sse("status", {"content": "Exploring uncharted territory..."})

    tone_text = extract_tone_text(adventure, user)
    max_npcs = max(0, min(5, int(zone.get("max_npcs", dyn_cfg.get("max_npcs", 2)))))
    origin_name = origin_scene.label if origin_scene else target_scene.label
    origin_desc = origin_scene.description if origin_scene else ""
    cluster_context = (
        await collect_cluster_context(db, state, zone["zone_id"], exclude_scene_id=target_scene.id)
        if zone.get("cluster_consistency", True)
        else None
    )
    existing_scene_hint = await _collect_existing_scene_hint(db, state.session_id, target_scene)

    generate_fn = payload_fn or generate_dynamic_scene_payload
    interlude_task = await start_interlude_task(
        dyn_cfg=dyn_cfg,
        emit_sse=emit_sse,
        db=db,
        state=state,
        adventure=adventure,
        user=user,
        origin_name=origin_name,
        tone_text=tone_text,
        zone=zone,
        language=language or adventure.language or "English",
        exit_label=exit_label or target_scene.label,
        interlude_fn=interlude_fn,
    )
    scene_task = asyncio.create_task(
        generate_fn(
            adventure_title=adventure.title or "Adventure",
            adventure_setting=adventure.plot or adventure.teaser or "",
            adventure_tone=tone_text,
            origin_scene_name=origin_name,
            origin_scene_description=origin_desc,
            exit_label=exit_label or "Passage",
            dynamic_zone=zone,
            user=user,
            db=db,
            adventure_id=adventure.id,
            game_id=state.session_id,
            language=language or adventure.language or "English",
            max_npcs_default=int(dyn_cfg.get("max_npcs", 2)),
            generation_config=dyn_cfg,
            cluster_context=cluster_context,
            existing_scene_hint=existing_scene_hint,
        )
    )
    try:
        payload = await scene_task
    except Exception:
        if interlude_task and not interlude_task.done():
            interlude_task.cancel()
        raise
    await finish_interlude_task(interlude_task)

    zone_key_prompt_args = await resolve_fallback_zone_key_prompt(
        db=db,
        session_id=state.session_id,
        zone=zone,
        payload=payload,
        max_npcs=max_npcs,
        adventure=adventure,
        user=user,
    )
    (
        scene_image,
        npc_images,
        object_images,
        scene_audio_track_id,
        visuals_task,
    ) = await prepare_scene_audio_and_visuals(
        db=db,
        state=state,
        dyn_cfg=dyn_cfg,
        origin_scene=origin_scene,
        target_id=target_scene.id,
        zone=zone,
        payload=payload,
        adventure=adventure,
        user=user,
        max_npcs=max_npcs,
        zone_key_prompt_args=zone_key_prompt_args,
        defer_visuals=pending_visuals is not None,
    )
    existing_ids = await _existing_entity_ids(db, state.session_id)
    try:
        updated_scene, generated_scene_data = await _persist_existing_scene_contents(
            db=db,
            state=state,
            existing_scene=target_scene,
            existing_ids=existing_ids,
            origin_scene=origin_scene,
            zone=zone,
            payload=payload,
            scene_image=scene_image,
            npc_images=npc_images,
            object_images=object_images,
            scene_audio_track_id=scene_audio_track_id,
            dyn_cfg=dyn_cfg,
            user=user,
            adventure=adventure,
            visuals_task=visuals_task,
            pending_visuals=pending_visuals,
        )
        await db.flush()
    except Exception:
        if visuals_task and not visuals_task.done():
            visuals_task.cancel()
        raise

    after_script = str(zone.get("on_after_generated_script") or "").strip()
    if after_script:
        from backend.engine.interaction.trigger_service import TriggerService

        await TriggerService.execute_trigger(
            db,
            state,
            "after_generated",
            target_scene.id,
            script_code=after_script,
            extra_scope={"generated_scene": generated_scene_data},
        )
        await db.flush()

    return updated_scene


__all__ = [
    "_DYNAMIC_ZONE_META_KEY",
    "_build_npc_entity",
    "_build_object_entity",
    "_find_session_scene",
    "_maybe_emit_interlude_quote",
    "_safe_slug",
    "finish_interlude_task",
    "is_unmaterialized_dynamic_scene",
    "load_interlude_candidates",
    "materialize_existing_dynamic_scene",
    "start_interlude_task",
]
