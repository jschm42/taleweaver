import asyncio
import io
import logging
import threading
import time
import wave

import numpy as np
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
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
    from faster_whisper import WhisperModel

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
            logger.info("Loading faster-whisper model: %s", model_name)
            model = WhisperModel(model_name, device="cpu", compute_type="int8")
            with _state_lock:
                _whisper_models[model_name] = model
                _whisper_model_states[model_name] = "loaded"
            return model
        except Exception as e:
            logger.exception("Failed to load faster-whisper model: %s", model_name)
            with _state_lock:
                _whisper_model_states[model_name] = "error"
            raise e
    else:
        # Wait for the loader thread to finish
        logger.info(
            "Whisper model %s is already loading in another thread; waiting for it...", model_name
        )
        start_wait = time.time()
        while True:
            with _state_lock:
                state = _whisper_model_states.get(model_name, "not_loaded")
                if state == "loaded":
                    return _whisper_models[model_name]
                if state == "error":
                    raise RuntimeError(
                        f"Whisper model {model_name} failed to load in the other thread."
                    )
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
    from backend.api.routes.config_api import (
        _normalize_game_settings,
        _resolve_global_settings_owner,
    )

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
    from backend.api.routes.config_api import (
        _normalize_game_settings,
        _resolve_global_settings_owner,
    )

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
            raise ValueError(
                f"Unsupported sample width: {sampwidth} bytes. Only 16-bit (2 bytes) PCM is supported."
            )

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


def transcribe_sync(model_name: str, audio_data: np.ndarray) -> str:
    """Runs the full transcription; meant to be called in a worker thread.

    faster-whisper returns a lazy segment generator, so the decoding happens while the
    segments are joined. That must stay inside the worker thread to keep the event loop free.
    """
    model = get_whisper_model(model_name)
    # The VAD filter strips the silence at the start of a push-to-talk recording (the mic
    # is still warming up on the first use). Without it, language detection runs on
    # near-silence and the speech gets transcribed as a wrong language.
    segments, info = model.transcribe(audio_data, vad_filter=True)
    text = "".join(segment.text for segment in segments).strip()
    logger.info(
        "Whisper transcription (%s, language=%s p=%.2f): %s",
        model_name,
        getattr(info, "language", "?"),
        getattr(info, "language_probability", 0.0),
        text,
    )
    return text


@router.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Transcribes an uploaded WAV file using a local faster-whisper model."""
    from backend.api.routes.config_api import (
        _normalize_game_settings,
        _resolve_global_settings_owner,
    )

    settings_owner = await _resolve_global_settings_owner(db, current_user)
    game_settings = _normalize_game_settings(settings_owner.game_settings)
    model_name = game_settings.get("whisper_model", "tiny")

    content = await file.read()

    try:
        audio_data = decode_wav_to_numpy(content)
    except Exception as e:
        logger.exception("Failed to decode WAV file")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid audio format. Must be 16kHz 16-bit mono WAV: {e}",
        ) from e

    try:
        text = await asyncio.to_thread(transcribe_sync, model_name, audio_data)
        return {"text": text}
    except Exception as e:
        logger.exception("Whisper transcription failed")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {e}") from e
