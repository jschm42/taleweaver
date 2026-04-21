import re
import os
import uuid
import logging
from fastapi import APIRouter, Depends, File, UploadFile, Form
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, Any

logger = logging.getLogger(__name__)

from backend.core.database import get_db
from backend.models.user import User
from backend.core.security import encryption_util
from backend.core.models_config import (
    LLM_PROVIDERS,
    IMAGE_PROVIDERS,
    PREDEFINED_LLM_MODELS,
    PREDEFINED_IMAGE_MODELS
)
from backend.core.llm_router import GameMasterLLM
from backend.engine.media_engine import MediaEngine
from backend.core.config import settings

router = APIRouter(prefix="/settings", tags=["Settings"])


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").strip().lower())
    return slug.strip("-") or "item"


def _default_image_styles_catalog() -> list[dict[str, Any]]:
    return [
        {
            "id": "dark-fantasy-painting",
            "name": "Dark Fantasy Painting",
            "description": "Moody brushwork with dramatic contrast and medieval grit.",
            "instruction": "dark fantasy painting, dramatic chiaroscuro, textured brush strokes, rich atmosphere",
            "image_url": None,
        },
        {
            "id": "cinematic-realism",
            "name": "Cinematic Realism",
            "description": "Film-like composition with realistic lighting and depth.",
            "instruction": "cinematic realism, volumetric lighting, detailed environment, film still composition",
            "image_url": None,
        },
        {
            "id": "stylized-rpg-art",
            "name": "Stylized RPG Art",
            "description": "Bold outlines, vivid palettes, and heroic fantasy readability.",
            "instruction": "stylized RPG concept art, clean silhouettes, vibrant but grounded colors",
            "image_url": None,
        },
    ]


def _default_tone_catalog() -> list[dict[str, Any]]:
    return [
        {
            "id": "horror",
            "name": "Horror",
            "description": "Dread, uncertainty, and escalating psychological pressure.",
            "instruction": "Maintain unsettling tension, sparse comfort, and consequences that feel dangerous.",
            "image_url": None,
        },
        {
            "id": "sci-fi",
            "name": "Sci-Fi",
            "description": "Futuristic systems, unknown tech, and speculative mystery.",
            "instruction": "Use futuristic world logic, technical flavor, and discovery-driven narrative beats.",
            "image_url": None,
        },
        {
            "id": "sitcom",
            "name": "Sitcom",
            "description": "Comedic misunderstandings, playful pacing, and memorable banter.",
            "instruction": "Favor witty dialogue, comic timing, and low-stakes chaos with charming setbacks.",
            "image_url": None,
        },
        {
            "id": "classic-rpg",
            "name": "Classic RPG",
            "description": "Heroic quest tone with balanced drama and wonder.",
            "instruction": "Keep a classic heroic arc, meaningful choices, and clear quest momentum.",
            "image_url": None,
        },
    ]


