import logging
import os
from copy import deepcopy
from typing import Any, Literal, Optional, Union

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.schemas import (
    AdventureTemplateDebugResponse,
    TraitGenerationRequest,
    TraitGenerationResponse,
    QuestDescriptionGenerationRequest,
    QuestDescriptionGenerationResponse,
    QuestGenerationRequest,
    QuestGenerationResponse,
)
from backend.core.auth import get_current_user
from backend.core.config import settings
from backend.core.database import get_db
from backend.core.llm_router import GameMasterLLM
from backend.core.prompts import (
    TRAIT_GENERATION_SYSTEM_PROMPT,
    TRAIT_GENERATION_USER_PROMPT_TEMPLATE,
    QUEST_DESCRIPTION_GENERATION_SYSTEM_PROMPT,
    QUEST_DESCRIPTION_GENERATION_USER_PROMPT_TEMPLATE,
    QUEST_GENERATION_SYSTEM_PROMPT,
    QUEST_GENERATION_USER_PROMPT_TEMPLATE,
)
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.api.routes.adventures.sessions import _backfill_avatar_items_from_template_entities
from backend.api.routes.adventures.logic import AdventureLogic
from backend.engine.media_engine import MediaEngine
from backend.models.user import User
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene
from backend.utils.path_security import data_url_to_local_path, local_path_to_data_url

router = APIRouter(tags=["Editor"])
logger = logging.getLogger(__name__)

class EntityUpdateRequest(BaseModel):
    target_type: Literal["cover", "scene", "npc", "object", "protagonist", "exit"]
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
    locked: Optional[bool] = None
    code_to_unlock: Optional[str] = None
    item_to_unlock: Optional[str] = None
    rule_to_unlock: Optional[str] = None
    inventory: Optional[list] = None
    text_log_content: Optional[str] = None
    text_log_format: Optional[str] = None
    exit_type: Optional[str] = None


class StartSceneUpdateRequest(BaseModel):
    scene_id: str

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
            metadata_json = dict(obj.metadata_json or {})
            data["code_to_unlock"] = str(metadata_json.get("code_to_unlock") or "")
            data["item_to_unlock"] = str(metadata_json.get("item_to_unlock") or "")
            data["rule_to_unlock"] = str(metadata_json.get("rule_to_unlock") or "")
            if isinstance(metadata_json.get("locked"), bool):
                data["locked"] = metadata_json.get("locked")
            else:
                data["locked"] = bool(metadata_json.get("code_to_unlock") or metadata_json.get("item_to_unlock") or metadata_json.get("rule_to_unlock"))
    return data

def _is_npc_entity(ent):
    return ent.entity_type == "NPC"

def _is_object_entity(ent):
    return ent.entity_type == "OBJECT"


def _public_data_to_local_path(path: str) -> Optional[str]:
    return data_url_to_local_path(path)


def _local_to_public_data_path(path: str) -> str:
    return local_path_to_data_url(path)


def _resolve_library_image_url(image_url: Optional[str]) -> Optional[str]:
    raw = str(image_url or "").strip()
    if not raw:
        return image_url

    local_path = _public_data_to_local_path(raw)
    if not local_path:
        return image_url

    if os.path.exists(local_path):
        return raw

    # Intentionally do not remap missing assets by basename across adventures.
    # Cross-adventure fallback causes confusing visuals when source adventures are deleted.
    return image_url


async def _get_template_avatar(db: AsyncSession, template_id: str) -> Optional[Avatar]:
    avatar_res = await db.execute(
        select(Avatar)
        .where(Avatar.template_id == template_id)
        .order_by(Avatar.created_at.asc(), Avatar.id.asc())
        .limit(1)
    )
    return avatar_res.scalars().first()


