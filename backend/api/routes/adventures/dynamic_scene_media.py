"""Visual and audio generation helpers for Dynamic Scenes."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from collections.abc import Awaitable
from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from backend.api.routes.adventures.audio_snapshot import start_missing_tracks
from backend.api.routes.adventures.script_image import (
    LOCAL_PROVIDERS,
    _style_instruction,
    _tier_options,
)
from backend.core.audio_settings import (
    audio_api_key,
    is_audio_available,
    normalize_audio_settings,
)
from backend.core.global_settings import read_server_settings
from backend.core.style_catalog import resolve_tone_instruction
from backend.engine.audio.audio_state import apply_audio_ops, read_audio_state
from backend.engine.interaction.map_engine import MapEngine
from backend.engine.media.asset_naming import asset_filename
from backend.engine.media.image_prompt_context import (
    build_npc_image_prompt,
    build_object_image_prompt,
    build_scene_image_prompt,
)
from backend.engine.media.media_engine import MediaEngine
from backend.engine.world.dynamic_required_entities import npcs_to_persist, objects_to_persist
from backend.engine.world.dynamic_scene_schemas import DynamicGeneratedScenePayload
from backend.models.adventure_template import AdventureTemplate
from backend.models.session_state import SessionState
from backend.models.world_entity import WorldEntity, WorldScene
from backend.models.world_map import WorldMap
from backend.utils.path_security import safe_data_path, sanitize_path_component

logger = logging.getLogger(__name__)

_DYNAMIC_AUDIO_MAP_KEY = "__dynamic_scene_audio__"


def extract_tone_text(adv: Any, user: Any = None) -> str:
    """Return a readable tone string (name + instruction) from an adventure's selected_tone and user catalog."""
    tone = getattr(adv, "selected_tone", None)
    if not tone:
        return ""
    user_catalog = list(getattr(user, "tone_catalog", None) or []) if user is not None else []
    instruction = resolve_tone_instruction(tone, user_catalog).strip()
    if isinstance(tone, dict):
        name = str(tone.get("name") or tone.get("id") or "").strip()
        desc = str(tone.get("description") or "").strip()
        detail = instruction or desc
        if name and detail and detail.lower() != name.lower():
            return f"{name} — {detail}"
        return name or detail
    name = str(tone).strip()
    if instruction and instruction.lower() != name.lower():
        return f"{name} — {instruction}"
    return name


async def _generate_tier_image(
    *,
    prompt: str,
    tier: str,
    user: Any,
    adventure: AdventureTemplate,
    session_id: str,
    prefix: str,
) -> Optional[str]:
    if tier not in {"simple", "hq"} or not user:
        return None
    safe_game_id = sanitize_path_component(str(session_id or ""))
    if not safe_game_id:
        return None

    t2i = dict(getattr(user, "t2i_settings", None) or {})
    provider, model, options = _tier_options(t2i, tier)
    if not model:
        return None
    api_keys = dict(getattr(user, "encrypted_api_keys", None) or {})
    api_key = MediaEngine._resolve_api_key(provider, api_keys)
    if provider not in LOCAL_PROVIDERS and not api_key:
        return None

    try:
        return await MediaEngine.generate_image(
            prompt=prompt,
            model=model,
            api_key=api_key,
            provider=provider,
            adventure_id=getattr(adventure, "id", None),
            target_dir=safe_data_path("adventures", "sessions", safe_game_id, "dynamic_assets"),
            filename=asset_filename(prefix, t2i.get("image_format")),
            provider_options=options,
            style_instruction=_style_instruction(user, adventure, apply_style=True),
        )
    except Exception as exc:
        logger.warning("Dynamic image generation failed (%s): %s", prefix, exc)
        return None


