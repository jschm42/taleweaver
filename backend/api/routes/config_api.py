import logging
import os
import re
import uuid
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

SUPPORTED_TTS_MODELS = {
    "gemini-3.1-flash-tts-preview",
    "gemini-2.5-flash-preview-tts",
}

TTS_MODEL_ALIASES = {
    "gemini-2.5-flash-tts-preview": "gemini-2.5-flash-preview-tts",
    "gemini-2.5-flash-tts": "gemini-2.5-flash-preview-tts",
}

from backend.core.auth import get_current_admin, get_current_user
from backend.core.config import settings
from backend.core.database import get_db
from backend.core.llm_router import GameMasterLLM
from backend.core.models_config import (
    IMAGE_PROVIDERS,
    LLM_PROVIDERS,
    PREDEFINED_IMAGE_MODELS,
    PREDEFINED_LLM_MODELS,
    PREDEFINED_TTS_MODELS,
    TTS_PROVIDERS,
)
from backend.core.security import encryption_util
from backend.core.tts_voices import GOOGLE_TTS_VOICE_CATALOG, GOOGLE_TTS_VOICE_LIST
from backend.engine.media_engine import MediaEngine
from backend.engine.tts_engine import TTSEngine
from backend.models.user import User

router = APIRouter(prefix="/settings", tags=["Settings"])
print(f"DEBUG: Loading config_api module, router prefix: {router.prefix}")

DEFAULT_SMALL_MAX_TOKENS = 12288
DEFAULT_COMPLEX_MAX_TOKENS = 24576
DEFAULT_GENERATOR_MAX_TOKENS = 32768
_SAFE_PATH_COMPONENT_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_SAFE_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
_ALLOWED_CATALOG_TYPES = {"styles", "tones"}


async def _resolve_global_settings_owner(db: AsyncSession, fallback_user: User) -> User:
    """Return the user that acts as global settings source (prefer admin)."""
    admin_res = await db.execute(select(User).where(User.role == "admin").limit(1))
    admin_user = admin_res.scalars().first()
    return admin_user or fallback_user


async def _broadcast_global_settings(db: AsyncSession, source_user: User) -> None:
    """Copy global settings from source user to all users efficiently."""
    # Using a bulk update is much better for SQLite to avoid lock contention
    # and memory overhead of fetching all user objects.
    await db.execute(
        update(User).values(
            encrypted_api_keys=dict(source_user.encrypted_api_keys or {}),
            llm_settings=dict(source_user.llm_settings or {}),
            t2i_settings=dict(source_user.t2i_settings or {}),
            image_styles_catalog=list(source_user.image_styles_catalog or []),
            tone_catalog=list(source_user.tone_catalog or []),
            game_settings=dict(source_user.game_settings or {}),
            tts_settings=dict(source_user.tts_settings or {})
        )
    )
    # No need to loop and modify objects manually


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").strip().lower())
    return slug.strip("-") or "item"


def _sanitize_filename_component(value: str) -> Optional[str]:
    """Return a safe filename component for user-provided identifiers."""
    candidate = _slugify(value)
    if not candidate:
        return None
    if any(sep in candidate for sep in (os.sep, os.altsep) if sep):
        return None
    if candidate in {".", ".."} or ".." in candidate:
        return None
    if not re.fullmatch(r"[a-z0-9-]{1,64}", candidate):
        return None
    return candidate


def _sanitize_path_component(value: str) -> Optional[str]:
    """Return a safe single path segment, or None when invalid."""
    candidate = (value or "").strip()
    if not candidate:
        return None
    if any(sep in candidate for sep in (os.sep, os.altsep) if sep):
        return None
    if candidate in {".", ".."} or ".." in candidate:
        return None
    if not _SAFE_PATH_COMPONENT_RE.fullmatch(candidate):
        return None
    return candidate


def _ensure_within_data_dir(path: str) -> str:
    """Validate that path resolves inside DATA_DIR and return absolute path."""
    data_root = os.path.abspath(settings.DATA_DIR)
    resolved = os.path.abspath(path)
    try:
        if os.path.commonpath([resolved, data_root]) != data_root:
            raise ValueError("Resolved path escapes DATA_DIR.")
    except ValueError as exc:
        raise ValueError("Invalid path: cannot resolve against DATA_DIR.") from exc
    return resolved


def _safe_data_path(*parts: str) -> str:
    """Build a safe path rooted at DATA_DIR."""
    return _ensure_within_data_dir(os.path.join(settings.DATA_DIR, *parts))


def _sanitize_image_extension(filename: Optional[str]) -> str:
    """Return a safe image extension with png fallback."""
    if not filename or "." not in filename:
        return "png"
    ext = filename.rsplit(".", 1)[-1].strip().lower()
    return ext if ext in _SAFE_IMAGE_EXTENSIONS else "png"


def _route_error_response(operation: str, message: str, exc: Exception) -> dict[str, str]:
    """Log internal exception details while returning a generic client-safe message."""
    logger.exception("%s failed", operation, exc_info=exc)
    return {"status": "error", "message": message}


