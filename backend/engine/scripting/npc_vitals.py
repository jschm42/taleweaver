"""NPC vitals in scripts: mana / stamina, ``heal`` / ``damage`` and ``consume``.

``npc.consume("HEALING_POTION")`` lets an NPC use a consumable it carries: the item is destroyed
and its HP / Mana / Stamina effects (the same ones ``/consume`` applies to the protagonist) change
the NPC's values, capped at the NPC's maximum. HP reaching 0 defeats the NPC.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Optional

from backend.engine.rules.consumable_effects import consumable_deltas
from backend.engine.rules.rule_engine import RESOURCE_CAP


class NPCVitalsMixin:
    """``.mana``, ``.stamina``, ``.heal()``, ``.damage()`` and ``.consume()`` on ``NPCProxy``."""

    _id: str
    _data: dict[str, Any]
    _changeset: Any
    _entity_mgr: Any
    hp: int
    is_defeated: bool
    kill: Callable[..., None]
    modify_hp: Callable[[int], None]
    contains: Callable[[str], bool]
    inventory: list[Any]
    _item_mover: Callable[[], Any]

    def _resource(self, name: str) -> int:
        for upd in reversed(self._changeset.entity_updates):
            if upd.get("entity_id") == self._id and name in upd:
                return int(upd[name] or 0)
        return int(self._data.get(name) or 0)

    def _cap(self, resource: str) -> int:
        return int(self._data.get(f"max_{resource}") or 0) or RESOURCE_CAP

    @property
    def mana(self) -> int:
        return self._resource("mana")

    @property
    def stamina(self) -> int:
        return self._resource("stamina")

    def _apply_delta(self, resource: str, delta: int) -> None:
        current = self.hp if resource == "hp" else self._resource(resource)
        new_value = max(0, min(self._cap(resource), current + int(delta)))
        self._changeset.entity_updates.append({"entity_id": self._id, resource: new_value})
        if resource == "hp" and new_value == 0 and not self.is_defeated:
            self.kill()

    def heal(self, amount: int) -> None:
        """Restores HP, up to the NPC's maximum."""
        self._apply_delta("hp", abs(int(amount)))

    def damage(self, amount: int) -> None:
        """Deals damage; HP reaching 0 defeats the NPC."""
        self.modify_hp(-abs(int(amount)))

    def _consumable(self, item_id: str) -> Optional[dict[str, Any]]:
        if not self.contains(item_id):
            return None
        target = str(item_id).strip().upper()
        entry = next(
            (
                e
                for e in self.inventory
                if isinstance(e, dict) and str(e.get("id", "")).upper() == target
            ),
            {},
        )
        world = self._entity_mgr.item_data(item_id) if self._entity_mgr else None
        item = {**(world or {}), **entry}
        if str(item.get("item_type") or "").upper() != "CONSUMABLE":
            return None
        return item

    def consume(self, item_id: str) -> Optional[dict[str, int]]:
        """Uses a consumable this NPC carries; returns its effects, or None if nothing happened."""
        mover = self._item_mover()
        item = self._consumable(item_id) if mover else None
        if item is None:
            return None
        mover.destroy(item_id)
        deltas = consumable_deltas(item)
        for resource, delta in deltas.items():
            self._apply_delta(resource, delta)
        return deltas


class NPCVitalsManagerMixin:
    """``tw.npcs.consume(npc_id, item_id)`` shortcut."""

    get: Callable[[str], Any]

    def consume(self, npc_id: str, item_id: str) -> Optional[dict[str, int]]:
        return self.get(npc_id).consume(item_id)