def _append_entity_image_tasks(
    *,
    entities: list[Any],
    mode: str,
    kind: str,
    prefix_base: str,
    prompt_builder: Any,
    user: Any,
    adventure: AdventureTemplate,
    session_id: str,
    tasks: list[Awaitable[Optional[str]]],
    task_keys: list[tuple[str, int]],
) -> None:
    if mode not in {"simple", "hq"}:
        return
    for idx, entity in enumerate(entities):
        prompt = prompt_builder(
            entity.name,
            entity.description,
            appearance=entity.visual_description,
        )
        tasks.append(
            _generate_tier_image(
                prompt=prompt,
                tier=mode,
                user=user,
                adventure=adventure,
                session_id=session_id,
                prefix=f"{prefix_base}_{idx}",
            )
        )
        task_keys.append((kind, idx))


async def generate_dynamic_object_image(
    *,
    name: str,
    description: str,
    appearance: str = "",
    dyn_cfg: Optional[dict[str, Any]],
    user: Any,
    adventure: Optional[AdventureTemplate],
    session_id: str,
    prefix: str,
) -> Optional[str]:
    """Generate a single dynamic item artwork according to dyn_cfg['item_image_mode']."""
    item_mode = str((dyn_cfg or {}).get("item_image_mode") or "simple")
    if item_mode not in {"simple", "hq"} or not user or not adventure:
        return None
    prompt = build_object_image_prompt(name, description, appearance=appearance)
    return await _generate_tier_image(
        prompt=prompt,
        tier=item_mode,
        user=user,
        adventure=adventure,
        session_id=session_id,
        prefix=prefix,
    )


def inherited_scene_image(
    dyn_cfg: dict[str, Any], origin_scene: Optional[WorldScene]
) -> Optional[str]:
    """Return the origin scene image immediately when scene_image_mode is 'inherit'."""
    if str(dyn_cfg.get("scene_image_mode") or "simple") == "inherit" and origin_scene:
        return origin_scene.image_url
    return None


def _has_visual_generation_tasks(
    *,
    payload: DynamicGeneratedScenePayload,
    dyn_cfg: dict[str, Any],
    npc_limit: int,
    zone_key_prompt_args: Optional[tuple[str, str, str]],
) -> bool:
    scene_mode = str(dyn_cfg.get("scene_image_mode") or "simple")
    npc_mode = str(dyn_cfg.get("npc_image_mode") or "simple")
    item_mode = str(dyn_cfg.get("item_image_mode") or "simple")
    return (
        scene_mode in {"simple", "hq"}
        or (npc_mode in {"simple", "hq"} and bool(npcs_to_persist(payload, npc_limit)))
        or (
            item_mode in {"simple", "hq"}
            and (bool(objects_to_persist(payload)) or bool(zone_key_prompt_args))
        )
    )


