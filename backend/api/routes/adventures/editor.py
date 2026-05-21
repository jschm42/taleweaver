import logging
from typing import Literal, Optional, Union

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.schemas import AdventureTemplateDebugResponse, TraitGenerationRequest, TraitGenerationResponse
from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.core.llm_router import GameMasterLLM
from backend.core.prompts import TRAIT_GENERATION_SYSTEM_PROMPT, TRAIT_GENERATION_USER_PROMPT_TEMPLATE
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.api.routes.adventures.sessions import _backfill_avatar_items_from_template_entities
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
    goal: Optional[str] = None
    character: Optional[str] = None
    is_killable: Optional[bool] = None
    item_type: Optional[str] = None
    is_portable: Optional[bool] = None
    unlock_rule: Optional[str] = None
    inventory: Optional[list] = None

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
        
    scene_res = await db.execute(
        select(WorldScene).where(
            WorldScene.template_id == template_id,
            WorldScene.session_id.is_(None),
        )
    )
    scenes = scene_res.scalars().all()
    
    exit_res = await db.execute(
        select(WorldExit).where(
            WorldExit.template_id == template_id,
            WorldExit.session_id.is_(None),
        )
    )
    exits = exit_res.scalars().all()
    
    entity_res = await db.execute(
        select(WorldEntity).where(
            WorldEntity.template_id == template_id,
            WorldEntity.session_id.is_(None),
        )
    )
    entities = entity_res.scalars().all()

    avatar_res = await db.execute(select(Avatar).where(Avatar.template_id == template_id))
    avatar = avatar_res.scalars().first()

    # Backfill avatar inventory/equipment dicts from template entities so debug view shows full item data.
    if avatar:
        entities_by_id = {ent.id: ent for ent in entities if getattr(ent, 'id', None)}
        if entities_by_id:
            _backfill_avatar_items_from_template_entities(avatar, entities_by_id)

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
            if payload.goal is not None: avatar.goal = payload.goal
            if payload.character is not None: avatar.character = payload.character
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
            if payload.hp is not None: 
                ent.hp = payload.hp
                ent.max_hp = payload.hp
            if payload.mana is not None: 
                ent.mana = payload.mana
                ent.max_mana = payload.mana
            if payload.stamina is not None: 
                ent.stamina = payload.stamina
                ent.max_stamina = payload.stamina
            if ent.entity_type == "NPC":
                if payload.goal is not None: ent.goal = payload.goal
                if payload.character is not None: ent.character = payload.character
                if payload.is_killable is not None: ent.is_killable = payload.is_killable
            if ent.entity_type == "OBJECT":
                if payload.item_type is not None:
                    ent.item_type = str(payload.item_type).upper()
                if payload.is_portable is not None:
                    ent.is_portable = bool(payload.is_portable)
                if payload.unlock_rule is not None:
                    ent.unlock_rule = payload.unlock_rule or None
                if payload.inventory is not None:
                    ent.inventory = payload.inventory
            
    await db.commit()
    return {"status": "success"}

@router.post("/{template_id}/editor/generate-traits", response_model=TraitGenerationResponse)
async def generate_entity_traits(
    template_id: str,
    payload: TraitGenerationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generates NPC/Protagonist goal and character traits based on description/bio."""
    # Verify ownership
    adv = await db.get(AdventureTemplate, template_id)
    if not adv or adv.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="AdventureTemplate not found")

    llm_settings = current_user.llm_settings or {}
    provider = llm_settings.get("small_model_provider") or "openai"
    model = llm_settings.get("small_model") or "gpt-4o-mini"
    
    gm = GameMasterLLM(user=current_user, provider=provider, model_category="small")
    
    field_instruction = ""
    if payload.target_field == "goal":
        field_instruction = "IMPORTANT: Focus specifically on generating a compelling Goal/Motivation."
    elif payload.target_field == "character":
        field_instruction = "IMPORTANT: Focus specifically on generating evocative Personality/Traits."

    base_prompt = TRAIT_GENERATION_USER_PROMPT_TEMPLATE.format(
        name=payload.name,
        description=payload.description,
        adventure_theme=payload.adventure_theme or adv.original_prompt or 'Fantasy Adventure'
    )
    user_prompt = f"{base_prompt}\n{field_instruction}"
    
    try:
        result = await gm.aexecute_complex_task(
            system_prompt=TRAIT_GENERATION_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_model=TraitGenerationResponse,
            model=model
        )
        return result
    except Exception as e:
        logger.error(f"Failed to generate traits: {e}")
        raise HTTPException(status_code=500, detail=str(e))

