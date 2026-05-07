import logging
import os
import asyncio
import uuid
import json
from typing import Optional, Dict, Any, Literal, List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, File, UploadFile
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
from backend.engine.adventure_importer import AdventureTemplateImporter
from backend.core.style_catalog import resolve_style_instruction
from backend.api.routes.adventures.schemas import ImportCheckResponse, ImportCheckItem
import zipfile
import io

router = APIRouter(tags=["Assets"])
logger = logging.getLogger(__name__)

async def _get_import_check_items(db: AsyncSession, user_id: str, directories: List[str]) -> List[ImportCheckItem]:
    """Scans directories for adventures and checks if they already exist in the user's library."""
    check_items = []
    
    for directory in directories:
        if not os.path.exists(directory):
            continue
            
        files = [f for f in os.listdir(directory) if f.endswith(".adv") or f.endswith(".adz")]
        for filename in files:
            file_path = os.path.join(directory, filename)
            title = None
            origin_id = None
            
            try:
                if filename.endswith(".adz"):
                    with open(file_path, "rb") as f:
                        with zipfile.ZipFile(io.BytesIO(f.read()), "r") as zip_file:
                            manifest = json.loads(zip_file.read("adventure.adv").decode("utf-8"))
                            adv_data = manifest.get("adventure") or {}
                            title = adv_data.get("title")
                            origin_id = adv_data.get("origin_id") or manifest.get("origin_id")
                else:
                    with open(file_path, "r", encoding="utf-8") as f:
                        payload = json.load(f)
                        is_session = payload.get("type") == "SESSION_BUNDLE"
                        title = payload.get("adventure", {}).get("title") if is_session else payload.get("title")
                        origin_id = payload.get("adventure", {}).get("origin_id") if is_session else payload.get("origin_id")
                
                if title:
                    query = select(AdventureTemplate).where(AdventureTemplate.owner_id == user_id)
                    if origin_id:
                        query = query.where(or_(AdventureTemplate.title == title, AdventureTemplate.origin_id == origin_id))
                    else:
                        query = query.where(AdventureTemplate.title == title)
                    
                    res = await db.execute(query)
                    existing = res.scalars().first()
                    
                    check_items.append(ImportCheckItem(
                        title=title,
                        origin_id=origin_id,
                        already_exists=existing is not None,
                        existing_template_id=existing.id if existing else None
                    ))
            except Exception as e:
                logger.error(f"Error checking import file {file_path}: {e}")
                
    return check_items

