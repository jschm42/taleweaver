from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Any
import logging

from backend.core.auth import get_current_user
from backend.models.user import User
from backend.engine.tts_engine import TTSEngine, TTSTimeoutError
from backend.core.security import encryption_util
from backend.core.config import settings

router = APIRouter(prefix="/tts", tags=["TTS"])
logger = logging.getLogger(__name__)

class TTSGeneratePayload(BaseModel):
    text: str = Field(default="")
    scene_description: Optional[str] = Field(default=None)
    adventure_id: Optional[str] = Field(default=None)
    title: Optional[str] = Field(default=None)
    scene_name: Optional[str] = Field(default=None)
    tone: Optional[str] = Field(default=None)
    voice_override: Optional[str] = Field(default=None)

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

    @field_validator("scene_description", "adventure_id", "title", "scene_name", "tone", "voice_override", mode="before")
    @classmethod
    def _validate_optional_text(cls, value: Any) -> Optional[str]:
        return cls._coerce_optional_text(value)

@router.post("/generate")
async def generate_tts(
    payload: TTSGeneratePayload = Body(...),
    current_user: User = Depends(get_current_user)
):
    """
    Manually generate speech for a given text.
    """
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="Text is required for TTS generation.")

    # 1. Resolve API Key
    # Prefer env key, then user key
    api_key = settings.get_env_api_key("google")
    if not api_key and current_user.encrypted_api_keys:
        enc_key = current_user.encrypted_api_keys.get("google")
        if enc_key:
            api_key = encryption_util.decrypt_key(enc_key)

    if not api_key:
        raise HTTPException(status_code=400, detail="Google API Key not configured for TTS.")

    # 2. Get TTS Settings
    tts_settings = current_user.tts_settings or {}
    
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
    model = tts_settings.get("selected_model", "gemini-3.1-flash-tts-preview")

    # 3. Generate Speech
    try:
        audio_url = await TTSEngine.generate_speech(
            text=payload.text,
            voice=voice,
            api_key=api_key,
            scene_description=payload.scene_description,
            style_description=style,
            model_name=model,
            title=payload.title,
            scene_name=payload.scene_name,
            tone=payload.tone
        )
    except TTSTimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail="TTS generation timed out. Try a shorter narration block or retry.",
        ) from exc

    if not audio_url:
        raise HTTPException(status_code=500, detail="Failed to generate speech.")

    return {"audio_url": audio_url}
