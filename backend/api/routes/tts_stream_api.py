"""Streaming speech for ElevenLabs: audio plays while it is still being generated.

An ``<audio>`` element cannot send the auth header, so playback takes two steps:
``POST /tts/stream`` (authenticated) checks the settings and parks the request under a random,
single-use token; ``GET /tts/stream/{token}`` relays the ElevenLabs audio stream for that token.
"""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass
from typing import Final, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.tts_api import (
    _rate_limit_http_exception,
    _resolve_elevenlabs_voice,
    _resolve_tts_config,
)
from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.engine.elevenlabs_stream import open_elevenlabs_stream
from backend.engine.tts_helpers import TTSProviderError, TTSRateLimitError, TTSTimeoutError
from backend.engine.tts_tag_format import prepare_elevenlabs_text
from backend.engine.voice_casting import NPC_VOICE_PROVIDER
from backend.models.user import User

router = APIRouter(prefix="/tts", tags=["TTS"])

_TOKEN_TTL_SECONDS: Final = 120
_MAX_PENDING: Final = 256


@dataclass(frozen=True)
class _PendingStream:
    text: str
    voice_id: str
    model_id: str
    api_key: str
    expires_at: float


_pending: dict[str, _PendingStream] = {}


class TTSStreamPayload(BaseModel):
    text: str = Field(default="", max_length=5000)
    voice_override: Optional[str] = Field(default=None, max_length=100)


def _drop_expired(now: float) -> None:
    for token in [t for t, p in _pending.items() if p.expires_at <= now]:
        _pending.pop(token, None)
    while len(_pending) >= _MAX_PENDING:
        _pending.pop(next(iter(_pending)))


@router.post("/stream")
async def prepare_tts_stream(
    payload: TTSStreamPayload = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Returns a single-use token for streaming this text; only used with ElevenLabs."""
    config = await _resolve_tts_config(db, current_user, require_enabled=True)
    if config.provider != NPC_VOICE_PROVIDER:
        raise HTTPException(
            status_code=409, detail="Streaming playback is used with ElevenLabs only."
        )
    text = prepare_elevenlabs_text(payload.text, config.model, config.use_vocal_tags)
    if not text.strip():
        raise HTTPException(status_code=400, detail="Text is required for TTS generation.")

    now = time.monotonic()
    _drop_expired(now)
    token = secrets.token_urlsafe(24)
    _pending[token] = _PendingStream(
        text=text,
        voice_id=_resolve_elevenlabs_voice(config, payload.voice_override),
        model_id=config.model,
        api_key=str(config.api_key),
        expires_at=now + _TOKEN_TTL_SECONDS,
    )
    return {"token": token}


@router.get("/stream/{token}")
async def stream_tts(token: str):
    """Relays the audio for a prepared token (no auth header: the token is the credential)."""
    pending = _pending.pop(token, None)
    if not pending or pending.expires_at <= time.monotonic():
        raise HTTPException(status_code=404, detail="Unknown or expired speech stream.")
    try:
        chunks = await open_elevenlabs_stream(
            pending.text, pending.voice_id, pending.api_key, pending.model_id
        )
    except TTSRateLimitError as exc:
        raise _rate_limit_http_exception(exc) from exc
    except TTSTimeoutError as exc:
        raise HTTPException(status_code=504, detail="TTS generation timed out.") from exc
    except TTSProviderError as exc:
        raise HTTPException(status_code=502, detail=f"TTS Provider error: {exc}") from exc
    return StreamingResponse(chunks, media_type="audio/mpeg", headers={"Cache-Control": "no-store"})
