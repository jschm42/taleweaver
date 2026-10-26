"""Narration styles: how much the narrator writes per turn (player setting per session).

Each style replaces the length and pacing rules of the narration prompt (Pass 2). Everything
else (formatting, dialogue lines, item rules) stays shared in ``prompts.py``.
The ids mirror ``frontend/src/components/game/settings/narrationStyles.ts``.
"""

from __future__ import annotations

from typing import Final, Literal

NarrationStyle = Literal["terse", "dialogue", "balanced", "rich", "epic"]

DEFAULT_NARRATION_STYLE: Final[NarrationStyle] = "dialogue"

# One-line length reminders, repeated at the end of every turn message where the model weighs
# them most (the full rules in the system prompt alone were too easy to ignore).
_STYLE_REMINDERS: Final[dict[str, str]] = {
    "terse": "LENGTH: 1-2 short sentences of narration in total; NPC lines are one short sentence.",
    "dialogue": (
        "LENGTH: narration only as single short sentences between dialogue lines (at most 3); "
        "let the characters do the talking."
    ),
    "balanced": "LENGTH: at most 2 short paragraphs of at most 3 sentences each; NPC lines 1-3 sentences.",
    "rich": "LENGTH: at most 3 paragraphs of at most 4 sentences each.",
    "epic": "LENGTH: at most 5 paragraphs of at most 5 sentences each.",
}

_STYLE_RULES: Final[dict[str, str]] = {
    "terse": (
        "NARRATION STYLE — TERSE (CRITICAL): Write sparse, punchy story snippets. "
        "Routine actions get 1-2 short sentences in total. A new location or a major event gets at most "
        "3 short sentences. Name only the single most striking detail; never describe a room in full. "
        "NPC dialogue is one short sentence per character per turn. Skip transitions, inner thoughts and "
        "atmosphere padding; move straight to what changed and who reacts."
    ),
    "dialogue": (
        "NARRATION STYLE — DIALOGUE-FIRST SCRIPT (CRITICAL): Write the turn like a radio play. The "
        "characters carry the scene; the narrator only bridges between their lines. Alternate narrator "
        "beats and dialogue lines, each on its own line with a blank line in between. A narrator beat is "
        "exactly ONE short sentence (at most about 20 words) naming an action, a reaction or one sensory "
        "detail. Never write two narrator beats in a row and use at most 3 per turn; a new location may "
        "open with one extra beat of up to 2 sentences. Narration stays below a third of the words of the "
        "turn. Present NPCs speak in short lines of 1-2 sentences, and a turn usually holds 3-6 dialogue "
        "lines: several quick exchanges, interruptions and replies instead of one long speech. When no NPC "
        "is present, write 1-3 narrator beats and never invent speakers. Never label narration with "
        "'Narrator:' or any other speaker name."
    ),
    "balanced": (
        "NARRATION STYLE — BALANCED (CRITICAL): 1-2 short paragraphs for standard actions. Up to 3 "
        "paragraphs ONLY for new scenes or major events. Every prose paragraph has at most 3 sentences "
        "(roughly 60 words). A new location gets a compact, atmospheric introduction (about 120 words) with "
        "the 2-3 most striking details; leave the rest for the player to discover. "
        "Keep dialogue and prose crisp and engaging; DO NOT produce walls of text or exposition dumps. "
        "NPC dialogue stays snappy (1-3 sentences per character per turn). Let the player act frequently "
        "and focus on the most salient sensory details instead of cataloging every object."
    ),
    "rich": (
        "NARRATION STYLE — RICH (CRITICAL): Write descriptive, immersive prose. Standard actions get 2-3 "
        "paragraphs; new scenes and major events up to 4. Every prose paragraph has at most 4 sentences "
        "(roughly 80 words). Use concrete sensory detail (light, sound, smell, texture) and show how the "
        "world and its characters react. NPC dialogue may run 2-4 sentences per character and reveal "
        "personality. Stay focused on the current moment; never pad with repetition or recaps."
    ),
    "epic": (
        "NARRATION STYLE — EPIC (CRITICAL): Write like a novel. Standard actions get 3-5 paragraphs; new "
        "scenes and major events up to 6. Every prose paragraph has at most 5 sentences (roughly 100 words). "
        "Build atmosphere and tension, describe the setting and the characters' body language in depth, and "
        "vary rhythm between long flowing sentences and short beats. NPC dialogue may be expansive and "
        "layered (up to 5 sentences per character), and NPCs may talk among themselves. Every paragraph must "
        "still add something new: no repetition, no recaps of earlier turns, and no decisions on behalf of "
        "the player."
    ),
}


def is_narration_style(value: object) -> bool:
    return isinstance(value, str) and value in _STYLE_RULES


def narration_style_rules(style: object) -> str:
    """Length and pacing rules for the narration prompt; unknown values fall back to balanced."""
    key = style if is_narration_style(style) else DEFAULT_NARRATION_STYLE
    return _STYLE_RULES[str(key)]


def narration_style_reminder(style: object) -> str:
    """Per-turn one-line length reminder; unknown values fall back to the default style."""
    key = style if is_narration_style(style) else DEFAULT_NARRATION_STYLE
    return _STYLE_REMINDERS[str(key)]


# Hard cap on narration tokens per style: a safety net for models that ignore the length rules
# and run on. Generous enough that a model following the rules never reaches it.
_STYLE_MAX_TOKENS: Final[dict[str, int]] = {
    "terse": 300,
    "dialogue": 600,
    "balanced": 800,
    "rich": 1200,
    "epic": 2000,
}


def narration_max_tokens(style: object) -> int:
    """Token cap for one narration answer; unknown values fall back to the default style."""
    key = style if is_narration_style(style) else DEFAULT_NARRATION_STYLE
    return _STYLE_MAX_TOKENS[str(key)]
