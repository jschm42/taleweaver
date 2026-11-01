"""Hiding and revealing NPCs from scripts (``npc.hide()`` / ``tw.npcs.hide(id)``).

A hidden NPC drops out of the story: it vanishes from the scene list, cannot be talked to,
attacked, given items or targeted by talents, and the Game Master no longer sees it in the
scene. ``reveal`` brings it back where it stands. Use ``tw.npcs.move(id, scene)`` first to
make it reappear somewhere else.
"""

from __future__ import annotations

from typing import Any


class NPCVisibilityMixin:
    """``hide()`` / ``reveal()`` on a single NPC proxy (mirrors ``ObjectProxy``)."""

    def hide(self) -> None:
        """Takes the NPC out of the story until a script reveals it again."""
        self.set_hidden(True)  # type: ignore[attr-defined]

    def reveal(self) -> None:
        """Brings a hidden NPC (back) into its current scene."""
        self.set_hidden(False)  # type: ignore[attr-defined]


class NPCVisibilityManagerMixin:
    """``tw.npcs.hide(npc_id)`` / ``tw.npcs.reveal(npc_id)``; False when the ID is no NPC."""

    def _set_npc_hidden(self, npc_id: str, hidden: bool) -> bool:
        if not self.exists(npc_id):  # type: ignore[attr-defined]
            return False
        npc: Any = self.get(npc_id)  # type: ignore[attr-defined]
        if not isinstance(npc, NPCVisibilityMixin):
            return False
        npc.set_hidden(hidden)  # type: ignore[attr-defined]
        return True

    def hide(self, npc_id: str) -> bool:
        return self._set_npc_hidden(npc_id, True)

    def reveal(self, npc_id: str) -> bool:
        return self._set_npc_hidden(npc_id, False)
