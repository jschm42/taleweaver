"""One audio-tag format for speech: lowercase tags in square brackets, e.g. ``[sighs]``.

The narrator is asked to write only square-bracket tags, but models still slip into Gemini's
``<sigh>`` or stage directions like ``(sigh)``. Everything is canonicalized here before it reaches
a TTS provider; Gemini then gets its angle-bracket form, ElevenLabs the square brackets it expects
(see https://elevenlabs.io/docs/overview/capabilities/text-to-speech/best-practices).
"""

from __future__ import annotations

import re
from typing import Final

from backend.core.voice_tags import GEMINI_TO_ELEVENLABS_SOUNDS

# SSML is not supported by ElevenLabs v3/v4 and must never be read aloud.
_SSML_TAG: Final = re.compile(
    r"</?(?:break|phoneme|speak|prosody|emphasis|say-as)\b[^>\n]{0,200}>", re.I
)
_ANGLE_TAG: Final = re.compile(r"<\s*([A-Za-z][A-Za-z '\-]{0,40}?)\s*>")
_SQUARE_TAG: Final = re.compile(r"\[\s*([^\[\]\n]{1,60}?)\s*\]")
# Stage directions in parentheses are converted only for known sounds, never for prose asides.
_PAREN_SOUND: Final = re.compile(
    r"\(\s*(sighs?|laughs?|chuckles?|coughs?|gasps?|groans?|gulps|snorts|breath|heavy breath|"
    r"exhales(?: sharply)?|inhales deeply|throat-clearing|clears throat|(?:short |long )?pause)\s*\)",
    re.I,
)
_SPACES: Final = re.compile(r"[ \t]{2,}")

# Models that understand audio tags; all others would read them aloud.
_TAG_CAPABLE_ELEVENLABS_PREFIXES: Final = ("eleven_v3", "eleven_v4")


def canonicalize_tags(text: str) -> str:
    """Rewrites every tag variant to ``[lowercase tag]`` and drops SSML."""
    if not text:
        return ""
    text = _SSML_TAG.sub(" ", text)
    text = _ANGLE_TAG.sub(lambda m: f"[{m.group(1).strip().lower()}]", text)
    text = _PAREN_SOUND.sub(lambda m: f"[{m.group(1).strip().lower()}]", text)
    text = _SQUARE_TAG.sub(lambda m: f"[{m.group(1).strip().lower()}]", text)
    return _SPACES.sub(" ", text).strip()


def strip_tags(text: str) -> str:
    return _SPACES.sub(" ", _SQUARE_TAG.sub(" ", canonicalize_tags(text))).strip()


def supports_audio_tags(model_id: str) -> bool:
    return (model_id or "").startswith(_TAG_CAPABLE_ELEVENLABS_PREFIXES)


def prepare_elevenlabs_text(text: str, model_id: str, use_tags: bool = True) -> str:
    """Square-bracket tags in ElevenLabs wording, or no tags for models that cannot use them."""
    if not use_tags or not supports_audio_tags(model_id):
        return strip_tags(text)
    return _SQUARE_TAG.sub(
        lambda m: f"[{GEMINI_TO_ELEVENLABS_SOUNDS.get(m.group(1), m.group(1))}]",
        canonicalize_tags(text),
    )
