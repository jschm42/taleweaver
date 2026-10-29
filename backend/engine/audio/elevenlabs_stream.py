"""ElevenLabs speech over the streaming endpoint.

``open_elevenlabs_stream`` checks the upstream status before the first byte is relayed, so errors
(rate limits, bad voice ids) still become proper HTTP errors instead of a broken audio stream.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Final

import httpx

from backend.engine.tts_helpers import (
    TTSProviderError,
    TTSRateLimitError,
    TTSTimeoutError,
    _compute_429_retry_delay_seconds,
    _extract_error_detail,
)

logger = logging.getLogger(__name__)

ELEVENLABS_STREAM_URL: Final = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
OUTPUT_FORMAT: Final = "mp3_44100_128"
DEFAULT_MODEL: Final = "eleven_v4"
# v3/v4 accept only 0.0, 0.5 or 1.0 for stability; 0.5 is the natural setting.
_VOICE_SETTINGS: Final = {"stability": 0.5, "similarity_boost": 0.75}


async def _relay(client: httpx.AsyncClient, response: httpx.Response) -> AsyncIterator[bytes]:
    try:
        async for chunk in response.aiter_bytes():
            if chunk:
                yield chunk
    finally:
        await response.aclose()
        await client.aclose()


async def _raise_for_status(response: httpx.Response) -> None:
    await response.aread()
    if response.status_code == 429:
        raise TTSRateLimitError(
            "ElevenLabs TTS rate limit reached.",
            retry_after_seconds=_compute_429_retry_delay_seconds(response, 1),
        )
    logger.error("ElevenLabs TTS error %s: %s", response.status_code, response.text)
    raise TTSProviderError(
        _extract_error_detail(
            response, f"ElevenLabs TTS request failed with status {response.status_code}"
        )
    )


async def open_elevenlabs_stream(
    text: str, voice_id: str, api_key: str, model_id: str = DEFAULT_MODEL
) -> AsyncIterator[bytes]:
    """Starts streaming synthesis and returns the MP3 byte chunks as they arrive."""
    if not voice_id:
        raise TTSProviderError("No ElevenLabs voice selected.")
    client = httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0))
    request = client.build_request(
        "POST",
        ELEVENLABS_STREAM_URL.format(voice_id=voice_id),
        params={"output_format": OUTPUT_FORMAT},
        headers={"Accept": "audio/mpeg", "xi-api-key": api_key},
        json={
            "text": text,
            "model_id": model_id or DEFAULT_MODEL,
            "voice_settings": _VOICE_SETTINGS,
        },
    )
    try:
        response = await client.send(request, stream=True)
    except httpx.TimeoutException as exc:
        await client.aclose()
        raise TTSTimeoutError("Timed out while starting speech.") from exc
    except httpx.HTTPError as exc:
        await client.aclose()
        raise TTSProviderError("Could not reach ElevenLabs.") from exc

    if response.status_code != 200:
        try:
            await _raise_for_status(response)
        finally:
            await response.aclose()
            await client.aclose()
    return _relay(client, response)


async def synthesize_elevenlabs_bytes(
    text: str, voice_id: str, api_key: str, model_id: str = DEFAULT_MODEL
) -> bytes:
    """The whole clip at once (downloads and fallback playback), over the same streaming endpoint."""
    chunks = await open_elevenlabs_stream(text, voice_id, api_key, model_id)
    try:
        return b"".join([chunk async for chunk in chunks])
    except httpx.TimeoutException as exc:
        raise TTSTimeoutError("Timed out while generating speech.") from exc