def _build_catalog_upload_path(catalog_type: str, target_id: str, original_filename: Optional[str]) -> str:
    """Create a validated file path for uploaded catalog images."""
    safe_catalog_type = _sanitize_path_component(catalog_type)
    if safe_catalog_type not in _ALLOWED_CATALOG_TYPES:
        raise ValueError("Invalid catalog type.")

    catalog_dir = _safe_data_path("catalog", safe_catalog_type)
    os.makedirs(catalog_dir, exist_ok=True)

    ext = _sanitize_image_extension(original_filename)
    safe_target_id = _sanitize_filename_component(target_id)
    if not safe_target_id:
        raise ValueError("Invalid target id.")
    filename = f"{safe_target_id}_{uuid.uuid4().hex[:8]}.{ext}"
    return _ensure_within_data_dir(os.path.join(catalog_dir, filename))


from backend.core.catalog_defaults import DEFAULT_IMAGE_STYLES, DEFAULT_TONES


def _default_image_styles_catalog() -> list[dict[str, Any]]:
    return [dict(item) for item in DEFAULT_IMAGE_STYLES]


def _default_tone_catalog() -> list[dict[str, Any]]:
    return [dict(item) for item in DEFAULT_TONES]


def _normalize_catalog(catalog: list[dict[str, Optional[Any]]], *, fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
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


async def _fetch_ollama_models(ollama_url: Optional[str]) -> list[str]:
    """Return installed Ollama model names from the local Ollama daemon."""
    base_url = (ollama_url or "http://localhost:11434").rstrip("/")
    endpoint = f"{base_url}/api/tags"
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            response = await client.get(endpoint)
        response.raise_for_status()
        payload = response.json()

        models: list[str] = []
        for item in payload.get("models") or []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            if name:
                models.append(name)

        return sorted(set(models))
    except (httpx.HTTPError, ValueError, TypeError):
        logger.info("Could not fetch Ollama models from %s", endpoint)
        return []


async def _fetch_stable_diffusion_models(stable_diffusion_url: Optional[str]) -> list[str]:
    """Return available Stable Diffusion model checkpoints from local Automatic1111/Forge daemon."""
    base_url = (stable_diffusion_url or "http://127.0.0.1:7860").rstrip("/")
    endpoint = f"{base_url}/sdapi/v1/sd-models"
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            response = await client.get(endpoint)
        response.raise_for_status()
        payload = response.json()

        models: list[str] = ["default"]
        if isinstance(payload, list):
            for item in payload:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("title") or item.get("model_name") or "").strip()
                if name:
                    models.append(name)

        unique_models = ["default"]
        for m in sorted(set(models)):
            if m != "default":
                unique_models.append(m)
        return unique_models
    except (httpx.HTTPError, ValueError, TypeError):
        logger.info("Could not fetch Stable Diffusion models from %s", endpoint)
        return ["default"]


async def _build_available_constants(llm_settings: Optional[dict], t2i_settings: Optional[dict] = None) -> dict[str, Any]:
    """Return available providers and model catalogs for the admin UI."""
    normalized_llm = _normalize_llm_settings(llm_settings)

    def _uses_ollama_llm(settings_payload: dict[str, Any]) -> bool:
        provider_fields = (
            "small_model_provider",
            "complex_model_provider",
            "generator_model_provider",
            "play_agent_model_provider",
            "preferred_provider",
        )
        return any(
            str(settings_payload.get(field) or "").strip().lower() == "ollama"
            for field in provider_fields
        )

    predefined_llm_models = dict(PREDEFINED_LLM_MODELS)
    if _uses_ollama_llm(normalized_llm):
        ollama_models = await _fetch_ollama_models(normalized_llm.get("ollama_url"))
        if ollama_models:
            predefined_llm_models["ollama"] = ollama_models

    normalized_t2i = _normalize_t2i_settings(t2i_settings)
    sd_models = await _fetch_stable_diffusion_models(normalized_t2i.get("stable_diffusion_url"))

    predefined_image_models = dict(PREDEFINED_IMAGE_MODELS)
    predefined_image_models["stable_diffusion"] = sd_models

    return {
        "llm_providers": LLM_PROVIDERS,
        "image_providers": IMAGE_PROVIDERS,
        "tts_providers": TTS_PROVIDERS,
        "predefined_llm_models": predefined_llm_models,
        "predefined_image_models": predefined_image_models,
    }