async def _restore_missing_template_avatar(
    db: AsyncSession,
    template_id: str,
    adventure: AdventureTemplate,
) -> Optional[Avatar]:
    manifest = adventure.original_manifest if isinstance(adventure.original_manifest, dict) else {}
    prot = manifest.get("protagonist") if isinstance(manifest, dict) else None
    if not isinstance(prot, dict):
        return None

    image_url = str(prot.get("profile_image") or "").strip() or None
    if image_url:
        image_url = AdventureLogic.resolve_existing_data_asset_url(image_url) or image_url

    avatar = Avatar(
        user_id=adventure.owner_id,
        template_id=template_id,
        name=str(prot.get("name") or "Hero"),
        role=(str(prot.get("role") or "").strip() or "Protagonist"),
        description=(str(prot.get("description") or "").strip() or None),
        goal=(str(prot.get("goal") or "").strip() or None),
        character=(str(prot.get("character") or "").strip() or None),
        profile_image=image_url,
        hp=int(prot.get("hp") or 200),
        max_hp=int(prot.get("hp") or 200),
        stamina=int(prot.get("stamina") or 200),
        max_stamina=int(prot.get("stamina") or 200),
        mana=int(prot.get("mana") or 200),
        max_mana=int(prot.get("mana") or 200),
        strength=int(prot.get("strength") or 10),
        dexterity=int(prot.get("dexterity") or 10),
        intelligence=int(prot.get("intelligence") or 10),
        wisdom=int(prot.get("wisdom") or 10),
        charisma=int(prot.get("charisma") or 10),
        armor_class=int(prot.get("armor_class") or 10),
        exp=int(prot.get("exp") or 0),
        stats=dict(prot.get("stats") or {}),
        inventory=list(prot.get("starting_inventory") or prot.get("inventory") or []),
        equipment=dict(
            prot.get("starting_equipment")
            or {
                "Head": None,
                "Chest": None,
                "Arms": None,
                "Legs": None,
                "Hands": None,
                "Feet": None,
                "Ring_1": None,
                "Ring_2": None,
                "Neck": None,
                "MainHand": None,
                "OffHand": None,
            }
        ),
        status_effects=list(prot.get("status_effects") or []),
    )
    db.add(avatar)
    await db.commit()
    return avatar