def _normalize_catalog(catalog: Optional[list[dict[str, Any]]], *, fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not catalog:
        return fallback

    normalized: list[dict[str, Any]] = []
    for raw_item in catalog:
        if not isinstance(raw_item, dict):
            continue
        name = (raw_item.get("name") or "").strip()
        if not name:
            continue
        item_id = (raw_item.get("id") or "").strip() or _slugify(name)
        normalized.append(
            {
                "id": item_id,
                "name": name,
                "description": (raw_item.get("description") or "").strip(),
                "instruction": (raw_item.get("instruction") or "").strip(),
                "image_url": (raw_item.get("image_url") or None),
            }
        )

    return normalized or fallback


def _normalize_openrouter_model(model: Optional[str]) -> Optional[str]:
    """Strip provider prefixes from models stored for OpenRouter."""
    if not isinstance(model, str):
        return model

    normalized = model.strip()
    if not normalized:
        return normalized

    if normalized.lower().startswith("openrouter/"):
        return normalized[len("openrouter/"):].strip()

    return normalized


def _normalize_llm_settings(settings: Optional[dict]) -> dict:
    """Return LLM settings with separate providers, tokens and thinking modes."""
    fallback = {
        "small_model": "gpt-4o-mini",
        "small_model_provider": "openai",
        "small_max_tokens": 4096,
        "small_enable_thinking": False,
        "small_max_thinking_tokens": 1024,
        "complex_model": "gpt-4o",
        "complex_model_provider": "openai",
        "complex_max_tokens": 4096,
        "complex_enable_thinking": False,
        "complex_max_thinking_tokens": 1024,
        "preferred_provider": "openai",  # Legacy/Default
        "ollama_url": "http://localhost:11434",
    }
    if not settings:
        return fallback

    normalized = dict(settings)
    
    # Provider normalization
    if "small_model_provider" not in normalized:
        normalized["small_model_provider"] = normalized.get("preferred_provider") or "openai"
    if "complex_model_provider" not in normalized:
        normalized["complex_model_provider"] = normalized.get("preferred_provider") or "openai"

    # Per-model Max Tokens
    if "small_max_tokens" not in normalized:
        normalized["small_max_tokens"] = normalized.get("max_tokens") or 4096
    if "complex_max_tokens" not in normalized:
        normalized["complex_max_tokens"] = normalized.get("max_tokens") or 4096

    # Per-model Thinking Mode
    if "small_enable_thinking" not in normalized:
        normalized["small_enable_thinking"] = normalized.get("enable_thinking") or False
    if "small_max_thinking_tokens" not in normalized:
        normalized["small_max_thinking_tokens"] = normalized.get("max_thinking_tokens") or 1024

    if "complex_enable_thinking" not in normalized:
        normalized["complex_enable_thinking"] = normalized.get("enable_thinking") or False
    if "complex_max_thinking_tokens" not in normalized:
        normalized["complex_max_thinking_tokens"] = normalized.get("max_thinking_tokens") or 1024

    # OpenRouter normalization
    if normalized.get("small_model_provider") == "openrouter":
        normalized["small_model"] = _normalize_openrouter_model(normalized.get("small_model"))
    if normalized.get("complex_model_provider") == "openrouter":
        normalized["complex_model"] = _normalize_openrouter_model(normalized.get("complex_model"))

    return normalized


def _normalize_t2i_settings(settings: Optional[dict]) -> dict:
    """Return T2I settings with separate providers."""
    fallback = {
        "simple_model": "dall-e-2",
        "simple_model_provider": "openai",
        "advanced_model": "dall-e-3",
        "advanced_model_provider": "openai",
        "provider": "openai",  # Legacy/Default
        "ollama_url": "http://localhost:11434",
        "width": None,
        "height": None,
        "steps": None,
        "seed": None,
        "image_format": "jpeg",
        "image_quality": 85,
        "negative_prompt": None,
    }
    if not settings:
        return fallback

    normalized = dict(settings)
    if "simple_model_provider" not in normalized:
        normalized["simple_model_provider"] = normalized.get("provider") or "openai"
    if "advanced_model_provider" not in normalized:
        normalized["advanced_model_provider"] = normalized.get("provider") or "openai"

    # OpenRouter normalization
    if normalized.get("simple_model_provider") == "openrouter":
        normalized["simple_model"] = _normalize_openrouter_model(normalized.get("simple_model"))
    if normalized.get("advanced_model_provider") == "openrouter":
        normalized["advanced_model"] = _normalize_openrouter_model(normalized.get("advanced_model"))

    return normalized

class ApiKeyPayload(BaseModel):
    provider: str
    api_key: str

class SettingsPayload(BaseModel):
    small_model: str
    small_model_provider: str
    small_max_tokens: int = 4096
    small_enable_thinking: bool = False
    small_max_thinking_tokens: int = 1024
    
    complex_model: str
    complex_model_provider: str
    complex_max_tokens: int = 4096
    complex_enable_thinking: bool = False
    complex_max_thinking_tokens: int = 1024
    
    preferred_provider: str # Legacy
    ollama_url: Optional[str] = None

class T2ISettingsPayload(BaseModel):
    simple_model: str
    simple_model_provider: str
    advanced_model: str
    advanced_model_provider: str
    provider: str # Legacy
    ollama_url: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    steps: Optional[int] = None
    seed: Optional[int] = None
    image_format: Optional[str] = "jpeg"
    image_quality: Optional[int] = 85
    negative_prompt: Optional[str] = None
class GameSettingsPayload(BaseModel):
    clock_24h: bool = False
    date_format: str = "DD.MM.YY"


class CatalogTilePayload(BaseModel):
    id: Optional[str] = None
    name: str
    description: Optional[str] = None
    instruction: Optional[str] = None
    image_url: Optional[str] = None


class CatalogUpdatePayload(BaseModel):
    items: list[CatalogTilePayload]


class CatalogGeneratePayload(BaseModel):
    target_id: str
    catalog_type: str  # 'styles' or 'tones'
    prompt: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None

@router.get("")
async def get_settings(db: AsyncSession = Depends(get_db)):
    """Returns the current settings (sanitized keys)."""
    result = await db.execute(select(User).limit(1))
    user = result.scalars().first()
    
    # Common defaults if no user/settings
    default_llm = _normalize_llm_settings(None)
    default_t2i = _normalize_t2i_settings(None)
    
    if not user:
        return {
            "keys": {},
            "llm_settings": default_llm,
            "t2i_settings": default_t2i,
            "image_styles_catalog": _default_image_styles_catalog(),
            "tone_catalog": _default_tone_catalog(),
            "game_settings": {
                "clock_24h": False,
                "date_format": "DD.MM.YY"
            },
            "available_constants": {
                "llm_providers": LLM_PROVIDERS,
                "image_providers": IMAGE_PROVIDERS,
                "predefined_llm_models": PREDEFINED_LLM_MODELS,
                "predefined_image_models": PREDEFINED_IMAGE_MODELS,
            }
        }
    
    # Return providers that have keys, but not the actual keys
    configured_providers = list(user.encrypted_api_keys.keys()) if user.encrypted_api_keys else []
    return {
        "keys": {provider: "********" for provider in configured_providers},
        "llm_settings": _normalize_llm_settings(user.llm_settings),
        "t2i_settings": _normalize_t2i_settings(user.t2i_settings),
        "image_styles_catalog": _normalize_catalog(
            user.image_styles_catalog,
            fallback=_default_image_styles_catalog(),
        ),
        "tone_catalog": _normalize_catalog(
            user.tone_catalog,
            fallback=_default_tone_catalog(),
        ),
        "game_settings": user.game_settings or {
            "clock_24h": False,
            "date_format": "DD.MM.YY"
        },
        "available_constants": {
            "llm_providers": LLM_PROVIDERS,
            "image_providers": IMAGE_PROVIDERS,
            "predefined_llm_models": PREDEFINED_LLM_MODELS,
            "predefined_image_models": PREDEFINED_IMAGE_MODELS,
        }
    }

@router.post("/keys")
async def update_api_key(payload: ApiKeyPayload, db: AsyncSession = Depends(get_db)):
    """Saves an encrypted API key for the default local user."""
    result = await db.execute(select(User).limit(1))
    user = result.scalars().first()
    
    if not user:
        user = User(username="local_default_user")
        db.add(user)
        await db.flush()
    
    encrypted_key = encryption_util.encrypt_key(payload.api_key)
    
    current_keys = user.encrypted_api_keys or {}
    new_keys = dict(current_keys)
    new_keys[payload.provider.lower()] = encrypted_key
    user.encrypted_api_keys = new_keys
    
    await db.commit()
    return {"status": "success", "message": f"{payload.provider} key saved securely."}

@router.post("/llm")
async def update_llm_settings(payload: SettingsPayload, db: AsyncSession = Depends(get_db)):
    """Updates the LLM model preferences."""
    result = await db.execute(select(User).limit(1))
    user = result.scalars().first()
    
    if not user:
        user = User(username="local_default_user")
        db.add(user)
        await db.flush()
        
    user.llm_settings = _normalize_llm_settings(payload.model_dump())
    await db.commit()
    return {"status": "success", "message": "LLM settings updated."}

@router.post("/t2i")
async def update_t2i_settings(payload: T2ISettingsPayload, db: AsyncSession = Depends(get_db)):
    """Updates the Text-to-Image model preferences."""
    result = await db.execute(select(User).limit(1))
    user = result.scalars().first()
    
    if not user:
        user = User(username="local_default_user")
        db.add(user)
        await db.flush()
        
    user.t2i_settings = _normalize_t2i_settings(payload.model_dump())
    await db.commit()
    return {"status": "success", "message": "Image generation settings updated."}


class TestLLMPayload(BaseModel):
    model: str
    provider: str
    ollama_url: Optional[str] = None

@router.post("/test-llm")
async def test_llm_connection(payload: TestLLMPayload, db: AsyncSession = Depends(get_db)):
    """Tests the connection to an LLM provider with a simple prompt and measures latency."""
    result = await db.execute(select(User).limit(1))
    user = result.scalars().first()
    if not user:
        return {"status": "error", "message": "No user found to fetch API keys."}

    # Inject temporary ollama_url if provided
    if payload.provider == "ollama" and payload.ollama_url:
        old_settings = user.llm_settings or {}
        user.llm_settings = {**old_settings, "ollama_url": payload.ollama_url}

    import time
    try:
        gm = GameMasterLLM(user, provider=payload.provider)
        start_time = time.perf_counter()
        response = gm.execute_simple_task(
            system_prompt="You are a helpful RPG assistant.",
            user_prompt="Say 'TaleWeaver connection test successful!' in a fantasy style.",
            model=payload.model
        )
        end_time = time.perf_counter()
        latency = round(end_time - start_time, 2)
        return {"status": "success", "message": response, "response_time": latency}
    except Exception as e:
        return {"status": "error", "message": str(e)}

class TestVisionPayload(BaseModel):
    model: str
    provider: str
    ollama_url: Optional[str] = None

@router.post("/test-vision")
async def test_vision_connection(payload: TestVisionPayload, db: AsyncSession = Depends(get_db)):
    """Tests the connection to an Image provider by generating a wizard."""
    result = await db.execute(select(User).limit(1))
    user = result.scalars().first()
    if not user:
        return {"status": "error", "message": "No user found to fetch API keys."}

    provider_key = payload.provider.lower()
    api_key = None
    if provider_key != "ollama":
        if not user.encrypted_api_keys or provider_key not in user.encrypted_api_keys:
             return {"status": "error", "message": f"No API key for {payload.provider}"}
        api_key = encryption_util.decrypt_key(user.encrypted_api_keys[provider_key])

    try:
        # Use a scratch directory for test images
        test_dir = os.path.join(settings.DATA_DIR, "scratch", "test_connection")
        os.makedirs(test_dir, exist_ok=True)
        
        provider_options = {"ollama_url": payload.ollama_url} if payload.ollama_url else {}
        
        img_url = await MediaEngine.generate_image(
            prompt="A Wizard",
            model=payload.model,
            api_key=api_key,
            provider=payload.provider,
            target_dir=test_dir,
            provider_options=provider_options
        )
        
        if img_url:
            return {"status": "success", "message": "Image generation successful!", "image_url": img_url}
        else:
            return {"status": "error", "message": "Image generation failed (returned no URL)."}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/image-styles")
async def update_image_styles_catalog(payload: CatalogUpdatePayload, db: AsyncSession = Depends(get_db)):
    """Updates the admin-managed image styles catalog for adventure generation."""
    result = await db.execute(select(User).limit(1))
    user = result.scalars().first()

    if not user:
        user = User(username="local_default_user")
        db.add(user)
        await db.flush()

    raw_items = [item.model_dump() for item in payload.items]
    user.image_styles_catalog = _normalize_catalog(raw_items, fallback=_default_image_styles_catalog())
    await db.commit()
    return {"status": "success", "message": "Image styles catalog updated."}


@router.post("/tones")
async def update_tone_catalog(payload: CatalogUpdatePayload, db: AsyncSession = Depends(get_db)):
    """Updates the admin-managed tone catalog for world generation."""
    result = await db.execute(select(User).limit(1))
    user = result.scalars().first()

    if not user:
        user = User(username="local_default_user")
        db.add(user)
        await db.flush()

    raw_items = [item.model_dump() for item in payload.items]
    user.tone_catalog = _normalize_catalog(raw_items, fallback=_default_tone_catalog())
    await db.commit()
    return {"status": "success", "message": "Tone catalog updated."}


@router.post("/catalog/generate")
async def generate_catalog_image(payload: CatalogGeneratePayload, db: AsyncSession = Depends(get_db)):
    """Generates an image for a catalog tile (style or tone)."""
    result = await db.execute(select(User).limit(1))
    user = result.scalars().first()
    if not user:
        return {"status": "error", "message": "No user found."}

    t2i = user.t2i_settings or {}
    provider = (t2i.get("simple_model_provider") or t2i.get("provider", "openai")).lower()
    model = t2i.get("simple_model")
    
    if not model:
        return {"status": "error", "message": "The 'Simple Model' for image generation is not configured. Please set it in Visual Preferences."}
        
    api_key = None
    if provider != "ollama":
        if not user.encrypted_api_keys or provider not in user.encrypted_api_keys:
             return {"status": "error", "message": f"No API key for {provider}"}
        api_key = encryption_util.decrypt_key(user.encrypted_api_keys[provider])

    try:
        catalog_dir = os.path.join(settings.DATA_DIR, "catalog", payload.catalog_type)
        os.makedirs(catalog_dir, exist_ok=True)
        
        # Use simple model for catalog items (consistent with NPC/Items)
        # Construct a rich prompt using name and description if available
        base_prompt = payload.prompt
        if not base_prompt:
            item_name = payload.name or payload.target_id.replace('-', ' ')
            base_prompt = f"A visual representation of the visual style '{item_name}'."
            if payload.description:
                base_prompt += f" Context: {payload.description}"
            base_prompt += " High quality, professional digital art, no text."

        img_url = await MediaEngine.generate_image(
            prompt=base_prompt,
            model=model,
            api_key=api_key,
            provider=provider,
            target_dir=catalog_dir,
            filename=f"{payload.target_id}_{uuid.uuid4().hex[:8]}",
            provider_options=t2i
        )
        
        logger.info(f"Catalog generate result for '{payload.target_id}': img_url={img_url!r}")
        if img_url:
            return {"status": "success", "image_url": img_url}
        else:
            return {"status": "error", "message": "Generation failed: The provider returned no image data. Check your API logs or model configuration."}
    except Exception as e:
        logger.exception(f"Catalog generate exception for '{payload.target_id}'")
        error_msg = str(e)
        # Clean up some common LiteLLM/OpenRouter error strings to be more readable
        if "OpenrouterException" in error_msg:
             try:
                 import json
                 err_json = error_msg.split("-", 1)[1].strip()
                 err_data = json.loads(err_json)
                 error_msg = err_data.get("error", {}).get("message", error_msg)
             except:
                 pass
        return {"status": "error", "message": f"Generation Error: {error_msg}"}


@router.post("/catalog/upload")
async def upload_catalog_image(
    catalog_type: str = Form(...), 
    target_id: str = Form(...), 
    file: UploadFile = File(...), 
    db: AsyncSession = Depends(get_db)
):
    """Uploads a manual image for a catalog tile."""
    try:
        catalog_dir = os.path.join(settings.DATA_DIR, "catalog", catalog_type)
        os.makedirs(catalog_dir, exist_ok=True)
        
        ext = file.filename.split(".")[-1] if "." in file.filename else "png"
        filename = f"{target_id}_{uuid.uuid4().hex[:8]}.{ext}"
        filepath = os.path.join(catalog_dir, filename)
        
        with open(filepath, "wb") as f:
            f.write(await file.read())
            
        rel_path = os.path.relpath(filepath, settings.DATA_DIR).replace("\\", "/")
        return {"status": "success", "image_url": f"/data/{rel_path}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/game")
async def update_game_settings(payload: GameSettingsPayload, db: AsyncSession = Depends(get_db)):
    """Updates the general game preferences."""
    result = await db.execute(select(User).limit(1))
    user = result.scalars().first()
    
    if not user:
        user = User(username="local_default_user")
        db.add(user)
        await db.flush()
        
    user.game_settings = payload.model_dump()
    await db.commit()
    return {"status": "success", "message": "Game settings updated."}

