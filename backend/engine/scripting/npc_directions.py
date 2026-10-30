"""Directed NPC speech: the script says what an NPC should talk about, the GM writes the line.

``tw.npcs.say("BRAM", text)`` prints a fixed line. ``tw.npcs.say_directed("BRAM", "sings
Yellow Submarine")`` instead queues a GM direction (like ``tw.story.direct``), so the next
narration lets the NPC say or sing it in their own voice, in character and in the scene.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from backend.engine.scripting.gm_directions import clean_direction


def speech_direction(name: str, npc_id: str, direction: Any) -> str:
    """GM direction asking for one in-character line of the NPC; empty without a direction."""
    what = clean_direction(direction)
    if not what:
        return ""
    return clean_direction(
        f'{name} ({npc_id}) speaks in this narration, as a separate dialogue line {name}: "..." '
        f"on its own line (not quoted inside prose), in character and fitting the scene. "
        f"Content: {what}"
    )


class NPCDirectionMixin:
    """``npc.say_directed(direction)`` on ``NPCProxy``."""

    id: str
    name: str
    _changeset: Any

    def say_directed(self, direction: str) -> None:
        """Lets the GM voice this NPC in the next narration, following the direction."""
        text = speech_direction(self.name, self.id, direction)
        if text:
            self._changeset.gm_directions.append(text)


class NPCDirectionManagerMixin:
    """``tw.npcs.say_directed(npc_id, direction)`` shortcut."""

    get: Callable[[str], Any]

    def say_directed(self, npc_id: str, direction: str) -> None:
        self.get(npc_id).say_directed(direction)