def _normalize_llm_settings(llm_settings: Optional[dict]) -> dict:
    """Return LLM settings with separate providers, tokens and thinking modes."""
    fallback = {
        "small_model": "",
        "small_model_provider": "openai",
        "small_max_tokens": DEFAULT_SMALL_MAX_TOKENS,
        "small_enable_thinking": False,
        "small_max_thinking_tokens": 1024,
        "complex_model": "",
        "complex_model_provider": "openai",
        "complex_max_tokens": DEFAULT_COMPLEX_MAX_TOKENS,
        "complex_enable_thinking": False,
        "complex_max_thinking_tokens": 2048,
        "generator_model": "",
        "generator_model_provider": "openai",
        "generator_max_tokens": DEFAULT_GENERATOR_MAX_TOKENS,
        "generator_enable_thinking": False,
        "generator_max_thinking_tokens": 2048,
        "play_agent_model": "",
        "play_agent_model_provider": "openai",
        "preferred_provider": "openai",  # Legacy/Default
        "ollama_url": "http://localhost:11434",
    }
    if not llm_settings:
        return fallback

    normalized = dict(llm_settings)
    
    # Provider normalization
    if "small_model_provider" not in normalized:
        normalized["small_model_provider"] = normalized.get("preferred_provider") or "openai"
    if "complex_model_provider" not in normalized:
        normalized["complex_model_provider"] = normalized.get("preferred_provider") or "openai"
    if "generator_model_provider" not in normalized:
        normalized["generator_model_provider"] = normalized.get("complex_model_provider") or "openai"
    if "play_agent_model_provider" not in normalized:
        normalized["play_agent_model_provider"] = (
            normalized.get("small_model_provider")
            or normalized.get("complex_model_provider")
            or normalized.get("preferred_provider")
            or "openai"
        )

    # Per-model Max Tokens
    if "small_max_tokens" not in normalized:
        normalized["small_max_tokens"] = normalized.get("max_tokens") or DEFAULT_SMALL_MAX_TOKENS
    if "complex_max_tokens" not in normalized:
        normalized["complex_max_tokens"] = normalized.get("max_tokens") or DEFAULT_COMPLEX_MAX_TOKENS
    if "generator_max_tokens" not in normalized:
        normalized["generator_max_tokens"] = normalized.get("max_tokens") or DEFAULT_GENERATOR_MAX_TOKENS

    # Per-model Thinking Mode
    if "small_enable_thinking" not in normalized:
        normalized["small_enable_thinking"] = normalized.get("enable_thinking") or False
    if "small_max_thinking_tokens" not in normalized:
        normalized["small_max_thinking_tokens"] = normalized.get("max_thinking_tokens") or 1024

    if "complex_enable_thinking" not in normalized:
        normalized["complex_enable_thinking"] = normalized.get("enable_thinking") or False
    if "complex_max_thinking_tokens" not in normalized:
        normalized["complex_max_thinking_tokens"] = normalized.get("max_thinking_tokens") or 1024

    if "generator_enable_thinking" not in normalized:
        normalized["generator_enable_thinking"] = normalized.get("enable_thinking") or False
    if "generator_max_thinking_tokens" not in normalized:
        normalized["generator_max_thinking_tokens"] = normalized.get("max_thinking_tokens") or 1024

    # Fallback between small and complex if one is missing
    s_model = normalized.get("small_model")
    c_model = normalized.get("complex_model")
    
    if s_model and not c_model:
        normalized["complex_model"] = s_model
        normalized["complex_model_provider"] = normalized.get("small_model_provider")
        normalized["complex_max_tokens"] = normalized.get("small_max_tokens")
        normalized["complex_enable_thinking"] = normalized.get("small_enable_thinking")
        normalized["complex_max_thinking_tokens"] = normalized.get("small_max_thinking_tokens")
    elif c_model and not s_model:
        normalized["small_model"] = c_model
        normalized["small_model_provider"] = normalized.get("complex_model_provider")
        normalized["small_max_tokens"] = normalized.get("complex_max_tokens")
        normalized["small_enable_thinking"] = normalized.get("complex_enable_thinking")
        normalized["small_max_thinking_tokens"] = normalized.get("small_max_thinking_tokens")

    # If generator is missing, fallback to complex
    if not normalized.get("generator_model") and normalized.get("complex_model"):
        normalized["generator_model"] = normalized.get("complex_model")
        normalized["generator_model_provider"] = normalized.get("complex_model_provider")
        normalized["generator_max_tokens"] = normalized.get("complex_max_tokens")
        normalized["generator_enable_thinking"] = normalized.get("complex_enable_thinking")
        normalized["generator_max_thinking_tokens"] = normalized.get("complex_max_thinking_tokens")

    # If play-agent model is missing, fallback to small for autonomous gameplay mode.
    if not normalized.get("play_agent_model") and normalized.get("small_model"):
        normalized["play_agent_model"] = normalized.get("small_model")
        normalized["play_agent_model_provider"] = normalized.get("small_model_provider")

    # OpenRouter normalization
    if normalized.get("small_model_provider") == "openrouter":
        normalized["small_model"] = _normalize_openrouter_model(normalized.get("small_model"))
    if normalized.get("complex_model_provider") == "openrouter":
        normalized["complex_model"] = _normalize_openrouter_model(normalized.get("complex_model"))
    if normalized.get("generator_model_provider") == "openrouter":
        normalized["generator_model"] = _normalize_openrouter_model(normalized.get("generator_model"))
    if normalized.get("play_agent_model_provider") == "openrouter":
        normalized["play_agent_model"] = _normalize_openrouter_model(normalized.get("play_agent_model"))

    return normalized


