"""Which voice speaks a line: the character's voice for the active provider, else the narrator.

Characters store the id of their voice-list voice (an ElevenLabs id) or a custom ElevenLabs id.
ElevenLabs speaks those ids directly; Google TTS and the OpenAI-compatible server use the voice
the admin mapped to the list voice (``voice_provider_map``). Without one the narrator voice is used.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Optional

from backend.engine.audio.elevenlabs_voices import looks_like_voice_id
from backend.engine.audio.openai_compatible_tts import SpeechEndpoint
from backend.engine.audio.voice_provider_map import (
    ELEVENLABS_PROVIDER,
    GOOGLE_PROVIDER,
    provider_voice,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NarratorVoices:
    """The configured narrator voice per provider."""

    google_voice: str
    elevenlabs_voice_id: str
    speech_endpoint: Optional[SpeechEndpoint] = None


@dataclass(frozen=True)
class SpeakerVoices:
    """The voice arguments of one speech request."""

    voice: str
    elevenlabs_voice_id: str
    speech_endpoint: Optional[SpeechEndpoint]


def elevenlabs_speaker_voice(provider: str, narrator_id: str, voice_override: Optional[str]) -> str:
    """The character's list or custom voice id under ElevenLabs, else the narrator voice."""
    if provider == ELEVENLABS_PROVIDER and looks_like_voice_id(voice_override):
        return str(voice_override)
    return narrator_id


def resolve_speaker_voices(
    provider: str,
    narrator: NarratorVoices,
    voice_map: Mapping[str, Mapping[str, str]],
    voice_override: Optional[str],
) -> SpeakerVoices:
    """The voices for a line spoken by the character with voice-list id ``voice_override``."""
    mapped = provider_voice(voice_map, provider, voice_override)
    if voice_override and not mapped:
        logger.debug("No %s voice for '%s'; using the narrator voice.", provider, voice_override)
    endpoint = narrator.speech_endpoint
    if endpoint is not None and mapped and provider != ELEVENLABS_PROVIDER:
        endpoint = replace(endpoint, voice=mapped)
    return SpeakerVoices(
        voice=mapped if provider == GOOGLE_PROVIDER and mapped else narrator.google_voice,
        elevenlabs_voice_id=elevenlabs_speaker_voice(
            provider, narrator.elevenlabs_voice_id, voice_override
        ),
        speech_endpoint=endpoint,
    )
