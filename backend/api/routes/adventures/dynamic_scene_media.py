"""Visual and audio generation helpers for Dynamic Scenes."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from collections.abc import Awaitable
from typing import Any, Optional

from sqlalchemy.orm.attributes import flag_modified

from backend.api.routes.adventures.script_image import (
    LOCAL_PROVIDERS,
    _style_instruction,
    _tier_options,
)
from backend.engine.audio.audio_state import apply_audio_ops, read_audio_state
from backend.engine.media.asset_naming import asset_filename
from backend.engine.media.image_prompt_context import (
    build_npc_image_prompt,
    build_object_image_prompt,
    build_scene_image_prompt,
)
from backend.engine.media.media_engine import MediaEngine
from backend.engine.world.dynamic_scene_schemas import DynamicGeneratedScenePayload
from backend.models.adventure_template import AdventureTemplate
from backend.models.session_state import SessionState
from backend.models.world_entity import WorldScene
from backend.utils.path_security import safe_data_path, sanitize_path_component

logger = logging.getLogger(__name__)

_DYNAMIC_AUDIO_MAP_KEY = "__dynamic_scene_audio__"


def extract_tone_text(adv: AdventureTemplate) -> str:
    """Return a readable tone string from an adventure's selected_tone."""
    tone = getattr(adv, "selected_tone", None)
    if isinstance(tone, dict):
        return str(tone.get("name") or tone.get("id") or "").strip()
    return str(tone or "").strip()


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
) -> tuple[Optional[str], dict[int, Optional[str]], dict[int, Optional[str]]]:
    """Generate dynamic scene backdrop, NPC portraits, and item artwork according to config."""
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
        entities=payload.npcs[:npc_limit],
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
        entities=payload.objects[:3],
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