def _normalize_tts_settings(tts_settings: Optional[dict]) -> dict:
    """Return TTS settings with voice list, selected voice and style context."""
    full_voice_list = list(GOOGLE_TTS_VOICE_LIST)
    full_voice_catalog = [dict(entry) for entry in GOOGLE_TTS_VOICE_CATALOG]
    fallback = {
        "enabled": False,
        "provider": "google",
        "selected_model": "gemini-3.1-flash-tts-preview",
        "voice_list": full_voice_list,
        "voice_catalog": full_voice_catalog,
        "selected_voice": "Puck",
        "elevenlabs_voice_id": "",
        "use_vocal_tags": True,
        "use_text_chunking": True,
        "sample_context": "A resonant, authoritative voice. Cinematic, grand, and articulate. The tone is epic and wise, carrying the weight of history with a clear, commanding presence and immersive storytelling.",
        "speech_rate": 1.0
    }
    if not tts_settings:
        return fallback

    normalized = dict(tts_settings)

    # Accept historical/alternate keys to avoid silently resetting model selection.
    if "selected_model" not in normalized:
        selected_model_legacy = (
            normalized.get("model")
            or normalized.get("tts_model")
            or normalized.get("single_voice_model")
            or normalized.get("single_voice_tts_model")
        )
        if selected_model_legacy:
            normalized["selected_model"] = selected_model_legacy

    selected_model = str(normalized.get("selected_model") or "").strip()
    if selected_model in TTS_MODEL_ALIASES:
        normalized["selected_model"] = TTS_MODEL_ALIASES[selected_model]

    # Ensure new fields exist
    # Ensure new fields exist with safe defaults
    normalized["provider"] = normalized.get("provider") or "google"
    normalized["elevenlabs_voice_id"] = normalized.get("elevenlabs_voice_id", "")
    
    # Handle booleans carefully: only set to True if the key is missing entirely
    if "use_vocal_tags" not in normalized:
        normalized["use_vocal_tags"] = True
    if "use_text_chunking" not in normalized:
        normalized["use_text_chunking"] = True

    if "enabled" not in normalized:
        normalized["enabled"] = fallback["enabled"]
    if "selected_model" not in normalized:
        normalized["selected_model"] = fallback["selected_model"]
    elif normalized.get("provider") == "google" and normalized.get("selected_model") not in SUPPORTED_TTS_MODELS:
        normalized["selected_model"] = fallback["selected_model"]
    
    # Always ensure the full list is available
    normalized["voice_list"] = full_voice_list
    normalized["voice_catalog"] = full_voice_catalog
    
    if "selected_voice" not in normalized:
        normalized["selected_voice"] = fallback["selected_voice"]
    if "sample_context" not in normalized:
        normalized["sample_context"] = fallback["sample_context"]
    if "speech_rate" not in normalized:
        normalized["speech_rate"] = fallback["speech_rate"]
    return normalized


def _normalize_t2i_settings(t2i_settings: Optional[dict]) -> dict:
    """Return T2I settings with separate providers."""
    fallback = {
        "simple_model": "",
        "simple_model_provider": "openai",
        "advanced_model": "",
        "advanced_model_provider": "openai",
        "provider": "openai",  # Legacy/Default
        "ollama_url": "http://localhost:11434",
        "stable_diffusion_url": "http://127.0.0.1:7860",
        "width": None,
        "height": None,
        "steps": None,
        "cfg_scale": None,
        "simple_steps": None,
        "simple_cfg_scale": None,
        "advanced_steps": None,
        "advanced_cfg_scale": None,
        "simple_sampler_name": None,
        "simple_scheduler": None,
        "advanced_sampler_name": None,
        "advanced_scheduler": None,
        "simple_min_long_edge": None,
        "advanced_min_long_edge": None,
        "seed": None,
        "image_format": "jpeg",
        "image_quality": 85,
        "negative_prompt": None,
        # Model usage quality per content type
        "scene_model_quality": "advanced",
        "profile_model_quality": "advanced",
        "protagonist_model_quality": "advanced",
        "asset_model_quality": "simple",
    }
    if not t2i_settings:
        return fallback

    normalized = dict(t2i_settings)
    if "simple_model_provider" not in normalized:
        normalized["simple_model_provider"] = normalized.get("provider") or "openai"
    if "advanced_model_provider" not in normalized:
        normalized["advanced_model_provider"] = normalized.get("provider") or "openai"

    if "stable_diffusion_url" not in normalized:
        normalized["stable_diffusion_url"] = "http://127.0.0.1:7860"
    if "ollama_url" not in normalized:
        normalized["ollama_url"] = "http://localhost:11434"
    if "cfg_scale" not in normalized:
        normalized["cfg_scale"] = None

    for field in (
        "simple_steps", "simple_cfg_scale", 
        "advanced_steps", "advanced_cfg_scale",
        "simple_sampler_name", "simple_scheduler",
        "advanced_sampler_name", "advanced_scheduler",
        "simple_min_long_edge", "advanced_min_long_edge"
    ):
        if field not in normalized:
            normalized[field] = None

    # Model usage quality defaults
    for field, default in (
        ("scene_model_quality", "advanced"),
        ("profile_model_quality", "advanced"),
        ("protagonist_model_quality", "advanced"),
        ("asset_model_quality", "simple"),
    ):
        if field not in normalized:
            normalized[field] = default

    # OpenRouter normalization
    if normalized.get("simple_model_provider") == "openrouter":
        normalized["simple_model"] = _normalize_openrouter_model(normalized.get("simple_model"))
    if normalized.get("advanced_model_provider") == "openrouter":
        normalized["advanced_model"] = _normalize_openrouter_model(normalized.get("advanced_model"))

    return normalized


