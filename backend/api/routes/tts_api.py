import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.api_keys import PersonalKeyRequiredError
from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.core.error_diagnostics import diagnose_provider_error
from backend.core.global_settings import read_server_settings
from backend.engine.audio.openai_compatible_tts import (
    OPENAI_COMPATIBLE_PROVIDER,
    SpeechEndpoint,
    normalize_response_format,
    resolve_speech_api_key,
)
from backend.engine.audio.speaker_voice import (
    NarratorVoices,
    SpeakerVoices,
    elevenlabs_speaker_voice,
    resolve_speaker_voices,
)
from backend.engine.audio.tts_engine import (
    TTSEngine,
    TTSModelSwitchSuggestionError,
    TTSProviderError,
    TTSRateLimitError,
    TTSTimeoutError,
)
from backend.engine.audio.voice_casting import provider_api_key
from backend.engine.audio.voice_provider_map import effective_voice_map
from backend.models.game_session import GameSession
from backend.models.server_settings import ServerSettings
from backend.models.user import User

router = APIRouter(prefix="/tts", tags=["TTS"])
logger = logging.getLogger(__name__)
DEFAULT_TTS_MODEL = "gemini-3.8-flash-tts"
DEFAULT_ELEVENLABS_MODEL = "eleven_v4"
SUPPORTED_TTS_MODELS = {
    "gemini-3.8-flash-tts",
    "gemini-3.8-flash-lite-tts",
}

TTS_MODEL_ALIASES = {
    # Legacy aliases for backward compatibility
    "gemini-2.5-flash-preview-tts": "gemini-3.8-flash-tts",
    "gemini-2.5-flash-tts-preview": "gemini-3.8-flash-tts",
    "gemini-2.5-flash-tts": "gemini-3.8-flash-tts",
    "gemini-3.1-flash-tts-preview": "gemini-3.8-flash-tts",
}

_TRUTHY_STRINGS = ("true", "1", "yes", "on")


@dataclass(frozen=True)
class ResolvedTTSConfig:
    provider: str
    api_key: Optional[str]
    voice: str
    elevenlabs_voice_id: str
    use_vocal_tags: bool
    use_streaming: bool
    model: str
    speech_endpoint: Optional[SpeechEndpoint] = None
    # Voice-list id -> {provider: voice} (see engine/audio/voice_provider_map.py).
    voice_map: dict[str, dict[str, str]] = field(default_factory=dict)


