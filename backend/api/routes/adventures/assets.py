import asyncio
import logging
import os
import re
import uuid
from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.schemas import SuggestPromptRequest, SuggestPromptResponse
from backend.core import prompts
from backend.core.auth import get_current_user
from backend.core.config import settings
from backend.core.database import get_db
from backend.core.llm_router import GameMasterLLM
from backend.core.style_catalog import resolve_style_instruction, resolve_tone_instruction
from backend.engine.media_engine import MediaEngine
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User
from backend.utils.path_security import (
    ensure_within_base_dir,
    ensure_within_data_dir,
    safe_data_path,
    sanitize_path_component,
)
from typing import Any
from io import BytesIO
from PIL import Image

# Mirror frontend visual limits here so server-side validation matches client hints
_VISUAL_UPLOAD_LIMITS = {
    "cover": {"maxWidth": 2048, "maxHeight": 1024, "maxBytes": 4 * 1024 * 1024},
    "protagonist": {"maxWidth": 1024, "maxHeight": 1280, "maxBytes": 2 * 1024 * 1024},
    "scene": {"maxWidth": 1600, "maxHeight": 900, "maxBytes": 3 * 1024 * 1024},
    "npc": {"maxWidth": 1024, "maxHeight": 1280, "maxBytes": 2 * 1024 * 1024},
    "object": {"maxWidth": 1024, "maxHeight": 1024, "maxBytes": 2 * 1024 * 1024},
}

_ALLOWED_MIME_TYPES = {"image/png", "image/jpeg", "image/webp"}

router = APIRouter(prefix="/{template_id}/visuals", tags=["Assets"])
logger = logging.getLogger(__name__)
_SAFE_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
_ALLOWED_VISUAL_TARGET_TYPES = {"cover", "scene", "npc", "object", "protagonist"}


def _build_visual_prompt(
    target_type: str,
    target_obj: Any,
    custom_prompt: Optional[str],
    *,
    style_instruction: Optional[str] = None,
    tone_instruction: Optional[str] = None,
) -> str:
    if custom_prompt and custom_prompt.strip():
        return custom_prompt.strip()

    prompt_suffix = ""
    if style_instruction:
        prompt_suffix += f" Style constraints: {style_instruction}."
    if tone_instruction:
        prompt_suffix += f" Narrative tone reference: {tone_instruction}."

    def get_attr(obj, attr, default=""):
        if isinstance(obj, dict):
            return obj.get(attr) or default
        return getattr(obj, attr, None) or default

    if target_type == "protagonist":
        name = get_attr(target_obj, "name", "The protagonist")
        role = get_attr(target_obj, "role", "adventurer")
        description = get_attr(target_obj, "description", "A distinctive fantasy hero.")
        return f"Portrait of character {name}, {role}. {description}. Game character art style.{prompt_suffix}"

    if target_type == "scene":
        label = get_attr(target_obj, "label") or get_attr(target_obj, "name") or "Scene"
        description = get_attr(target_obj, "description")
        return f"Atmospheric background: {label}. {description}. RPG visual novel style, high detail.{prompt_suffix}"

    if target_type == "npc":
        name = get_attr(target_obj, "name", "NPC")
        description = get_attr(target_obj, "description", "A distinctive non-player character.")
        return f"Portrait of NPC {name}. {description}. Character portrait, high detail.{prompt_suffix}"

    if target_type == "object":
        name = get_attr(target_obj, "name", "Object")
        description = get_attr(target_obj, "description", "A detailed fantasy object.")
        return f"Detailed illustration of object {name}. {description}. Fantasy item concept art, isolated and clearly readable.{prompt_suffix}"

    raise HTTPException(status_code=400, detail="Unsupported visual target type.")


def _sanitize_image_extension(filename: Optional[str]) -> str:
    if not filename or "." not in filename:
        return "png"
    ext = filename.rsplit(".", 1)[-1].strip().lower()
    return ext if ext in _SAFE_IMAGE_EXTENSIONS else "png"


def _extension_from_content_type(content_type: Optional[str]) -> str:
    ext_by_type = {
        "image/png": "png",
        "image/jpeg": "jpg",
        "image/webp": "webp",
    }
    return ext_by_type.get((content_type or "").strip().lower(), "png")


def _sanitize_filename_token(value: Optional[str]) -> Optional[str]:
    candidate = (value or "").strip()
    if not candidate:
        return None
    token = re.sub(r"[^A-Za-z0-9_-]+", "-", candidate).strip("-")
    return token[:96] or None


