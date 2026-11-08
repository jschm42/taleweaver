"""Admin helpers for the OpenAI-compatible TTS provider: model and voice discovery.

``base_url`` lets the settings form check a server before it is saved; without it the saved
URL is used. Admin only, because the backend connects to that URL with the provider key.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.api_keys import PersonalKeyRequiredError
from backend.core.auth import get_current_admin
from backend.core.database import get_db
from backend.core.global_settings import read_server_settings
from backend.engine.audio.openai_compatible_tts import (
    checked_base_url,
    list_speech_models,
    list_speech_voices,
    resolve_speech_api_key,
)
from backend.engine.audio.tts_helpers import TTSProviderError
from backend.models.user import User

router = APIRouter(prefix="/tts/openai-compatible", tags=["TTS"])


async def _target(
    db: AsyncSession, user: User, base_url: Optional[str]
) -> tuple[str, Optional[str]]:
    """The validated base URL and the key that may be sent to it."""
    if not base_url:
        base_url = ((await read_server_settings(db)).tts_settings or {}).get("custom_openai_url")
    try:
        base = checked_base_url(base_url)
    except TTSProviderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        return base, resolve_speech_api_key(user.encrypted_api_keys, base)
    except PersonalKeyRequiredError:
        return base, None


@router.get("/models")
async def get_speech_models(
    base_url: Optional[str] = Query(default=None, max_length=500),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Model ids of the server (speech models only where the server marks them)."""
    base, api_key = await _target(db, admin, base_url)
    try:
        models = await list_speech_models(base, api_key)
    except TTSProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"base_url": base, "models": models}


@router.get("/voices")
async def get_speech_voices(
    base_url: Optional[str] = Query(default=None, max_length=500),
    model: str = Query(default="", max_length=200),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Voices from the server, else from the model entry, else OpenAI's voice names."""
    base, api_key = await _target(db, admin, base_url)
    voices, source = await list_speech_voices(base, api_key, model.strip())
    return {"base_url": base, "source": source, "voices": voices}
