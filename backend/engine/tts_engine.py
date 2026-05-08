import os
import uuid
import base64
import logging
import struct
import math
import httpx
from typing import Optional
from backend.core.config import settings

logger = logging.getLogger(__name__)


class TTSTimeoutError(RuntimeError):
    """Raised when the upstream TTS request times out."""


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


def _resolve_audio_output_dir(adventure_id: Optional[str]) -> str:
    """Return target directory for generated audio.

    If an adventure_id is known, store clips inside that adventure's session area.
    """
    if adventure_id:
        return os.path.join(settings.DATA_DIR, "adventures", adventure_id, "sessions", "tts")
    return os.path.join(settings.DATA_DIR, "audio")


def _resolve_audio_public_url(adventure_id: Optional[str], filename: str) -> str:
    """Return static URL for generated audio based on storage location."""
    if adventure_id:
        return f"/data/adventures/{adventure_id}/sessions/tts/{filename}"
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

        # Keep the TTS prompt compact and avoid extra context sections.
        prompt_parts = []
        if include_style_context and style_description:
            prompt_parts.append(f"Voice style context: {style_description}")
        if tone:
            prompt_parts.append(f"Tone: {tone}")
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
        prompt_parts.append("Transcript:")
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

        logger.info(
            "TTS request model=%s multi_speaker=%s speakers=%s",
            model_name,
            len(valid_speaker_voices) >= 2,
            list(valid_speaker_voices.keys()),
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
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, timeout=timeout)
                if response.status_code != 200:
                    logger.error("Gemini TTS Error %s: %s", response.status_code, response.text)
                response.raise_for_status()
                data = response.json()

            candidates = data.get("candidates", [])
            if not candidates:
                logger.error("No candidates returned from Gemini TTS: %s", data)
                return None

            audio_part = next((p for p in candidates[0]["content"]["parts"] if "inlineData" in p), None)
            if not audio_part:
                logger.error("No audio data found in Gemini response: %s", data)
                return None

            mime_type = audio_part["inlineData"]["mimeType"]
            audio_base64 = audio_part["inlineData"]["data"]
            audio_bytes = base64.b64decode(audio_base64)

            # Determine file extension and process raw PCM if needed
            ext = "wav"
            if "audio/l16" in mime_type:
                # Gemini returns raw PCM for audio/l16, browsers need a WAV header
                audio_bytes = _add_wav_header(audio_bytes)
                ext = "wav"
            elif "mp3" in mime_type: 
                ext = "mp3"
            elif "ogg" in mime_type: 
                ext = "ogg"

            # Save to adventure session directory when adventure_id is known.
            audio_dir = _resolve_audio_output_dir(adventure_id)
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
        except Exception:
            logger.exception("Failed to generate speech with Gemini")
            return None