def _is_llm_configured(user: User, db_keys: dict) -> bool:
    llm = _normalize_llm_settings(user.llm_settings)
    small_provider = llm.get("small_model_provider", "openai")
    complex_provider = llm.get("complex_model_provider", "openai")
    small_model = llm.get("small_model")
    complex_model = llm.get("complex_model")

    def has_key(provider):
        if provider == "ollama":
            return True
        return bool(settings.get_env_api_key(provider)) or (db_keys and provider in db_keys)

    return all([
        has_key(small_provider),
        bool(small_model),
        has_key(complex_provider),
        bool(complex_model)
    ])


def _is_t2i_configured(user: User, db_keys: dict) -> bool:
    t2i = _normalize_t2i_settings(user.t2i_settings)
    simple_provider = t2i.get("simple_model_provider", "openai")
    simple_model = t2i.get("simple_model")

    def has_key(provider):
        if provider in ("ollama", "stable_diffusion"):
            return True
        return bool(settings.get_env_api_key(provider)) or (db_keys and provider in db_keys)

    return has_key(simple_provider) and bool(simple_model)


def _resolve_provider_api_key(provider: str, encrypted_keys: Optional[dict]) -> Optional[str]:
    """Resolve provider API key from environment first, then encrypted DB keys."""
    provider_key = (provider or "").lower()
    env_key = settings.get_env_api_key(provider_key)
    if env_key:
        return env_key

    if encrypted_keys and provider_key in encrypted_keys:
        try:
            return encryption_util.decrypt_key(encrypted_keys[provider_key])
        except (ValueError, TypeError, KeyError):
            logger.error("Failed to decrypt API key for provider: %s", provider_key)
            return None
    return None

class ApiKeyPayload(BaseModel):
    provider: str
    api_key: str

class SettingsPayload(BaseModel):
    small_model: str
    small_model_provider: str
    small_max_tokens: int = DEFAULT_SMALL_MAX_TOKENS
    small_enable_thinking: bool = False
    small_max_thinking_tokens: int = 1024
    
    complex_model: str
    complex_model_provider: str
    complex_max_tokens: int = DEFAULT_COMPLEX_MAX_TOKENS
    complex_enable_thinking: bool = False
    complex_max_thinking_tokens: int = 1024
    
    generator_model: Optional[str] = ""
    generator_model_provider: Optional[str] = "openai"
    generator_max_tokens: int = DEFAULT_GENERATOR_MAX_TOKENS
    generator_enable_thinking: bool = False
    generator_max_thinking_tokens: int = 1024

    play_agent_model: Optional[str] = ""
    play_agent_model_provider: Optional[str] = "openai"
    
    preferred_provider: str # Legacy
    ollama_url: Optional[str] = None

class T2ISettingsPayload(BaseModel):
    simple_model: str
    simple_model_provider: str
    advanced_model: str
    advanced_model_provider: str
    provider: str # Legacy
    ollama_url: Optional[str] = None
    stable_diffusion_url: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    steps: Optional[int] = None
    cfg_scale: Optional[float] = None
    simple_steps: Optional[int] = None
    simple_cfg_scale: Optional[float] = None
    advanced_steps: Optional[int] = None
    advanced_cfg_scale: Optional[float] = None
    simple_sampler_name: Optional[str] = None
    simple_scheduler: Optional[str] = None
    advanced_sampler_name: Optional[str] = None
    advanced_scheduler: Optional[str] = None
    simple_min_long_edge: Optional[int] = None
    advanced_min_long_edge: Optional[int] = None
    seed: Optional[int] = None
    image_format: Optional[str] = "jpeg"
    image_quality: Optional[int] = 85
    negative_prompt: Optional[str] = None
    scene_model_quality: Optional[str] = "advanced"
    profile_model_quality: Optional[str] = "advanced"
    protagonist_model_quality: Optional[str] = "advanced"
    asset_model_quality: Optional[str] = "simple"
class GameSettingsPayload(BaseModel):
    clock_24h: bool = False
    date_format: str = "DD.MM.YY"


