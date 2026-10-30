"""Create/delete/clone endpoints for scenes, exits, and entities."""

import logging
from copy import deepcopy

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from backend.api.routes.adventures.editing.common import (
    _ensure_template_scene_exists,
    _get_owned_adventure_or_404,
    _normalize_lock_fields,
    _sanitize_object_id,
)
from backend.api.routes.adventures.editing.entity_create import create_template_entity
from backend.api.routes.adventures.editing.image_clone import _clone_entity_image
from backend.api.routes.adventures.editing.payload import _serialize_model
from backend.api.routes.adventures.editing.schemas import (
    EntityCreateRequest,
    ExitCreateRequest,
    SceneCreateRequest,
    StartSceneUpdateRequest,
)
from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Editor"])


@router.post("/{template_id}/editor/scene")
async def create_editor_scene(
    template_id: str,
    payload: SceneCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    await _get_owned_adventure_or_404(db, template_id, current_user.id)

    scene_id = _sanitize_object_id(payload.scene_id, "scene_id")
    label = str(payload.label or "").strip()
    description = str(payload.description or "").strip()
    if not label:
        raise HTTPException(status_code=400, detail="label is required")
    if not description:
        raise HTTPException(status_code=400, detail="description is required")

    clean_decor: list[str] = []
    if payload.decorative_objects:
        for d in payload.decorative_objects:
            s = d.strip()
            if not s:
                continue
            if len(s) > 100:
                raise HTTPException(
                    status_code=400, detail="Each decorative object must be at most 100 characters."
                )
            clean_decor.append(s)
        clean_decor = clean_decor[:7]

    existing_scene = await db.execute(
        select(WorldScene).where(
            WorldScene.template_id == template_id,
            WorldScene.session_id.is_(None),
            WorldScene.id == scene_id,
        )
    )
    if existing_scene.scalars().first():
        raise HTTPException(status_code=409, detail="scene_id already exists")

    existing_entity = await db.execute(
        select(WorldEntity).where(
            WorldEntity.template_id == template_id,
            WorldEntity.session_id.is_(None),
            WorldEntity.id == scene_id,
        )
    )
    if existing_entity.scalars().first():
        raise HTTPException(status_code=409, detail="ID already exists as an entity")

    scene = WorldScene(
        id=scene_id,
        template_id=template_id,
        session_id=None,
        label=label,
        description=description,
        image_url=str(payload.image_url or "").strip() or None,
        decorative_objects=clean_decor or None,
    )
    db.add(scene)
    await db.commit()
    return {"status": "success", "scene": _serialize_model(scene)}


@router.delete("/{template_id}/editor/scene/{scene_id}")
async def delete_editor_scene(
    template_id: str,
    scene_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    adv = await _get_owned_adventure_or_404(db, template_id, current_user.id)
    scene_id = _sanitize_object_id(scene_id, "scene_id")

    scene_res = await db.execute(
        select(WorldScene).where(
            WorldScene.template_id == template_id,
            WorldScene.session_id.is_(None),
            WorldScene.id == scene_id,
        )
    )
    scene = scene_res.scalars().first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    await db.execute(
        delete(WorldExit).where(
            WorldExit.template_id == template_id,
            WorldExit.session_id.is_(None),
            ((WorldExit.from_scene_id == scene_id) | (WorldExit.to_scene_id == scene_id)),
        )
    )
    await db.execute(
        delete(WorldEntity).where(
            WorldEntity.template_id == template_id,
            WorldEntity.session_id.is_(None),
            WorldEntity.current_scene_id == scene_id,
        )
    )
    await db.delete(scene)

    manifest = deepcopy(adv.original_manifest or {})
    if (manifest.get("start_scene_id") or "") == scene_id:
        replacement_scene_res = await db.execute(
            select(WorldScene.id).where(
                WorldScene.template_id == template_id,
                WorldScene.session_id.is_(None),
                WorldScene.id != scene_id,
            )
        )
        replacement_scene_id = replacement_scene_res.scalars().first()
        if replacement_scene_id:
            manifest["start_scene_id"] = replacement_scene_id
        else:
            manifest.pop("start_scene_id", None)
        adv.original_manifest = manifest

    await db.commit()
    return {"status": "success", "deleted_scene_id": scene_id}


@router.post("/{template_id}/editor/exit")
async def create_editor_exit(
    template_id: str,
    payload: ExitCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    adv = await _get_owned_adventure_or_404(db, template_id, current_user.id)

    from_scene_id = _sanitize_object_id(payload.from_scene_id, "from_scene_id")
    to_scene_id = _sanitize_object_id(payload.to_scene_id, "to_scene_id")
    if from_scene_id == to_scene_id:
        raise HTTPException(status_code=400, detail="from_scene_id and to_scene_id must differ")

    await _ensure_template_scene_exists(db, template_id, from_scene_id)
    await _ensure_template_scene_exists(db, template_id, to_scene_id)

    label = str(payload.label or "").strip()
    if not label:
        raise HTTPException(status_code=400, detail="label is required")

    code, item, rule = _normalize_lock_fields(
        code_to_unlock=payload.code_to_unlock,
        item_to_unlock=payload.item_to_unlock,
        rule_to_unlock=payload.rule_to_unlock,
    )

    lock_description = str(payload.lock_description or "").strip()
    if (code or item or rule) and not lock_description:
        raise HTTPException(
            status_code=400,
            detail="A lock description is required when a code, item, or rule gate is configured on an exit.",
        )

    world_exit = WorldExit(
        template_id=template_id,
        session_id=None,
        from_scene_id=from_scene_id,
        to_scene_id=to_scene_id,
        label=label,
        exit_type=payload.exit_type,
        is_locked=bool(payload.is_locked or code or item or rule),
        lock_description=lock_description or None,
        code_to_unlock=code or None,
        item_to_unlock=item or None,
        rule_to_unlock=rule or None,
    )
    db.add(world_exit)
    if isinstance(adv.original_manifest, dict) and isinstance(
        adv.original_manifest.get("exits"), list
    ):
        manifest = deepcopy(adv.original_manifest)
        manifest["exits"].append(
            {
                "id": world_exit.id,
                "from_scene_id": world_exit.from_scene_id,
                "to_scene_id": world_exit.to_scene_id,
                "label": world_exit.label,
                "exit_type": world_exit.exit_type,
                "is_bidirectional": (world_exit.exit_type == "bidirectional"),
                "is_locked": world_exit.is_locked,
                "lock_description": world_exit.lock_description,
                "code_to_unlock": world_exit.code_to_unlock,
                "item_to_unlock": world_exit.item_to_unlock,
                "rule_to_unlock": world_exit.rule_to_unlock,
            }
        )
        adv.original_manifest = manifest
        flag_modified(adv, "original_manifest")
    await db.commit()
    return {"status": "success", "exit": _serialize_model(world_exit)}


@router.delete("/{template_id}/editor/exit/{exit_id}")
async def delete_editor_exit(
    template_id: str,
    exit_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    adv = await _get_owned_adventure_or_404(db, template_id, current_user.id)

    exit_res = await db.execute(
        select(WorldExit).where(
            WorldExit.template_id == template_id,
            WorldExit.session_id.is_(None),
            WorldExit.id == exit_id,
        )
    )
    world_exit = exit_res.scalars().first()
    if not world_exit:
        raise HTTPException(status_code=404, detail="Exit not found")

    await db.delete(world_exit)
    if isinstance(adv.original_manifest, dict) and isinstance(
        adv.original_manifest.get("exits"), list
    ):
        manifest = deepcopy(adv.original_manifest)
        manifest["exits"] = [
            ex for ex in manifest["exits"] if isinstance(ex, dict) and ex.get("id") != exit_id
        ]
        adv.original_manifest = manifest
        flag_modified(adv, "original_manifest")
    await db.commit()
    return {"status": "success", "deleted_exit_id": exit_id}


@router.post("/{template_id}/editor/entity")
async def create_editor_entity(
    template_id: str,
    payload: EntityCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    await _get_owned_adventure_or_404(db, template_id, current_user.id)

    entity = await create_template_entity(db, template_id, payload)
    await db.commit()
    return {"status": "success", "entity": _serialize_model(entity)}


@router.delete("/{template_id}/editor/entity/{entity_id}")
async def delete_editor_entity(
    template_id: str,
    entity_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    await _get_owned_adventure_or_404(db, template_id, current_user.id)
    entity_id = _sanitize_object_id(entity_id, "entity_id")

    ent_res = await db.execute(
        select(WorldEntity).where(
            WorldEntity.template_id == template_id,
            WorldEntity.session_id.is_(None),
            WorldEntity.id == entity_id,
        )
    )
    entity = ent_res.scalars().first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    await db.delete(entity)
    await db.commit()
    return {"status": "success", "deleted_entity_id": entity_id}


@router.post("/{template_id}/editor/entity/{entity_id}/clone")
async def clone_editor_entity(
    template_id: str,
    entity_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    await _get_owned_adventure_or_404(db, template_id, current_user.id)
    entity_id = _sanitize_object_id(entity_id, "entity_id")

    ent_res = await db.execute(
        select(WorldEntity).where(
            WorldEntity.template_id == template_id,
            WorldEntity.session_id.is_(None),
            WorldEntity.id == entity_id,
        )
    )
    source = ent_res.scalars().first()
    if not source:
        raise HTTPException(status_code=404, detail="Entity not found")

    base_id = f"{entity_id}_1"
    new_id = base_id
    suffix = 1
    while True:
        exists = await db.execute(
            select(WorldEntity.id).where(
                WorldEntity.template_id == template_id,
                WorldEntity.session_id.is_(None),
                WorldEntity.id == new_id,
            )
        )
        if not exists.scalars().first():
            break
        suffix += 1
        new_id = f"{entity_id}_{suffix}"

    cloned_image_url = await _clone_entity_image(
        source_image_url=source.image_url,
        template_id=template_id,
        new_entity_id=new_id,
    )

    clone = WorldEntity(
        id=new_id,
        template_id=template_id,
        session_id=None,
        entity_type=source.entity_type,
        name=source.name,
        description=source.description,
        current_scene_id=source.current_scene_id,
        spatial_position=source.spatial_position,
        image_url=cloned_image_url,
        item_type=source.item_type,
        wearable_slots=list(source.wearable_slots) if source.wearable_slots is not None else None,
        is_in_inventory=source.is_in_inventory,
        is_hidden=source.is_hidden,
        reveal_rule=source.reveal_rule,
        unlock_rule=source.unlock_rule,
        is_portable=source.is_portable,
        combination_ingredients=list(source.combination_ingredients)
        if source.combination_ingredients is not None
        else None,
        reveals_item_id=None,
        is_final_state=source.is_final_state,
        state_comment=source.state_comment,
        npc_type=source.npc_type,
        movement_type=source.movement_type,
        goal=source.goal,
        character=source.character,
        appearance=source.appearance,
        hp=source.hp,
        max_hp=source.max_hp,
        mana=source.mana,
        max_mana=source.max_mana,
        stamina=source.stamina,
        max_stamina=source.max_stamina,
        voice=source.voice,
        stat_modifier_strength=source.stat_modifier_strength,
        stat_modifier_dexterity=source.stat_modifier_dexterity,
        stat_modifier_intelligence=source.stat_modifier_intelligence,
        stat_modifier_wisdom=source.stat_modifier_wisdom,
        stat_modifier_charisma=source.stat_modifier_charisma,
        stat_modifier_armor_class=source.stat_modifier_armor_class,
        is_attackable=source.is_attackable,
        is_killable=source.is_killable,
        moveable=source.moveable,
        allowed_scenes=list(source.allowed_scenes or []) if source.allowed_scenes else [],
        notes=source.notes,
        inventory=[
            item if isinstance(item, str) else dict(item) for item in (source.inventory or [])
        ],
        metadata_json=dict(source.metadata_json or {}),
    )
    db.add(clone)
    await db.commit()
    return {
        "status": "success",
        "entity": _serialize_model(clone),
        "source_id": entity_id,
        "new_id": new_id,
    }


@router.patch("/{template_id}/editor/start-scene")
async def update_editor_start_scene(
    template_id: str,
    payload: StartSceneUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    adv = await db.get(AdventureTemplate, template_id)
    if not adv or adv.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="AdventureTemplate not found")

    scene_id = str(payload.scene_id or "").strip()
    if not scene_id:
        raise HTTPException(status_code=400, detail="scene_id is required")

    sc_res = await db.execute(
        select(WorldScene).where(
            WorldScene.template_id == template_id,
            WorldScene.session_id.is_(None),
            WorldScene.id == scene_id,
        )
    )
    scene = sc_res.scalars().first()
    if not scene:
        raise HTTPException(status_code=400, detail="scene_id does not exist in this adventure")

    manifest = deepcopy(adv.original_manifest or {})
    manifest["start_scene_id"] = scene_id
    adv.original_manifest = manifest

    await db.commit()
    return {"status": "success", "start_scene_id": scene_id}
