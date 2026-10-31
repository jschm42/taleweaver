"""Item operations on the script proxies: ``tw.objects``, item and holder proxies.

The mixins delegate to the ``ItemMover`` that ``GameContext`` attaches to the entity managers
(``manager.mover``), so every proxy works on the same changeset.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from backend.engine.scripting.context import EntityManagerProxy, ObjectProxy
    from backend.engine.scripting.item_ops import ItemMover


class _MoverAccess:
    """Shared lookup of the ``ItemMover`` a proxy's manager carries."""

    _entity_mgr: Optional[EntityManagerProxy]
    _id: str

    def _item_mover(self) -> Optional[ItemMover]:
        return getattr(self._entity_mgr, "mover", None)


class ItemHolderMixin(_MoverAccess):
    """Contents access for item holders (NPC inventories and containers)."""

    @property
    def items(self) -> list[ObjectProxy]:
        """The items this NPC carries or this container holds."""
        mover = self._item_mover()
        return mover.contents(self._id) if mover else []

    @property
    def item_ids(self) -> list[str]:
        return [item.id for item in self.items]

    def contains(self, item_id: str) -> bool:
        target = str(item_id).strip().upper()
        return any(item.id.upper() == target for item in self.items)

    def put_item(self, item_id: str) -> bool:
        """Moves a world item (from anywhere) into this NPC's inventory or this container."""
        mover = self._item_mover()
        return bool(mover and mover.move(item_id, self._id))

    def take_item(self, item_id: str, to: str = "player") -> bool:
        """Moves a held item out: to "player", a scene, "current", an NPC or a container."""
        mover = self._item_mover()
        if mover is None or not self.contains(item_id):
            return False
        return mover.move(item_id, to)


class ItemOpsMixin(_MoverAccess):
    """Clone, destroy, hide/reveal and transfers for ``ObjectProxy``."""

    def clone(self, scene_id: Optional[str] = None, hidden: Optional[bool] = None):
        """Creates a copy of this item with a new ID and returns its proxy (or None)."""
        mover = self._item_mover()
        return mover.clone(self._id, scene_id, hidden) if mover else None

    def destroy(self) -> bool:
        """Removes this item from the game for good."""
        mover = self._item_mover()
        return bool(mover and mover.destroy(self._id))

    @property
    def is_destroyed(self) -> bool:
        return bool(self.get_attribute("is_destroyed", False))  # type: ignore[attr-defined]

    def hide(self) -> None:
        self.set_hidden(True)  # type: ignore[attr-defined]

    def reveal(self) -> None:
        self.set_hidden(False)  # type: ignore[attr-defined]

    @property
    def location(self) -> dict[str, str]:
        """Where this item is: {"type": player|npc|container|scene|destroyed, "id": ...}."""
        mover = self._item_mover()
        return mover.location(self._id) if mover else {"type": "unknown", "id": ""}

    def move_to(self, target: str) -> bool:
        """Moves this item to "player", an NPC, a container, "current" or a scene ID."""
        mover = self._item_mover()
        return bool(mover and mover.move(self._id, target))

    def give_to_player(self) -> bool:
        mover = self._item_mover()
        return bool(mover and mover.to_player(self._id))

    def put_into(self, container_id: str) -> bool:
        mover = self._item_mover()
        return bool(mover and mover.to_container(self._id, container_id))


class ItemManagerMixin:
    """Item shortcuts on ``tw.objects`` / ``tw.items``."""

    mover: Optional[ItemMover] = None

    def _require_mover(self) -> ItemMover:
        if self.mover is None:
            raise RuntimeError("Item operations are not available in this context.")
        return self.mover

    def clone(self, item_id: str, scene_id: Optional[str] = None, hidden: Optional[bool] = None):
        return self._require_mover().clone(item_id, scene_id, hidden)

    def destroy(self, item_id: str) -> bool:
        return self._require_mover().destroy(item_id)

    def hide(self, item_id: str) -> bool:
        return self._require_mover().set_hidden(item_id, True)

    def reveal(self, item_id: str) -> bool:
        return self._require_mover().set_hidden(item_id, False)

    def location(self, item_id: str) -> dict[str, str]:
        return self._require_mover().location(item_id)

    def contents(self, holder_id: str) -> list:
        """Items held by "player", an NPC or a container."""
        return self._require_mover().contents(holder_id)

    def move_item(self, item_id: str, target: str) -> bool:
        """Moves an item to "player", an NPC, a container, "current" or a scene ID."""
        return self._require_mover().move(item_id, target)

    def add_to_player(self, item_id: str) -> bool:
        return self._require_mover().to_player(item_id) is not None

    def remove_from_player(self, item_id: str) -> bool:
        """Takes an item out of the inventory without placing it anywhere."""
        return self._require_mover()._player._take_entry(item_id) is not None

    def add_to_scene(self, item_id: str, scene_id: Optional[str] = None) -> bool:
        return self._require_mover().to_scene(item_id, scene_id)

    def put_in_container(self, item_id: str, container_id: str) -> bool:
        return self._require_mover().to_container(item_id, container_id)

    def take_from_container(self, container_id: str, item_id: str, to: str = "player") -> bool:
        mover = self._require_mover()
        if mover.holder_of(str(item_id)) != ("container", mover.item_id(container_id)):
            return False
        return mover.move(item_id, to)
