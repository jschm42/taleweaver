"""Keeps the protagonist's starting loadout free of duplicates.

An item is a single world object, so it is either in the backpack or in one equipment
slot, never in both. When an edit puts an item into a second place, the latest placement
wins and the item is removed from where it was before.
"""

from typing import Any, Optional

from backend.api.routes.adventures.editing.entity_update.fields import ref_id, ref_ids


def _slot_ids(equipment: Optional[dict[str, Any]]) -> dict[str, str]:
    """Slot -> item ID for every filled slot."""
    slots: dict[str, str] = {}
    for slot, entry in (equipment or {}).items():
        item_id = ref_id(entry)
        if item_id:
            slots[slot] = item_id
    return slots


def _dedupe_slots(equipment: dict[str, Any], old_slots: dict[str, str]) -> None:
    """An item in several slots keeps the slot it was just put in."""
    seen: dict[str, str] = {}
    for slot, item_id in _slot_ids(equipment).items():
        keeper = seen.get(item_id)
        if keeper is None:
            seen[item_id] = slot
            continue
        moved_here = old_slots.get(slot) != item_id
        loser = keeper if moved_here else slot
        equipment[loser] = None
        seen[item_id] = slot if moved_here else keeper


def resolve_loadout(
    old_inventory: Optional[list[Any]],
    old_equipment: Optional[dict[str, Any]],
    inventory: list[Any],
    equipment: dict[str, Any],
) -> tuple[list[Any], dict[str, Any]]:
    """Returns ``(inventory, equipment)`` with every item in exactly one place.

    Items newly added to the backpack leave their equipment slot; in every other
    conflict (newly equipped, or duplicates already stored) the equipment slot wins.
    """
    old_slots = _slot_ids(old_equipment)
    equipment = dict(equipment)
    _dedupe_slots(equipment, old_slots)

    newly_packed = ref_ids(inventory) - ref_ids(old_inventory)
    newly_equipped = set(_slot_ids(equipment).values()) - set(old_slots.values())
    unequip = newly_packed - newly_equipped
    for slot, item_id in _slot_ids(equipment).items():
        if item_id in unequip:
            equipment[slot] = None

    equipped = set(_slot_ids(equipment).values())
    inventory = [entry for entry in inventory if ref_id(entry) not in equipped]
    return inventory, equipment
