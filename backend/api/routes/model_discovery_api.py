"""Live model lists per provider for the admin settings and the setup wizard."""

import logging
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from backend.core.auth import get_current_admin
from backend.core.config import settings
from backend.core.security import encryption_util
from backend.models.user import User
from backend.services.model_discovery import (
    discover_models,
    supports_custom_base,
    supports_kind,
)
from backend.utils.path_security import validate_provider_url

router = APIRouter(prefix="/settings/models", tags=["Model Discovery"])
logger = logging.getLogger(__name__)


class ModelInfo(BaseModel):
    id: str
    label: str


class ModelListResponse(BaseModel):
    provider: str
    kind: Literal["llm", "image"]
    source: Literal["live", "static", "fallback"]
    error: Optional[str] = None
    models: list[ModelInfo]


def _resolve_api_key(user: User, provider: str) -> Optional[str]:
    """Environment first (as at runtime), then the admin's stored key.

    Global settings are broadcast to every user, so the admin's own copy is current.
    """
    env_key = settings.get_env_api_key(provider)
    if env_key:
        return env_key
    stored = (user.encrypted_api_keys or {}).get(provider)
    if not stored:
        return None
    try:
        return encryption_util.decrypt_key(stored)
    except (ValueError, TypeError, KeyError):
        logger.error("Failed to decrypt API key for provider '%s'", provider)
        return None


def _validated_base_url(provider: str, base_url: Optional[str]) -> Optional[str]:
    """Custom endpoints are honoured for self-hosted providers only, and SSRF-checked."""
    if not base_url or not supports_custom_base(provider):
        return None
    if provider == "custom_openai":
        from backend.core.custom_openai import validate_custom_url

        return validate_custom_url(base_url)
    try:
        return validate_provider_url(base_url)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.get("", response_model=ModelListResponse)
async def list_provider_models(
    provider: str,
    kind: Literal["llm", "image"] = "llm",
    base_url: Optional[str] = None,
    refresh: bool = False,
    current_user: User = Depends(get_current_admin),
):
    """List a provider's models for a role, live when possible.

    `base_url` only applies to Ollama, Stable Diffusion, ComfyUI and MiniMax and is ignored
    otherwise. `refresh` bypasses the 10-minute cache.
    """
    provider_id = provider.lower()
    if not supports_kind(provider_id, kind):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"Provider '{provider}' does not offer {kind} models."
        )
    target_base = base_url
    if provider_id == "custom_openai" and not target_base:
        target_base = (current_user.llm_settings or {}).get("custom_openai_url") or None
    result = await discover_models(
        provider_id,
        kind,
        api_key=_resolve_api_key(current_user, provider_id),
        base_url=_validated_base_url(provider_id, target_base),
        refresh=refresh,
    )
    return ModelListResponse(
        provider=provider_id,
        kind=kind,
        source=result.source,
        error=result.error,
        models=[ModelInfo(id=m.id, label=m.label) for m in result.models],
    )
