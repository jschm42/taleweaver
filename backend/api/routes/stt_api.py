import io
import logging
import wave
import numpy as np
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.models.user import User

router = APIRouter(prefix="/stt", tags=["STT"])
logger = logging.getLogger(__name__)

# Cache loaded Whisper models to avoid re-loading weights on every call.
_whisper_models = {}


def get_whisper_model(model_name: str):
    import whisper
    if model_name not in _whisper_models:
        logger.info("Loading Whisper model: %s", model_name)
        _whisper_models[model_name] = whisper.load_model(model_name)
    return _whisper_models[model_name]


def decode_wav_to_numpy(wav_bytes: bytes) -> np.ndarray:
    """
    Decodes raw WAV file bytes to a float32 mono numpy array at 16kHz.
    Avoids using external ffmpeg subprocess.
    """
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        n_channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
        n_frames = wf.getnframes()
        
        if framerate != 16000:
            raise ValueError(f"Unsupported sample rate: {framerate}Hz. Only 16000Hz is supported.")
        if sampwidth != 2:
            raise ValueError(f"Unsupported sample width: {sampwidth} bytes. Only 16-bit (2 bytes) PCM is supported.")
        
        raw_data = wf.readframes(n_frames)
        # Convert raw PCM 16-bit to numpy array
        audio = np.frombuffer(raw_data, dtype=np.int16).astype(np.float32)
        
        # Scale to [-1.0, 1.0]
        audio /= 32768.0
        
        # Convert stereo/multi-channel to mono
        if n_channels > 1:
            audio = audio.reshape(-1, n_channels)
            audio = audio.mean(axis=1)
            
        return audio


@router.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Transcribes an uploaded WAV file using OpenAI Whisper."""
    from backend.api.routes.config_api import _resolve_global_settings_owner, _normalize_game_settings
    settings_owner = await _resolve_global_settings_owner(db, current_user)
    game_settings = _normalize_game_settings(settings_owner.game_settings)
    model_name = game_settings.get("whisper_model", "tiny")

    content = await file.read()
    
    try:
        audio_data = decode_wav_to_numpy(content)
    except Exception as e:
        logger.exception("Failed to decode WAV file")
        raise HTTPException(status_code=400, detail=f"Invalid audio format. Must be 16kHz 16-bit mono WAV: {e}")

    try:
        model = get_whisper_model(model_name)
        result = model.transcribe(audio_data)
        text = result.get("text", "").strip()
        logger.info("Whisper transcription result (%s): %s", model_name, text)
        return {"text": text}
    except Exception as e:
        logger.exception("Whisper transcription failed")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {e}")
