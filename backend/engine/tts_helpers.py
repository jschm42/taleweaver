"""Provider-agnostic helpers for the TTS engine.

Covers retry/backoff timing, request pacing, vocal-tag text transforms,
Gemini audio payload decoding, and safe audio file persistence.
"""

import asyncio
import base64
import binascii
import logging
import math
import os
import random
import struct
import uuid
from typing import Optional

import httpx

from backend.core.config import settings
from backend.utils.path_security import (
    ensure_within_data_dir,
    local_path_to_data_url,
    safe_data_path,
    sanitize_path_component,
)

logger = logging.getLogger(__name__)

_TTS_REQUEST_LOCK = asyncio.Lock()
_TTS_PACING_STATE = {"last_request_at": 0.0}
_DEFAULT_L16_MIME = "audio/l16;rate=24000"


def _parse_retry_after_seconds(response: httpx.Response) -> Optional[float]:
    header = response.headers.get("Retry-After")
    if not header:
        return None
    try:
        value = float(header.strip())
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    return min(value, 60.0)


def _parse_retry_delay_text(retry_delay: object) -> Optional[float]:
    if not isinstance(retry_delay, str):
        return None
    delay_text = retry_delay.strip().lower().removesuffix("s")
    try:
        delay = float(delay_text)
    except (TypeError, ValueError):
        return None
    if delay <= 0:
        return None
    return min(delay, 60.0)


def _parse_google_retry_delay_seconds(response: httpx.Response) -> Optional[float]:
    """Extract retry delay from Google error details when available.

    Expected shape includes retry info entries like:
    {"error": {"details": [{"retryDelay": "12s"}]}}
    """
    try:
        payload = response.json()
    except ValueError:
        return None

    details = (payload.get("error") or {}).get("details") or []
    if not isinstance(details, list):
        return None

    for detail in details:
        if not isinstance(detail, dict):
            continue
        delay = _parse_retry_delay_text(detail.get("retryDelay"))
        if delay is not None:
            return delay

    return None


def _backoff_delay_seconds(attempt: int) -> float:
    base_delay = float(getattr(settings, "TTS_RATE_LIMIT_BASE_DELAY_SECONDS", 2.0))
    max_delay = float(getattr(settings, "TTS_RATE_LIMIT_MAX_DELAY_SECONDS", 30.0))
    return min(base_delay * (2 ** max(0, attempt - 1)), max_delay)


def _compute_429_retry_delay_seconds(response: httpx.Response, attempt: int) -> float:
    explicit_delay = _parse_retry_after_seconds(response)
    if explicit_delay is None:
        explicit_delay = _parse_google_retry_delay_seconds(response)

    max_delay = float(getattr(settings, "TTS_RATE_LIMIT_MAX_DELAY_SECONDS", 30.0))
    delay = explicit_delay if explicit_delay is not None else _backoff_delay_seconds(attempt)

    jitter_low = float(getattr(settings, "TTS_RATE_LIMIT_JITTER_MIN", 0.9))
    jitter_high = float(getattr(settings, "TTS_RATE_LIMIT_JITTER_MAX", 1.15))
    if jitter_low > jitter_high:
        jitter_low, jitter_high = jitter_high, jitter_low
    jitter = random.uniform(max(0.1, jitter_low), max(jitter_low, jitter_high))
    return max(0.2, min(delay * jitter, max_delay))


async def _wait_for_tts_request_slot() -> None:
    """Smooth bursty frontend segment requests before hitting provider limits."""
    min_interval_ms = float(getattr(settings, "TTS_REQUEST_MIN_INTERVAL_MS", 650))
    min_interval = max(0.0, min_interval_ms / 1000.0)
    if min_interval == 0:
        return

    loop = asyncio.get_running_loop()
    async with _TTS_REQUEST_LOCK:
        now = loop.time()
        wait_seconds = (_TTS_PACING_STATE["last_request_at"] + min_interval) - now
        if wait_seconds > 0:
            await asyncio.sleep(wait_seconds)
            now = loop.time()
        _TTS_PACING_STATE["last_request_at"] = now


def _tts_timeout_seconds(text: str) -> float:
    """Compute timeout for TTS requests based on text length.

    Longer single-block narrations need more upstream synthesis time.
    """
    base_timeout = float(getattr(settings, "TTS_TIMEOUT_SECONDS", 120))
    max_timeout = float(getattr(settings, "TTS_TIMEOUT_MAX_SECONDS", 300))
    per_1k_chars = float(getattr(settings, "TTS_TIMEOUT_PER_1K_CHARS", 20))

    text_length = len(text or "")
    chunks = math.ceil(text_length / 1000) if text_length > 0 else 0
    timeout = base_timeout + (chunks * per_1k_chars)
    return max(30.0, min(timeout, max_timeout))


_TAG_DEPTH_KEYS = {
    "[": "square",
    "]": "square",
    "(": "paren",
    ")": "paren",
    "<": "angle",
    ">": "angle",
}
_TAG_OPENERS = frozenset("[(<")


def _strip_vocal_tags(text: str) -> str:
    """Remove simple bracketed vocal tags without regex backtracking."""
    if not text:
        return ""

    result: list[str] = []
    depth = {"square": 0, "paren": 0, "angle": 0}

    for char in text:
        kind = _TAG_DEPTH_KEYS.get(char)
        if kind and char in _TAG_OPENERS:
            depth[kind] += 1
            continue
        if kind and depth[kind] > 0:
            depth[kind] -= 1
            continue
        if not any(depth.values()):
            result.append(char)

    return "".join(result).strip()


