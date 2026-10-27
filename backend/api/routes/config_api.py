import logging
import os
import re
import time
import uuid
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.settings_normalization import (
    DEFAULT_COMPLEX_MAX_TOKENS,
    DEFAULT_GENERATOR_MAX_TOKENS,
    DEFAULT_SMALL_MAX_TOKENS,
    TTS_MODEL_ALIASES,
)
from backend.api.routes.settings_normalization import (
    normalize_llm_settings as _normalize_llm_settings,
)
from backend.api.routes.settings_normalization import (
    normalize_t2i_settings as _normalize_t2i_settings,
)
from backend.api.routes.settings_normalization import (
    normalize_tts_settings as _normalize_tts_settings,
)
from backend.core.auth import get_current_admin, get_current_user
from backend.core.catalog_defaults import DEFAULT_IMAGE_STYLES, DEFAULT_TONES
from backend.core.config import settings
from backend.core.custom_openai_diagnostics import connection_test_diagnostic
from backend.core.database import get_db
from backend.core.error_diagnostics import diagnose_provider_error
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
from backend.engine.media_engine import MediaEngine
from backend.engine.tts_engine import TTSEngine, TTSModelSwitchSuggestionError
from backend.models.user import User
from backend.services.model_discovery import clear_cache as clear_model_discovery_cache
from backend.utils.path_security import (
    ensure_within_base_dir,
    ensure_within_data_dir,
    safe_data_path,
    sanitize_path_component,
    validate_provider_url,
)

logger = logging.getLogger(__name__)

_MODEL_FETCH_LOG_COOLDOWN_SECONDS = 300.0
_MODEL_FETCH_LAST_LOGGED_AT: dict[str, float] = {}

router = APIRouter(prefix="/settings", tags=["Settings"])
print(f"DEBUG: Loading config_api module, router prefix: {router.prefix}")

_SAFE_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
_ALLOWED_CATALOG_TYPES = {"styles", "tones"}
_CATALOG_EXT_BY_CONTENT_TYPE = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
}


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
            tts_settings=dict(source_user.tts_settings or {}),
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
    return sanitize_path_component(value)


def _ensure_within_data_dir(path: str) -> str:
    """Validate that path resolves inside DATA_DIR and return absolute path."""
    return ensure_within_data_dir(path)


def _safe_data_path(*parts: str) -> str:
    """Build a safe path rooted at DATA_DIR."""
    return safe_data_path(*parts)


def _sanitize_image_extension(filename: Optional[str]) -> str:
    """Return a safe image extension with png fallback."""
    if not filename or "." not in filename:
        return "png"
    ext = filename.rsplit(".", 1)[-1].strip().lower()
    return ext if ext in _SAFE_IMAGE_EXTENSIONS else "png"


def _extension_from_content_type(content_type: Optional[str]) -> str:
    """Resolve a safe image extension from content type with png fallback."""
    return _CATALOG_EXT_BY_CONTENT_TYPE.get((content_type or "").strip().lower(), "png")


def _route_error_response(operation: str, message: str, exc: Exception) -> dict[str, str]:
    """Log internal exception details while returning a generic client-safe message."""
    logger.exception("%s failed", operation, exc_info=exc)
    return {"status": "error", "message": message}


def _canonical_catalog_type(value: str) -> Optional[str]:
    """Return a canonical catalog type literal, or None when invalid."""
    cleaned = _sanitize_path_component(value)
    for allowed in ("styles", "tones"):
        if cleaned == allowed:
            return allowed
    return None


