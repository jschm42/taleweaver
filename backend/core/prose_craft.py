"""Prose rules for the narration prompt (Pass 2) that keep the narrator from sounding machine-written.

The rules target the tells readers name most often in AI-written fiction (dash punctuation,
the "not X, but Y" cadence, stock phrases, reflexive triplets, uniform rhythm, mood-summary
endings) and warn against the over-corrected register of choppy fragments. They hold in every
response language and sit next to the length rules of ``narration_styles.py``.
"""

from __future__ import annotations

from typing import Final

PROSE_CRAFT_RULES: Final[str] = (
    "PROSE CRAFT: Write like a human author, not like a language model. "
    "Never use dash punctuation (— or –) in narration or dialogue; use a comma or a period. "
    "State things directly instead of contrasting them ('not X, but Y', 'it's not just X, it's Y'). "
    "Skip stock phrases such as 'a testament to', 'tapestry', 'palpable', 'a symphony of', "
    "'the air is thick with', 'barely above a whisper' or 'a shiver runs down your spine'; "
    "pick the plain, concrete word. One precise detail beats a habitual list of three. "
    "Vary sentence length on purpose, but never fall into strings of clipped fragments. "
    "End on an action or a line of dialogue, never on a summary of the mood or an ominous teaser. "
    "These rules apply in every response language."
)