async def _build_adventure_editor_assets(template_id: str, db: AsyncSession) -> AdventureTemplateDebugResponse:
    """Builds full world/editor asset state for a specific adventure."""
    adv_res = await db.execute(select(AdventureTemplate).where(AdventureTemplate.id == template_id))
    adventure = adv_res.scalars().first()
    if not adventure:
        raise HTTPException(status_code=404, detail="AdventureTemplate not found")

    try:
        await MediaEngine.ensure_thumbnails(template_id)
    except Exception as exc:
        logger.warning("Thumbnail ensure failed for adventure %s: %s", template_id, exc)
        
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

    # Heal stale library image URLs (e.g. slug changed after import/reuse) without failing the editor UI.
    for scene in scenes:
        scene.image_url = _resolve_library_image_url(getattr(scene, "image_url", None))
    for ent in entities:
        ent.image_url = _resolve_library_image_url(getattr(ent, "image_url", None))

    avatar = await _get_template_avatar(db, template_id)
    if not avatar:
        avatar = await _restore_missing_template_avatar(db, template_id, adventure)

    # Backfill avatar inventory/equipment dicts from template entities so debug view shows full item data.
    if avatar:
        entities_by_id = {ent.id: ent for ent in entities if getattr(ent, 'id', None)}
        if entities_by_id:
            _backfill_avatar_items_from_template_entities(avatar, entities_by_id)

    db_scenes = [_serialize_model(s) for s in scenes]
    db_npcs = [_serialize_model(ent) for ent in entities if _is_npc_entity(ent)]
    db_objects = [_serialize_model(ent) for ent in entities if _is_object_entity(ent)]
    db_exits = [_serialize_model(ex) for ex in exits]

    adventure_payload = _serialize_model(adventure) or {}
    adventure_payload["start_scene_id"] = await AdventureLogic.resolve_initial_scene_id(db, template_id)

    return AdventureTemplateDebugResponse(
        adventure=adventure_payload,
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
        avatar = await _get_template_avatar(db, template_id)
        if not avatar:
            avatar = await _restore_missing_template_avatar(db, template_id, adv)
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
    elif payload.target_type == "exit":
        ex_res = await db.execute(select(WorldExit).where(WorldExit.template_id == template_id, WorldExit.id == payload.target_id))
        world_exit = ex_res.scalars().first()
        if world_exit:
            if payload.name is not None: world_exit.label = payload.name
            if payload.locked is not None: world_exit.is_locked = bool(payload.locked)
            if payload.description is not None: world_exit.lock_description = payload.description
            if payload.exit_type is not None: world_exit.exit_type = payload.exit_type
            
            # Enforce mutual exclusivity and priority on exit lock attributes
            if payload.code_to_unlock is not None or payload.item_to_unlock is not None or payload.rule_to_unlock is not None:
                code = world_exit.code_to_unlock or ""
                item = world_exit.item_to_unlock or ""
                rule = world_exit.rule_to_unlock or ""
                if payload.code_to_unlock is not None:
                    code = str(payload.code_to_unlock or "").strip()
                if payload.item_to_unlock is not None:
                    item = str(payload.item_to_unlock or "").strip().upper()
                if payload.rule_to_unlock is not None:
                    rule = str(payload.rule_to_unlock or "").strip()

                if code:
                    code = code[:32]
                    item = ""
                    rule = ""
                elif item:
                    from backend.utils.text_utils import slugify
                    item = slugify(item).upper().replace("-", "_")[:64]
                    code = ""
                    rule = ""
                elif rule:
                    rule = rule[:500]
                    code = ""
                    item = ""
                else:
                    code = ""
                    item = ""
                    rule = ""

                world_exit.code_to_unlock = code
                world_exit.item_to_unlock = item
                world_exit.rule_to_unlock = rule
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
                is_readable_object = str(ent.item_type or "").upper() == "READABLE"
                if payload.description is not None and is_readable_object and len(payload.description) > 200:
                    raise HTTPException(status_code=400, detail="description must be at most 200 characters for READABLE objects.")
                if payload.is_portable is not None:
                    ent.is_portable = bool(payload.is_portable)
                if payload.code_to_unlock is not None or payload.item_to_unlock is not None or payload.rule_to_unlock is not None or payload.locked is not None:
                    metadata_json = dict(ent.metadata_json or {})
                    code = metadata_json.get("code_to_unlock") or ""
                    item = metadata_json.get("item_to_unlock") or ""
                    rule = metadata_json.get("rule_to_unlock") or ""
                    
                    if payload.code_to_unlock is not None:
                        code = str(payload.code_to_unlock or "").strip()
                    if payload.item_to_unlock is not None:
                        item = str(payload.item_to_unlock or "").strip().upper()
                    if payload.rule_to_unlock is not None:
                        rule = str(payload.rule_to_unlock or "").strip()

                    if code:
                        code = code[:32]
                        item = ""
                        rule = ""
                    elif item:
                        from backend.utils.text_utils import slugify
                        item = slugify(item).upper().replace("-", "_")[:64]
                        code = ""
                        rule = ""
                    elif rule:
                        rule = rule[:500]
                        code = ""
                        item = ""
                    else:
                        code = ""
                        item = ""
                        rule = ""

                    metadata_json["code_to_unlock"] = code
                    metadata_json["item_to_unlock"] = item
                    metadata_json["rule_to_unlock"] = rule
                    if payload.locked is not None:
                        metadata_json["locked"] = bool(payload.locked)
                    else:
                        metadata_json["locked"] = bool(code or item or rule)
                    
                    ent.metadata_json = metadata_json
                    # Legacy free-text unlock rules are deprecated in favor of deterministic attributes.
                    ent.unlock_rule = None
                if payload.inventory is not None:
                    ent.inventory = payload.inventory
                if payload.text_log_content is not None:
                    if len(payload.text_log_content) > 500:
                        raise HTTPException(status_code=400, detail="text_log_content must be at most 500 characters.")
                    metadata_json = dict(ent.metadata_json or {})
                    metadata_json["text_log_content"] = payload.text_log_content.strip()
                    ent.metadata_json = metadata_json
                if payload.text_log_format is not None:
                    normalized_format = str(payload.text_log_format).strip().upper()
                    allowed_formats = {"DOCUMENT", "SCROLL", "BOOK", "SIGN"}
                    if normalized_format not in allowed_formats:
                        raise HTTPException(status_code=400, detail="text_log_format must be one of DOCUMENT, SCROLL, BOOK, SIGN.")
                    metadata_json = dict(ent.metadata_json or {})
                    metadata_json["text_log_format"] = normalized_format
                    ent.metadata_json = metadata_json
            
    await db.commit()
    return {"status": "success"}


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


@router.post("/{template_id}/editor/generate-quest-description", response_model=QuestDescriptionGenerationResponse)
async def generate_quest_description(
    template_id: str,
    payload: QuestDescriptionGenerationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(AdventureTemplate).where(AdventureTemplate.id == template_id)
    res = await db.execute(stmt)
    adv = res.scalars().first()
    if not adv or adv.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="AdventureTemplate not found")

    llm_settings = current_user.llm_settings or {}
    provider = llm_settings.get("small_model_provider") or "openai"
    model = llm_settings.get("small_model") or "gpt-4o-mini"
    
    gm = GameMasterLLM(user=current_user, provider=provider, model_category="small")
    
    # Format other quests to prevent duplication
    other_quests_text = ""
    if payload.other_quests:
        lines = []
        for q in payload.other_quests:
            q_title = q.get("title") or "Unnamed Quest"
            q_desc = q.get("description") or "No description."
            q_type = "Main" if q.get("is_main") else "Side"
            lines.append(f"- [{q_type}] {q_title}: {q_desc}")
        other_quests_text = "\n".join(lines)
    else:
        other_quests_text = "No other quests defined yet."

    user_prompt = QUEST_DESCRIPTION_GENERATION_USER_PROMPT_TEMPLATE.format(
        title=payload.title,
        quest_type="Main" if payload.is_main else "Side",
        adventure_title=adv.title or "Untitled Adventure",
        adventure_plot=adv.plot or adv.original_prompt or "No description provided.",
        adventure_tone=adv.selected_tone or "Standard",
        other_quests_text=other_quests_text,
    )
    
    try:
        result = await gm.aexecute_complex_task(
            system_prompt=QUEST_DESCRIPTION_GENERATION_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_model=QuestDescriptionGenerationResponse,
            model=model
        )
        return result
    except Exception as e:
        logger.error(f"Failed to generate quest description: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{template_id}/editor/generate-new-quest", response_model=QuestGenerationResponse)
async def generate_new_quest(
    template_id: str,
    payload: QuestGenerationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(AdventureTemplate).where(AdventureTemplate.id == template_id)
    res = await db.execute(stmt)
    adv = res.scalars().first()
    if not adv or adv.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="AdventureTemplate not found")

    llm_settings = current_user.llm_settings or {}
    provider = llm_settings.get("small_model_provider") or "openai"
    model = llm_settings.get("small_model") or "gpt-4o-mini"
    
    gm = GameMasterLLM(user=current_user, provider=provider, model_category="small")
    
    # Format other quests to prevent duplication
    other_quests_text = ""
    if payload.other_quests:
        lines = []
        for q in payload.other_quests:
            q_title = q.get("title") or "Unnamed Quest"
            q_desc = q.get("description") or "No description."
            q_type = "Main" if q.get("is_main") else "Side"
            lines.append(f"- [{q_type}] {q_title}: {q_desc}")
        other_quests_text = "\n".join(lines)
    else:
        other_quests_text = "No other quests defined yet."

    user_prompt = QUEST_GENERATION_USER_PROMPT_TEMPLATE.format(
        quest_type="Main" if payload.is_main else "Side",
        adventure_title=adv.title or "Untitled Adventure",
        adventure_plot=adv.plot or adv.original_prompt or "No description provided.",
        adventure_tone=adv.selected_tone or "Standard",
        other_quests_text=other_quests_text,
    )
    
    try:
        result = await gm.aexecute_complex_task(
            system_prompt=QUEST_GENERATION_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_model=QuestGenerationResponse,
            model=model
        )
        return result
    except Exception as e:
        logger.error(f"Failed to generate new quest: {e}")
        raise HTTPException(status_code=500, detail=str(e))