def _build_catalog_upload_path(
    catalog_type: str, target_id: str, original_filename: Optional[str]
) -> str:
    """Create a validated file path for uploaded catalog images."""
    safe_catalog_type = _canonical_catalog_type(catalog_type)
    if not safe_catalog_type:
        raise ValueError("Invalid catalog type.")

    catalog_dir = _safe_data_path("catalog", safe_catalog_type)
    os.makedirs(catalog_dir, exist_ok=True)

    ext = _sanitize_image_extension(original_filename)
    safe_target_id = _sanitize_filename_component(target_id)
    if not safe_target_id:
        raise ValueError("Invalid target id.")
    filename = f"{safe_target_id}_{uuid.uuid4().hex[:8]}.{ext}"
    return _ensure_within_data_dir(os.path.join(catalog_dir, filename))


def _default_image_styles_catalog() -> list[dict[str, Any]]:
    return [dict(item) for item in DEFAULT_IMAGE_STYLES]


def _default_tone_catalog() -> list[dict[str, Any]]:
    return [dict(item) for item in DEFAULT_TONES]


def _normalize_catalog(
    catalog: list[dict[str, Optional[Any]]], *, fallback: list[dict[str, Any]]
) -> list[dict[str, Any]]:
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


async def _fetch_ollama_models(ollama_url: Optional[str]) -> list[str]:
    """Return installed Ollama model names from the local Ollama daemon."""
    base_url = (ollama_url or "http://localhost:11434").rstrip("/")
    endpoint = f"{base_url}/api/tags"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
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
        _log_model_fetch_failure_once_per_interval("ollama", endpoint)
        return []


async def _fetch_stable_diffusion_models(stable_diffusion_url: Optional[str]) -> list[str]:
    """Return available Stable Diffusion model checkpoints from local Automatic1111/Forge daemon."""
    base_url = (stable_diffusion_url or "http://127.0.0.1:7860").rstrip("/")
    endpoint = f"{base_url}/sdapi/v1/sd-models"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
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
        _log_model_fetch_failure_once_per_interval("stable_diffusion", endpoint)
        return ["default"]


def _parse_model_ids(payload: Any, dict_item_keys: tuple[str, ...]) -> list[str]:
    """Extracts model ids from `{"data": [...]}` or plain list payloads."""
    if isinstance(payload, dict):
        items, keys = payload.get("data") or [], dict_item_keys
    elif isinstance(payload, list):
        items, keys = payload, ("id", "name")
    else:
        return []
    model_ids = (
        str(next((item.get(k) for k in keys if item.get(k)), "") or "").strip()
        for item in items
        if isinstance(item, dict)
    )
    return sorted({model_id for model_id in model_ids if model_id})


