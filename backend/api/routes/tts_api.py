import logging
import uuid
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.auth import get_current_user
from backend.core.config import settings
from backend.core.database import get_db
from backend.core.security import encryption_util
from backend.engine.tts_engine import TTSEngine, TTSRateLimitError, TTSTimeoutError
from backend.models.adventure_template import AdventureTemplate
from backend.models.game_session import GameSession
from backend.models.session_state import SessionState
from backend.models.user import User

router = APIRouter(prefix="/tts", tags=["TTS"])
logger = logging.getLogger(__name__)
SUPPORTED_TTS_MODELS = {
    "gemini-2.5-flash-preview-tts",
}

TTS_MODEL_ALIASES = {
    "gemini-3.1-flash-tts-preview": "gemini-2.5-flash-preview-tts",
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
    speaker_voices: Optional[dict[str, Optional[str]]] = Field(default=None)
    director_notes: Optional[str] = Field(default=None)

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

    @field_validator("scene_description", "adventure_id", "session_id", "title", "scene_name", "tone", "voice_override", "director_notes", mode="before")
    @classmethod
    def _validate_optional_text(cls, value: Any) -> Optional[str]:
        return cls._coerce_optional_text(value)

    @staticmethod
    def _coerce_optional_uuid(value: Any) -> Optional[str]:
        if value is None:
            return None
        candidate = str(value).strip()
        if not candidate:
            return None
        try:
            return str(uuid.UUID(candidate))
        except (ValueError, AttributeError, TypeError) as exc:
            raise ValueError("Must be a valid UUID.") from exc

    @field_validator("adventure_id", "session_id", mode="before")
    @classmethod
    def _validate_optional_uuid(cls, value: Any) -> Optional[str]:
        return cls._coerce_optional_uuid(value)

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
    logger.info("[TTS] Resolving settings from user: %s (ID: %s, Role: %s)", settings_user.username, settings_user.id, settings_user.role)

    # 1. Resolve Provider and API Key
    tts_settings = settings_user.tts_settings or {}
    if not tts_settings.get("enabled", False):
        raise HTTPException(status_code=400, detail="TTS is globally disabled in settings.")

    provider = tts_settings.get("provider", "google").lower()
    api_key = settings.get_env_api_key(provider)
    if not api_key and settings_user.encrypted_api_keys:
        enc_key = settings_user.encrypted_api_keys.get(provider)
        if enc_key:
            api_key = encryption_util.decrypt_key(enc_key)

    if not api_key:
        raise HTTPException(status_code=400, detail=f"{provider.capitalize()} API Key not configured for TTS.")

    # 2. Get TTS Settings
    voice = tts_settings.get("selected_voice", "Puck")
    elevenlabs_voice_id = tts_settings.get("elevenlabs_voice_id", "")
    
    # Coerce to boolean in case it's stored as 0/1 or string "true"/"false" in DB
    raw_vocal_tags = tts_settings.get("use_vocal_tags", True)
    use_vocal_tags = str(raw_vocal_tags).lower() in ("true", "1", "yes", "on") if not isinstance(raw_vocal_tags, bool) else raw_vocal_tags
    
    logger.info("[TTS] Vocal tags enabled: %s (raw value: %s)", use_vocal_tags, raw_vocal_tags)
    
    style = tts_settings.get("sample_context")
    speed = float(tts_settings.get("speech_rate", 1.0))
    model = str(tts_settings.get("selected_model", "gemini-2.5-flash-preview-tts") or "").strip()
    model = TTS_MODEL_ALIASES.get(model, model)
    if provider == "google" and model not in SUPPORTED_TTS_MODELS:
        logger.warning("Unsupported Google TTS model '%s' configured; falling back to gemini-2.5-flash-preview-tts.", model)
        model = "gemini-2.5-flash-preview-tts"
    
    # Log provider and model
    logger.info("TTS provider: %s, model: %s", provider, model)
    logger.info("[API] TTS Request: provider=%s, model=%s, text_len=%d", provider, model, len(payload.text or ""))

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

    # 3. Resolve Director Notes if not provided in payload
    final_director_notes = payload.director_notes
    if not final_director_notes:
        if normalized_session_id:
            state_res = await db.execute(select(SessionState).where(SessionState.session_id == normalized_session_id))
            state = state_res.scalars().first()
            if state and state.tts_director_notes:
                final_director_notes = state.tts_director_notes
        
        if not final_director_notes and normalized_adventure_id:
            # Check if it's a UUID-like adventure_id or a template ID
            template_res = await db.execute(select(AdventureTemplate).where(AdventureTemplate.id == normalized_adventure_id))
            template = template_res.scalars().first()
            if template:
                final_director_notes = template.tts_director_notes

    # 4. Generate Speech
    try:
        audio_url = await TTSEngine.generate_speech(
            text=payload.text,
            provider=provider,
            voice=voice,
            elevenlabs_voice_id=elevenlabs_voice_id,
            use_vocal_tags=use_vocal_tags,
            api_key=api_key,
            adventure_id=normalized_adventure_id,
            session_id=normalized_session_id,
            scene_description=payload.scene_description,
            style_description=style,
            model_name=model,
            title=payload.title,
            scene_name=payload.scene_name,
            tone=payload.tone,
            include_style_context=(payload.voice_override is None and not payload.speaker_voices),
            speed=speed,
            director_notes=final_director_notes,
        )
    except TTSTimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail="TTS generation timed out. Try a shorter narration block or retry.",
        ) from exc
    except TTSRateLimitError as exc:
        retry_after = exc.retry_after_seconds
        detail = "TTS rate limit reached. Please retry in a moment."
        headers = None
        if retry_after:
            detail = f"TTS rate limit reached. Retry in about {int(round(retry_after))}s."
            headers = {"Retry-After": str(max(1, int(round(retry_after))))}
        raise HTTPException(status_code=429, detail=detail, headers=headers) from exc

    if not audio_url:
        raise HTTPException(status_code=500, detail="Failed to generate speech.")

    return {"audio_url": audio_url}


@router.post("/test-connection")
async def test_tts_connection_v2(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generates a short test sentence to verify TTS configuration."""
    from backend.api.routes.config_api import _resolve_global_settings_owner
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

    use_vocal_tags = tts_settings.get("use_vocal_tags", True)
    test_text = "Tale Weaver connection test successful!"
    if use_vocal_tags:
        test_text = "[excited] Tale Weaver connection test successful!"

    audio_url = await TTSEngine.generate_speech(
        text=test_text,
        provider=provider,
        voice=tts_settings.get("selected_voice", "Puck"),
        elevenlabs_voice_id=tts_settings.get("elevenlabs_voice_id", ""),
        use_vocal_tags=tts_settings.get("use_vocal_tags", True),
        api_key=api_key,
        model_name=TTS_MODEL_ALIASES.get(
            str(tts_settings.get("selected_model", "gemini-2.5-flash-preview-tts") or "").strip(),
            "gemini-2.5-flash-preview-tts",
        ),
        speed=float(tts_settings.get("speech_rate", 1.0)),
    )
    if not audio_url:
        return {"status": "error", "message": "Failed to generate test audio."}
    return {"status": "success", "audio_url": audio_url}

