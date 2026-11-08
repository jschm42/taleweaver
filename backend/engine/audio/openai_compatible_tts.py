"""Speech through any server with the OpenAI speech API (``POST {base}/audio/speech``).

Works with local servers (Kokoro-FastAPI, Speaches, LocalAI, openedai-speech, ...) as well as
hosted ones (OpenAI, OpenRouter, other gateways). The base URL ends in ``/v1`` and goes through
the same endpoint policy as the OpenAI-compatible LLM provider (``validate_custom_url``). The key
is optional: the vault's ``custom_openai`` key, else the OpenRouter key for openrouter.ai URLs.

Models and voices are discovered where the server offers it (``GET /models``, Kokoro-style
``GET /audio/voices``, OpenRouter's ``supported_voices``); any id can still be typed in.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final, Optional
from urllib.parse import urlsplit

import httpx
from fastapi import HTTPException

from backend.core.api_keys import has_api_key, is_blocked, resolve_api_key
from backend.core.custom_openai import validate_custom_url
from backend.engine.audio.tts_helpers import (
    TTSProviderError,
    TTSTimeoutError,
    _add_wav_header,
    _extract_error_detail,
    _parse_l16_sample_rate,
    _tts_timeout_seconds,
)

logger = logging.getLogger(__name__)

OPENAI_COMPATIBLE_PROVIDER: Final = "custom_openai"
RESPONSE_FORMATS: Final = ("mp3", "wav", "pcm")
DEFAULT_RESPONSE_FORMAT: Final = "mp3"
_DISCOVERY_TIMEOUT_SECONDS: Final = 15.0
# Voices of OpenAI's speech models; suggested for OpenAI models when the server lists none.
# Other models (e.g. Fish Audio via OpenRouter) reject these names.
OPENAI_DEFAULT_VOICES: Final = (
    "alloy",
    "ash",
    "ballad",
    "cedar",
    "coral",
    "echo",
    "fable",
    "marin",
    "nova",
    "onyx",
    "sage",
    "shimmer",
    "verse",
)


@dataclass(frozen=True)
class SpeechEndpoint:
    """Where and how to synthesize: validated per request, never trusted from storage."""

    base_url: str
    model: str
    voice: str
    api_key: Optional[str] = None
    response_format: str = DEFAULT_RESPONSE_FORMAT
    instructions: str = ""


def checked_base_url(base_url: object) -> str:
    """The validated base URL (``.../v1``); ``TTSProviderError`` when the policy rejects it."""
    url = str(base_url or "").strip()
    if not url:
        raise TTSProviderError("Configure the Base URL of the OpenAI-compatible speech server.")
    try:
        return validate_custom_url(url)
    except HTTPException as exc:
        raise TTSProviderError(f"Speech server URL rejected: {exc.detail}") from exc


def normalize_response_format(value: object) -> str:
    fmt = str(value or "").strip().lower()
    return fmt if fmt in RESPONSE_FORMATS else DEFAULT_RESPONSE_FORMAT


def resolve_speech_api_key(keys: Optional[Mapping[str, str]], base_url: str) -> Optional[str]:
    """Same rule as the OpenAI-compatible LLM: own key, else OpenRouter's for openrouter.ai.

    Raises ``PersonalKeyRequiredError`` when the ``custom_openai`` key is blocked for the user.
    """
    if has_api_key(keys, OPENAI_COMPATIBLE_PROVIDER) or is_blocked(
        keys, OPENAI_COMPATIBLE_PROVIDER
    ):
        return resolve_api_key(keys, OPENAI_COMPATIBLE_PROVIDER)
    if _is_openrouter(base_url) and has_api_key(keys, "openrouter"):
        return resolve_api_key(keys, "openrouter")
    return None


def _is_openrouter(base_url: str) -> bool:
    """Host check, so a URL merely containing "openrouter.ai" never receives that key."""
    host = (urlsplit(base_url).hostname or "").lower()
    return host == "openrouter.ai" or host.endswith(".openrouter.ai")


def _headers(api_key: Optional[str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"} if api_key else {}


def _speech_payload(text: str, endpoint: SpeechEndpoint) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": endpoint.model,
        "input": text,
        "response_format": endpoint.response_format,
    }
    # Optional: without it the model speaks with its default voice.
    if endpoint.voice:
        payload["voice"] = endpoint.voice
    if endpoint.instructions:
        payload["instructions"] = endpoint.instructions
    return payload


def _require_model(endpoint: SpeechEndpoint) -> None:
    if not endpoint.model:
        raise TTSProviderError("Choose a speech model for the OpenAI-compatible provider.")


async def synthesize_speech(text: str, endpoint: SpeechEndpoint) -> tuple[bytes, str]:
    """Audio bytes and file extension; raises ``TTSProviderError`` / ``TTSTimeoutError``."""
    _require_model(endpoint)
    base = checked_base_url(endpoint.base_url)
    timeout = httpx.Timeout(_tts_timeout_seconds(text), connect=10.0)
    logger.info(
        "[TTS] OpenAI-compatible request model=%s voice=%s chars=%d",
        endpoint.model,
        endpoint.voice or "(model default)",
        len(text),
    )
    try:
        async with httpx.AsyncClient(follow_redirects=False) as client:
            response = await client.post(
                f"{base}/audio/speech",
                json=_speech_payload(text, endpoint),
                headers=_headers(endpoint.api_key),
                timeout=timeout,
            )
    except httpx.TimeoutException as exc:
        raise TTSTimeoutError("Timed out while generating speech.") from exc
    except httpx.HTTPError as exc:
        raise TTSProviderError(f"Speech server not reachable at {base}.") from exc
    if response.status_code != 200:
        logger.error("Speech server error %s: %s", response.status_code, response.text[:500])
        raise TTSProviderError(
            _extract_error_detail(response, f"Speech request failed ({response.status_code})")
        )
    content_type = response.headers.get("content-type", "")
    return _as_audio_file(response.content, endpoint.response_format, content_type)


def _as_audio_file(audio: bytes, response_format: str, content_type: str = "") -> tuple[bytes, str]:
    """Raw PCM becomes WAV with the server's rate (``audio/pcm;rate=44100``; else 24 kHz)."""
    if response_format == "pcm":
        return _add_wav_header(audio, _parse_l16_sample_rate(content_type)), "wav"
    return audio, response_format


