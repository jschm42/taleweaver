import os
import uuid
import base64
import logging
import struct
import math
import asyncio
import random
import httpx
from typing import Optional
from backend.core.config import settings

logger = logging.getLogger(__name__)

_TTS_REQUEST_LOCK = asyncio.Lock()
_TTS_PACING_STATE = {"last_request_at": 0.0}


class TTSTimeoutError(RuntimeError):
    """Raised when the upstream TTS request times out."""


class TTSRateLimitError(RuntimeError):
    """Raised when upstream TTS provider rate-limits requests (HTTP 429)."""

    def __init__(self, message: str, retry_after_seconds: Optional[float] = None):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


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
        retry_delay = detail.get("retryDelay")
        if not isinstance(retry_delay, str):
            continue
        delay_text = retry_delay.strip().lower()
        if delay_text.endswith("s"):
            delay_text = delay_text[:-1]
        try:
            delay = float(delay_text)
        except (TypeError, ValueError):
            continue
        if delay > 0:
            return min(delay, 60.0)

    return None


def _compute_429_retry_delay_seconds(response: httpx.Response, attempt: int) -> float:
    explicit_delay = _parse_retry_after_seconds(response)
    if explicit_delay is None:
        explicit_delay = _parse_google_retry_delay_seconds(response)

    base_delay = float(getattr(settings, "TTS_RATE_LIMIT_BASE_DELAY_SECONDS", 2.0))
    max_delay = float(getattr(settings, "TTS_RATE_LIMIT_MAX_DELAY_SECONDS", 30.0))
    fallback_delay = min(base_delay * (2 ** max(0, attempt - 1)), max_delay)
    delay = explicit_delay if explicit_delay is not None else fallback_delay

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