async def generate_dynamic_visuals(
    *,
    payload: DynamicGeneratedScenePayload,
    dyn_cfg: dict[str, Any],
    origin_scene: Optional[WorldScene],
    user: Any,
    adventure: AdventureTemplate,
    session_id: str,
    target_id: str,
    max_npcs: Optional[int] = None,
    zone_key_prompt_args: Optional[tuple[str, str, str]] = None,
) -> tuple[Optional[str], dict[int, Optional[str]], dict[int, Optional[str]]]:
    """Generate dynamic scene backdrop, NPC portraits, and item artwork in parallel."""
    scene_mode = str(dyn_cfg.get("scene_image_mode") or "simple")
    npc_mode = str(dyn_cfg.get("npc_image_mode") or "simple")
    item_mode = str(dyn_cfg.get("item_image_mode") or "simple")
    npc_limit = max(0, int(max_npcs if max_npcs is not None else dyn_cfg.get("max_npcs", 2)))

    scene_image: Optional[str] = None
    tasks: list[Awaitable[Optional[str]]] = []
    task_keys: list[tuple[str, int]] = []

    if scene_mode == "inherit":
        scene_image = origin_scene.image_url if origin_scene else None
    elif scene_mode in {"simple", "hq"}:
        scene_prompt = build_scene_image_prompt(
            payload.name,
            payload.visual_description or payload.description,
        )
        tasks.append(
            _generate_tier_image(
                prompt=scene_prompt,
                tier=scene_mode,
                user=user,
                adventure=adventure,
                session_id=session_id,
                prefix=f"dyn_scene_{target_id.lower()}",
            )
        )
        task_keys.append(("scene", 0))

    _append_entity_image_tasks(
        entities=npcs_to_persist(payload, npc_limit),
        mode=npc_mode,
        kind="npc",
        prefix_base=f"dyn_npc_{target_id.lower()}",
        prompt_builder=build_npc_image_prompt,
        user=user,
        adventure=adventure,
        session_id=session_id,
        tasks=tasks,
        task_keys=task_keys,
    )
    _append_entity_image_tasks(
        entities=objects_to_persist(payload),
        mode=item_mode,
        kind="obj",
        prefix_base=f"dyn_obj_{target_id.lower()}",
        prompt_builder=build_object_image_prompt,
        user=user,
        adventure=adventure,
        session_id=session_id,
        tasks=tasks,
        task_keys=task_keys,
    )
    if zone_key_prompt_args and item_mode in {"simple", "hq"}:
        key_name, key_desc, key_appearance = zone_key_prompt_args
        tasks.append(
            _generate_tier_image(
                prompt=build_object_image_prompt(key_name, key_desc, appearance=key_appearance),
                tier=item_mode,
                user=user,
                adventure=adventure,
                session_id=session_id,
                prefix=f"{target_id.lower()}_zone_key",
            )
        )
        task_keys.append(("zone_key", -1))

    npc_images: dict[int, Optional[str]] = {}
    object_images: dict[int, Optional[str]] = {}
    if not tasks:
        return scene_image, npc_images, object_images

    results = await asyncio.gather(*tasks, return_exceptions=True)
    for (kind, idx), result in zip(task_keys, results, strict=False):
        url = result if isinstance(result, str) and result else None
        if kind == "scene":
            scene_image = url
        elif kind == "npc":
            npc_images[idx] = url
        else:
            object_images[idx] = url
    return scene_image, npc_images, object_images


@dataclass
class PendingDynamicVisuals:
    """In-flight background visual generation task for a dynamic scene."""

    scene_id: str
    npc_idx_by_id: dict[str, int]
    object_idx_by_id: dict[str, int]
    task: asyncio.Task[tuple[Optional[str], dict[int, Optional[str]], dict[int, Optional[str]]]]

    def cancel(self) -> None:
        if not self.task.done():
            self.task.cancel()


def register_pending_dynamic_visuals(
    pending_visuals: Optional[list[PendingDynamicVisuals]],
    *,
    scene_id: str,
    npc_idx_by_id: dict[str, int],
    object_idx_by_id: dict[str, int],
    zone_key_entity: Optional[WorldEntity],
    visuals_task: Optional[
        asyncio.Task[tuple[Optional[str], dict[int, Optional[str]], dict[int, Optional[str]]]]
    ],
) -> None:
    """Register background visual task and optional Zone Key mapping for end-of-turn drain."""
    if zone_key_entity is not None:
        object_idx_by_id[zone_key_entity.id] = -1
    if visuals_task is None or pending_visuals is None:
        return
    pending_visuals.append(
        PendingDynamicVisuals(
            scene_id=scene_id,
            npc_idx_by_id=npc_idx_by_id,
            object_idx_by_id=object_idx_by_id,
            task=visuals_task,
        )
    )


async def start_dynamic_scene_audio_generation(
    db: AsyncSession, state: SessionState, user: Any
) -> None:
    """Trigger background audio rendering immediately for newly registered dynamic tracks."""
    if not getattr(state, "session_id", None):
        return
    audio = read_audio_state(state.entity_states)
    if not audio["tracks"]:
        return
    raw = (await read_server_settings(db)).audio_settings
    if not is_audio_available(raw):
        return
    api_key = audio_api_key(user, normalize_audio_settings(raw))
    start_missing_tracks(state.session_id, audio["tracks"], raw, api_key)


