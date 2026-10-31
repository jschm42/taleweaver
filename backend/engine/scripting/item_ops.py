"""Item operations for scripts: clone, destroy, hide/reveal and moving items between holders.

A world item is held by exactly one place: the protagonist's inventory, an NPC's inventory,
a container's contents (the container's ``inventory``) or a scene. ``ItemMover`` detaches an
item from its current holder before handing it to the next one, so moved items never exist
twice or vanish. Every change goes into the script changeset like all other mutations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from backend.engine.scripting.item_transfer import inventory_entry, ref_id

if TYPE_CHECKING:
    from backend.engine.scripting.context import (
        EntityManagerProxy,
        ObjectProxy,
        PlayerProxy,
        ScriptChangeset,
    )

INVENTORY_SCENE_ID = "INVENTORY"
# Scene ID of destroyed items: no scene has it, so they never show up again.
DESTROYED_SCENE_ID = "__DESTROYED__"
MAX_CLONES_PER_SCRIPT = 20
_MAX_ID_LENGTH = 50
_PLAYER_TARGETS = {"player", "protagonist", "inventory"}
_HERE_TARGETS = {"", "scene", "current", "here"}


def current_inventory(changeset: ScriptChangeset, entity_id: str, data: dict[str, Any]) -> list:
    """An entity's inventory including the changes of the running script."""
    for upd in reversed(changeset.entity_updates):
        if upd.get("entity_id") == entity_id and "inventory" in upd:
            return list(upd["inventory"])
    return list(data.get("inventory") or [])


def _is_container(data: dict[str, Any]) -> bool:
    return str(data.get("item_type") or "").strip().upper() == "CONTAINER"