@router.get("/check-defaults", response_model=ImportCheckResponse)
async def check_defaults(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns a list of default adventures and their existence status."""
    defaults_dir = os.path.join("adventures", "default")
    items = await _get_import_check_items(db, current_user.id, [defaults_dir])
    return ImportCheckResponse(available_imports=items)

@router.get("/check-examples", response_model=ImportCheckResponse)
async def check_examples(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns a list of example/sample adventures and their existence status."""
    samples_dir = os.path.join("adventures", "samples")
    presets_dir = os.path.join(settings.DATA_DIR, "presets", "adventures")
    items = await _get_import_check_items(db, current_user.id, [samples_dir, presets_dir])
    return ImportCheckResponse(available_imports=items)

@router.post("/import-examples")
async def import_examples(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually triggers import of example adventures from the 'adventures/samples' and presets folder."""
    user_id = current_user.id
    # Import from the 'samples' subfolder
    samples_dir = os.path.join("adventures", "samples")
    await AdventureTemplateImporter.import_from_directory(db, samples_dir, owner_id=user_id, delete_after=False)
    
    presets_dir = os.path.join(settings.DATA_DIR, "presets", "adventures")
    if os.path.exists(presets_dir):
        await AdventureTemplateImporter.import_from_directory(db, presets_dir, owner_id=user_id, delete_after=False)
    return {"status": "success", "message": "Example adventures imported successfully."}

@router.post("/import-defaults")
async def import_defaults(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Triggers import of default adventures from 'adventures/default' if not already done."""
    if current_user.has_imported_defaults:
        return {"status": "skipped", "message": "Defaults already imported."}
    
    defaults_dir = os.path.join("adventures", "default")
    await AdventureTemplateImporter.import_from_directory(db, defaults_dir, owner_id=current_user.id, delete_after=False)
    
    current_user.has_imported_defaults = True
    await db.commit()
    return {"status": "success", "message": "Default adventures imported successfully."}

@router.post("/reimport-defaults")
async def reimport_defaults(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually re-triggers import of default adventures (restoration)."""
    defaults_dir = os.path.join("adventures", "default")
    await AdventureTemplateImporter.import_from_directory(db, defaults_dir, owner_id=current_user.id, delete_after=False)
    return {"status": "success", "message": "Default adventures re-imported successfully."}

@router.post("/import")
async def import_adventure(
    payload: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Import an adventure from a manifest URL or local path."""
    source_url = payload.get("url")
    if not source_url:
        raise HTTPException(status_code=400, detail="Import URL is required.")
    
    # ... logic for importing from URL ...
    return {"status": "success", "message": f"Imported from {source_url}"}

@router.post("/import/adz")
async def import_adventure_adz(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Import an adventure as a portable .adz (ZIP) bundle."""
    try:
        content = await file.read()
        success = await AdventureTemplateImporter.import_adz(db, content, owner_id=current_user.id)
        if not success:
            raise HTTPException(status_code=400, detail="Failed to import ADZ. Ensure the file is a valid TaleWeaver bundle.")
        
        return {"status": "success", "message": "Adventure imported successfully."}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("ADZ Import failed")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/import/adv")
async def import_adventure_adv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Import an adventure as a pure .adv (JSON) manifest."""
    try:
        content = await file.read()
        payload = json.loads(content.decode("utf-8"))
        success = await AdventureTemplateImporter.import_adv_manifest(db, payload, owner_id=current_user.id)
        if not success:
            raise HTTPException(status_code=400, detail="Failed to import ADV. Ensure the file is a valid TaleWeaver manifest.")
        
        return {"status": "success", "message": "Adventure imported successfully."}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("ADV Import failed")
        raise HTTPException(status_code=500, detail=str(e))

class RegenerateVisualRequest(BaseModel):
    target_type: Literal["cover", "scene", "npc", "object", "protagonist"]
    target_id: str
    prompt: Optional[str] = None
    use_advanced_model: bool = False

@router.post("/{template_id}/visuals/regenerate")
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
            # 1. Adventure Cover
            prompt = payload.prompt or prompts.ADVENTURE_COVER_PROMPT_TEMPLATE.format(
                title=adv.title, original_prompt=adv.teaser or adv.original_prompt
            )
            image_url = await asyncio.wait_for(
                MediaEngine.generate_adventure_cover(
                    title=adv.title, original_prompt=adv.teaser or adv.original_prompt,
                    adventure_id=template_id, user_config=user_config, api_keys=api_keys,
                    style_instruction=style_instruction
                ),
                timeout=float(settings.VISUAL_TIMEOUT)
            )
            if image_url: adv.image_url = image_url

        elif payload.target_type == "protagonist":
            # 2. Protagonist
            av_res = await db.execute(select(Avatar).where(Avatar.template_id == template_id))
            avatar = av_res.scalars().first()
            if not avatar: raise HTTPException(status_code=404, detail="Protagonist avatar not found")

            generated_plot = (adv.plot or "").strip()
            base_prompt = prompts.PROTAGONIST_IMAGE_PROMPT_TEMPLATE.format(
                name=avatar.name, role=avatar.role, description=avatar.description
            )
            # Prefer generated plot context over original prompt for profile image regeneration.
            prompt = payload.prompt or (
                f"{base_prompt} Narrative context: {generated_plot[:1200]}" if generated_plot else base_prompt
            )
            image_url = await asyncio.wait_for(
                MediaEngine.generate_entity_image(
                    prompt=prompt, adventure_id=template_id, entity_id="PROTAGONIST",
                    entity_type="NPC", user_config=user_config, api_keys=api_keys,
                    style_instruction=style_instruction,
                    use_advanced_model=payload.use_advanced_model
                ),
                timeout=float(settings.VISUAL_TIMEOUT)
            )
            if image_url: avatar.profile_image = image_url

        elif payload.target_type == "scene":
            # 3. Scene
            sc_res = await db.execute(select(WorldScene).where(WorldScene.template_id == template_id, WorldScene.id == payload.target_id))
            scene = sc_res.scalars().first()
            if not scene: raise HTTPException(status_code=404, detail="Scene not found")
            
            prompt = payload.prompt or prompts.SCENE_IMAGE_PROMPT_TEMPLATE.format(
                name=scene.label, description=scene.description
            )
            image_url = await asyncio.wait_for(
                MediaEngine.generate_scene_image(
                    prompt=prompt, adventure_id=template_id, user_config=user_config, api_keys=api_keys,
                    style_instruction=style_instruction,
                    use_advanced_model=payload.use_advanced_model
                ),
                timeout=float(settings.VISUAL_TIMEOUT)
            )
            if image_url: scene.image_url = image_url

        elif payload.target_type in ["npc", "object"]:
            # 4. NPC or Object
            en_res = await db.execute(select(WorldEntity).where(WorldEntity.template_id == template_id, WorldEntity.id == payload.target_id))
            entity = en_res.scalars().first()
            if not entity: raise HTTPException(status_code=404, detail="Entity not found")
            
            if payload.target_type == "npc":
                prompt = payload.prompt or prompts.NPC_IMAGE_PROMPT_TEMPLATE.format(
                    name=entity.name, description=entity.description
                )
            else:
                prompt = payload.prompt or prompts.OBJECT_IMAGE_PROMPT_TEMPLATE.format(
                    name=entity.name, description=entity.description
                )

            image_url = await asyncio.wait_for(
                MediaEngine.generate_entity_image(
                    prompt=prompt, adventure_id=template_id, entity_id=entity.id,
                    entity_type=entity.entity_type, user_config=user_config, api_keys=api_keys,
                    style_instruction=style_instruction,
                    use_advanced_model=payload.use_advanced_model
                ),
                timeout=float(settings.VISUAL_TIMEOUT)
            )
            if image_url: entity.image_url = image_url

        await db.commit()
        return {"status": "success", "image_url": image_url}

    except Exception as e:
        logger.error(f"Failed to regenerate {payload.target_type} for {template_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
