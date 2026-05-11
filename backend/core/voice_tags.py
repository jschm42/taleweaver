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
)

ELEVENLABS_VOICE_TAG_CATALOG: Final[tuple[str, ...]] = (
    "excited",
    "nervous",
    "frustrated",
    "sorrowful",
    "calm",
    "sigh",
    "gulps",
    "gasps",
    "whispers",
    "pauses",
    "hesitates",
    "stammers",
    "resigned tone",
    "cheerfully",
    "flatly",
    "deadpan",
    "playfully",
    "pause",
    "continues softly",
    "hesitates",
    "resigned",
    "dramatic tone",
    "lighthearted",
    "reflective",
    "serious tone",
    "awe",
    "sarcastic tone",
    "wistful",
    "matter-of-fact",
    "slows down",
    "rushed",
    "emphasized",
    "frustrated",
    "sarcastically",
    "matter-of-fact",
    "whiny",
    "panicking",
    "rapid-fire",
    "stammers",
    "drawn out",
    "fantasy narrator",
    "sci-fi AI voice",
    "classic film noir",
    "robotic tone",
    "deep voice",
    "pirate voice",
    "evil scientist voice",
    "childlike tone",
    "British accent",
    "Australian accent",
    "Southern US accent",
    "Indian English",
    "French accent",
    "German accent",
    "Scottish accent",
    "Russian accent",
    "Chinese accent",
    "Japanese accent",
    "Spanish accent",
    "Italian accent"
)

VOICE_TAG_SET: Final[set[str]] = set(VOICE_TAG_CATALOG) | set(ELEVENLABS_VOICE_TAG_CATALOG)


def build_voice_tag_catalog_prompt_block(provider: str = "google") -> str:
    """Return a formatted prompt block listing allowed English voice tags."""
    catalog = ELEVENLABS_VOICE_TAG_CATALOG if provider == "elevenlabs" else VOICE_TAG_CATALOG
    tags = ", ".join(f"[{tag}]" for tag in catalog)
    return (
        "VOICE TAG CATALOG (ENGLISH ONLY): Use ONLY these tags exactly as written.\n"
        f"{tags}\n"
    )
