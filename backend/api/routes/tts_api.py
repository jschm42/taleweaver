import logging
import uuid
from dataclasses import dataclass
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.engine.elevenlabs_voices import load_voice_catalog, looks_like_voice_id
from backend.engine.tts_engine import (
    TTSEngine,
    TTSModelSwitchSuggestionError,
    TTSProviderError,
    TTSRateLimitError,
    TTSTimeoutError,
)
from backend.engine.voice_casting import NPC_VOICE_PROVIDER, load_tts_owner, provider_api_key
from backend.models.game_session import GameSession
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


def _coerce_bool(value: Any, default: bool) -> bool:
    """Coerce DB-stored flags (bool, 0/1, "true"/"false") to a real boolean."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).lower() in _TRUTHY_STRINGS


def _resolve_model(provider: str, raw_model: Any) -> str:
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


def _resolve_api_key(provider: str, settings_user: User) -> str:
    api_key = provider_api_key(provider, settings_user)
    if not api_key:
        raise HTTPException(
            status_code=400, detail=f"{provider.capitalize()} API Key not configured for TTS."
        )
    return api_key


async def _resolve_tts_settings_source_user(db: AsyncSession, current_user: User) -> User:
    """Use global/admin settings owner for TTS, falling back to current user."""
    return await load_tts_owner(db) or current_user


async def _resolve_tts_config(
    db: AsyncSession, current_user: User, require_enabled: bool = False
) -> ResolvedTTSConfig:
    """Load the global TTS configuration (admin-owned) and the provider API key."""
    settings_user = await _resolve_tts_settings_source_user(db, current_user)
    tts_settings = settings_user.tts_settings or {}
    if require_enabled and not _coerce_bool(tts_settings.get("enabled"), False):
        raise HTTPException(status_code=400, detail="TTS is globally disabled in settings.")
    provider = str(tts_settings.get("provider", "google")).lower()
    return ResolvedTTSConfig(
        provider=provider,
        api_key=_resolve_api_key(provider, settings_user),
        voice=tts_settings.get("selected_voice", "Puck"),
        elevenlabs_voice_id=tts_settings.get("elevenlabs_voice_id", ""),
        use_vocal_tags=_coerce_bool(tts_settings.get("use_vocal_tags"), True),
        use_streaming=_coerce_bool(tts_settings.get("use_streaming"), False),
        model=_resolve_model(provider, tts_settings.get("selected_model")),
    )


def _resolve_elevenlabs_voice(config: ResolvedTTSConfig, voice_override: Optional[str]) -> str:
    """Per-character voices are an ElevenLabs feature; Gemini always uses the narrator voice."""
    if config.provider == NPC_VOICE_PROVIDER and looks_like_voice_id(voice_override):
        return str(voice_override)
    if voice_override:
        logger.debug(
            "Ignoring voice override '%s' for provider %s.", voice_override, config.provider
        )
    return config.elevenlabs_voice_id


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

    try:
        audio_url = await TTSEngine.generate_speech(
            text=payload.text,
            provider=config.provider,
            voice=config.voice,
            elevenlabs_voice_id=_resolve_elevenlabs_voice(config, payload.voice_override),
            use_vocal_tags=config.use_vocal_tags,
            api_key=config.api_key,
            adventure_id=adventure_id,
            session_id=session_id,
            model_name=config.model,
            language=payload.language,
            use_streaming=config.use_streaming,
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
        raise HTTPException(status_code=502, detail=f"TTS Provider error: {exc}") from exc

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
        return {"status": "error", "message": f"TTS provider error: {exc}"}
    if not audio_url:
        return {"status": "error", "message": "Failed to generate test audio."}
    return {"status": "success", "audio_url": audio_url}


@router.get("/voices")
async def list_tts_voices(
    provider: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Voices from the voice list for per-character speech. Only ElevenLabs supports them.

    ``provider`` lets the settings form list ElevenLabs voices before the provider is saved.
    """
    owner = await _resolve_tts_settings_source_user(db, current_user)
    active = str((owner.tts_settings or {}).get("provider") or "google").lower()
    requested = (provider or active).lower()
    if requested != NPC_VOICE_PROVIDER:
        return {"provider": requested, "supports_npc_voices": False, "voices": []}
    return {"provider": requested, "supports_npc_voices": True, "voices": load_voice_catalog()}
