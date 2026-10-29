"""NPC persona (character and goal) that scripts can rewrite during a game.

The GM prompt reads every NPC's ``character`` and ``goal`` on each turn, so a script that
changes them changes how the NPC talks and acts from then on. Changes are stored on the
session's copy of the NPC; the adventure template is never touched.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Optional

PERSONA_FIELDS = ("character", "goal")
# Column size of WorldEntity.character / WorldEntity.goal.
MAX_PERSONA_LENGTH = 1000
_TRAIT_SEPARATOR = ","


def clean_persona(text: Any) -> Optional[str]:
    """Single-line, length-capped persona text; ``None`` clears the field."""
    value = " ".join(str(text or "").split())[:MAX_PERSONA_LENGTH]
    return value or None


def _traits(text: str) -> list[str]:
    return [part.strip() for part in text.split(_TRAIT_SEPARATOR) if part.strip()]


def _has_trait(traits: list[str], trait: str) -> bool:
    return trait.lower() in (t.lower() for t in traits)


class NPCPersonaMixin:
    """Persona properties and methods of ``NPCProxy``."""

    get_attribute: Callable[..., Any]
    set_attribute: Callable[[str, Any], None]

    @property
    def character(self) -> str:
        return str(self.get_attribute("character") or "")

    @character.setter
    def character(self, text: str) -> None:
        self.set_character(text)

    @property
    def goal(self) -> str:
        return str(self.get_attribute("goal") or "")

    @goal.setter
    def goal(self, text: str) -> None:
        self.set_goal(text)

    def set_character(self, text: str) -> None:
        """Replaces the NPC's personality; an empty text clears it."""
        self.set_attribute("character", clean_persona(text))

    def set_goal(self, text: str) -> None:
        """Replaces what the NPC wants; an empty text clears it."""
        self.set_attribute("goal", clean_persona(text))

    def add_trait(self, trait: str) -> None:
        """Appends a comma-separated trait to the character unless it is already there."""
        clean = clean_persona(trait)
        traits = _traits(self.character)
        if not clean or _has_trait(traits, clean):
            return
        self.set_character(f"{_TRAIT_SEPARATOR} ".join([*traits, clean]))

    def remove_trait(self, trait: str) -> None:
        """Removes a comma-separated trait from the character (case-insensitive)."""
        clean = str(trait or "").strip().lower()
        traits = _traits(self.character)
        kept = [t for t in traits if t.lower() != clean]
        if len(kept) == len(traits):
            return
        self.set_character(f"{_TRAIT_SEPARATOR} ".join(kept))

    def has_trait(self, trait: str) -> bool:
        """True when the character lists this comma-separated trait (case-insensitive)."""
        return _has_trait(_traits(self.character), str(trait or "").strip())


class NPCPersonaManagerMixin:
    """``tw.npcs.<method>(npc_id, ...)`` shortcuts for the persona methods."""

    get: Callable[[str], Any]

    def set_character(self, npc_id: str, text: str) -> None:
        self.get(npc_id).set_character(text)

    def set_goal(self, npc_id: str, text: str) -> None:
        self.get(npc_id).set_goal(text)

    def add_trait(self, npc_id: str, trait: str) -> None:
        self.get(npc_id).add_trait(trait)

    def remove_trait(self, npc_id: str, trait: str) -> None:
        self.get(npc_id).remove_trait(trait)


def apply_persona(entity: Any, state: dict[str, Any]) -> None:
    """Copies script-changed persona fields from a session entity state onto its DB row."""
    for field in PERSONA_FIELDS:
        if field in state:
            setattr(entity, field, state[field])