async def prepare_scene_audio_and_visuals(
    *,
    db: AsyncSession,
    state: SessionState,
    dyn_cfg: dict[str, Any],
    origin_scene: Optional[WorldScene],
    target_id: str,
    zone: dict[str, Any],
    payload: DynamicGeneratedScenePayload,
    adventure: AdventureTemplate,
    user: Any,
    max_npcs: int,
    zone_key_prompt_args: Optional[tuple[str, str, str]],
    defer_visuals: bool,
) -> tuple[
    Optional[str],
    dict[int, Optional[str]],
    dict[int, Optional[str]],
    Optional[str],
    Optional[
        asyncio.Task[tuple[Optional[str], dict[int, Optional[str]], dict[int, Optional[str]]]]
    ],
]:
    """Start music generation immediately and either await or background-launch image generation."""
    scene_audio_track_id = configure_scene_audio(
        state=state,
        dyn_cfg=dyn_cfg,
        origin_scene=origin_scene,
        target_id=target_id,
        zone=zone,
        payload=payload,
        adventure=adventure,
    )
    await start_dynamic_scene_audio_generation(db, state, user)

    visuals_coro = generate_dynamic_visuals(
        payload=payload,
        dyn_cfg=dyn_cfg,
        origin_scene=origin_scene,
        user=user,
        adventure=adventure,
        session_id=state.session_id,
        target_id=target_id,
        max_npcs=max_npcs,
        zone_key_prompt_args=zone_key_prompt_args,
    )
    if defer_visuals and _has_visual_generation_tasks(
        payload=payload,
        dyn_cfg=dyn_cfg,
        npc_limit=max_npcs,
        zone_key_prompt_args=zone_key_prompt_args,
    ):
        task = asyncio.create_task(visuals_coro)
        return inherited_scene_image(dyn_cfg, origin_scene), {}, {}, scene_audio_track_id, task

    scene_image, npc_images, object_images = await visuals_coro
    return scene_image, npc_images, object_images, scene_audio_track_id, None


async def _apply_pending_scene_image(
    db: AsyncSession, session_id: str, scene_id: str, scene_image: Optional[str]
) -> None:
    if not scene_image:
        return
    scene_res = await db.execute(
        select(WorldScene).where(WorldScene.session_id == session_id, WorldScene.id == scene_id)
    )
    scene_row = scene_res.scalars().first()
    if not scene_row or scene_row.image_url:
        return
    scene_row.image_url = scene_image
    map_res = await db.execute(select(WorldMap).where(WorldMap.session_id == session_id))
    world_map = map_res.scalars().first()
    if not world_map or not isinstance(world_map.nodes, dict):
        return
    sid = MapEngine._safe_id(scene_row.id)
    if sid not in world_map.nodes:
        return
    nodes = dict(world_map.nodes)
    nodes[sid] = {**nodes[sid], "image_url": scene_image}
    world_map.nodes = nodes
    flag_modified(world_map, "nodes")


async def _apply_pending_entity_images(
    db: AsyncSession,
    session_id: str,
    entry: PendingDynamicVisuals,
    npc_images: dict[int, Optional[str]],
    object_images: dict[int, Optional[str]],
) -> None:
    target_entity_ids = list(entry.npc_idx_by_id) + list(entry.object_idx_by_id)
    if not target_entity_ids:
        return
    ent_res = await db.execute(
        select(WorldEntity).where(
            WorldEntity.session_id == session_id,
            WorldEntity.id.in_(target_entity_ids),
        )
    )
    for ent in ent_res.scalars().all():
        if ent.id in entry.npc_idx_by_id:
            url = npc_images.get(entry.npc_idx_by_id[ent.id])
        else:
            url = object_images.get(entry.object_idx_by_id[ent.id])
        if url and not ent.image_url:
            ent.image_url = url


async def _apply_pending_entry(
    db: AsyncSession, state: SessionState, entry: PendingDynamicVisuals
) -> None:
    scene_image, npc_images, object_images = await entry.task
    await _apply_pending_scene_image(db, state.session_id, entry.scene_id, scene_image)
    await _apply_pending_entity_images(db, state.session_id, entry, npc_images, object_images)