class TTSSettingsPayload(BaseModel):
    enabled: bool = False
    provider: str = "google"
    selected_model: str = "gemini-3.1-flash-tts-preview"
    selected_voice: str = "Puck"
    elevenlabs_voice_id: str = ""
    use_vocal_tags: bool = True
    use_text_chunking: bool = True
    voice_list: list[str] = Field(default_factory=list)
    voice_catalog: list[dict[str, Optional[str]]] = None
    sample_context: str = ""
    speech_rate: float = 1.0


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
async def get_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns the current settings (sanitized keys)."""
    user = await _resolve_global_settings_owner(db, current_user)
    
    # Common defaults if no user/settings
    default_llm = _normalize_llm_settings(None)
    default_t2i = _normalize_t2i_settings(None)
    default_available_constants = await _build_available_constants(default_llm, default_t2i)
    
    def get_keys_status(db_keys):
        status = {}
        all_providers = {p["id"] for p in LLM_PROVIDERS} | {p["id"] for p in IMAGE_PROVIDERS} | {p["id"] for p in TTS_PROVIDERS}
        for p in all_providers:
            # Check environment first
            if settings.get_env_api_key(p):
                status[p] = {"masked": "********", "is_env": True}
            elif db_keys and p in db_keys:
                status[p] = {"masked": "********", "is_env": False}
        return status

    if not user:
        return {
            "app_version": settings.APP_VERSION,
            "keys": get_keys_status({}),
            "llm_settings": default_llm,
            "t2i_settings": default_t2i,
            "is_llm_configured": False,
            "is_t2i_configured": False,
            "image_styles_catalog": _default_image_styles_catalog(),
            "tone_catalog": _default_tone_catalog(),
            "game_settings": {
                "clock_24h": False,
                "date_format": "DD.MM.YY"
            },
            "available_constants": {
                **default_available_constants,
            }
        }

    normalized_llm_settings = _normalize_llm_settings(user.llm_settings)
    available_constants = await _build_available_constants(normalized_llm_settings, user.t2i_settings)
    
    return {
        "app_version": settings.APP_VERSION,
        "keys": get_keys_status(user.encrypted_api_keys),
        "llm_settings": normalized_llm_settings,
        "t2i_settings": _normalize_t2i_settings(user.t2i_settings),
        "is_llm_configured": _is_llm_configured(user, user.encrypted_api_keys),
        "is_t2i_configured": _is_t2i_configured(user, user.encrypted_api_keys),
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
        "tts_settings": _normalize_tts_settings(user.tts_settings),
        "available_constants": available_constants,
    }


@router.get("/ollama-models")
async def get_ollama_models(ollama_url: Optional[str] = None):
    """Return installed Ollama model names for the configured Ollama endpoint."""
    return {"models": await _fetch_ollama_models(ollama_url)}

@router.get("/stable-diffusion-models")
async def get_stable_diffusion_models(stable_diffusion_url: Optional[str] = None):
    """Return available Stable Diffusion checkpoints for the configured endpoint."""
    return {"models": await _fetch_stable_diffusion_models(stable_diffusion_url)}

@router.post("/keys")
async def update_api_key(
    payload: ApiKeyPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """Saves an encrypted API key for the authenticated user."""
    provider_lower = payload.provider.lower()
    
    # Block updates for environment-configured keys
    if settings.get_env_api_key(provider_lower):
        raise HTTPException(
            status_code=403, 
            detail=f"The API key for {payload.provider} is managed via environment variables and cannot be modified here."
        )

    user = await _resolve_global_settings_owner(db, current_user)

    normalized_api_key = (payload.api_key or "").strip()
    if (
        len(normalized_api_key) >= 2
        and normalized_api_key[0] == normalized_api_key[-1]
        and normalized_api_key[0] in {'"', "'"}
    ):
        normalized_api_key = normalized_api_key[1:-1].strip()

    if not normalized_api_key:
        raise HTTPException(status_code=400, detail="API key cannot be empty.")

    encrypted_key = encryption_util.encrypt_key(normalized_api_key)
    
    current_keys = user.encrypted_api_keys or {}
    new_keys = dict(current_keys)
    new_keys[provider_lower] = encrypted_key
    user.encrypted_api_keys = new_keys

    await _broadcast_global_settings(db, user)
    await db.commit()
    return {"status": "success", "message": f"{payload.provider} key saved securely."}

@router.delete("/keys/{provider}")
async def delete_api_key(
    provider: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """Deletes an encrypted API key for the authenticated user."""
    provider_lower = provider.lower()
    logger.info("[Admin] Deleting API key for provider: %s (lower: %s)", provider, provider_lower)
    
    # Block deletion for environment-configured keys
    if settings.get_env_api_key(provider_lower):
        logger.warning("[Admin] Blocked deletion of env key: %s", provider_lower)
        raise HTTPException(
            status_code=403, 
            detail=f"The API key for {provider} is managed via environment variables and cannot be deleted here."
        )

    user = await _resolve_global_settings_owner(db, current_user)
    logger.info("[Admin] Settings owner resolved for delete operation")
    
    current_keys = user.encrypted_api_keys or {}
    logger.info("[Admin] Current API key count in DB: %d", len(current_keys))
    
    if provider_lower not in current_keys:
        logger.error("[Admin] Key not found for provider: %s", provider_lower)
        raise HTTPException(status_code=404, detail=f"No key found for {provider}.")

    new_keys = dict(current_keys)
    del new_keys[provider_lower]
    user.encrypted_api_keys = new_keys

    await _broadcast_global_settings(db, user)
    await db.commit()
    logger.info("[Admin] Successfully removed key for %s", provider_lower)
    return {"status": "success", "message": f"{provider} key removed."}

@router.post("/llm")
async def update_llm_settings(
    payload: SettingsPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """Updates the LLM model preferences."""
    user = await _resolve_global_settings_owner(db, current_user)
        
    user.llm_settings = _normalize_llm_settings(payload.model_dump())
    await _broadcast_global_settings(db, user)
    await db.commit()
    return {"status": "success", "message": "LLM settings updated."}

@router.post("/t2i")
async def update_t2i_settings(
    payload: T2ISettingsPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """Updates the Text-to-Image model preferences."""
    user = await _resolve_global_settings_owner(db, current_user)
        
    user.t2i_settings = _normalize_t2i_settings(payload.model_dump())
    await _broadcast_global_settings(db, user)
    await db.commit()
    return {"status": "success", "message": "Image generation settings updated."}


@router.post("/tts")
async def update_tts_settings(
    payload: TTSSettingsPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """Updates the TTS settings."""
    user = await _resolve_global_settings_owner(db, current_user)

    # Use full model dump to capture all fields from the UI, then normalize.
    user.tts_settings = _normalize_tts_settings(payload.model_dump())
    
    await _broadcast_global_settings(db, user)
    await db.commit()
    return {"status": "success", "message": "TTS settings updated."}


class TestLLMPayload(BaseModel):
    model: str
    provider: str
    ollama_url: Optional[str] = None

@router.post("/test-llm")
async def test_llm_connection(
    payload: TestLLMPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Tests the connection to an LLM provider with a simple prompt and measures latency."""
    user = await _resolve_global_settings_owner(db, current_user)

    # Inject temporary ollama_url if provided
    if payload.provider == "ollama" and payload.ollama_url:
        old_settings = user.llm_settings or {}
        user.llm_settings = {**old_settings, "ollama_url": payload.ollama_url}

    import time
    try:
        gm = GameMasterLLM(user, provider=payload.provider)
        start_time = time.perf_counter()
        response = await gm.aexecute_simple_task(
            system_prompt="You are a helpful RPG assistant.",
            user_prompt="Say 'TaleWeaver connection test successful!' in a fantasy style.",
            model=payload.model
        )
        end_time = time.perf_counter()
        latency = round(end_time - start_time, 2)
        return {"status": "success", "message": response, "response_time": latency}
    except (ValueError, RuntimeError, TypeError) as exc:
        return _route_error_response(
            "LLM connection test",
            "Connection test failed. Check provider settings and server logs.",
            exc,
        )

