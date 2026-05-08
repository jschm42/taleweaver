from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional

from backend.core.database import get_db
from backend.core.auth import get_current_user
from backend.models.user import User
from backend.engine.tts_engine import TTSEngine
from backend.core.security import encryption_util
from backend.core.config import settings

router = APIRouter(prefix="/tts", tags=["TTS"])

class TTSGeneratePayload(BaseModel):
    text: str
    scene_description: Optional[str] = None
    adventure_id: Optional[str] = None

@router.post("/generate")
async def generate_tts(
    payload: TTSGeneratePayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Manually generate speech for a given text.
    """
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
    style = tts_settings.get("sample_context")
    model = tts_settings.get("selected_model", "gemini-3.1-flash-tts-preview")

    # 3. Generate Speech
    audio_url = await TTSEngine.generate_speech(
        text=payload.text,
        voice=voice,
        api_key=api_key,
        scene_description=payload.scene_description,
        style_description=style,
        model_name=model
    )

    if not audio_url:
        raise HTTPException(status_code=500, detail="Failed to generate speech.")

    return {"audio_url": audio_url}