async def _fetch_bearer_models(
    provider: str, endpoint: str, api_key: str, dict_item_keys: tuple[str, ...]
) -> list[str]:
    """GETs a /models endpoint with bearer auth; returns [] (logged) on failure."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(endpoint, headers={"Authorization": f"Bearer {api_key}"})
        response.raise_for_status()
        return _parse_model_ids(response.json(), dict_item_keys)
    except (httpx.HTTPError, ValueError, TypeError):
        _log_model_fetch_failure_once_per_interval(provider, endpoint)
        return []


async def _fetch_minimax_models(
    api_key: Optional[str], api_base: Optional[str] = None
) -> list[str]:
    """Return available model names from MiniMax API."""
    if not api_key:
        _log_model_fetch_failure_once_per_interval("minimax", "https://api.minimax.chat/v1")
        return []

    base_url = (api_base or "https://api.minimax.chat/v1").rstrip("/")
    return await _fetch_bearer_models("minimax", f"{base_url}/models", api_key, ("id",))


_OPENAI_COMPATIBLE_PROVIDERS = {
    "openai": {"default_base": "https://api.openai.com/v1", "env_key": "OPENAI_API_KEY"},
    "anthropic": {"default_base": "https://api.anthropic.com/v1", "env_key": "ANTHROPIC_API_KEY"},
    "google": {
        "default_base": "https://generativelanguage.googleapis.com/v1beta",
        "env_key": "GOOGLE_API_KEY",
    },
    "openrouter": {"default_base": "https://openrouter.ai/api/v1", "env_key": "OPENROUTER_API_KEY"},
    "deepseek": {"default_base": "https://api.deepseek.com/v1", "env_key": "DEEPSEEK_API_KEY"},
    "kimi": {"default_base": "https://api.moonshot.ai/v1", "env_key": "KIMI_API_KEY"},
}


async def _fetch_openai_compatible_models(
    provider: str,
    api_key: Optional[str],
    api_base: Optional[str] = None,
) -> list[str]:
    """Return model names from any OpenAI-compatible /v1/models endpoint."""
    if provider not in _OPENAI_COMPATIBLE_PROVIDERS:
        return []
    default_base = _OPENAI_COMPATIBLE_PROVIDERS[provider]["default_base"]
    if not api_key:
        _log_model_fetch_failure_once_per_interval(provider, default_base)
        return []

    base_url = (api_base or default_base).rstrip("/")
    return await _fetch_bearer_models(provider, f"{base_url}/models", api_key, ("id", "name"))


def _safe_provider_url(url: Optional[str], *, default: Optional[str] = None) -> str:
    """Validate a user-supplied provider URL with a sensible default fallback.

    Raises HTTPException(400) on SSRF rejection or invalid format.
    """
    candidate = (url or default or "").strip()
    try:
        return validate_provider_url(candidate)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _log_model_fetch_failure_once_per_interval(provider: str, endpoint: str) -> None:
    """Rate-limit model-fetch failure logs to avoid flooding app logs while polling settings."""
    now = time.monotonic()
    last_logged = _MODEL_FETCH_LAST_LOGGED_AT.get(provider)
    if last_logged is not None and (now - last_logged) < _MODEL_FETCH_LOG_COOLDOWN_SECONDS:
        return

    _MODEL_FETCH_LAST_LOGGED_AT[provider] = now
    logger.info(
        "Could not fetch %s models from %s (suppressing repeated messages for %.0fs)",
        "Stable Diffusion" if provider == "stable_diffusion" else "Ollama",
        endpoint,
        _MODEL_FETCH_LOG_COOLDOWN_SECONDS,
    )


async def _build_available_constants(
    llm_settings: Optional[dict], t2i_settings: Optional[dict] = None
) -> dict[str, Any]:
    """Return available providers and model catalogs for the admin UI."""
    normalized_llm = _normalize_llm_settings(llm_settings)

    def _uses_ollama_llm(settings_payload: dict[str, Any]) -> bool:
        provider_fields = (
            "small_model_provider",
            "complex_model_provider",
            "generator_model_provider",
            "play_agent_model_provider",
            "compression_model_provider",
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
    uses_stable_diffusion = (
        normalized_t2i.get("simple_model_provider") == "stable_diffusion"
        or normalized_t2i.get("advanced_model_provider") == "stable_diffusion"
    )
    if uses_stable_diffusion:
        sd_models = await _fetch_stable_diffusion_models(normalized_t2i.get("stable_diffusion_url"))
    else:
        sd_models = ["default"]

    predefined_image_models = dict(PREDEFINED_IMAGE_MODELS)
    predefined_image_models["stable_diffusion"] = sd_models

    return {
        "llm_providers": LLM_PROVIDERS,
        "image_providers": IMAGE_PROVIDERS,
        "tts_providers": TTS_PROVIDERS,
        "predefined_llm_models": predefined_llm_models,
        "predefined_image_models": predefined_image_models,
    }


def _normalize_game_settings(game_settings: Optional[dict]) -> dict:
    fallback = {
        "clock_24h": False,
        "date_format": "DD.MM.YY",
        "whisper_model": "tiny",
    }
    if not game_settings:
        return fallback
    normalized = dict(game_settings)
    if "clock_24h" not in normalized:
        normalized["clock_24h"] = False
    if "date_format" not in normalized:
        normalized["date_format"] = "DD.MM.YY"
    if "whisper_model" not in normalized:
        normalized["whisper_model"] = "tiny"
    return normalized


def _is_llm_configured(user: User, db_keys: dict) -> bool:
    llm = _normalize_llm_settings(user.llm_settings)
    small_provider = llm.get("small_model_provider", "openai")
    complex_provider = llm.get("complex_model_provider", "openai")
    small_model = llm.get("small_model")
    complex_model = llm.get("complex_model")

    def has_key(provider):
        if provider == "custom_openai":
            return bool(llm.get("custom_openai_url"))
        if provider == "ollama":
            return True
        return bool(settings.get_env_api_key(provider)) or (db_keys and provider in db_keys)

    return all(
        [has_key(small_provider), bool(small_model), has_key(complex_provider), bool(complex_model)]
    )


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
    small_openrouter_provider: Optional[str] = ""

    complex_model: str
    complex_model_provider: str
    complex_max_tokens: int = DEFAULT_COMPLEX_MAX_TOKENS
    complex_enable_thinking: bool = False
    complex_max_thinking_tokens: int = 1024
    complex_openrouter_provider: Optional[str] = ""

    generator_model: Optional[str] = ""
    generator_model_provider: Optional[str] = "openai"
    generator_max_tokens: int = DEFAULT_GENERATOR_MAX_TOKENS
    generator_enable_thinking: bool = False
    generator_max_thinking_tokens: int = 1024
    generator_openrouter_provider: Optional[str] = ""

    play_agent_model: Optional[str] = ""
    play_agent_model_provider: Optional[str] = "openai"
    play_agent_monkey_mode: bool = False
    play_agent_allow_walkthrough: bool = True
    play_agent_step_by_step: bool = False
    play_agent_openrouter_provider: Optional[str] = ""
    play_agent_personality: Optional[str] = "casual"
    play_agent_custom_personality: Optional[str] = ""

    compression_model: Optional[str] = ""
    compression_model_provider: Optional[str] = "openai"
    compression_max_tokens: int = 4096
    compression_openrouter_provider: Optional[str] = ""

    turns_before_compacting: int = 10
    enable_history_compression: bool = True

    preferred_provider: str  # Legacy
    openrouter_provider: Optional[str] = ""
    ollama_url: Optional[str] = None
    minimax_url: Optional[str] = None
    custom_openai_url: str = ""
    custom_openai_timeout: int = Field(default=300, ge=1, le=3600)
    custom_openai_response_format: str = Field(
        default="prompt", pattern="^(prompt|json_object|json_schema)$"
    )


class T2ISettingsPayload(BaseModel):
    simple_model: str
    simple_model_provider: str
    advanced_model: str
    advanced_model_provider: str
    provider: str  # Legacy
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
    whisper_model: str = "tiny"


class TTSSettingsPayload(BaseModel):
    enabled: bool = False
    provider: str = "google"
    selected_model: str = "gemini-3.8-flash-tts"
    selected_voice: str = "Puck"
    elevenlabs_voice_id: str = ""
    use_vocal_tags: bool = True
    use_streaming: bool = False
    auto_speak: bool = True
    voice_list: list[str] = Field(default_factory=list)
    voice_catalog: list[dict[str, Optional[str]]] = None
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
    include_available_constants: bool = True,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns the current settings (sanitized keys)."""
    user = await _resolve_global_settings_owner(db, current_user)

    # Common defaults if no user/settings
    default_llm = _normalize_llm_settings(None)
    default_t2i = _normalize_t2i_settings(None)
    default_available_constants = (
        await _build_available_constants(default_llm, default_t2i)
        if include_available_constants
        else {
            "llm_providers": LLM_PROVIDERS,
            "image_providers": IMAGE_PROVIDERS,
            "tts_providers": TTS_PROVIDERS,
            "predefined_llm_models": dict(PREDEFINED_LLM_MODELS),
            "predefined_image_models": dict(PREDEFINED_IMAGE_MODELS),
        }
    )

    def get_keys_status(db_keys):
        status = {}
        all_providers = (
            {p["id"] for p in LLM_PROVIDERS}
            | {p["id"] for p in IMAGE_PROVIDERS}
            | {p["id"] for p in TTS_PROVIDERS}
        )
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
            "game_settings": _normalize_game_settings(None),
            "available_constants": {
                **default_available_constants,
            },
        }

    normalized_llm_settings = _normalize_llm_settings(user.llm_settings)
    available_constants = (
        await _build_available_constants(normalized_llm_settings, user.t2i_settings)
        if include_available_constants
        else {
            "llm_providers": LLM_PROVIDERS,
            "image_providers": IMAGE_PROVIDERS,
            "tts_providers": TTS_PROVIDERS,
            "predefined_llm_models": dict(PREDEFINED_LLM_MODELS),
            "predefined_image_models": dict(PREDEFINED_IMAGE_MODELS),
        }
    )

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
        "game_settings": _normalize_game_settings(user.game_settings),
        "tts_settings": _normalize_tts_settings(user.tts_settings),
        "available_constants": available_constants,
    }


