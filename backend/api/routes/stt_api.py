import io
import logging
import wave
import numpy as np
import threading
import asyncio
import time
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.models.user import User

router = APIRouter(prefix="/stt", tags=["STT"])
logger = logging.getLogger(__name__)

# Cache loaded Whisper models and track loading states.
_whisper_models = {}
_whisper_model_states = {}  # model_name -> "not_loaded" | "loading" | "loaded" | "error"
_active_background_loaders = set()
_state_lock = threading.Lock()


def get_whisper_model(model_name: str, is_background_loader: bool = False):
    import whisper
    
    # Check if already loaded
    with _state_lock:
        if model_name in _whisper_models:
            return _whisper_models[model_name]
        
        state = _whisper_model_states.get(model_name, "not_loaded")
        
        # If we are the background loader thread, or state is not currently "loading", we should load it.
        if is_background_loader or state != "loading":
            _whisper_model_states[model_name] = "loading"
            is_loader = True
            if model_name in _active_background_loaders:
                _active_background_loaders.remove(model_name)
        else:
            is_loader = False
            
    if is_loader:
        try:
            logger.info("Loading Whisper model: %s", model_name)
            model = whisper.load_model(model_name)
            with _state_lock:
                _whisper_models[model_name] = model
                _whisper_model_states[model_name] = "loaded"
            return model
        except Exception as e:
            logger.exception("Failed to load Whisper model: %s", model_name)
            with _state_lock:
                _whisper_model_states[model_name] = "error"
            raise e
    else:
        # Wait for the loader thread to finish
        logger.info("Whisper model %s is already loading in another thread; waiting for it...", model_name)
        start_wait = time.time()
        while True:
            with _state_lock:
                state = _whisper_model_states.get(model_name, "not_loaded")
                if state == "loaded":
                    return _whisper_models[model_name]
                if state == "error":
                    raise RuntimeError(f"Whisper model {model_name} failed to load in the other thread.")
            if time.time() - start_wait > 90.0:  # Timeout after 90 seconds
                raise TimeoutError(f"Timed out waiting for Whisper model {model_name} to load.")
            time.sleep(0.5)


def load_whisper_model_sync(model_name: str):
    try:
        get_whisper_model(model_name, is_background_loader=True)
    except Exception:
        logger.exception("Background preloading of Whisper model failed: %s", model_name)


@router.get("/status")
async def get_stt_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Gets the load status of the configured Whisper model."""
    from backend.api.routes.config_api import _resolve_global_settings_owner, _normalize_game_settings
    settings_owner = await _resolve_global_settings_owner(db, current_user)
    game_settings = _normalize_game_settings(settings_owner.game_settings)
    model_name = game_settings.get("whisper_model", "tiny")
    
    with _state_lock:
        state = _whisper_model_states.get(model_name, "not_loaded")
        
    return {"model_name": model_name, "status": state}


@router.post("/preload")
async def preload_stt_model(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Starts preloading the configured Whisper model in a background thread."""
    from backend.api.routes.config_api import _resolve_global_settings_owner, _normalize_game_settings
    settings_owner = await _resolve_global_settings_owner(db, current_user)
    game_settings = _normalize_game_settings(settings_owner.game_settings)
    model_name = game_settings.get("whisper_model", "tiny")
    
    with _state_lock:
        state = _whisper_model_states.get(model_name, "not_loaded")
    
    if state not in ("loading", "loaded"):
        with _state_lock:
            _whisper_model_states[model_name] = "loading"
            _active_background_loaders.add(model_name)
        background_tasks.add_task(load_whisper_model_sync, model_name)
        return {"model_name": model_name, "status": "loading"}
        
    return {"model_name": model_name, "status": state}


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
        model = await asyncio.to_thread(get_whisper_model, model_name)
        result = await asyncio.to_thread(model.transcribe, audio_data)
        text = result.get("text", "").strip()
        logger.info("Whisper transcription result (%s): %s", model_name, text)
        return {"text": text}
    except Exception as e:
        logger.exception("Whisper transcription failed")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {e}")
