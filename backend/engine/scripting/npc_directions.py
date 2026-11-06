"""Directed NPC speech: the script says what an NPC should talk about, the GM writes the line.

``tw.npcs.say("BRAM", text)`` prints a fixed line. ``tw.npcs.say_directed("BRAM", "sings
Yellow Submarine")`` instead queues a GM direction (like ``tw.story.direct``), so the next
narration lets the NPC say or sing it in their own voice, in character and in the scene.
Like ``tw.story.direct`` it takes ``after``/``after_args``: an init-script function that runs
once that narration is done.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from backend.engine.scripting.gm_directions import clean_direction, queue_direction

logger = logging.getLogger(__name__)


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

    def say_directed(self, direction: str, after: Any = None, after_args: Any = None) -> None:
        """Lets the GM voice this NPC in the next narration, following the direction.

        An NPC outside the player's scene does not speak (the direction is dropped), but the
        ``after`` callback (an init-script function run once the narration is done) still runs.
        """
        text = speech_direction(self.name, self.id, direction)
        if not getattr(self, "is_with_player", True):
            logger.info("[Script] %s is not in the player's scene; direction dropped.", self.id)
            text = ""
        queue_direction(self._changeset, text, after, after_args)


class NPCDirectionManagerMixin:
    """``tw.npcs.say_directed(npc_id, direction)`` shortcut."""

    get: Callable[[str], Any]

    def say_directed(
        self, npc_id: str, direction: str, after: Any = None, after_args: Any = None
    ) -> None:
        self.get(npc_id).say_directed(direction, after=after, after_args=after_args)
