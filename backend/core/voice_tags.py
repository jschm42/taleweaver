"""Canonical voice-tag catalog used by GM narration and TTS guidance.

Tags are intentionally fixed and English-only so downstream TTS interpretation
stays predictable.
"""

from typing import Final

VOICE_TAG_CATALOG: Final[tuple[str, ...]] = (
    "bored",
    "reluctantly",
    "amazed",
    "crying",
    "curious",
    "excited",
    "sighs",
    "gasp",
    "giggles",
    "laughs",
    "mischievously",
    "panicked",
    "sarcastic",
    "serious",
    "shouting",
    "tired",
    "trembling",
    "whispers",
    "very fast",
    "very slow",
    "sarcastically",
    "tense",
    "solemn",
    "mocking",
    "dramatic pause",
    "amused",
    "angry",
    "cheerful",
    "thoughtful",
    "sad",
    "surprised",
    "confused",
    "gentle",
    "stern",
    "warmly",
    "coldly",
    "playful",
    "relieved",
    "calm",
    "nervous",
)

# ElevenLabs v3/v4 audio tags: lowercase, in square brackets, directly before (or right after)
# the words they color. See https://elevenlabs.io/docs/overview/capabilities/text-to-speech/best-practices
ELEVENLABS_VOICE_TAG_CATALOG: Final[tuple[str, ...]] = (
    "excited",
    "nervous",
    "frustrated",
    "sorrowful",
    "calm",
    "whispers",
    "hesitates",
    "stammers",
    "resigned",
    "cheerfully",
    "flatly",
    "deadpan",
    "playfully",
    "sarcastic",
    "sarcastically",
    "mischievously",
    "curious",
    "amused",
    "angry",
    "annoyed",
    "appalled",
    "thoughtful",
    "sad",
    "surprised",
    "confused",
    "gentle",
    "stern",
    "warmly",
    "coldly",
    "relieved",
    "wistful",
    "awe",
    "matter-of-fact",
    "panicking",
    "crying",
    "rushed",
    "slows down",
    "drawn out",
    "dramatic tone",
    "low, gravelly voice",
    "deep voice",
    "childlike tone",
    "robotic tone",
    "strong british accent",
    "strong scottish accent",
    "strong irish accent",
    "strong southern us accent",
    "strong french accent",
    "strong german accent",
    "strong russian accent",
    "strong italian accent",
    "strong spanish accent",
)

# Non-verbal sounds and pauses for ElevenLabs, placed exactly where they happen.
ELEVENLABS_SOUND_TAG_CATALOG: Final[tuple[str, ...]] = (
    "sighs",
    "laughs",
    "chuckles",
    "starts laughing",
    "clears throat",
    "coughs",
    "gasps",
    "gulps",
    "exhales",
    "exhales sharply",
    "inhales deeply",
    "snorts",
    "short pause",
    "long pause",
)

# Gemini-style vocal bursts and their ElevenLabs equivalents (used when converting old text).
GEMINI_TO_ELEVENLABS_SOUNDS: Final[dict[str, str]] = {
    "sigh": "sighs",
    "laugh": "laughs",
    "chuckle": "chuckles",
    "cough": "coughs",
    "gasp": "gasps",
    "groan": "sighs",
    "breath": "exhales",
    "heavy breath": "exhales sharply",
    "throat-clearing": "clears throat",
}

VOICE_TAG_SET: Final[set[str]] = (
    set(VOICE_TAG_CATALOG) | set(ELEVENLABS_VOICE_TAG_CATALOG) | set(ELEVENLABS_SOUND_TAG_CATALOG)
)


def _elevenlabs_catalog_prompt_block() -> str:
    tones = ", ".join(f"[{tag}]" for tag in ELEVENLABS_VOICE_TAG_CATALOG)
    sounds = ", ".join(f"[{tag}]" for tag in ELEVENLABS_SOUND_TAG_CATALOG)
    return (
        "TONE CATALOG (ENGLISH ONLY): Use ONLY these tags, lowercase, exactly as written in square brackets.\n"
        f"{tones}\n\n"
        "SOUNDS CATALOG: Use ONLY these tags, lowercase, in square brackets, exactly where the sound happens.\n"
        f"{sounds}\n"
        "NEVER use angle brackets, SSML (<break>) or parentheses for tags. "
        "For pauses use [short pause], [long pause] or an ellipsis (...).\n"
    )


def build_voice_tag_catalog_prompt_block(provider: str = "google") -> str:
    """Return a formatted prompt block listing allowed English voice tags."""
    if provider == "elevenlabs":
        return _elevenlabs_catalog_prompt_block()
    tags = ", ".join(f"[{tag}]" for tag in VOICE_TAG_CATALOG)
    return (
        "TONE CATALOG (ENGLISH ONLY): Use ONLY these tags exactly as written in square brackets.\n"
        f"{tags}\n\n"
        "SOUNDS CATALOG: Use ONLY these tags, lowercase, in square brackets, exactly where the sound happens.\n"
        "[cough], [sigh], [breath], [heavy breath], [laugh], [chuckle], [throat-clearing], [short pause], [long pause], [gasp], [groan]\n"
        "NEVER use angle brackets or parentheses for tags.\n"
    )


def vocal_tag_reminder() -> str:
    """Short per-turn reminder of the one tag syntax (the TTS engine converts it per provider)."""
    return (
        "Audio tags are lowercase and in square brackets only, never <...> or (...): a tone tag like "
        "[excited] at the start of a line, a sound like [sighs] exactly where it happens. Use them sparingly."
    )