def _add_wav_header(pcm_data: bytes, sample_rate: int = 24000) -> bytes:
    """Adds a WAV header to raw PCM data (Linear 16-bit)."""
    num_channels = 1
    bits_per_sample = 16
    byte_rate = sample_rate * num_channels * bits_per_sample // 8
    block_align = num_channels * bits_per_sample // 8
    data_length = len(pcm_data)
    
    header = struct.pack('<4sI4s4sIHHIIHH4sI',
        b'RIFF',
        36 + data_length,
        b'WAVE',
        b'fmt ',
        16, # Subchunk1Size
        1,  # AudioFormat (PCM)
        num_channels,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample,
        b'data',
        data_length
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


def _resolve_audio_output_dir(adventure_id: Optional[str], session_id: Optional[str] = None) -> str:
    """Return target directory for generated audio.

    If adventure_id + session_id are known, store clips under that concrete session.
    Otherwise, keep legacy global fallback for compatibility.
    """
    if session_id:
        return os.path.join(settings.DATA_DIR, "adventures", "sessions", session_id, "tts")
    return os.path.join(settings.DATA_DIR, "audio")


def _resolve_audio_public_url(adventure_id: Optional[str], filename: str, session_id: Optional[str] = None) -> str:
    """Return static URL for generated audio based on storage location."""
    if session_id:
        return f"/data/adventures/sessions/{session_id}/tts/{filename}"
    return f"/data/audio/{filename}"


def _public_url_from_filepath(filepath: str) -> str:
    """Build a stable /data URL from the actual file path on disk."""
    data_root = os.path.abspath(settings.DATA_DIR)
    abs_path = os.path.abspath(filepath)
    rel_path = os.path.relpath(abs_path, data_root)
    return f"/data/{rel_path.replace(os.sep, '/')}"

class TTSEngine:
    """
    Handles speech generation using Google Gemini 1.5 Flash (Preview) TTS API.
    """

    @staticmethod
    async def generate_speech(
        text: str,
        voice: str = "Puck",
        speaker_voices: Optional[dict[str, str]] = None,
        api_key: Optional[str] = None,
        adventure_id: Optional[str] = None,
        session_id: Optional[str] = None,
        scene_description: Optional[str] = None,
        style_description: Optional[str] = None,
        model_name: str = "gemini-3.1-flash-tts-preview",
        title: Optional[str] = None,
        scene_name: Optional[str] = None,
        tone: Optional[str] = None,
        include_style_context: bool = True,
        **_unused_kwargs: object,
    ) -> Optional[str]:
        """
        Generates speech and returns the relative URL to the audio file.
        """
        if not api_key:
            logger.error("No Google API key provided for TTS.")
            return None

        valid_speaker_voices = {
            str(speaker).strip(): str(voice_name).strip()
            for speaker, voice_name in (speaker_voices or {}).items()
            if str(speaker).strip() and str(voice_name).strip()
        }
        if len(valid_speaker_voices) > 2:
            # Gemini multi-speaker supports at most two speakers.
            limited_items = list(valid_speaker_voices.items())[:2]
            valid_speaker_voices = dict(limited_items)
            logger.info(
                "Limiting multi-speaker TTS to first two speakers: %s",
                list(valid_speaker_voices.keys()),
            )

        # Use a structured prompt format (similar to Gemini SDK examples) so
        # voice/style instructions are applied more reliably.
        prompt_parts = [
            "Read the following transcript based on the audio profile and director's note.",
            "",
            "# Audio Profile",
            "A helpful and professional personal assistant.",
            "",
            "# Director's note",
        ]

        director_notes: list[str] = []
        if tone:
            director_notes.append(f"Style: {tone}.")
        if include_style_context and style_description:
            director_notes.append(f"Sample Context: {style_description}")
        if not director_notes:
            director_notes.append("Style: Natural and clear.")
        prompt_parts.append(" ".join(director_notes))

        if title or scene_name:
            location = " / ".join([part for part in [title, scene_name] if part])
            if location:
                prompt_parts.extend(["", "## Scene:", location])
        elif scene_description:
            prompt_parts.extend(["", "## Scene:", scene_description])

        if include_style_context and style_description:
            prompt_parts.extend(["", "## Sample Context:", style_description])

        if len(valid_speaker_voices) >= 2:
            speakers = ", ".join(valid_speaker_voices.keys())
            prompt_parts.append(
                f"Use multi-speaker synthesis. Match speaker labels exactly as written: {speakers}."
            )

        prompt_parts.append(
            "The transcript may contain inline voice-direction tags in square brackets, "
            "e.g. [shouting], [whispers], [very fast], [very slow], [excited], [sarcastically, one painfully slow word at a time]. "
            "Honour these as acting cues until the next paragraph."
        )
        prompt_parts.append("")
        prompt_parts.append("## Transcript:")
        prompt_parts.append(text)
        user_content = "\n".join(prompt_parts)

        # Force log to console for the user
        print(f"DEBUG: TTS Prompt for model '{model_name}':\n{user_content}")

        # Note: Using generateContent with responseModalities: ["AUDIO"]
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"

        speech_config: dict = {}
        if len(valid_speaker_voices) >= 2:
            speech_config["multiSpeakerVoiceConfig"] = {
                "speakerVoiceConfigs": [
                    {
                        "speaker": speaker,
                        "voiceConfig": {
                            "prebuiltVoiceConfig": {"voiceName": voice_name}
                        },
                    }
                    for speaker, voice_name in valid_speaker_voices.items()
                ]
            }
        else:
            selected_voice = voice
            if len(valid_speaker_voices) == 1:
                selected_voice = next(iter(valid_speaker_voices.values()))
            speech_config["voiceConfig"] = {
                "prebuiltVoiceConfig": {
                    "voiceName": selected_voice
                }
            }

        selected_voice_for_log = None
        if len(valid_speaker_voices) == 0:
            selected_voice_for_log = voice
        elif len(valid_speaker_voices) == 1:
            selected_voice_for_log = next(iter(valid_speaker_voices.values()))

        logger.info(
            "TTS request model=%s multi_speaker=%s voice=%s speakers=%s include_style=%s",
            model_name,
            len(valid_speaker_voices) >= 2,
            selected_voice_for_log,
            list(valid_speaker_voices.keys()),
            include_style_context,
        )

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": user_content
                        }
                    ]
                }
            ],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": speech_config,
            }
        }

        try:
            timeout_seconds = _tts_timeout_seconds(text)
            timeout = httpx.Timeout(timeout_seconds, connect=20.0)
            max_attempts = int(getattr(settings, "TTS_RATE_LIMIT_MAX_RETRIES", 5))
            max_attempts = max(1, min(max_attempts, 10))
            data: Optional[dict] = None

            async with httpx.AsyncClient() as client:
                for attempt in range(1, max_attempts + 1):
                    await _wait_for_tts_request_slot()
                    response = await client.post(url, json=payload, timeout=timeout)

                    if response.status_code == 429:
                        delay = _compute_429_retry_delay_seconds(response, attempt)
                        logger.warning(
                            "Gemini TTS rate-limited (429), attempt %d/%d, retrying in %.1fs (model=%s, chars=%d).",
                            attempt,
                            max_attempts,
                            delay,
                            model_name,
                            len(text or ""),
                        )

                        if attempt < max_attempts:
                            await asyncio.sleep(delay)
                            continue

                        raise TTSRateLimitError(
                            "Gemini TTS rate limit reached.",
                            retry_after_seconds=delay,
                        )

                    if response.status_code != 200:
                        logger.error("Gemini TTS Error %s: %s", response.status_code, response.text)
                    response.raise_for_status()
                    data = response.json()
                    break

            if data is None:
                raise TTSRateLimitError("Gemini TTS rate limit reached.")

            candidates = data.get("candidates", [])
            if not candidates:
                logger.error("No candidates returned from Gemini TTS: %s", data)
                return None

            content = candidates[0].get("content") or {}
            parts = content.get("parts") or []

            # Some TTS responses include multiple inlineData parts where the first
            # part may have empty data. Aggregate all non-empty audio chunks.
            audio_chunks: list[bytes] = []
            mime_type: Optional[str] = None

            for part in parts:
                inline_data = part.get("inlineData") or {}
                if not inline_data:
                    continue

                candidate_mime = str(inline_data.get("mimeType") or "").strip()
                candidate_b64 = inline_data.get("data")
                if not isinstance(candidate_b64, str) or not candidate_b64.strip():
                    continue

                if mime_type is None:
                    mime_type = candidate_mime

                try:
                    audio_chunks.append(base64.b64decode(candidate_b64))
                except Exception:
                    logger.warning("Failed to decode inline audio chunk (mime=%s).", candidate_mime)

            if not audio_chunks:
                logger.error("No non-empty audio chunk found in Gemini response: %s", data)
                return None

            if not mime_type:
                mime_type = "audio/l16;rate=24000"

            audio_bytes = b"".join(audio_chunks)

            if not audio_bytes:
                logger.error("Gemini TTS returned zero audio bytes after chunk decode.")
                return None

            normalized_mime_type = str(mime_type or "").strip().lower()

            # Determine file extension and process raw PCM if needed
            ext = "wav"
            if "audio/l16" in normalized_mime_type:
                # Gemini returns raw PCM (little-endian in practice) for audio/l16.
                # Wrap with a WAV header directly — no byte-swap needed.
                sample_rate = _parse_l16_sample_rate(mime_type)
                audio_bytes = _add_wav_header(audio_bytes, sample_rate=sample_rate)
                ext = "wav"
            elif "mp3" in normalized_mime_type:
                ext = "mp3"
            elif "ogg" in normalized_mime_type:
                ext = "ogg"

            # Save to concrete session directory when session_id is available.
            audio_dir = _resolve_audio_output_dir(adventure_id, session_id=session_id)
            os.makedirs(audio_dir, exist_ok=True)

            filename = f"{uuid.uuid4()}.{ext}"
            filepath = os.path.join(audio_dir, filename)

            with open(filepath, "wb") as f:
                f.write(audio_bytes)

            return _public_url_from_filepath(filepath)

        except httpx.ReadTimeout as exc:
            logger.warning(
                "Gemini TTS timed out after %.1fs for %d chars using model '%s'.",
                _tts_timeout_seconds(text),
                len(text or ""),
                model_name,
            )
            raise TTSTimeoutError("Timed out while generating speech.") from exc
        except TTSRateLimitError:
            raise
        except Exception:
            logger.exception("Failed to generate speech with Gemini")
            return None
