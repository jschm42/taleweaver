"""Combat group and assist mode of NPCs, changeable from scripts.

``npc.set_combat_group('GUARDS')`` makes an NPC fight alongside the guards from now on;
``npc.set_assist_mode('NEVER')`` turns it into a bystander (e.g. after a bribe). Changes
are stored on the session and take effect when the next fight starts or someone joins.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from backend.engine.combat.groups import (
    ASSIST_MODES,
    normalize_assist_mode,
    normalize_group,
    resolve_assist_mode,
)


class NPCCombatGroupMixin:
    """``combat_group`` / ``assist_mode`` properties and setters of ``NPCProxy``."""

    get_attribute: Callable[..., Any]
    set_attribute: Callable[[str, Any], None]

    def _metadata_value(self, key: str) -> Any:
        meta = self.get_attribute("metadata_json") or {}
        return meta.get(key) if isinstance(meta, dict) else None

    def _stored(self, key: str) -> Any:
        override = self.get_attribute(key)
        return override if override is not None else self._metadata_value(key)

    @property
    def combat_group(self) -> str:
        """The NPC's combat group tag, or an empty string without one."""
        return normalize_group(self._stored("combat_group")) or ""

    @property
    def assist_mode(self) -> str:
        """The effective assist mode: GROUP, ANYONE or NEVER."""
        return resolve_assist_mode(self.combat_group or None, self._stored("assist_mode"))

    def set_combat_group(self, group: str) -> None:
        """Moves the NPC into another combat group; an empty text removes it from every group."""
        self.set_attribute("combat_group", normalize_group(group) or "")

    def set_assist_mode(self, mode: str) -> None:
        """Sets when the NPC joins fights: GROUP, ANYONE or NEVER (empty text: automatic)."""
        clean = str(mode or "").strip()
        explicit = normalize_assist_mode(clean)
        if clean and not explicit:
            raise ValueError(f"assist mode must be one of {', '.join(ASSIST_MODES)}, got '{mode}'")
        self.set_attribute("assist_mode", explicit or "")


class NPCCombatGroupManagerMixin:
    """``tw.npcs.set_combat_group(npc_id, group)`` / ``tw.npcs.set_assist_mode(npc_id, mode)``."""

    get: Callable[[str], Any]

    def set_combat_group(self, npc_id: str, group: str) -> None:
        self.get(npc_id).set_combat_group(group)

    def set_assist_mode(self, npc_id: str, mode: str) -> None:
        self.get(npc_id).set_assist_mode(mode)
