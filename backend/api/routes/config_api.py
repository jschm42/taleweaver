import re
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, Any

from backend.core.database import get_db
from backend.models.user import User
from backend.core.security import encryption_util

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
    """Return LLM settings with OpenRouter-safe model names."""
    fallback = {
        "small_model": "openai/gpt-4o-mini",
        "complex_model": "openai/gpt-4o-mini",
        "preferred_provider": "openai",
        "ollama_url": "http://localhost:11434",
    }
    if not settings:
        return fallback

    normalized = dict(settings)
    if (normalized.get("preferred_provider") or "").lower() == "openrouter":
        normalized["small_model"] = _normalize_openrouter_model(normalized.get("small_model"))
        normalized["complex_model"] = _normalize_openrouter_model(normalized.get("complex_model"))

    return normalized

class ApiKeyPayload(BaseModel):
    provider: str
    api_key: str

class SettingsPayload(BaseModel):
    small_model: str
    complex_model: str
    preferred_provider: str # openai, openrouter, etc.
    ollama_url: Optional[str] = None

class T2ISettingsPayload(BaseModel):
    simple_model: str
    advanced_model: str
    provider: str
    ollama_url: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    steps: Optional[int] = None
    seed: Optional[int] = None
    image_format: Optional[str] = "jpeg"
    image_quality: Optional[int] = 85
    negative_prompt: Optional[str] = None


class CatalogTilePayload(BaseModel):
    id: Optional[str] = None
    name: str
    description: Optional[str] = None
    instruction: Optional[str] = None
    image_url: Optional[str] = None


class CatalogUpdatePayload(BaseModel):
    items: list[CatalogTilePayload]

@router.get("")
async def get_settings(db: AsyncSession = Depends(get_db)):
    """Returns the current settings (sanitized keys)."""
    result = await db.execute(select(User).limit(1))
    user = result.scalars().first()
    if not user:
        return {
            "keys": {},
            "llm_settings": {
                "small_model": "openai/gpt-4o-mini",
                "complex_model": "openai/gpt-4o-mini",
                "preferred_provider": "openai",
                "ollama_url": "http://localhost:11434",
            },
            "t2i_settings": {
                "simple_model": "openai/dall-e-2",
                "advanced_model": "openai/dall-e-3",
                "provider": "openai",
                "ollama_url": "http://localhost:11434",
                "width": None,
                "height": None,
                "steps": None,
                "seed": None,
                "image_format": "jpeg",
                "image_quality": 85,
                "negative_prompt": None,
            },
            "image_styles_catalog": _default_image_styles_catalog(),
            "tone_catalog": _default_tone_catalog(),
        }
    
    # Return providers that have keys, but not the actual keys
    configured_providers = list(user.encrypted_api_keys.keys()) if user.encrypted_api_keys else []
    return {
        "keys": {provider: "********" for provider in configured_providers},
        "llm_settings": _normalize_llm_settings(user.llm_settings),
        "t2i_settings": user.t2i_settings or {
            "simple_model": "openai/dall-e-2",
            "advanced_model": "openai/dall-e-3",
            "provider": "openai",
            "ollama_url": "http://localhost:11434",
            "width": None,
            "height": None,
            "steps": None,
            "seed": None,
            "image_format": "jpeg",
            "image_quality": 85,
            "negative_prompt": None,
        },
        "image_styles_catalog": _normalize_catalog(
            user.image_styles_catalog,
            fallback=_default_image_styles_catalog(),
        ),
        "tone_catalog": _normalize_catalog(
            user.tone_catalog,
            fallback=_default_tone_catalog(),
        ),
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
        
    user.t2i_settings = payload.model_dump()
    await db.commit()
    return {"status": "success", "message": "Image generation settings updated."}


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

