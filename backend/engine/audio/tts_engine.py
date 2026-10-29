import asyncio
import json
import logging
from typing import Optional

import httpx

from backend.core.config import settings
from backend.engine.audio.elevenlabs_stream import synthesize_elevenlabs_bytes
from backend.engine.audio.tts_helpers import (
    TTSModelSwitchSuggestionError,
    TTSProviderError,
    TTSRateLimitError,
    TTSTimeoutError,
    _backoff_delay_seconds,
    _build_audio_output_path,
    _compute_429_retry_delay_seconds,
    _convert_brackets_to_angles,
    _extract_error_detail,
    _extract_gemini_audio,
    _strip_vocal_tags,
    _tts_timeout_seconds,
    _wait_for_tts_request_slot,
    _write_audio_file,
)
from backend.engine.audio.tts_tag_format import canonicalize_tags, prepare_elevenlabs_text
from backend.utils.path_security import sanitize_path_component

logger = logging.getLogger(__name__)

# Re-exported for callers and tests that import helpers from the engine module.
__all__ = [
    "TTSEngine",
    "TTSModelSwitchSuggestionError",
    "TTSProviderError",
    "TTSRateLimitError",
    "TTSTimeoutError",
    "_build_audio_output_path",
    "_strip_vocal_tags",
]

_GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


def _parse_sse_audio_response(response: httpx.Response) -> dict:
    """Merge the parts of all SSE chunks into a single generateContent-shaped payload."""
    parts: list = []
    for line in response.iter_lines():
        if not line.startswith("data: "):
            continue
        try:
            chunk_data = json.loads(line[6:])
        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse SSE chunk: %s", exc)
            continue
        candidates = chunk_data.get("candidates") or []
        if candidates:
            parts.extend((candidates[0].get("content") or {}).get("parts", []))
    return {"candidates": [{"content": {"parts": parts}}]}