def _convert_brackets_to_angles(text: str) -> str:
    """Convert [tag] to <tag> safely in linear time without regular expressions."""
    if not text or "[" not in text:
        return text

    result: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        end = text.find("]", i + 1) if text[i] == "[" else -1
        inner = text[i + 1 : end] if end != -1 else ""
        # Vocal tag must be non-empty, single-line, and cannot contain nested brackets
        if inner and "\n" not in inner and "[" not in inner:
            result.append(f"<{inner}>")
            i = end + 1
            continue
        result.append(text[i])
        i += 1
    return "".join(result)


def _add_wav_header(pcm_data: bytes, sample_rate: int = 24000) -> bytes:
    """Adds a WAV header to raw PCM data (Linear 16-bit)."""
    num_channels = 1
    bits_per_sample = 16
    byte_rate = sample_rate * num_channels * bits_per_sample // 8
    block_align = num_channels * bits_per_sample // 8
    data_length = len(pcm_data)

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_length,
        b"WAVE",
        b"fmt ",
        16,  # Subchunk1Size
        1,  # AudioFormat (PCM)
        num_channels,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample,
        b"data",
        data_length,
    )
    return header + pcm_data


def _parse_l16_sample_rate(mime_type: str) -> int:
    """Extract sample rate from L16 MIME type, defaulting to 24000 Hz.

    Example input: "audio/L16;rate=24000".
    """
    default_rate = 24000
    if not mime_type:
        return default_rate

    for raw_part in mime_type.split(";"):
        part = raw_part.strip().lower()
        if not part.startswith("rate="):
            continue
        try:
            value = int(part.split("=", 1)[1])
        except (TypeError, ValueError, IndexError):
            return default_rate
        return value if value > 0 else default_rate

    return default_rate


def _collect_inline_audio(parts: list) -> tuple[list[bytes], Optional[str]]:
    """Aggregate all non-empty inline audio chunks and the first chunk's MIME type.

    Some TTS responses include multiple inlineData parts where the first
    part may have empty data.
    """
    audio_chunks: list[bytes] = []
    mime_type: Optional[str] = None

    for part in parts:
        inline_data = part.get("inlineData") or {}
        candidate_b64 = inline_data.get("data")
        if not isinstance(candidate_b64, str) or not candidate_b64.strip():
            continue

        candidate_mime = str(inline_data.get("mimeType") or "").strip()
        mime_type = mime_type or candidate_mime
        try:
            audio_chunks.append(base64.b64decode(candidate_b64))
        except (binascii.Error, ValueError, TypeError):
            logger.warning("Failed to decode inline audio chunk (mime=%s).", candidate_mime)

    return audio_chunks, mime_type


def _extract_gemini_audio(data: dict) -> Optional[tuple[bytes, str]]:
    """Decode a Gemini TTS response into (audio_bytes, file_extension)."""
    candidates = data.get("candidates", [])
    if not candidates:
        logger.error("No candidates returned from Gemini TTS: %s", data)
        return None

    parts = (candidates[0].get("content") or {}).get("parts") or []
    audio_chunks, mime_type = _collect_inline_audio(parts)
    audio_bytes = b"".join(audio_chunks)
    if not audio_bytes:
        logger.error("No non-empty audio chunk found in Gemini response.")
        return None

    mime_type = mime_type or _DEFAULT_L16_MIME
    normalized_mime_type = mime_type.lower()

    if "audio/l16" in normalized_mime_type:
        # Gemini returns raw little-endian PCM for audio/l16; wrap it in a WAV header.
        return _add_wav_header(audio_bytes, sample_rate=_parse_l16_sample_rate(mime_type)), "wav"
    if "mp3" in normalized_mime_type:
        return audio_bytes, "mp3"
    if "ogg" in normalized_mime_type:
        return audio_bytes, "ogg"
    return audio_bytes, "wav"


def _resolve_audio_output_dir(session_id: Optional[str] = None) -> str:
    """Return target directory for generated audio.

    If session_id is known, store clips under that concrete session.
    Otherwise, keep legacy global fallback for compatibility.
    """
    safe_session_id = sanitize_path_component(session_id)
    if session_id and not safe_session_id:
        logger.warning("Invalid session_id for audio output path; using global audio fallback.")
    if safe_session_id:
        return safe_data_path("adventures", "sessions", safe_session_id, "tts")
    return safe_data_path("audio")


def _build_audio_output_path(
    adventure_id: Optional[str],
    session_id: Optional[str],
    extension: str,
) -> str:
    """Create a validated output file path for synthesized audio."""
    _ = adventure_id
    normalized_ext = str(extension or "wav").strip().lower()
    if normalized_ext not in {"mp3", "wav", "ogg"}:
        normalized_ext = "wav"

    audio_dir = ensure_within_data_dir(_resolve_audio_output_dir(session_id=session_id))
    os.makedirs(audio_dir, exist_ok=True)
    filename = f"{uuid.uuid4()}.{normalized_ext}"
    return ensure_within_data_dir(os.path.join(audio_dir, filename))


def _write_audio_file(
    audio_bytes: bytes,
    adventure_id: Optional[str],
    session_id: Optional[str],
    extension: str,
) -> str:
    """Persist synthesized audio and return its public /data URL."""
    filepath = _build_audio_output_path(adventure_id, session_id, extension)
    with open(filepath, "wb") as f:
        f.write(audio_bytes)
    return local_path_to_data_url(filepath)
