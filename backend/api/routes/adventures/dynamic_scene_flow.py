"""Session-scoped materialization and runtime flow for Dynamic Scenes."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from backend.api.routes.adventures.dynamic_scene_media import (
    configure_scene_audio,
    extract_tone_text,
    generate_dynamic_visuals,
    sync_dynamic_scene_audio,
)
from backend.api.routes.adventures.dynamic_teleport import apply_script_teleport
from backend.engine.world.dynamic_scene_generator import (
    generate_dynamic_interlude_quote,
    generate_dynamic_scene_payload,
)
from backend.engine.world.dynamic_scene_schemas import (
    DynamicGeneratedNpc,
    DynamicGeneratedObject,
    DynamicGeneratedScenePayload,
    build_dynamic_placeholder_scene_id,
    normalize_dynamic_generation,
    normalize_dynamic_zone,
)
from backend.models.adventure_template import AdventureTemplate
from backend.models.session_state import SessionState
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene

logger = logging.getLogger(__name__)

_DYNAMIC_ZONE_META_KEY = "__dynamic_zones__"

_COMBAT_ROLE_DEFAULTS: dict[str, dict[str, int]] = {
    "minion": {"hp": 45, "ac": 11},
    "standard": {"hp": 85, "ac": 13},
    "elite": {"hp": 140, "ac": 15},
    "boss": {"hp": 220, "ac": 16},
}


def _safe_slug(raw: str, max_len: int = 24) -> str:
    cleaned = re.sub(r"[^A-Z0-9]+", "_", str(raw or "").upper()).strip("_")
    return (cleaned or "ITEM")[:max_len]


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


def _build_npc_entity(
    *,
    session_id: str,
    target_id: str,
    npc: DynamicGeneratedNpc,
    image_url: Optional[str],
    state: SessionState,
) -> WorldEntity:
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


def _build_object_entity(
    *,
    session_id: str,
    target_id: str,
    obj: DynamicGeneratedObject,
    image_url: Optional[str] = None,
) -> WorldEntity:
    entity_id = f"{target_id}_{_safe_slug(obj.id, 16)}"[:50]
    metadata: dict[str, Any] = {"dynamic_generated": True}
    if obj.item_type == "SWITCH":
        metadata["switch_states"] = ["OFF", "ON"]
        metadata["switch_initial_state"] = "OFF"
        metadata["switch"] = {"states": ["OFF", "ON"], "initial_state": "OFF"}
    if obj.item_type == "READABLE" and obj.text_log_content:
        metadata["text_log_content"] = obj.text_log_content[:1000]
        metadata["text_log_format"] = "DOCUMENT"
    if obj.effect_type:
        metadata["effect_type"] = obj.effect_type
    if obj.effect_value is not None:
        metadata["effect_value"] = obj.effect_value

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
        is_portable=bool(
            obj.is_takeable and obj.item_type in {"STANDARD", "CONSUMABLE", "READABLE"}
        ),
        inventory=[],
        metadata_json=metadata,
    )


async def _maybe_emit_interlude_quote(
    *,
    db: AsyncSession,
    state: SessionState,
    adventure: AdventureTemplate,
    user: Any,
    world_exit: WorldExit,
    origin_name: str,
    tone_text: str,
    zone: dict[str, Any],
    language: str,
    emit_sse: Callable[[str, dict[str, Any]], Awaitable[None]],
) -> None:
    npc_rows = (
        await db.execute(
            select(WorldEntity).where(
                WorldEntity.session_id == state.session_id,
                WorldEntity.entity_type == "NPC",
            )
        )
    ).scalars()
    candidates = [
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
    if not candidates:
        return
    quote_data = await generate_dynamic_interlude_quote(
        adventure_title=adventure.title or "Adventure",
        adventure_setting=adventure.plot or adventure.teaser or "",
        adventure_tone=tone_text,
        origin_scene_name=origin_name,
        exit_label=world_exit.label or "Passage",
        zone_theme=zone["theme"],
        candidate_npcs=candidates,
        user=user,
        db=db,
        adventure_id=adventure.id,
        game_id=state.session_id,
        language=language or adventure.language or "English",
    )
    if quote_data:
        await emit_sse(
            "dynamic_interlude",
            {**quote_data, "target_scene_name": world_exit.label or "Uncharted Area"},
        )


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
) -> WorldScene:
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

    if int(zone["depth"]) < int(zone["max_depth"]):
        for idx, child_exit in enumerate(payload.forward_exits[:2], start=1):
            child_target = build_dynamic_placeholder_scene_id(
                zone["zone_id"],
                int(zone["depth"]) + 1,
                idx,
                suffix=target_id[-4:],
            )
            child_zone = {
                **zone,
                "depth": int(zone["depth"]) + 1,
                "theme": child_exit.theme_hint or zone["theme"],
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

    max_npcs = max(0, int(zone.get("max_npcs", 2)))
    for idx, npc in enumerate(payload.npcs[:max_npcs]):
        db.add(
            _build_npc_entity(
                session_id=state.session_id,
                target_id=target_id,
                npc=npc,
                image_url=npc_images.get(idx),
                state=state,
            )
        )

    for idx, obj in enumerate(payload.objects[:3]):
        db.add(
            _build_object_entity(
                session_id=state.session_id,
                target_id=target_id,
                obj=obj,
                image_url=(object_images or {}).get(idx),
            )
        )

    entity_states = dict(state.entity_states or {})
    dyn_meta = dict(entity_states.get(_DYNAMIC_ZONE_META_KEY) or {})
    dyn_meta[target_id] = zone
    entity_states[_DYNAMIC_ZONE_META_KEY] = dyn_meta
    state.entity_states = entity_states
    flag_modified(state, "entity_states")
    return new_scene


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
    new_scene = _persist_generated_scene_entities(
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
    return new_scene


async def prepare_dynamic_traversal_sse(
    *,
    interactions: Any,
    exit_ref: str,
    language: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """Stream interlude quote and materialize a dynamic exit target before traversal."""
    state: SessionState = interactions.state
    db: AsyncSession = interactions.db
    world_exit = await interactions._resolve_traversal_exit(exit_ref)
    if not world_exit or world_exit.is_locked or not world_exit.dynamic_zone:
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

    if await _find_session_scene(db, state.session_id, target_id):
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
    "apply_script_teleport",
    "materialize_dynamic_scene_for_exit",
    "prepare_dynamic_traversal_sse",
    "sync_dynamic_scene_audio",
]