async def _get_json(url: str, api_key: Optional[str], params: Optional[dict] = None) -> Any:
    async with httpx.AsyncClient(follow_redirects=False) as client:
        response = await client.get(
            url, headers=_headers(api_key), params=params, timeout=_DISCOVERY_TIMEOUT_SECONDS
        )
    response.raise_for_status()
    return response.json()


def _model_items(payload: Any) -> list[dict[str, Any]]:
    items = payload.get("data") if isinstance(payload, dict) else None
    return [item for item in items or [] if isinstance(item, dict) and item.get("id")]


def _is_speech_model(item: dict[str, Any]) -> bool:
    """OpenRouter tags output modalities; plain OpenAI-style lists carry no such data."""
    modalities = (item.get("architecture") or {}).get("output_modalities")
    return not isinstance(modalities, list) or "speech" in modalities


async def _speech_model_items(base: str, api_key: Optional[str]) -> list[dict[str, Any]]:
    # OpenRouter filters by this parameter; other servers ignore it.
    payload = await _get_json(f"{base}/models", api_key, {"output_modalities": "speech"})
    return [item for item in _model_items(payload) if _is_speech_model(item)]


async def list_speech_models(base_url: str, api_key: Optional[str]) -> list[str]:
    """Model ids from ``GET /models`` (speech models only where the server says which)."""
    base = checked_base_url(base_url)
    try:
        items = await _speech_model_items(base, api_key)
    except (httpx.HTTPError, ValueError) as exc:
        raise TTSProviderError(
            f"Could not load models from {base}. Enter the model id manually."
        ) from exc
    return sorted({str(item["id"]) for item in items})


def _voice_ids(raw: Any) -> list[str]:
    """Voice ids from ``["af_heart", ...]`` or ``[{"id"|"voice_id"|"name": ...}, ...]``."""
    voices = {_voice_id(entry) for entry in raw or []}
    return sorted(v for v in voices if v.strip())


def _voice_id(entry: Any) -> str:
    if isinstance(entry, dict):
        entry = entry.get("id") or entry.get("voice_id") or entry.get("name")
    return entry if isinstance(entry, str) else ""


async def _server_voice_list(base: str, api_key: Optional[str]) -> list[str]:
    """Kokoro-FastAPI and similar servers list voices at ``/audio/voices``."""
    try:
        payload = await _get_json(f"{base}/audio/voices", api_key)
    except (httpx.HTTPError, ValueError):
        return []
    return _voice_ids(payload.get("voices") if isinstance(payload, dict) else payload)


async def _model_voice_list(base: str, api_key: Optional[str], model: str) -> list[str]:
    """OpenRouter publishes ``supported_voices`` per model in its model list."""
    if not model:
        return []
    try:
        items = await _speech_model_items(base, api_key)
    except (httpx.HTTPError, ValueError):
        return []
    match = next((item for item in items if item.get("id") == model), {})
    return _voice_ids(match.get("supported_voices"))


def _is_openai_speech_model(base: str, model: str) -> bool:
    """OpenAI's own API, or an OpenAI model behind a gateway (``openai/gpt-4o-mini-tts``)."""
    host = (urlsplit(base).hostname or "").lower()
    name = model.lower()
    return host == "api.openai.com" or name.startswith(("openai/", "tts-1", "gpt-4o-mini-tts"))


async def list_speech_voices(
    base_url: str, api_key: Optional[str], model: str = ""
) -> tuple[list[str], str]:
    """``(voices, source)``: ``server``, ``model``, ``suggested`` (OpenAI's voice names, for
    OpenAI models only) or ``none`` (leave the voice empty for the model's default voice).
    """
    base = checked_base_url(base_url)
    voices = await _server_voice_list(base, api_key)
    if voices:
        return voices, "server"
    voices = await _model_voice_list(base, api_key, model)
    if voices:
        return voices, "model"
    if _is_openai_speech_model(base, model):
        return list(OPENAI_DEFAULT_VOICES), "suggested"
    return [], "none"