class TestVisionPayload(BaseModel):
    model: str
    provider: str
    ollama_url: Optional[str] = None
    stable_diffusion_url: Optional[str] = None
    steps: Optional[int] = None
    cfg_scale: Optional[float] = None
    sampler_name: Optional[str] = None
    scheduler: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    min_long_edge: Optional[int] = None

@router.post("/test-vision")
async def test_vision_connection(
    payload: TestVisionPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Tests the connection to an image provider by generating a wizard portrait."""
    user = await _resolve_global_settings_owner(db, current_user)
    provider_key = payload.provider.lower()
    
    api_key = None
    if provider_key not in ("ollama", "stable_diffusion"):
        api_key = settings.get_env_api_key(provider_key)
        if not api_key:
            if not user.encrypted_api_keys or provider_key not in user.encrypted_api_keys:
                return {"status": "error", "message": f"No API key for {payload.provider}"}
            api_key = encryption_util.decrypt_key(user.encrypted_api_keys[provider_key])

    try:
        test_dir = _safe_data_path("scratch", "test_connection")
        os.makedirs(test_dir, exist_ok=True)
        provider_options = {}
        if payload.ollama_url:
            provider_options["ollama_url"] = payload.ollama_url
        if payload.stable_diffusion_url:
            provider_options["stable_diffusion_url"] = payload.stable_diffusion_url
        if payload.steps is not None:
            provider_options["steps"] = payload.steps
        if payload.cfg_scale is not None:
            provider_options["cfg_scale"] = payload.cfg_scale
        if payload.sampler_name:
            provider_options["sampler_name"] = payload.sampler_name
        if payload.scheduler:
            provider_options["scheduler"] = payload.scheduler
        
        # Test vision generates a wizard portrait (CHARACTER/4:5 aspect ratio)
        if provider_key in ("stable_diffusion", "ollama"):
            min_long_edge = payload.min_long_edge or 1024
            if not payload.width and not payload.height:
                width, height = MediaEngine._resolve_sd_dimensions("CHARACTER", min_long_edge)
                provider_options["width"] = width
                provider_options["height"] = height
            else:
                if payload.width is not None:
                    provider_options["width"] = payload.width
                if payload.height is not None:
                    provider_options["height"] = payload.height
        else:
            if payload.width is not None:
                provider_options["width"] = payload.width
            if payload.height is not None:
                provider_options["height"] = payload.height
        
        img_url = await MediaEngine.generate_image(
            prompt="A Wizard portrait",
            model=payload.model,
            api_key=api_key,
            provider=payload.provider,
            target_dir=test_dir,
            provider_options=provider_options
        )
        if img_url:
            return {"status": "success", "message": "Image generation successful!", "image_url": img_url}
        else:
            return {"status": "error", "message": "Image generation failed."}
    except (ValueError, RuntimeError, TypeError) as exc:
        return _route_error_response(
            "Vision connection test",
            "Image connection test failed. Check provider settings and server logs.",
            exc,
        )

@router.post("/test-tts")
async def test_tts_connection(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generates a short test sentence to verify TTS configuration."""
    user = await _resolve_global_settings_owner(db, current_user)
    tts_settings = user.tts_settings or {}
    
    provider = tts_settings.get("provider", "google").lower()
    api_key = settings.get_env_api_key(provider)
    if not api_key and user.encrypted_api_keys:
        enc_key = user.encrypted_api_keys.get(provider)
        if enc_key:
            api_key = encryption_util.decrypt_key(enc_key)

    if not api_key:
        raise HTTPException(status_code=400, detail=f"{provider.capitalize()} API Key not configured for TTS.")

    test_text = "Tale Weaver connection test successful! The journey begins now."
    
    try:
        audio_url = await TTSEngine.generate_speech(
            text=test_text,
            provider=provider,
            voice=tts_settings.get("selected_voice", "Puck"),
            elevenlabs_voice_id=tts_settings.get("elevenlabs_voice_id", ""),
            use_vocal_tags=tts_settings.get("use_vocal_tags", True),
            api_key=api_key,
            model_name=tts_settings.get("selected_model", "gemini-3.1-flash-tts-preview"),
        )
        if not audio_url:
            return {"status": "error", "message": "Failed to generate test audio."}
        return {"status": "success", "audio_url": audio_url}
    except (ValueError, RuntimeError, TypeError) as exc:
        return _route_error_response(
            "TTS connection test",
            "TTS connection test failed. Check provider settings and server logs.",
            exc,
        )


@router.post("/image-styles")
async def update_image_styles_catalog(
    payload: CatalogUpdatePayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """Updates the admin-managed image styles catalog for adventure generation."""
    user = await _resolve_global_settings_owner(db, current_user)

    raw_items = [item.model_dump() for item in payload.items]
    user.image_styles_catalog = _normalize_catalog(raw_items, fallback=_default_image_styles_catalog())
    await _broadcast_global_settings(db, user)
    await db.commit()
    return {"status": "success", "message": "Image styles catalog updated."}


@router.post("/tones")
async def update_tone_catalog(
    payload: CatalogUpdatePayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """Updates the admin-managed tone catalog for world generation."""
    user = await _resolve_global_settings_owner(db, current_user)

    raw_items = [item.model_dump() for item in payload.items]
    user.tone_catalog = _normalize_catalog(raw_items, fallback=_default_tone_catalog())
    await _broadcast_global_settings(db, user)
    await db.commit()
    return {"status": "success", "message": "Tone catalog updated."}


@router.post("/catalog/generate")
async def generate_catalog_image(
    payload: CatalogGeneratePayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generates an image for a catalog tile (style or tone)."""
    user = await _resolve_global_settings_owner(db, current_user)

    t2i = user.t2i_settings or {}
    provider = (t2i.get("simple_model_provider") or t2i.get("provider", "openai")).lower()
    model = t2i.get("simple_model")
    
    if not model:
        return {"status": "error", "message": "The 'Simple Model' for image generation is not configured. Please set it in Visual Preferences."}
        
    api_key = _resolve_provider_api_key(provider, user.encrypted_api_keys)
    if provider not in ("ollama", "stable_diffusion") and not api_key:
        return {"status": "error", "message": f"No API key for {provider}"}

    try:
        catalog_type = _sanitize_path_component(payload.catalog_type)
        if catalog_type not in _ALLOWED_CATALOG_TYPES:
            return {"status": "error", "message": "Invalid catalog type."}

        catalog_dir = _safe_data_path("catalog", catalog_type)
        os.makedirs(catalog_dir, exist_ok=True)
        
        base_prompt = payload.prompt
        if not base_prompt:
            item_name = payload.name or payload.target_id.replace('-', ' ')
            base_prompt = f"A visual representation of the visual style '{item_name}'."
            if payload.description:
                base_prompt += f" Context: {payload.description}"
            base_prompt += " High quality, professional digital art, no text."

        safe_target_id = _slugify(payload.target_id)

        img_url = await MediaEngine.generate_image(
            prompt=base_prompt,
            model=model,
            api_key=api_key,
            provider=provider,
            target_dir=catalog_dir,
            filename=f"{safe_target_id}_{uuid.uuid4().hex[:8]}",
            provider_options=t2i
        )
        
        logger.info("Catalog generate result for '%s': img_url=%r", payload.target_id, img_url)
        if img_url:
            return {"status": "success", "image_url": img_url}
        else:
            return {"status": "error", "message": "Generation failed: The provider returned no image data. Check your API logs or model configuration."}
    except (ValueError, RuntimeError, TypeError) as exc:
        return _route_error_response(
            "Catalog image generation",
            "Generation failed. Check provider settings and server logs.",
            exc,
        )


@router.post("/catalog/upload")
async def upload_catalog_image(
    catalog_type: str = Form(...), 
    target_id: str = Form(...), 
    file: UploadFile = File(...), 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Uploads a manual image for a catalog tile."""
    _ = db
    _ = current_user
    try:
        filepath = _build_catalog_upload_path(catalog_type, target_id, file.filename)
        
        with open(filepath, "wb") as f:
            f.write(await file.read())
            
        rel_path = os.path.relpath(filepath, settings.DATA_DIR).replace("\\", "/")
        return {"status": "success", "image_url": f"/data/{rel_path}"}
    except (ValueError, RuntimeError, TypeError) as exc:
        return _route_error_response(
            "Catalog image upload",
            "Upload failed. Verify the catalog type and file, then try again.",
            exc,
        )


@router.post("/game")
async def update_game_settings(
    payload: GameSettingsPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """Updates the general game preferences."""
    user = await _resolve_global_settings_owner(db, current_user)
        
    user.game_settings = payload.model_dump()
    await _broadcast_global_settings(db, user)
    await db.commit()
    return {"status": "success", "message": "Game settings updated."}

@router.get("/tts/elevenlabs-models")
async def get_elevenlabs_models():
    """Returns a list of available ElevenLabs models from central config."""
    models = PREDEFINED_TTS_MODELS.get("elevenlabs", [])
    # Return in the format expected by frontend: {model_id, name}
    return [{"model_id": m["id"], "name": m["name"]} for m in models]