class ItemMover:
    """Moves world items between the protagonist, NPCs, containers and scenes."""

    def __init__(
        self,
        changeset: ScriptChangeset,
        player: PlayerProxy,
        npcs: EntityManagerProxy,
        objects: EntityManagerProxy,
        current_scene_id: str,
    ):
        self._changeset = changeset
        self._player = player
        self._npcs = npcs
        self._objects = objects
        self._current_scene_id = current_scene_id

    # --- lookups -------------------------------------------------------------------------

    def _player_scene(self) -> str:
        return self._changeset.teleport_scene_id or self._current_scene_id

    @staticmethod
    def _find_id(entities: dict[str, dict[str, Any]], entity_id: Any) -> Optional[str]:
        target = str(entity_id or "").strip()
        if target in entities:
            return target
        upper = target.upper()
        return next((eid for eid in entities if str(eid).strip().upper() == upper), None)

    def item_id(self, item_id: Any) -> Optional[str]:
        """Canonical ID of a world item (object), or None when no such item exists."""
        return self._find_id(self._objects._entities, item_id)

    def _holders(self) -> list[tuple[str, str, dict[str, Any]]]:
        """(kind, id, data) of every NPC and container that can hold items."""
        npcs = [("npc", eid, data) for eid, data in self._npcs._entities.items()]
        containers = [
            ("container", eid, data)
            for eid, data in self._objects._entities.items()
            if _is_container(data)
        ]
        return [*npcs, *containers]

    def holder_of(self, item_id: str) -> Optional[tuple[str, str]]:
        """(kind, id) of the NPC or container holding the item, ("player", "PLAYER") or None."""
        target = str(item_id).strip().upper()
        if self._player.has_item(target):
            return "player", "PLAYER"
        for kind, eid, data in self._holders():
            if any(ref_id(e) == target for e in current_inventory(self._changeset, eid, data)):
                return kind, eid
        return None

    def location(self, item_id: str) -> dict[str, str]:
        """Where an item is: {"type": player|npc|container|scene|destroyed|unknown, "id": ...}."""
        eid = self.item_id(item_id)
        if eid is None:
            return {"type": "unknown", "id": ""}
        holder = self.holder_of(eid)
        if holder is not None:
            return {"type": holder[0], "id": holder[1]}
        scene = self._objects.get(eid).current_scene_id
        if scene == DESTROYED_SCENE_ID:
            return {"type": "destroyed", "id": ""}
        return {"type": "scene", "id": scene}

    def contents(self, holder_id: str) -> list[ObjectProxy]:
        """Items held by the protagonist ("player"), an NPC or a container."""
        if str(holder_id).strip().lower() in _PLAYER_TARGETS:
            ids = self._player.item_ids
        else:
            ids = [ref_id(e) for e in self._holder_inventory(holder_id)]
        found = [self.item_id(i) for i in ids]
        return [self._objects.get(eid) for eid in found if eid]

    def _holder_inventory(self, holder_id: str) -> list[Any]:
        holder = self._resolve_holder(holder_id)
        if holder is None:
            return []
        _kind, eid, data = holder
        return current_inventory(self._changeset, eid, data)

    def _resolve_holder(self, holder_id: str) -> Optional[tuple[str, str, dict[str, Any]]]:
        target = str(holder_id or "").strip().upper()
        return next(
            ((k, eid, d) for k, eid, d in self._holders() if str(eid).upper() == target), None
        )

    # --- moving ----------------------------------------------------------------------------

    def detach(self, eid: str) -> Optional[Any]:
        """Removes the item from its holder; returns the entry it was held as (or None)."""
        holder = self.holder_of(eid)
        if holder is None:
            return None
        kind, holder_id = holder
        if kind == "player":
            return self._player._take_entry(eid)
        holder_data = (self._npcs if kind == "npc" else self._objects)._entities[holder_id]
        inventory = current_inventory(self._changeset, holder_id, holder_data)
        target = eid.upper()
        entry = next((e for e in inventory if ref_id(e) == target), None)
        remaining = [e for e in inventory if e is not entry]
        self._changeset.entity_updates.append({"entity_id": holder_id, "inventory": remaining})
        return entry

    def _place(self, eid: str, scene_id: str, *, hidden: bool, in_inventory: bool) -> None:
        self._changeset.entity_movements.append(
            {"entity_id": eid, "to_scene_id": scene_id, "to_spatial_position": ""}
        )
        self._changeset.entity_updates.append(
            {
                "entity_id": eid,
                "current_scene_id": scene_id,
                "is_in_inventory": in_inventory,
                "is_hidden": hidden,
            }
        )

    def _entry(self, eid: str, held_as: Any) -> dict[str, Any]:
        return inventory_entry(held_as or eid, self._objects._entities.get(eid))

    def to_player(self, item_id: str) -> Optional[dict[str, Any]]:
        """Moves a world item into the protagonist's inventory; returns its inventory entry."""
        eid = self.item_id(item_id)
        if eid is None:
            return None
        if self._player.has_item(eid):
            return self._entry(eid, None)
        entry = self._entry(eid, self.detach(eid))
        self._player._add_entry(entry)
        self._place(eid, INVENTORY_SCENE_ID, hidden=False, in_inventory=True)
        return entry

    def to_npc(self, item_id: str, npc_id: str) -> bool:
        """Moves a world item into an NPC's inventory."""
        eid = self.item_id(item_id)
        npc = self._find_id(self._npcs._entities, npc_id)
        if eid is None or npc is None:
            return False
        return self._into_holder(eid, npc, self._npcs._entities[npc], hidden=True)

    def to_container(self, item_id: str, container_id: str) -> bool:
        """Moves a world item into a container that lies in a scene."""
        eid = self.item_id(item_id)
        container = self.item_id(container_id)
        if eid is None or container is None or eid == container:
            return False
        data = self._objects._entities[container]
        if not _is_container(data) or self._player.has_item(container):
            return False
        return self._into_holder(eid, container, data, hidden=False)

    def _into_holder(self, eid: str, holder_id: str, holder_data: dict, *, hidden: bool) -> bool:
        if self.holder_of(eid) == ("npc" if hidden else "container", holder_id):
            return True
        entry = self._entry(eid, self.detach(eid))
        inventory = current_inventory(self._changeset, holder_id, holder_data)
        self._changeset.entity_updates.append(
            {"entity_id": holder_id, "inventory": [*inventory, entry]}
        )
        # Items in a container lie in the container's scene; NPCs carry theirs out of sight.
        holder_scene = INVENTORY_SCENE_ID
        if not hidden:
            holder_scene = self._objects.get(holder_id).current_scene_id or self._player_scene()
        self._place(eid, holder_scene, hidden=hidden, in_inventory=False)
        return True

    def to_scene(self, item_id: str, scene_id: Optional[str] = None) -> bool:
        """Moves a world item into a scene (default: the protagonist's scene)."""
        eid = self.item_id(item_id)
        if eid is None:
            return False
        target = str(scene_id or "").strip()
        if target.lower() in _HERE_TARGETS:
            target = self._player_scene()
        self.detach(eid)
        self._place(eid, target, hidden=False, in_inventory=False)
        return True

    def move(self, item_id: str, target: str) -> bool:
        """Moves an item to "player", an NPC, a container, "current"/"here" or a scene ID."""
        key = str(target or "").strip()
        if key.lower() in _PLAYER_TARGETS:
            return self.to_player(item_id) is not None
        if self._find_id(self._npcs._entities, key):
            return self.to_npc(item_id, key)
        container = self.item_id(key)
        if container and _is_container(self._objects._entities[container]):
            return self.to_container(item_id, container)
        return self.to_scene(item_id, key)

    # --- lifecycle -------------------------------------------------------------------------

    def destroy(self, item_id: str) -> bool:
        """Removes an item from the game for good (from its holder and from every scene)."""
        eid = self.item_id(item_id)
        if eid is None:
            return False
        self.detach(eid)
        self._place(eid, DESTROYED_SCENE_ID, hidden=True, in_inventory=False)
        self._changeset.entity_updates.append({"entity_id": eid, "is_destroyed": True})
        return True

    def set_hidden(self, item_id: str, hidden: bool) -> bool:
        eid = self.item_id(item_id)
        if eid is None:
            return False
        self._changeset.entity_updates.append({"entity_id": eid, "is_hidden": bool(hidden)})
        return True

    def clone(
        self, item_id: str, scene_id: Optional[str] = None, hidden: Optional[bool] = None
    ) -> Optional[ObjectProxy]:
        """Creates a copy of an item with a new ID; returns its proxy (None if impossible).

        The copy lies where the original lies when that is a scene, otherwise in the
        protagonist's scene, and keeps the original's hidden flag unless ``hidden`` is given.
        A cloned container starts empty.
        """
        source = self.item_id(item_id)
        if source is None or len(self._changeset.cloned_entities) >= MAX_CLONES_PER_SCRIPT:
            return None
        data = self._objects._entities[source]
        new_id = self._clone_id(str(data.get("cloned_from") or source))
        placement = self._clone_scene(source, scene_id)
        is_hidden = bool(data.get("is_hidden")) if hidden is None else bool(hidden)
        self._objects._entities[new_id] = {
            **data,
            "id": new_id,
            "cloned_from": source,
            "inventory": [],
            "current_scene_id": placement,
            "is_hidden": is_hidden,
            "is_in_inventory": False,
            "is_destroyed": False,
        }
        self._changeset.cloned_entities.append(
            {
                "source_id": source,
                "new_id": new_id,
                "current_scene_id": placement,
                "is_hidden": is_hidden,
            }
        )
        return self._objects.get(new_id)

    def _clone_scene(self, source: str, scene_id: Optional[str]) -> str:
        target = str(scene_id or "").strip()
        if target:
            return self._player_scene() if target.lower() in _HERE_TARGETS else target
        source_scene = self._objects.get(source).current_scene_id
        not_a_scene = ("", INVENTORY_SCENE_ID, DESTROYED_SCENE_ID)
        if self.holder_of(source) is None and source_scene not in not_a_scene:
            return source_scene
        return self._player_scene()

    def _clone_id(self, base: str) -> str:
        taken = {str(e).upper() for e in (*self._objects._entities, *self._npcs._entities)}
        stem = base[: _MAX_ID_LENGTH - 4]
        number = 1
        while f"{stem}_{number}".upper() in taken:
            number += 1
        return f"{stem}_{number}"
