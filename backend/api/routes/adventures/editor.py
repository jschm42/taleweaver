import logging
from typing import Literal, Optional, Union

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.schemas import AdventureTemplateDebugResponse
from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.user import User
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene

router = APIRouter(tags=["Editor"])
logger = logging.getLogger(__name__)

class EntityUpdateRequest(BaseModel):
    target_type: Literal["cover", "scene", "npc", "object", "protagonist"]
    target_id: str
    name: Optional[str] = None
    teaser: Optional[str] = None
    description: Optional[str] = None
    hp: Optional[int] = None
    mana: Optional[int] = None
    stamina: Optional[int] = None
    voice: Optional[str] = None

class AIEditRequest(BaseModel):
    prompt: str
    auto_visualize: bool = True

def _serialize_model(obj):
    if not obj: return None
    data = {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
    
    # Group stats for easier frontend access
    if isinstance(obj, WorldEntity):
        if obj.entity_type == "NPC":
            data["stats"] = {
                "hp": obj.hp,
                "mana": obj.mana,
                "stamina": obj.stamina
            }
        elif obj.entity_type == "OBJECT":
            stats = {}
            if obj.stat_modifier_strength: stats["STR"] = obj.stat_modifier_strength
            if obj.stat_modifier_dexterity: stats["DEX"] = obj.stat_modifier_dexterity
            if obj.stat_modifier_intelligence: stats["INT"] = obj.stat_modifier_intelligence
            if obj.stat_modifier_wisdom: stats["WIS"] = obj.stat_modifier_wisdom
            if obj.stat_modifier_charisma: stats["CHA"] = obj.stat_modifier_charisma
            if obj.stat_modifier_armor_class: stats["AC"] = obj.stat_modifier_armor_class
            data["stats"] = stats
    return data

def _is_npc_entity(ent):
    return ent.entity_type == "NPC"

def _is_object_entity(ent):
    return ent.entity_type == "OBJECT"

async def _build_adventure_editor_assets(template_id: str, db: AsyncSession) -> AdventureTemplateDebugResponse:
    """Builds full world/editor asset state for a specific adventure."""
    adv_res = await db.execute(select(AdventureTemplate).where(AdventureTemplate.id == template_id))
    adventure = adv_res.scalars().first()
    if not adventure:
        raise HTTPException(status_code=404, detail="AdventureTemplate not found")
        
    scene_res = await db.execute(select(WorldScene).where(WorldScene.template_id == template_id))
    scenes = scene_res.scalars().all()
    
    exit_res = await db.execute(select(WorldExit).where(WorldExit.template_id == template_id))
    exits = exit_res.scalars().all()
    
    entity_res = await db.execute(select(WorldEntity).where(WorldEntity.template_id == template_id))
    entities = entity_res.scalars().all()

    avatar_res = await db.execute(select(Avatar).where(Avatar.template_id == template_id))
    avatar = avatar_res.scalars().first()

    db_scenes = [_serialize_model(s) for s in scenes]
    db_npcs = [_serialize_model(ent) for ent in entities if _is_npc_entity(ent)]
    db_objects = [_serialize_model(ent) for ent in entities if _is_object_entity(ent)]
    db_exits = [_serialize_model(ex) for ex in exits]

    return AdventureTemplateDebugResponse(
        adventure=_serialize_model(adventure),
        protagonist=_serialize_model(avatar) if avatar else None,
        scenes=db_scenes,
        npcs=db_npcs,
        objects=db_objects,
        exits=db_exits,
        entities_all=[_serialize_model(ent) for ent in entities]
    )

@router.get("/{template_id}/editor/assets", response_model=AdventureTemplateDebugResponse)
async def get_adventure_editor_assets(template_id: str, db: AsyncSession = Depends(get_db)):
    """Returns full world/editor asset data for the AdventureTemplate Editor UI."""
    return await _build_adventure_editor_assets(template_id, db)

@router.get("/{template_id}/debug", response_model=AdventureTemplateDebugResponse)
async def get_adventure_debug(template_id: str, db: AsyncSession = Depends(get_db)):
    """Legacy debug endpoint."""
    return await _build_adventure_editor_assets(template_id, db)

@router.patch("/{template_id}/editor/entity")
async def update_editor_entity(
    template_id: str,
    payload: EntityUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    adv = await db.get(AdventureTemplate, template_id)
    if not adv or adv.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="AdventureTemplate not found")
        
    if payload.target_type == "cover":
        if payload.name is not None: adv.title = payload.name
        if payload.teaser is not None: adv.teaser = payload.teaser
        if payload.description is not None: adv.original_prompt = payload.description
    elif payload.target_type == "protagonist":
        av_res = await db.execute(select(Avatar).where(Avatar.template_id == template_id))
        avatar = av_res.scalars().first()
        if avatar:
            if payload.name is not None: avatar.name = payload.name
            if payload.description is not None: avatar.description = payload.description
            if payload.hp is not None: 
                avatar.hp = payload.hp
                avatar.max_hp = payload.hp
            if payload.mana is not None: 
                avatar.mana = payload.mana
                avatar.max_mana = payload.mana
            if payload.stamina is not None: 
                avatar.stamina = payload.stamina
                avatar.max_stamina = payload.stamina
    elif payload.target_type == "scene":
        sc_res = await db.execute(select(WorldScene).where(WorldScene.template_id == template_id, WorldScene.id == payload.target_id))
        scene = sc_res.scalars().first()
        if scene:
            if payload.name is not None: scene.label = payload.name
            if payload.description is not None: scene.description = payload.description
    else:
        en_res = await db.execute(select(WorldEntity).where(WorldEntity.template_id == template_id, WorldEntity.id == payload.target_id))
        ent = en_res.scalars().first()
        if ent:
            if payload.name is not None: ent.name = payload.name
            if payload.description is not None: ent.description = payload.description
            if payload.voice is not None and ent.entity_type == "NPC":
                ent.voice = payload.voice or None
            if payload.hp is not None: 
                ent.hp = payload.hp
                ent.max_hp = payload.hp
            if payload.mana is not None: 
                ent.mana = payload.mana
                ent.max_mana = payload.mana
            if payload.stamina is not None: 
                ent.stamina = payload.stamina
                ent.max_stamina = payload.stamina
            
    await db.commit()
    return {"status": "success"}