def _coerce_bool(value: Any, default: bool) -> bool:
    """Coerce DB-stored flags (bool, 0/1, "true"/"false") to a real boolean."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).lower() in _TRUTHY_STRINGS


def _resolve_model(provider: str, raw_model: Any) -> str:
    if provider == OPENAI_COMPATIBLE_PROVIDER:
        return str(raw_model or "").strip()
    default = DEFAULT_ELEVENLABS_MODEL if provider == "elevenlabs" else DEFAULT_TTS_MODEL
    model = str(raw_model or default).strip()
    model = TTS_MODEL_ALIASES.get(model, model)
    if provider == "google" and model not in SUPPORTED_TTS_MODELS:
        logger.warning(
            "Unsupported Google TTS model '%s' configured; falling back to %s.",
            model,
            DEFAULT_TTS_MODEL,
        )
        return DEFAULT_TTS_MODEL
    return model


def _resolve_api_key(provider: str, user: User) -> str:
    try:
        api_key = provider_api_key(provider, user)
    except PersonalKeyRequiredError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    if not api_key:
        raise HTTPException(
            status_code=400, detail=f"{provider.capitalize()} API Key not configured for TTS."
        )
    return api_key


def _speech_endpoint(tts_settings: dict, model: str, user: User) -> SpeechEndpoint:
    """Server, model, voice and (optional) key for the OpenAI-compatible provider."""
    base_url = str(tts_settings.get("custom_openai_url") or "").strip()
    try:
        api_key = resolve_speech_api_key(user.encrypted_api_keys, base_url)
    except PersonalKeyRequiredError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None
    return SpeechEndpoint(
        base_url=base_url,
        model=model,
        voice=str(tts_settings.get("custom_openai_voice") or "").strip(),
        api_key=api_key,
        response_format=normalize_response_format(tts_settings.get("custom_openai_format")),
        instructions=str(tts_settings.get("custom_openai_instructions") or "").strip(),
    )


async def _resolve_tts_settings_source(db: AsyncSession) -> ServerSettings:
    """TTS configuration and keys are server-wide."""
    return await read_server_settings(db)


async def _resolve_tts_config(
    db: AsyncSession, current_user: User, require_enabled: bool = False
) -> ResolvedTTSConfig:
    """Server-wide TTS configuration plus the caller's key for it (per key policy)."""
    settings_user = await _resolve_tts_settings_source(db)
    tts_settings = settings_user.tts_settings or {}
    if require_enabled and not _coerce_bool(tts_settings.get("enabled"), False):
        raise HTTPException(status_code=400, detail="TTS is globally disabled in settings.")
    provider = str(tts_settings.get("provider", "google")).lower()
    model = _resolve_model(provider, tts_settings.get("selected_model"))
    is_compatible = provider == OPENAI_COMPATIBLE_PROVIDER
    endpoint = _speech_endpoint(tts_settings, model, current_user) if is_compatible else None
    return ResolvedTTSConfig(
        provider=provider,
        api_key=endpoint.api_key if endpoint else _resolve_api_key(provider, current_user),
        voice=tts_settings.get("selected_voice", "Puck"),
        elevenlabs_voice_id=tts_settings.get("elevenlabs_voice_id", ""),
        use_vocal_tags=_coerce_bool(tts_settings.get("use_vocal_tags"), True),
        use_streaming=_coerce_bool(tts_settings.get("use_streaming"), False),
        model=model,
        speech_endpoint=endpoint,
        voice_map=effective_voice_map(settings_user.voice_provider_map),
    )


def _resolve_elevenlabs_voice(config: ResolvedTTSConfig, voice_override: Optional[str]) -> str:
    """The ElevenLabs voice: the character's list or custom voice id, else the narrator voice."""
    return elevenlabs_speaker_voice(config.provider, config.elevenlabs_voice_id, voice_override)


def _resolve_speaker_voices(
    config: ResolvedTTSConfig, voice_override: Optional[str]
) -> SpeakerVoices:
    """The character's voice for the active provider (voice mapping), else the narrator voice."""
    narrator = NarratorVoices(config.voice, config.elevenlabs_voice_id, config.speech_endpoint)
    return resolve_speaker_voices(config.provider, narrator, config.voice_map, voice_override)


async def _normalize_session_ids(
    db: AsyncSession,
    current_user: User,
    adventure_id: Optional[str],
    session_id: Optional[str],
) -> tuple[Optional[str], Optional[str]]:
    """Older clients sent the game/session id via adventure_id; map it back."""
    if session_id or not adventure_id:
        return adventure_id, session_id
    session_res = await db.execute(
        select(GameSession)
        .where(GameSession.id == adventure_id, GameSession.user_id == current_user.id)
        .limit(1)
    )
    session = session_res.scalars().first()
    if not session:
        return adventure_id, session_id
    return session.template_id or adventure_id, session.id


_URL_PATTERN = re.compile(r"https?://\S+")
# Long unbroken letter/digit runs look like keys, tokens or request ids.
_TOKEN_PATTERN = re.compile(r"\b[A-Za-z0-9_\-]{24,}\b")
_MAX_REASON_CHARS = 240


def _safe_provider_reason(exc: Exception) -> str:
    """The provider's error text for the user, without URLs or token-like strings.

    The full exception stays in the server log only.
    """
    reason = _TOKEN_PATTERN.sub("[redacted]", _URL_PATTERN.sub("[url]", str(exc))).strip()
    if len(reason) > _MAX_REASON_CHARS:
        reason = reason[: _MAX_REASON_CHARS - 1].rstrip() + "…"
    return reason or "unknown provider error"


