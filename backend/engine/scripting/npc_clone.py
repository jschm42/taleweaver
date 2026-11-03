"""Cloning NPCs from scripts (``tw.npcs.clone(id)`` / ``npc.clone()``).

A clone is a new NPC of the current game with its own ID (``RAT_1``, ``RAT_2``, ...): same
name, description, portrait, combat profile, combat group and scripts, but full HP, not
defeated and with an empty inventory. Handy for spawning a pack of enemies from one template.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from backend.engine.scripting.item_ops import ItemMover


class NPCCloneManagerMixin:
    """``tw.npcs.clone(npc_id, scene_id=None, hidden=None)``."""

    mover: Optional[ItemMover]

    def clone(self, npc_id: str, scene_id: Optional[str] = None, hidden: Optional[bool] = None):
        """Returns the new NPC's proxy, or None for an unknown NPC or past the clone limit."""
        if self.mover is None:
            raise RuntimeError("NPC cloning is not available in this context.")
        return self.mover.clone_npc(npc_id, scene_id, hidden)


class NPCCloneMixin:
    """``npc.clone(scene_id=None, hidden=None)`` on ``NPCProxy``."""

    _id: str
    _entity_mgr: Any

    def clone(self, scene_id: Optional[str] = None, hidden: Optional[bool] = None):
        manager = self._entity_mgr
        if not isinstance(manager, NPCCloneManagerMixin):
            return None
        return manager.clone(self._id, scene_id, hidden)
