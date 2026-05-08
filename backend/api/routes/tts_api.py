from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Any
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.auth import get_current_user
from backend.models.user import User
from backend.models.game_session import GameSession
from backend.engine.tts_engine import TTSEngine, TTSTimeoutError, TTSRateLimitError
from backend.core.security import encryption_util
from backend.core.config import settings
from backend.core.database import get_db

router = APIRouter(prefix="/tts", tags=["TTS"])
logger = logging.getLogger(__name__)
SUPPORTED_TTS_MODELS = {
    "gemini-3.1-flash-tts-preview",
    "gemini-2.5-flash-preview-tts",
}

TTS_MODEL_ALIASES = {
    "gemini-2.5-flash-tts-preview": "gemini-2.5-flash-preview-tts",
    "gemini-2.5-flash-tts": "gemini-2.5-flash-preview-tts",
}


async def _resolve_tts_settings_source_user(db: AsyncSession, current_user: User) -> User:
    """Use global/admin settings owner for TTS, falling back to current user."""
    admin_res = await db.execute(select(User).where(User.role == "admin").limit(1))
    admin_user = admin_res.scalars().first()
    return admin_user or current_user

class TTSGeneratePayload(BaseModel):
    text: str = Field(default="")
    scene_description: Optional[str] = Field(default=None)
    adventure_id: Optional[str] = Field(default=None)
    session_id: Optional[str] = Field(default=None)
    title: Optional[str] = Field(default=None)
    scene_name: Optional[str] = Field(default=None)
    tone: Optional[str] = Field(default=None)
    voice_override: Optional[str] = Field(default=None)
    speaker_voices: Optional[dict[str, str]] = Field(default=None)

    @staticmethod
    def _coerce_required_text(value: Any) -> str:
        if isinstance(value, str):
            return value
        if value is None:
            return ""
        if isinstance(value, (int, float, bool)):
            return str(value)
        return ""

    @staticmethod
    def _coerce_optional_text(value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        if isinstance(value, (int, float, bool)):
            return str(value)
        return None

    @field_validator("text", mode="before")
    @classmethod
    def _validate_text(cls, value: Any) -> str:
        return cls._coerce_required_text(value)

    @field_validator("scene_description", "adventure_id", "session_id", "title", "scene_name", "tone", "voice_override", mode="before")
    @classmethod
    def _validate_optional_text(cls, value: Any) -> Optional[str]:
        return cls._coerce_optional_text(value)

@router.post("/generate")
async def generate_tts(
    payload: TTSGeneratePayload = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Manually generate speech for a given text.
    """
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="Text is required for TTS generation.")

    # Use global settings owner (admin) for consistent runtime behavior.
    settings_user = await _resolve_tts_settings_source_user(db, current_user)

    # 1. Resolve API Key
    # Prefer env key, then user key
    api_key = settings.get_env_api_key("google")
    if not api_key and settings_user.encrypted_api_keys:
        enc_key = settings_user.encrypted_api_keys.get("google")
        if enc_key:
            api_key = encryption_util.decrypt_key(enc_key)

    if not api_key:
        raise HTTPException(status_code=400, detail="Google API Key not configured for TTS.")

    # 2. Get TTS Settings
    tts_settings = settings_user.tts_settings or {}
    
    if not tts_settings.get("enabled", True):
        raise HTTPException(status_code=400, detail="TTS is globally disabled in settings.")

    voice = tts_settings.get("selected_voice", "Puck")
    allowed_voices = set(tts_settings.get("voice_list") or [])
    if payload.voice_override:
        if payload.voice_override in allowed_voices:
            voice = payload.voice_override
        else:
            logger.warning("Ignoring invalid voice override '%s'. Falling back to default voice.", payload.voice_override)
    style = tts_settings.get("sample_context")
    model = str(tts_settings.get("selected_model", "gemini-3.1-flash-tts-preview") or "").strip()
    model = TTS_MODEL_ALIASES.get(model, model)
    if model not in SUPPORTED_TTS_MODELS:
        logger.warning("Unsupported TTS model '%s' configured; falling back to gemini-3.1-flash-tts-preview.", model)
        model = "gemini-3.1-flash-tts-preview"
    logger.info("TTS selected model for request: %s", model)

    speaker_voices: Optional[dict[str, str]] = None
    if payload.speaker_voices:
        normalized: dict[str, str] = {}
        for raw_speaker, raw_voice in payload.speaker_voices.items():
            speaker = str(raw_speaker or "").strip()
            requested_voice = str(raw_voice or "").strip()
            if not speaker or not requested_voice:
                continue
            if requested_voice in allowed_voices:
                normalized[speaker] = requested_voice
            else:
                logger.warning(
                    "Ignoring invalid speaker voice mapping '%s' -> '%s'.",
                    speaker,
                    requested_voice,
                )
        if normalized:
            speaker_voices = normalized

    normalized_adventure_id = payload.adventure_id
    normalized_session_id = payload.session_id

    # Backward compatibility: older clients sent game/session id via adventure_id.
    if not normalized_session_id and normalized_adventure_id:
        session_res = await db.execute(
            select(GameSession).where(
                GameSession.id == normalized_adventure_id,
                GameSession.user_id == current_user.id,
            ).limit(1)
        )
        session = session_res.scalars().first()
        if session:
            normalized_session_id = session.id
            normalized_adventure_id = session.template_id or normalized_adventure_id

    # 3. Generate Speech
    try:
        audio_url = await TTSEngine.generate_speech(
            text=payload.text,
            voice=voice,
            speaker_voices=speaker_voices,
            api_key=api_key,
            adventure_id=normalized_adventure_id,
            session_id=normalized_session_id,
            scene_description=payload.scene_description,
            style_description=style,
            model_name=model,
            title=payload.title,
            scene_name=payload.scene_name,
            tone=payload.tone,
            include_style_context=(payload.voice_override is None and not speaker_voices),
        )
    except TTSTimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail="TTS generation timed out. Try a shorter narration block or retry.",
        ) from exc
    except TTSRateLimitError as exc:
        retry_after = exc.retry_after_seconds
        detail = "TTS rate limit reached. Please retry in a moment."
        if retry_after:
            detail = f"TTS rate limit reached. Retry in about {int(round(retry_after))}s."
        raise HTTPException(status_code=429, detail=detail) from exc

    if not audio_url:
        raise HTTPException(status_code=500, detail="Failed to generate speech.")

    return {"audio_url": audio_url}