class TTSEngine:
    """
    Handles speech generation using Google Gemini TTS or ElevenLabs.
    """

    @staticmethod
    async def generate_speech(
        text: str,
        provider: str = "google",
        voice: str = "Puck",
        elevenlabs_voice_id: str = "",
        use_vocal_tags: bool = True,
        api_key: Optional[str] = None,
        adventure_id: Optional[str] = None,
        session_id: Optional[str] = None,
        model_name: str = "gemini-3.8-flash-tts",
        language: Optional[str] = None,
        use_streaming: bool = False,
        **_unused_kwargs: object,
    ) -> Optional[str]:
        """
        Generates speech using the specified provider and returns the relative URL to the audio file.
        """
        logger.info(
            "[TTS] generate_speech called for provider: %s, text length: %d",
            provider,
            len(text or ""),
        )
        if not api_key:
            logger.error("No API key provided for %s TTS.", provider)
            return None

        safe_session_id = sanitize_path_component(session_id)
        if session_id and not safe_session_id:
            logger.warning(
                "Invalid session_id for TTS output path; using adventure-level fallback."
            )

        if provider == "elevenlabs":
            # ElevenLabs model ids use underscores, but some might be sent with dots
            sanitized_model = (
                model_name.replace(".", "_") if model_name else "eleven_multilingual_v2"
            )
            return await TTSEngine._synthesize_elevenlabs(
                text=prepare_elevenlabs_text(text or "", sanitized_model, use_vocal_tags),
                voice_id=elevenlabs_voice_id,
                api_key=api_key,
                adventure_id=adventure_id,
                session_id=safe_session_id,
                model_id=sanitized_model,
            )

        if not use_vocal_tags:
            text = _strip_vocal_tags(text or "")
        elif text:
            # Gemini TTS expects angle-bracket vocal tags.
            text = _convert_brackets_to_angles(canonicalize_tags(text))

        return await TTSEngine._synthesize_google(
            text=text,
            voice=voice,
            api_key=api_key,
            adventure_id=adventure_id,
            session_id=safe_session_id,
            language=language,
            model_name=model_name,
            use_streaming=use_streaming,
        )

    @staticmethod
    async def _synthesize_elevenlabs(
        text: str,
        voice_id: str,
        api_key: str,
        adventure_id: Optional[str] = None,
        session_id: Optional[str] = None,
        model_id: str = "eleven_v4",
    ) -> Optional[str]:
        """A whole ElevenLabs clip as a file (downloads, fallback playback); see elevenlabs_stream."""
        if not voice_id:
            logger.error("No ElevenLabs Voice ID provided.")
            return None
        logger.debug("[TTS] ElevenLabs input (model=%s, voice_id=%s): %s", model_id, voice_id, text)

        await _wait_for_tts_request_slot()
        audio = await synthesize_elevenlabs_bytes(text, voice_id, api_key, model_id)
        if not audio:
            logger.error("ElevenLabs TTS returned zero audio bytes.")
            return None

        try:
            return _write_audio_file(audio, adventure_id, session_id, "mp3")
        except (OSError, ValueError):
            logger.exception("Failed to store ElevenLabs audio")
            return None

    @staticmethod
    def _build_google_payload(text: str, voice: str, language: Optional[str] = None) -> dict:
        _ = language
        return {
            "contents": [{"role": "user", "parts": [{"text": text}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}},
            },
        }

    @staticmethod
    async def _post_google_with_retries(
        client: httpx.AsyncClient,
        url: str,
        payload: dict,
        timeout: httpx.Timeout,
        model_name: str,
        text_length: int,
    ) -> httpx.Response:
        """POST to Gemini, retrying 429/5xx with backoff. Returns the first 2xx/4xx response."""
        max_attempts = max(1, min(int(getattr(settings, "TTS_RATE_LIMIT_MAX_RETRIES", 5)), 10))

        for attempt in range(1, max_attempts + 1):
            await _wait_for_tts_request_slot()
            response = await client.post(url, json=payload, timeout=timeout)
            is_last = attempt == max_attempts

            if response.status_code == 429:
                delay = _compute_429_retry_delay_seconds(response, attempt)
                logger.warning(
                    "Gemini TTS rate-limited (429), attempt %d/%d, retrying in %.1fs (model=%s, chars=%d).",
                    attempt,
                    max_attempts,
                    delay,
                    model_name,
                    text_length,
                )
                if is_last:
                    raise TTSRateLimitError(
                        "Gemini TTS rate limit reached.", retry_after_seconds=delay
                    )
                await asyncio.sleep(delay)
                continue

            if response.status_code >= 500:
                delay = _backoff_delay_seconds(attempt)
                logger.warning(
                    "Gemini TTS server error (%s), attempt %d/%d, retrying in %.1fs (model=%s).",
                    response.status_code,
                    attempt,
                    max_attempts,
                    delay,
                    model_name,
                )
                if is_last:
                    logger.error("Gemini TTS Error %s: %s", response.status_code, response.text)
                    raise TTSModelSwitchSuggestionError(
                        f"Gemini TTS model '{model_name}' is currently unstable (repeated 5xx errors). "
                        "Please try switching to 'gemini-3.8-flash-lite-tts' and retry."
                    )
                await asyncio.sleep(delay)
                continue

            return response

        raise TTSRateLimitError("Gemini TTS retries exhausted.")

    @staticmethod
    async def _synthesize_google(
        text: str,
        voice: str,
        api_key: str,
        adventure_id: Optional[str],
        session_id: Optional[str] = None,
        model_name: str = "gemini-3.8-flash-tts",
        language: Optional[str] = None,
        use_streaming: bool = False,
    ) -> Optional[str]:
        """
        Generates speech and returns the relative URL to the audio file.
        """
        if not api_key:
            logger.error("No Google API key provided for TTS.")
            return None

        payload = TTSEngine._build_google_payload(text, voice, language)
        method = "streamGenerateContent?alt=sse" if use_streaming else "generateContent"
        url = f"{_GEMINI_API_BASE}/{model_name}:{method}"
        timeout = httpx.Timeout(_tts_timeout_seconds(text), connect=20.0)
        logger.info("TTS request model=%s voice=%s streaming=%s", model_name, voice, use_streaming)
        logger.debug("[TTS] Prompt sent to %s:\n%s", model_name, text)

        try:
            # The key travels in a header so it never appears in URLs, httpx logs, or exceptions.
            async with httpx.AsyncClient(headers={"x-goog-api-key": api_key}) as client:
                response = await TTSEngine._post_google_with_retries(
                    client, url, payload, timeout, model_name, len(text or "")
                )
                if response.status_code != 200:
                    logger.error("Gemini TTS Error %s: %s", response.status_code, response.text)
                    err_msg = _extract_error_detail(
                        response, f"Gemini TTS request failed with status {response.status_code}"
                    )
                    raise TTSProviderError(err_msg)
                data = _parse_sse_audio_response(response) if use_streaming else response.json()

            decoded = _extract_gemini_audio(data)
            if decoded is None:
                return None
            audio_bytes, ext = decoded
            return _write_audio_file(audio_bytes, adventure_id, session_id, ext)

        except (
            TTSTimeoutError,
            TTSRateLimitError,
            TTSModelSwitchSuggestionError,
            TTSProviderError,
        ):
            raise
        except httpx.ReadTimeout as exc:
            logger.warning(
                "Gemini TTS timed out after %.1fs for %d chars using model '%s'.",
                _tts_timeout_seconds(text),
                len(text or ""),
                model_name,
            )
            raise TTSTimeoutError("Timed out while generating speech.") from exc
        except (httpx.HTTPError, OSError, ValueError, TypeError):
            logger.exception("Failed to generate speech with Gemini")
            return None
