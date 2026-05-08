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

VOICE_TAG_SET: Final[set[str]] = set(VOICE_TAG_CATALOG)


def build_voice_tag_catalog_prompt_block() -> str:
    """Return a formatted prompt block listing allowed English voice tags."""
    tags = ", ".join(f"[{tag}]" for tag in VOICE_TAG_CATALOG)
    return (
        "VOICE TAG CATALOG (ENGLISH ONLY): Use ONLY these tags exactly as written.\n"
        f"{tags}\n"
    )