def _rate_limit_http_exception(exc: TTSRateLimitError) -> HTTPException:
    retry_after = exc.retry_after_seconds
    if not retry_after:
        return HTTPException(
            status_code=429, detail="TTS rate limit reached. Please retry in a moment."
        )
    seconds = max(1, int(round(retry_after)))
    return HTTPException(
        status_code=429,
        detail=f"TTS rate limit reached. Retry in about {seconds}s.",
        headers={"Retry-After": str(seconds)},
    )


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
    style_description: Optional[str] = Field(default=None)
    language: Optional[str] = Field(default=None)

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

    @field_validator(
        "scene_description",
        "adventure_id",
        "session_id",
        "title",
        "scene_name",
        "tone",
        "voice_override",
        "director_notes",
        "language",
        mode="before",
    )
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
        except (ValueError, AttributeError, TypeError):
            # Keep backward compatibility for non-UUID template/route ids.
            return candidate

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

    config = await _resolve_tts_config(db, current_user, require_enabled=True)
    adventure_id, session_id = await _normalize_session_ids(
        db, current_user, payload.adventure_id, payload.session_id
    )
    logger.info(
        "[API] TTS Request: provider=%s, model=%s, text_len=%d",
        config.provider,
        config.model,
        len(payload.text),
    )

    speaker = _resolve_speaker_voices(config, payload.voice_override)
    try:
        audio_url = await TTSEngine.generate_speech(
            text=payload.text,
            provider=config.provider,
            voice=speaker.voice,
            elevenlabs_voice_id=speaker.elevenlabs_voice_id,
            use_vocal_tags=config.use_vocal_tags,
            api_key=config.api_key,
            adventure_id=adventure_id,
            session_id=session_id,
            model_name=config.model,
            language=payload.language,
            use_streaming=config.use_streaming,
            speech_endpoint=speaker.speech_endpoint,
        )
    except TTSTimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail="TTS generation timed out. Try a shorter narration block or retry.",
        ) from exc
    except TTSModelSwitchSuggestionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except TTSRateLimitError as exc:
        raise _rate_limit_http_exception(exc) from exc
    except TTSProviderError as exc:
        logger.warning("TTS generation failed (provider=%s): %s", config.provider, exc)
        raise HTTPException(
            status_code=502, detail=f"TTS Provider error: {_safe_provider_reason(exc)}"
        ) from exc

    if not audio_url:
        raise HTTPException(status_code=500, detail="Failed to generate speech.")

    return {"audio_url": audio_url}


@router.post("/test-connection")
async def test_tts_connection_v2(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generates a short test sentence to verify TTS configuration."""
    config = await _resolve_tts_config(db, current_user)
    test_text = "Tale Weaver connection test successful!"
    if config.use_vocal_tags:
        test_text = f"[excited] {test_text}"

    try:
        audio_url = await TTSEngine.generate_speech(
            text=test_text,
            provider=config.provider,
            voice=config.voice,
            elevenlabs_voice_id=config.elevenlabs_voice_id,
            use_vocal_tags=config.use_vocal_tags,
            api_key=config.api_key,
            model_name=config.model,
            speech_endpoint=config.speech_endpoint,
        )
    except TTSModelSwitchSuggestionError:
        return {
            "status": "error",
            "message": "The selected TTS model is currently unavailable. Please choose a different model and try again.",
        }
    except TTSRateLimitError:
        return {"status": "error", "message": "TTS rate limit reached. Please retry in a moment."}
    except TTSTimeoutError:
        return {"status": "error", "message": "TTS request timed out. Please retry."}
    except TTSProviderError as exc:
        logger.warning(
            "TTS connection test failed (provider=%s, model=%s): %s",
            config.provider,
            config.model,
            exc,
        )
        diag = diagnose_provider_error(
            exc, provider=config.provider, model=config.model, context="tts"
        )
        return {
            "status": "error",
            "message": diag,
        }
    if not audio_url:
        return {"status": "error", "message": "Failed to generate test audio."}
    return {"status": "success", "audio_url": audio_url}