@router.get("/ollama-models")
async def get_ollama_models(
    ollama_url: Optional[str] = None,
    _user: User = Depends(get_current_user),
):
    """Return installed Ollama model names for the configured Ollama endpoint.

    Requires authentication. ``ollama_url`` is validated against SSRF
    (loopback/RFC1918 rejected unless ALLOW_PRIVATE_NETWORK_MODELS=true).
    """
    validated_url = _safe_provider_url(ollama_url, default="http://localhost:11434")
    return {"models": await _fetch_ollama_models(validated_url)}


@router.get("/stable-diffusion-models")
async def get_stable_diffusion_models(
    stable_diffusion_url: Optional[str] = None,
    _user: User = Depends(get_current_user),
):
    """Return available Stable Diffusion checkpoints for the configured endpoint.

    Requires authentication. ``stable_diffusion_url`` is validated against SSRF.
    """
    validated_url = _safe_provider_url(stable_diffusion_url, default="http://127.0.0.1:7860")
    return {"models": await _fetch_stable_diffusion_models(validated_url)}


@router.get("/minimax-models")
async def get_minimax_models(
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return available MiniMax model names for the configured endpoint."""
    if not api_key:
        user = await _resolve_global_settings_owner(db, current_user)
        if user and user.encrypted_api_keys and "minimax" in user.encrypted_api_keys:
            from backend.core.security import encryption_util

            api_key = encryption_util.decrypt_key(user.encrypted_api_keys["minimax"])
        elif settings.MINIMAX_API_KEY:
            api_key = settings.MINIMAX_API_KEY

    try:
        validated_base = validate_provider_url(api_base or settings.MINIMAX_API_BASE)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"models": await _fetch_minimax_models(api_key, validated_base)}


async def _resolve_provider_api_key_for_models(
    db: AsyncSession, current_user: User, provider: str
) -> Optional[str]:
    """Return the best available API key for a provider (user DB first, then env)."""
    user = await _resolve_global_settings_owner(db, current_user)
    if user and user.encrypted_api_keys and provider in user.encrypted_api_keys:
        from backend.core.security import encryption_util

        try:
            return encryption_util.decrypt_key(user.encrypted_api_keys[provider])
        except (ValueError, TypeError, KeyError):
            logger.error("Failed to decrypt API key for provider '%s'", provider)
    return settings.get_env_api_key(provider)


@router.get("/llm-models")
async def get_llm_models(
    provider: str,
    api_base: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return available model names for any OpenAI-compatible LLM provider."""
    provider_lower = provider.lower()
    if provider_lower == "custom_openai":
        from backend.core.custom_openai import discover_models

        if current_user.role != "admin":
            raise HTTPException(status_code=403, detail="Administrator access required.")
        user = await _resolve_global_settings_owner(db, current_user)
        base = api_base or (user.llm_settings or {}).get("custom_openai_url", "")
        key = await _resolve_provider_api_key_for_models(db, current_user, "custom_openai")
        return {"models": await discover_models(base, key)}
    if provider_lower == "minimax":
        api_key = await _resolve_provider_api_key_for_models(db, current_user, "minimax")
        try:
            validated_base = validate_provider_url(api_base or settings.MINIMAX_API_BASE)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        models = await _fetch_minimax_models(api_key, validated_base)
    elif provider_lower in _OPENAI_COMPATIBLE_PROVIDERS:
        api_key = await _resolve_provider_api_key_for_models(db, current_user, provider_lower)
        default_base = _OPENAI_COMPATIBLE_PROVIDERS[provider_lower]["default_base"]
        try:
            validated_base = validate_provider_url(api_base or default_base)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        models = await _fetch_openai_compatible_models(provider_lower, api_key, validated_base)
    else:
        raise HTTPException(
            status_code=400, detail=f"Model discovery not supported for provider '{provider}'."
        )
    return {"models": models}


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
            detail=f"The API key for {payload.provider} is managed via environment variables and cannot be modified here.",
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
    clear_model_discovery_cache()
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
            detail=f"The API key for {provider} is managed via environment variables and cannot be deleted here.",
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
    clear_model_discovery_cache()
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

    from backend.core.custom_openai import validate_custom_url

    if payload.custom_openai_url:
        payload.custom_openai_url = validate_custom_url(payload.custom_openai_url)
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
    openrouter_provider: Optional[str] = None


@router.post("/test-llm")
async def test_llm_connection(
    payload: TestLLMPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Tests the connection to an LLM provider with a simple prompt and measures latency."""
    user = await _resolve_global_settings_owner(db, current_user)

    # Inject temporary ollama_url or openrouter_provider if provided
    old_settings = user.llm_settings or {}
    temp_settings = dict(old_settings)
    if payload.provider == "ollama" and payload.ollama_url:
        temp_settings["ollama_url"] = payload.ollama_url
    if payload.provider == "openrouter" and payload.openrouter_provider is not None:
        temp_settings["small_openrouter_provider"] = payload.openrouter_provider
        temp_settings["complex_openrouter_provider"] = payload.openrouter_provider
        temp_settings["openrouter_provider"] = payload.openrouter_provider
    user.llm_settings = temp_settings

    import time

    test_stage = "configuration"
    try:
        gm = GameMasterLLM(user, provider=payload.provider)
        test_stage = "request_or_response"
        start_time = time.perf_counter()
        if payload.provider == "custom_openai":
            from backend.core.custom_openai import test_connection

            response = await test_connection(gm, payload.model)
        else:
            response = await gm.aexecute_simple_task(
                system_prompt="You are a helpful RPG assistant.",
                user_prompt="Say 'TaleWeaver connection test successful!' in a fantasy style.",
                model=payload.model,
            )
        end_time = time.perf_counter()
        latency = round(end_time - start_time, 2)
        return {"status": "success", "message": response, "response_time": latency}
    except Exception as exc:
        diag = (
            connection_test_diagnostic(exc, stage=test_stage, model=payload.model)
            if payload.provider == "custom_openai"
            else diagnose_provider_error(
                exc, provider=payload.provider, model=payload.model, context="llm"
            )
        )
        logger.warning(
            "LLM connection test failed for provider '%s': %s",
            payload.provider,
            exc,
        )
        return {"status": "error", "message": diag}
    finally:
        user.llm_settings = old_settings


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


_LOCAL_IMAGE_PROVIDERS = ("ollama", "stable_diffusion")


def _resolve_vision_api_key(
    user: User, provider_key: str, provider_name: str
) -> tuple[Optional[str], Optional[dict]]:
    """Returns (api_key, error_response); local providers need no key."""
    if provider_key in _LOCAL_IMAGE_PROVIDERS:
        return None, None
    api_key = settings.get_env_api_key(provider_key)
    if api_key:
        return api_key, None
    encrypted_keys = user.encrypted_api_keys
    if not encrypted_keys or provider_key not in encrypted_keys:
        return None, {"status": "error", "message": f"No API key configured for {provider_name}."}
    try:
        return encryption_util.decrypt_key(encrypted_keys[provider_key]), None
    except Exception as dec_exc:
        diag = diagnose_provider_error(dec_exc, provider=provider_name, context="vision")
        return None, {"status": "error", "message": diag}


def _build_vision_provider_options(payload: "TestVisionPayload", provider_key: str) -> dict:
    options: dict[str, Any] = {}
    for key in ("ollama_url", "stable_diffusion_url", "sampler_name", "scheduler"):
        if getattr(payload, key):
            options[key] = getattr(payload, key)
    for key in ("steps", "cfg_scale"):
        if getattr(payload, key) is not None:
            options[key] = getattr(payload, key)

    # Test vision generates a wizard portrait (CHARACTER/4:5 aspect ratio)
    if provider_key in _LOCAL_IMAGE_PROVIDERS and not payload.width and not payload.height:
        min_long_edge = payload.min_long_edge or 1024
        width, height = MediaEngine._resolve_sd_dimensions("CHARACTER", min_long_edge)
        options["width"] = width
        options["height"] = height
        return options

    for key in ("width", "height"):
        if getattr(payload, key) is not None:
            options[key] = getattr(payload, key)
    return options


@router.post("/test-vision")
async def test_vision_connection(
    payload: TestVisionPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Tests the connection to an image provider by generating a wizard portrait."""
    user = await _resolve_global_settings_owner(db, current_user)
    provider_key = payload.provider.lower()
    api_key, error_response = _resolve_vision_api_key(user, provider_key, payload.provider)
    if error_response:
        return error_response

    try:
        test_dir = _safe_data_path("scratch", "test_connection")
        os.makedirs(test_dir, exist_ok=True)
        img_url = await MediaEngine.generate_image(
            prompt="A Wizard portrait",
            model=payload.model,
            api_key=api_key,
            provider=payload.provider,
            target_dir=test_dir,
            provider_options=_build_vision_provider_options(payload, provider_key),
        )
        if img_url:
            return {
                "status": "success",
                "message": "Image generation successful!",
                "image_url": img_url,
            }
        return {"status": "error", "message": "Image generation failed."}
    except Exception as exc:
        diag = diagnose_provider_error(
            exc, provider=payload.provider, model=payload.model, context="vision"
        )
        logger.warning("Vision connection test failed for provider '%s': %s", payload.provider, exc)
        return {"status": "error", "message": diag}


@router.post("/test-tts")
async def test_tts_connection(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generates a short test sentence to verify TTS configuration."""
    user = await _resolve_global_settings_owner(db, current_user)
    tts_settings = user.tts_settings or {}

    provider = tts_settings.get("provider", "google").lower()
    api_key = None
    if provider != "qwen":
        api_key = settings.get_env_api_key(provider)
        if not api_key and user.encrypted_api_keys:
            enc_key = user.encrypted_api_keys.get(provider)
            if enc_key:
                try:
                    api_key = encryption_util.decrypt_key(enc_key)
                except Exception as dec_exc:
                    diag = diagnose_provider_error(dec_exc, provider=provider, context="tts")
                    return {"status": "error", "message": diag}

        if not api_key:
            return {
                "status": "error",
                "message": f"No API key configured for TTS provider '{provider.capitalize()}'.",
            }

    test_text = "Tale Weaver connection test successful! The journey begins now."

    try:
        audio_url = await TTSEngine.generate_speech(
            text=test_text,
            provider=provider,
            voice=tts_settings.get("selected_voice", "Puck"),
            elevenlabs_voice_id=tts_settings.get("elevenlabs_voice_id", ""),
            use_vocal_tags=tts_settings.get("use_vocal_tags", True),
            api_key=api_key,
            model_name=TTS_MODEL_ALIASES.get(
                str(tts_settings.get("selected_model", "gemini-3.8-flash-tts") or "").strip(),
                str(tts_settings.get("selected_model", "gemini-3.8-flash-tts") or "").strip(),
            ),
        )
        if not audio_url:
            return {"status": "error", "message": "Failed to generate test audio."}
        return {"status": "success", "audio_url": audio_url}
    except TTSModelSwitchSuggestionError:
        return {
            "status": "error",
            "message": "The selected TTS model is currently unavailable. Please choose a different model and try again.",
        }
    except Exception as exc:
        diag = diagnose_provider_error(exc, provider=provider, context="tts")
        logger.warning("TTS connection test failed for provider '%s': %s", provider, exc)
        return {"status": "error", "message": diag}


@router.post("/image-styles")
async def update_image_styles_catalog(
    payload: CatalogUpdatePayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """Updates the admin-managed image styles catalog for adventure generation."""
    user = await _resolve_global_settings_owner(db, current_user)

    raw_items = [item.model_dump() for item in payload.items]
    user.image_styles_catalog = _normalize_catalog(
        raw_items, fallback=_default_image_styles_catalog()
    )
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
        return {
            "status": "error",
            "message": "The 'Simple Model' for image generation is not configured. Please set it in Visual Preferences.",
        }

    api_key = _resolve_provider_api_key(provider, user.encrypted_api_keys)
    if provider not in ("ollama", "stable_diffusion") and not api_key:
        return {"status": "error", "message": f"No API key for {provider}"}

    try:
        catalog_type = _canonical_catalog_type(payload.catalog_type)
        if not catalog_type:
            return {"status": "error", "message": "Invalid catalog type."}

        safe_target_id = _sanitize_filename_component(payload.target_id) or "tile"
        catalog_dir = _safe_data_path("catalog", catalog_type)
        os.makedirs(catalog_dir, exist_ok=True)

        base_prompt = payload.prompt
        if not base_prompt:
            item_name = payload.name or safe_target_id.replace("-", " ")
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
            filename=f"{safe_target_id}_{uuid.uuid4().hex[:8]}",
            provider_options=t2i,
        )

        logger.info("Catalog generate result for '%s': img_url=%r", payload.target_id, img_url)
        if img_url:
            return {"status": "success", "image_url": img_url}
        else:
            return {
                "status": "error",
                "message": "Generation failed: The provider returned no image data. Check your API logs or model configuration.",
            }
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
    if not re.match(r"^[a-zA-Z0-9_-]{1,64}$", catalog_type):
        raise HTTPException(status_code=400, detail="Invalid catalog type format.")
    if not re.match(r"^[a-zA-Z0-9_-]{1,128}$", target_id):
        raise HTTPException(status_code=400, detail="Invalid target ID format.")
    try:
        safe_ext = _extension_from_content_type(file.content_type)
        filepath = _build_catalog_upload_path(catalog_type, target_id, f"upload.{safe_ext}")

        safe_filepath = _ensure_within_data_dir(filepath)
        safe_parent_dir = _ensure_within_data_dir(os.path.dirname(safe_filepath))
        safe_filepath = ensure_within_base_dir(safe_filepath, safe_parent_dir)
        # Re-verify containment at the sink so the taint analysis trusts the path.
        data_root = os.path.realpath(settings.DATA_DIR)
        if os.path.commonpath([os.path.realpath(safe_filepath), data_root]) != data_root:
            raise ValueError("Invalid filepath: escapes DATA_DIR.")
        with open(safe_filepath, "wb") as f:
            f.write(await file.read())

        rel_path = os.path.relpath(safe_filepath, settings.DATA_DIR).replace("\\", "/")
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