async def drain_pending_dynamic_visuals(
    db: AsyncSession,
    state: SessionState,
    pending_list: Optional[list[PendingDynamicVisuals]],
    *,
    only_done: bool = False,
) -> bool:
    """Apply completed (or all) background dynamic visual tasks onto session DB rows."""
    if not pending_list:
        return False
    applied_any = False
    remaining: list[PendingDynamicVisuals] = []
    for entry in list(pending_list):
        if only_done and not entry.task.done():
            remaining.append(entry)
            continue
        try:
            await _apply_pending_entry(db, state, entry)
            applied_any = True
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning(
                "Applying background dynamic visuals failed (%s): %s", entry.scene_id, exc
            )
    pending_list[:] = remaining
    if applied_any:
        await db.flush()
    return applied_any


def cancel_pending_dynamic_visuals(pending_list: Optional[list[PendingDynamicVisuals]]) -> None:
    """Cancel any remaining background dynamic visual tasks on aborted turns."""
    if not pending_list:
        return
    for entry in pending_list:
        entry.cancel()
    pending_list.clear()


def configure_scene_audio(
    *,
    state: SessionState,
    dyn_cfg: dict[str, Any],
    origin_scene: Optional[WorldScene],
    target_id: str,
    zone: dict[str, Any],
    payload: DynamicGeneratedScenePayload,
    adventure: AdventureTemplate,
) -> Optional[str]:
    """Configure inherited, empty, or generated music for a newly materialized dynamic scene."""
    zone_audio = str(zone.get("audio_mode") or "").strip().lower()
    mode = (
        zone_audio
        if zone_audio in {"inherit", "empty", "generate"}
        else str(dyn_cfg.get("audio_mode") or "inherit")
    )
    if mode == "empty":
        return None
    if mode == "inherit":
        return origin_scene.audio_track_id if origin_scene else None

    # "generate" mode registers a session track in entity_states so build_audio_snapshot renders it.
    entity_states = dict(state.entity_states or {})
    track_id = hashlib.sha256(f"dyn:{state.session_id}:{target_id}".encode()).hexdigest()[:32]
    tone_text = extract_tone_text(adventure) or "cinematic"
    prompt = payload.music_prompt or (
        f"Atmospheric instrumental background music for {zone['theme']}, {tone_text} mood, seamless loop"
    )
    apply_audio_ops(
        entity_states,
        [
            {
                "op": "generate",
                "id": track_id,
                "name": payload.name[:48] or f"Zone {zone['zone_id']}",
                "prompt": prompt[:900],
                "play": True,
                "loop": True,
                "fade": 1.5,
            }
        ],
    )
    audio_map = dict(entity_states.get(_DYNAMIC_AUDIO_MAP_KEY) or {})
    audio_map[target_id] = track_id
    entity_states[_DYNAMIC_AUDIO_MAP_KEY] = audio_map
    state.entity_states = entity_states
    flag_modified(state, "entity_states")
    return None


def sync_dynamic_scene_audio(state: SessionState, scene_id: str) -> None:
    """Keep generated zone music scoped to its dynamic scenes and restore normal track rules outside."""
    entity_states = dict(state.entity_states or {})
    audio_map = entity_states.get(_DYNAMIC_AUDIO_MAP_KEY)
    if not isinstance(audio_map, dict) or not audio_map:
        return

    managed_track_ids = set(audio_map.values())
    current_audio = read_audio_state(entity_states)
    current_now = current_audio.get("now") or {}
    current_track_id = current_now.get("id")
    desired_track_id = audio_map.get(scene_id)

    if desired_track_id and desired_track_id in current_audio["tracks"]:
        if current_track_id != desired_track_id:
            apply_audio_ops(
                entity_states,
                [{"op": "play", "id": desired_track_id, "loop": True, "fade": 1.5}],
            )
            state.entity_states = entity_states
            flag_modified(state, "entity_states")
        return

    if current_track_id in managed_track_ids:
        apply_audio_ops(entity_states, [{"op": "release"}])
        state.entity_states = entity_states
        flag_modified(state, "entity_states")
