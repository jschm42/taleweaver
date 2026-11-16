"""How much the play-agent talks with characters, from taciturn to full roleplay.

Stored as ``entity_states["__agent__"]["dialogue_level"]``. The level adds a DIALOGUE block to
the agent prompt; the play style (personality) still decides how the agent plays overall.
"""

from __future__ import annotations

DEFAULT_DIALOGUE_LEVEL = "normal"

DIALOGUE_LEVELS: dict[str, str] = {
    "taciturn": "Taciturn",
    "normal": "Normal",
    "talkative": "Talkative",
    "roleplay": "Full roleplay",
}

_ALIASES = {
    "terse": "taciturn",
    "quiet": "taciturn",
    "wortkarg": "taciturn",
    "balanced": "normal",
    "chatty": "talkative",
    "full": "roleplay",
    "full roleplay": "roleplay",
    "full_roleplay": "roleplay",
}

_DIRECTIVES: dict[str, str] = {
    "taciturn": (
        "TACITURN. Speak only when it is needed to make progress: ask for a missing fact or "
        "answer a direct question. Keep every `/say` line to a few words and prefer actions "
        "over conversation. Never start small talk."
    ),
    "normal": (
        "NORMAL. Talk to each new character once: greet them, ask what matters for your goal, "
        "then act on it. One or two sentences per `/say` line. Return to a character when you "
        "have a new question or item for them."
    ),
    "talkative": (
        "TALKATIVE. Talk to characters often: ask about their lives, opinions and the world, "
        "react to what they said and ask follow-up questions. Two to four sentences per `/say` "
        "line. Still keep the story moving between conversations."
    ),
    "roleplay": (
        "FULL ROLEPLAY. Conversations are the heart of your play. Speak with every character "
        "present before you move on and keep interesting conversations going for several turns. "
        "Speak entirely in your character's voice: show emotions, tell about yourself, joke, "
        "argue, comfort or bargain as your character would, and pick up what characters said "
        "earlier. `/say` lines may be several sentences long."
    ),
}


def normalize_dialogue_level(value: str | None) -> str | None:
    """A known level key for user input, or None when unknown."""
    key = " ".join((value or "").strip().lower().split())
    key = _ALIASES.get(key, key)
    return key if key in DIALOGUE_LEVELS else None


def dialogue_level_label(value: str | None) -> str:
    return DIALOGUE_LEVELS[normalize_dialogue_level(value) or DEFAULT_DIALOGUE_LEVEL]


def dialogue_prompt(value: str | None) -> str:
    """The DIALOGUE directive for the agent prompt."""
    return _DIRECTIVES[normalize_dialogue_level(value) or DEFAULT_DIALOGUE_LEVEL]
