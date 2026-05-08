import logging
import os
import asyncio
import uuid
import json
from typing import Optional, Dict, Any, Literal, List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, File, UploadFile, Form
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from backend.core.database import get_db
from backend.core.auth import get_current_user
from backend.core.config import settings
from backend.core import prompts
from backend.models.user import User
from backend.models.adventure_template import AdventureTemplate
from backend.engine.world_generator import WorldGenerator
from backend.engine.media_engine import MediaEngine
from backend.core.style_catalog import resolve_style_instruction
from backend.api.routes.adventures.schemas import SuggestPromptRequest, SuggestPromptResponse
from backend.core.llm_router import GameMasterLLM

router = APIRouter(prefix="/{template_id}/visuals", tags=["Assets"])
logger = logging.getLogger(__name__)

class RegenerateVisualRequest(BaseModel):
    target_type: Literal["cover", "scene", "npc", "object", "protagonist"]
    target_id: str
    prompt: Optional[str] = None
    use_advanced_model: bool = False

@router.post("/regenerate")
async def regenerate_visual(
    template_id: str,
    payload: RegenerateVisualRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Regenerate a specific visual asset (cover, scene, character)."""
    from backend.models.avatar import Avatar
    from backend.models.world_entity import WorldScene, WorldEntity
    
    adv = await db.get(AdventureTemplate, template_id)
    if not adv or adv.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Adventure template not found")

    image_url = None
    user_config = {"t2i_settings": current_user.t2i_settings}
    api_keys = current_user.encrypted_api_keys

    # Resolve Style Instruction
    style_instruction = resolve_style_instruction(
        adv.selected_image_styles,
        current_user.image_styles_catalog,
    )

    try:
        if payload.target_type == "cover":
            image_url = await asyncio.wait_for(
                MediaEngine.generate_adventure_cover(
                    title=adv.title, original_prompt=payload.prompt or adv.original_prompt or "",
                    adventure_id=template_id, user_config=user_config, api_keys=api_keys,
                    style_instruction=style_instruction
                ),
                timeout=float(settings.VISUAL_TIMEOUT)
            )
            if image_url: adv.image_url = image_url

        elif payload.target_type == "protagonist":
            av_res = await db.execute(select(Avatar).where(Avatar.template_id == template_id))
            avatar = av_res.scalars().first()
            if not avatar: raise HTTPException(status_code=404, detail="Protagonist not found")
            
            image_url = await asyncio.wait_for(
                MediaEngine.generate_entity_image(
                    prompt=payload.prompt or avatar.description or "",
                    adventure_id=template_id, entity_id="protagonist", entity_type="NPC",
                    user_config=user_config, api_keys=api_keys,
                    style_instruction=style_instruction
                ),
                timeout=float(settings.VISUAL_TIMEOUT)
            )
            if image_url: avatar.profile_image = image_url

        elif payload.target_type == "scene":
            res = await db.execute(select(WorldScene).where(WorldScene.id == payload.target_id, WorldScene.template_id == template_id))
            scene = res.scalars().first()
            if not scene: raise HTTPException(status_code=404, detail="Scene not found")
            
            image_url = await asyncio.wait_for(
                MediaEngine.generate_scene_image(
                    prompt=payload.prompt or scene.description or "",
                    adventure_id=template_id, user_config=user_config, api_keys=api_keys,
                    style_instruction=style_instruction
                ),
                timeout=float(settings.VISUAL_TIMEOUT)
            )
            if image_url: scene.image_url = image_url

        elif payload.target_type in ["npc", "object"]:
            res = await db.execute(select(WorldEntity).where(WorldEntity.id == payload.target_id, WorldEntity.template_id == template_id))
            entity = res.scalars().first()
            if not entity: raise HTTPException(status_code=404, detail="Entity not found")
            
            image_url = await asyncio.wait_for(
                MediaEngine.generate_entity_image(
                    prompt=payload.prompt or entity.description or "",
                    adventure_id=template_id, entity_id=entity.id, entity_type=payload.target_type.upper(),
                    user_config=user_config, api_keys=api_keys,
                    style_instruction=style_instruction
                ),
                timeout=float(settings.VISUAL_TIMEOUT)
            )
            if image_url: entity.image_url = image_url

        await db.commit()
        return {"status": "success", "image_url": image_url}
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Visual generation timed out.")
    except ValueError as e:
        logger.warning(f"Visual regeneration blocked/invalid: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Visual regeneration failed")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/suggest-prompt", response_model=SuggestPromptResponse)
async def suggest_prompt(
    template_id: str,
    payload: SuggestPromptRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate an AI prompt suggestion based on the asset's description."""
    from backend.models.avatar import Avatar
    from backend.models.world_entity import WorldScene, WorldEntity
    
    adv = await db.get(AdventureTemplate, template_id)
    if not adv or adv.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Adventure template not found")

    name = ""
    description = ""

    logger.info(f"Suggesting prompt for {payload.target_type} ({payload.target_id}) in adventure {template_id}")

    if payload.target_type == "cover":
        name = adv.title
        description = adv.teaser or adv.original_prompt or ""
    elif payload.target_type == "protagonist":
        av_res = await db.execute(select(Avatar).where(Avatar.template_id == template_id))
        avatar = av_res.scalars().first()
        if avatar:
            name = avatar.name
            description = avatar.description
    elif payload.target_type == "scene":
        res = await db.execute(select(WorldScene).where(WorldScene.id == payload.target_id, WorldScene.template_id == template_id))
        scene = res.scalars().first()
        if scene:
            name = scene.label
            description = scene.description
    elif payload.target_type in ["npc", "object"]:
        res = await db.execute(select(WorldEntity).where(WorldEntity.id == payload.target_id, WorldEntity.template_id == template_id))
        entity = res.scalars().first()
        if entity:
            name = entity.name
            description = entity.description

    logger.info(f"Resolved name: '{name}', description length: {len(description) if description else 0}")

    if not description:
        logger.warning(f"No description found for {payload.target_type} {payload.target_id}")
        return SuggestPromptResponse(suggested_prompt="")

    # Enforce small model for prompt optimization
    llm_settings = current_user.llm_settings or {}
    provider = (
        llm_settings.get("small_model_provider")
        or llm_settings.get("complex_model_provider")
        or llm_settings.get("preferred_provider")
        or "openai"
    )
    model = llm_settings.get("small_model") or "gpt-4o-mini"
    
    llm = GameMasterLLM(user=current_user, provider=provider, model_category="small")
    
    user_prompt = prompts.IMAGE_PROMPT_SUGGESTION_USER_PROMPT_TEMPLATE.format(
        target_type=payload.target_type.upper(),
        name=name,
        description=description
    )
    
    suggested = await llm.aexecute_simple_task(
        system_prompt=prompts.IMAGE_PROMPT_SUGGESTION_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        model=model
    )
    return SuggestPromptResponse(suggested_prompt=suggested.strip())

@router.post("/upload")
async def upload_visual(
    template_id: str,
    target_type: Literal["cover", "scene", "npc", "object", "protagonist"] = Form(...),
    target_id: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually upload a visual asset."""
    from backend.models.avatar import Avatar
    from backend.models.world_entity import WorldScene, WorldEntity
    
    adv = await db.get(AdventureTemplate, template_id)
    if not adv or adv.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Adventure template not found")

    try:
        content = await file.read()
        file_ext = file.filename.split(".")[-1] if "." in file.filename else "png"
        
        filename = f"{target_type}_{target_id}_{uuid.uuid4().hex[:8]}.{file_ext}"
        storage_path = os.path.join(settings.DATA_DIR, "adventures", "library", template_id, "visuals")
        os.makedirs(storage_path, exist_ok=True)
        
        full_path = os.path.join(storage_path, filename)
        with open(full_path, "wb") as f:
            f.write(content)
            
        relative_url = f"/data/adventures/library/{template_id}/visuals/{filename}"
        
        if target_type == "cover":
            adv.image_url = relative_url
        elif target_type == "protagonist":
            av_res = await db.execute(select(Avatar).where(Avatar.template_id == template_id))
            avatar = av_res.scalars().first()
            if avatar: avatar.profile_image = relative_url
        elif target_type == "scene":
            scene = await db.get(WorldScene, target_id)
            if scene: scene.image_url = relative_url
        elif target_type in ["npc", "object"]:
            entity = await db.get(WorldEntity, target_id)
            if entity: entity.image_url = relative_url
            
        await db.commit()
        return {"status": "success", "image_url": relative_url}
    except Exception as e:
        logger.error(f"Failed to upload visual for {template_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