def _build_uploaded_visual_path(
    template_id: str,
    target_type: str,
    file_ext: str,
    trusted_target_token: Optional[str] = None,
) -> str:
    safe_template_id = sanitize_path_component(template_id)
    if not safe_template_id:
        raise ValueError("Invalid adventure template identifier.")

    safe_target_type = sanitize_path_component(target_type)
    if safe_target_type not in _ALLOWED_VISUAL_TARGET_TYPES:
        raise ValueError("Invalid visual target type.")

    safe_file_ext = _sanitize_image_extension(file_ext)
    base_storage_path = safe_data_path("adventures", "library", safe_template_id, "visuals")

    if safe_target_type == "cover":
        storage_path = base_storage_path
        filename = f"cover_{uuid.uuid4().hex}.{safe_file_ext}"
    else:
        storage_path = safe_data_path("adventures", "library", safe_template_id, "visuals", safe_target_type)
        safe_token = _sanitize_filename_token(trusted_target_token)
        filename_prefix = safe_token or safe_target_type
        filename = f"{filename_prefix}_{uuid.uuid4().hex}.{safe_file_ext}"

    safe_storage_path = ensure_within_data_dir(storage_path)
    os.makedirs(safe_storage_path, exist_ok=True)
    candidate_path = ensure_within_data_dir(os.path.join(safe_storage_path, filename))
    return ensure_within_base_dir(candidate_path, safe_storage_path)

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
    from backend.models.world_entity import WorldEntity, WorldScene
    
    adv = await db.get(AdventureTemplate, template_id)
    if not adv or adv.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Adventure template not found")

    image_url = None
    user_config = {"t2i_settings": current_user.t2i_settings}
    api_keys = current_user.encrypted_api_keys
    t2i = current_user.t2i_settings or {}

    # Resolve Style Instruction
    style_instruction = resolve_style_instruction(
        adv.selected_image_styles,
        current_user.image_styles_catalog,
    )

    # Resolve Tone Instruction
    tone_instruction = resolve_tone_instruction(
        adv.selected_tone,
        current_user.tone_catalog,
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
            av_res = await db.execute(
                select(Avatar)
                .where(Avatar.template_id == template_id)
                .order_by(Avatar.created_at.asc(), Avatar.id.asc())
                .limit(1)
            )
            avatar = av_res.scalars().first()
            if not avatar: raise HTTPException(status_code=404, detail="Protagonist not found")
            
            prompt = _build_visual_prompt(
                payload.target_type,
                avatar,
                payload.prompt,
                style_instruction=style_instruction,
                tone_instruction=tone_instruction,
            )
            image_url = await asyncio.wait_for(
                MediaEngine.generate_entity_image(
                    prompt=prompt,
                    adventure_id=template_id, entity_id=avatar.id, entity_type="PROTAGONIST",
                    user_config=user_config, api_keys=api_keys,
                    style_instruction=style_instruction,
                    use_advanced_model=(t2i.get("protagonist_model_quality", "advanced") == "advanced")
                ),
                timeout=float(settings.VISUAL_TIMEOUT)
            )
            if image_url: avatar.profile_image = image_url

        elif payload.target_type == "scene":
            res = await db.execute(select(WorldScene).where(WorldScene.id == payload.target_id, WorldScene.template_id == template_id))
            scene = res.scalars().first()
            if not scene: raise HTTPException(status_code=404, detail="Scene not found")
            
            prompt = _build_visual_prompt(
                payload.target_type,
                scene,
                payload.prompt,
                style_instruction=style_instruction,
                tone_instruction=tone_instruction,
            )
            image_url = await asyncio.wait_for(
                MediaEngine.generate_scene_image(
                    prompt=prompt,
                    adventure_id=template_id, user_config=user_config, api_keys=api_keys,
                    style_instruction=style_instruction,
                    use_advanced_model=(t2i.get("scene_model_quality", "advanced") == "advanced")
                ),
                timeout=float(settings.VISUAL_TIMEOUT)
            )
            if image_url: scene.image_url = image_url

        elif payload.target_type in ["npc", "object"]:
            res = await db.execute(select(WorldEntity).where(WorldEntity.id == payload.target_id, WorldEntity.template_id == template_id))
            entity = res.scalars().first()
            if not entity: raise HTTPException(status_code=404, detail="Entity not found")
            
            prompt = _build_visual_prompt(
                payload.target_type,
                entity,
                payload.prompt,
                style_instruction=style_instruction,
                tone_instruction=tone_instruction,
            )
            image_url = await asyncio.wait_for(
                MediaEngine.generate_entity_image(
                    prompt=prompt,
                    adventure_id=template_id, entity_id=entity.id, entity_type=payload.target_type.upper(),
                    user_config=user_config, api_keys=api_keys,
                    style_instruction=style_instruction,
                    use_advanced_model=(
                        t2i.get("profile_model_quality", "advanced") == "advanced"
                        if payload.target_type == "npc"
                        else t2i.get("asset_model_quality", "simple") == "advanced"
                    )
                ),
                timeout=float(settings.VISUAL_TIMEOUT)
            )
            if image_url: entity.image_url = image_url

        await db.commit()
        return {"status": "success", "image_url": image_url}
    except asyncio.TimeoutError as exc:
        raise HTTPException(status_code=504, detail="Visual generation timed out.") from exc
    except ValueError as exc:
        logger.warning("Visual regeneration blocked/invalid: %s", exc)
        raise HTTPException(status_code=400, detail="Invalid visual regeneration request.") from exc
    except Exception as exc:
        logger.exception("Visual regeneration failed")
        raise HTTPException(status_code=500, detail="Visual generation failed.") from exc

@router.post("/suggest-prompt", response_model=SuggestPromptResponse)
async def suggest_prompt(
    template_id: str,
    payload: SuggestPromptRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate an AI prompt suggestion based on the asset's description."""
    from backend.models.avatar import Avatar
    from backend.models.world_entity import WorldEntity, WorldScene
    
    adv = await db.get(AdventureTemplate, template_id)
    if not adv or adv.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Adventure template not found")

    name = ""
    description = ""

    logger.info("Suggesting prompt for %s (%s) in adventure %s", payload.target_type, payload.target_id, template_id)

    if payload.target_type == "cover":
        name = adv.title
        description = adv.teaser or adv.original_prompt or ""
    elif payload.target_type == "protagonist":
        av_res = await db.execute(
            select(Avatar)
            .where(Avatar.template_id == template_id)
            .order_by(Avatar.created_at.asc(), Avatar.id.asc())
            .limit(1)
        )
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

    logger.info("Resolved name '%s', description length: %d", name, len(description) if description else 0)

    if not description:
        logger.warning("No description found for %s %s", payload.target_type, payload.target_id)
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
    from backend.models.world_entity import WorldEntity, WorldScene

    adv = await db.get(AdventureTemplate, template_id)
    if not adv or adv.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Adventure template not found")

    try:
        content = await file.read()

        # Validate mime type
        if file.content_type and file.content_type not in _ALLOWED_MIME_TYPES:
            raise HTTPException(status_code=400, detail="Unsupported file type. Please use PNG, JPEG, or WEBP.")

        limits = _VISUAL_UPLOAD_LIMITS.get(target_type)
        if not limits:
            raise HTTPException(status_code=400, detail="Invalid visual target type.")

        # Validate raw file bytes size first
        if limits and len(content) > int(limits["maxBytes"]):
            raise HTTPException(
                status_code=400,
                detail=f"Max file size for this asset is {int(limits['maxBytes']) // (1024 * 1024)} MB.",
            )

        # Validate image dimensions
        try:
            img = Image.open(BytesIO(content))
            width, height = img.size
        except Exception:
            raise HTTPException(status_code=400, detail="Could not read image dimensions.")

        if width > int(limits["maxWidth"]) or height > int(limits["maxHeight"]):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Max size for this asset is {limits['maxWidth']}x{limits['maxHeight']} px. "
                    f"Uploaded image is {width}x{height} px."
                ),
            )

        avatar = None
        scene = None
        entity = None
        trusted_target_token: Optional[str] = None

        if target_type == "protagonist":
            av_res = await db.execute(
                select(Avatar)
                .where(Avatar.template_id == template_id)
                .order_by(Avatar.created_at.asc(), Avatar.id.asc())
                .limit(1)
            )
            avatar = av_res.scalars().first()
            if not avatar:
                raise HTTPException(status_code=404, detail="Protagonist not found for this adventure")
            trusted_target_token = avatar.id
        elif target_type == "scene":
            sc_res = await db.execute(
                select(WorldScene).where(
                    WorldScene.template_id == template_id,
                    WorldScene.session_id.is_(None),
                    WorldScene.id == target_id,
                )
            )
            scene = sc_res.scalars().first()
            if not scene:
                raise HTTPException(status_code=404, detail="Scene not found for this adventure")
            trusted_target_token = scene.id
        elif target_type in ["npc", "object"]:
            en_res = await db.execute(
                select(WorldEntity).where(
                    WorldEntity.template_id == template_id,
                    WorldEntity.session_id.is_(None),
                    WorldEntity.id == target_id,
                )
            )
            entity = en_res.scalars().first()
            if not entity:
                raise HTTPException(status_code=404, detail="Entity not found for this adventure")
            trusted_target_token = entity.id

        full_path = _build_uploaded_visual_path(
            adv.id,
            target_type,
            _extension_from_content_type(file.content_type),
            trusted_target_token=trusted_target_token,
        )
        safe_parent_dir = ensure_within_data_dir(os.path.dirname(full_path))
        full_path = ensure_within_base_dir(full_path, safe_parent_dir)
        with open(full_path, "wb") as f:
            f.write(content)

        rel_path = os.path.relpath(full_path, settings.DATA_DIR).replace("\\", "/")
        relative_url = f"/data/{rel_path}"
        
        if target_type == "cover":
            adv.image_url = relative_url
        elif target_type == "protagonist":
            if not avatar:
                raise HTTPException(status_code=404, detail="Protagonist not found for this adventure")
            avatar.profile_image = relative_url
        elif target_type == "scene":
            if not scene:
                raise HTTPException(status_code=404, detail="Scene not found for this adventure")
            scene.image_url = relative_url
        elif target_type in ["npc", "object"]:
            if not entity:
                raise HTTPException(status_code=404, detail="Entity not found for this adventure")
            entity.image_url = relative_url
            
        await db.commit()
        return {"status": "uploaded", "target_type": target_type, "image_url": relative_url}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to upload visual for %s", template_id)
        raise HTTPException(status_code=500, detail="Visual upload failed.") from exc

