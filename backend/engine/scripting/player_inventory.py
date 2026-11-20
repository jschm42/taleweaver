"""The protagonist's inventory as scripts see it (``tw.player.inventory`` and item transfers).

The effective inventory is the avatar's stored inventory minus the entries a script removed
plus the ones it added. Adding and removing the same item within one script cancel out, so
the changeset never both adds and removes an ID (the engine applies additions first).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, Any, Optional

from backend.engine.scripting.item_transfer import ref_id

if TYPE_CHECKING:
    from backend.engine.scripting.context import PlayerProxy, ScriptChangeset
    from backend.engine.scripting.item_ops import ItemMover


class PlayerInventoryMixin:
    """Inventory access for ``PlayerProxy``; the mover is attached by ``GameContext``."""

    _avatar: dict[str, Any]
    _changeset: ScriptChangeset
    _mover: Optional[ItemMover] = None

    def _stored_inventory(self) -> list[Any]:
        return list(self._avatar.get("inventory") or [])

    @property
    def inventory(self) -> list[dict[str, Any]]:
        """Items the protagonist carries right now, as dicts (``id``, ``name``, ...)."""
        removed = {str(i).strip().upper() for i in self._changeset.player_removed_item_ids}
        kept = [e for e in self._stored_inventory() if ref_id(e) not in removed]
        entries = [*kept, *self._changeset.player_new_items]
        return [dict(e) if isinstance(e, dict) else {"id": e, "name": e} for e in entries]

    @property
    def item_ids(self) -> list[str]:
        """IDs of the items the protagonist carries right now."""
        return [str(e.get("id")) for e in self.inventory if e.get("id")]

    def _add_entry(self, entry: dict[str, Any]) -> None:
        """Adds an inventory entry, undoing an earlier removal of the same item."""
        target = ref_id(entry)
        removed = self._changeset.player_removed_item_ids
        undone = next((i for i in removed if str(i).strip().upper() == target), None)
        if undone is not None and any(ref_id(e) == target for e in self._stored_inventory()):
            removed.remove(undone)
            return
        self._changeset.player_new_items.append(entry)

    def _take_entry(self, item_id: str) -> Optional[Any]:
        """Removes an item from the inventory and returns its entry (None if not carried)."""
        target = str(item_id).strip().upper()
        new_items = self._changeset.player_new_items
        added = next((e for e in new_items if ref_id(e) == target), None)
        if added is not None:
            new_items.remove(added)
            return added
        stored = next((e for e in self.inventory if ref_id(e) == target), None)
        if stored is None:
            return None
        self._changeset.player_removed_item_ids.append(str(stored.get("id") or item_id))
        return stored

    def take_item(self, item_id: str) -> bool:
        """Moves an existing world item (scene, container or NPC) into the inventory."""
        return bool(self._mover and self._mover.to_player(item_id))

    def drop_item(self, item_id: str, scene_id: Optional[str] = None) -> bool:
        """Drops a carried item into a scene (default: the protagonist's scene)."""
        if not self.has_item(item_id):
            return False
        return bool(self._mover and self._mover.to_scene(item_id, scene_id))

    def transfer_item(self, item_id: str, target_id: str) -> bool:
        """Hands a carried item to an NPC or puts it into a container."""
        if not self.has_item(item_id):
            return False
        return bool(self._mover and self._mover.move(item_id, target_id))

    def has_item(self, item_id: str) -> bool:
        target = str(item_id).strip().upper()
        return any(ref_id(e) == target for e in self.inventory)

    def has(self, item_id: str) -> bool:
        """Alias for ``has_item()``."""
        return self.has_item(item_id)

    def remove_item(self, item_id: str) -> None:
        self._take_entry(item_id)


class InventoryProxy:
    """Safe root proxy exposed as ``tw.inventory``, delegating to ``tw.player``."""

    def __init__(self, player: PlayerProxy) -> None:
        self._player = player

    @property
    def items(self) -> list[dict[str, Any]]:
        """Items the protagonist carries right now."""
        return self._player.inventory

    @property
    def item_ids(self) -> list[str]:
        """IDs of items the protagonist carries right now."""
        return self._player.item_ids

    def all(self) -> list[dict[str, Any]]:
        """Returns all carried inventory entries."""
        return self._player.inventory

    def count(self) -> int:
        """Returns the number of carried inventory items."""
        return len(self._player.inventory)

    def has(self, item_id: str) -> bool:
        """Returns True if the protagonist carries ``item_id`` (case-insensitive)."""
        return self._player.has_item(item_id)

    def has_item(self, item_id: str) -> bool:
        """Alias for ``has()``."""
        return self._player.has_item(item_id)

    def take(self, item_id: str) -> bool:
        """Moves an existing world item into the protagonist's inventory."""
        return self._player.take_item(item_id)

    def take_item(self, item_id: str) -> bool:
        """Alias for ``take()``."""
        return self._player.take_item(item_id)

    def drop(self, item_id: str, scene_id: Optional[str] = None) -> bool:
        """Drops a carried item into a scene (default: current scene)."""
        return self._player.drop_item(item_id, scene_id)

    def drop_item(self, item_id: str, scene_id: Optional[str] = None) -> bool:
        """Alias for ``drop()``."""
        return self._player.drop_item(item_id, scene_id)

    def transfer(self, item_id: str, target_id: str) -> bool:
        """Hands a carried item to an NPC or puts it into a container."""
        return self._player.transfer_item(item_id, target_id)

    def transfer_item(self, item_id: str, target_id: str) -> bool:
        """Alias for ``transfer()``."""
        return self._player.transfer_item(item_id, target_id)

    def remove(self, item_id: str) -> None:
        """Removes an item from the protagonist's inventory."""
        self._player.remove_item(item_id)

    def remove_item(self, item_id: str) -> None:
        """Alias for ``remove()``."""
        self._player.remove_item(item_id)

    def give(
        self, item_id: str, name: Optional[str] = None, description: Optional[str] = None
    ) -> None:
        """Adds a custom non-world item entry to the protagonist's inventory."""
        self._player.give_item(item_id, name, description)

    def give_item(
        self, item_id: str, name: Optional[str] = None, description: Optional[str] = None
    ) -> None:
        """Alias for ``give()``."""
        self._player.give_item(item_id, name, description)

    def add(
        self, item_id: str, name: Optional[str] = None, description: Optional[str] = None
    ) -> None:
        """Alias for ``give()``."""
        self._player.give_item(item_id, name, description)

    def add_item(
        self, item_id: str, name: Optional[str] = None, description: Optional[str] = None
    ) -> None:
        """Alias for ``give()``."""
        self._player.give_item(item_id, name, description)

    def __contains__(self, item_id: object) -> bool:
        return self._player.has_item(str(item_id))

    def __iter__(self) -> Iterator[dict[str, Any]]:
        return iter(self._player.inventory)

    def __len__(self) -> int:
        return len(self._player.inventory)
