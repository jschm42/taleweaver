"""Creates template NPCs and objects; shared by the editor's Create dialog and the World-Builder."""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.editing.common import (
    _ensure_template_scene_exists,
    _sanitize_object_id,
)
from backend.api.routes.adventures.editing.entity_update.item import hide_recipe_results
from backend.api.routes.adventures.editing.entity_update.item_metadata import validated_switch
from backend.api.routes.adventures.editing.schemas import EntityCreateRequest
from backend.engine.media.image_prompt_context import clean_appearance
from backend.engine.rules.crafting_recipes import KEPT_FIELD, RESULT_FIELD, normalize_ids
from backend.models.world_entity import WorldEntity, WorldScene


async def create_template_entity(
    db: AsyncSession, template_id: str, payload: EntityCreateRequest
) -> WorldEntity:
    """Validates and adds a new template NPC/object (HTTP 400/409 on bad input; no commit)."""
    entity_id = _sanitize_object_id(payload.entity_id, "entity_id")
    scene_id = _sanitize_object_id(payload.scene_id, "scene_id")
    await _ensure_template_scene_exists(db, template_id, scene_id)

    name = str(payload.name or "").strip()
    description = str(payload.description or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    if not description:
        raise HTTPException(status_code=400, detail="description is required")

    existing_ent = await db.execute(
        select(WorldEntity).where(
            WorldEntity.template_id == template_id,
            WorldEntity.session_id.is_(None),
            WorldEntity.id == entity_id,
        )
    )
    if existing_ent.scalars().first():
        raise HTTPException(status_code=409, detail="entity_id already exists")

    existing_scene = await db.execute(
        select(WorldScene).where(
            WorldScene.template_id == template_id,
            WorldScene.session_id.is_(None),
            WorldScene.id == entity_id,
        )
    )
    if existing_scene.scalars().first():
        raise HTTPException(status_code=409, detail="ID already exists as a scene")

    item_type = (
        str(payload.item_type or "").strip().upper() if payload.entity_type == "OBJECT" else None
    )
    metadata_json = dict(payload.metadata_json or {})
    if item_type == "CONSTRUCTABLE":
        metadata_json[RESULT_FIELD] = normalize_ids(payload.result_item_ids)
        metadata_json[KEPT_FIELD] = normalize_ids(payload.kept_ingredients)
    if item_type == "SWITCH":
        metadata_json["switch"] = validated_switch(dict(metadata_json.get("switch") or {}))

    entity = WorldEntity(
        id=entity_id,
        template_id=template_id,
        session_id=None,
        entity_type=payload.entity_type,
        name=name,
        description=description,
        appearance=clean_appearance(payload.appearance),
        current_scene_id=scene_id,
        image_url=str(payload.image_url or "").strip() or None,
        item_type=item_type,
        is_hidden=True
        if item_type == "CONSTRUCTABLE"
        else (bool(payload.is_hidden) if payload.is_hidden is not None else False),
        reveal_rule=str(payload.reveal_rule or "").strip() or None,
        is_portable=bool(payload.is_portable) if payload.is_portable is not None else True,
        goal=str(payload.goal or "").strip() or None,
        character=str(payload.character or "").strip() or None,
        hp=payload.hp,
        max_hp=payload.hp,
        mana=payload.mana,
        max_mana=payload.mana,
        stamina=payload.stamina,
        max_stamina=payload.stamina,
        is_killable=bool(payload.is_killable) if payload.is_killable is not None else True,
        moveable=bool(payload.moveable) if payload.moveable is not None else False,
        movement_type="MOVABLE" if payload.moveable else "STATIONARY",
        allowed_scenes=list(payload.allowed_scenes or []),
        notes=str(payload.notes).strip() if payload.notes else None,
        metadata_json=metadata_json,
        inventory=list(payload.inventory or []),
        wearable_slots=payload.wearable_slots,
        combination_ingredients=payload.combination_ingredients,
        stat_modifier_strength=payload.stat_modifier_strength,
    )
    db.add(entity)
    await hide_recipe_results(db, template_id, entity)
    return entity
