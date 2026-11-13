"""The companion's equipment: slot -> item ID in ``entity_states[<npc>]["equipment"]``.

Equipped items stay in the companion's carried inventory (``entity_states[<npc>]["inventory"]``),
so the scripting ``ItemMover`` still sees exactly one holder per item. The equipment map only
says which carried item sits in which slot; readers drop slots whose item the companion no longer
carries (``carried_equipment``). The slots are the protagonist's slots.
"""

from __future__ import annotations

from typing import Any, Optional

from backend.engine.scripting.item_transfer import ref_id

EQUIPMENT_SLOTS = (
    "Head",
    "Neck",
    "Chest",
    "Arms",
    "Hands",
    "MainHand",
    "OffHand",
    "Ring_1",
    "Ring_2",
    "Legs",
    "Feet",
)
EQUIPMENT_KEY = "equipment"
STAT_MODIFIER_FIELDS = {
    "strength": "stat_modifier_strength",
    "dexterity": "stat_modifier_dexterity",
    "intelligence": "stat_modifier_intelligence",
    "wisdom": "stat_modifier_wisdom",
    "charisma": "stat_modifier_charisma",
    "armor_class": "stat_modifier_armor_class",
}
_SLOT_ALIASES = {"hand": "Hands", "ring": "Ring_1", "weapon": "MainHand", "shield": "OffHand"}
_EQUIPPABLE_TYPES = {"WEAPON", "WEARABLE"}


def _entry(entity_states: dict[str, Any], npc_id: str) -> dict[str, Any]:
    raw = entity_states.get(npc_id)
    return dict(raw) if isinstance(raw, dict) else {}


def read_equipment(entity_states: Any, npc_id: str) -> dict[str, str]:
    """Slot -> item ID of everything the companion has equipped."""
    states = entity_states if isinstance(entity_states, dict) else {}
    raw = _entry(states, npc_id).get(EQUIPMENT_KEY)
    if not isinstance(raw, dict):
        return {}
    return {slot: str(item) for slot, item in raw.items() if slot in EQUIPMENT_SLOTS and item}


def carried_equipment(entity_states: Any, npc_id: str, held_ids: set[str]) -> dict[str, str]:
    """The equipment map without items the companion no longer carries (given away, moved)."""
    return {
        slot: item
        for slot, item in read_equipment(entity_states, npc_id).items()
        if ref_id(item) in held_ids
    }


def _store(entity_states: dict[str, Any], npc_id: str, equipment: dict[str, str]) -> None:
    entry = _entry(entity_states, npc_id)
    entry[EQUIPMENT_KEY] = dict(equipment)
    entity_states[npc_id] = entry


def normalize_slot(raw: Any) -> Optional[str]:
    text = str(raw or "").strip()
    if not text:
        return None
    by_lower = {slot.lower(): slot for slot in EQUIPMENT_SLOTS}
    return by_lower.get(text.lower()) or _SLOT_ALIASES.get(text.lower())


def _wearable_slots(item: dict[str, Any]) -> list[str]:
    raw = item.get("wearable_slots")
    values = raw if isinstance(raw, list) else [raw] if raw else []
    return [slot for slot in (normalize_slot(v) for v in values) if slot]


def is_equippable(item: dict[str, Any]) -> bool:
    item_type = str(item.get("item_type") or "").upper()
    return item_type in _EQUIPPABLE_TYPES or bool(_wearable_slots(item))


def choose_slot(item: dict[str, Any], requested: Any, equipment: dict[str, str]) -> Optional[str]:
    """The slot an item goes to: the requested one, else a free fitting one, else the first."""
    if requested:
        return normalize_slot(requested)
    candidates = _wearable_slots(item)
    if not candidates and str(item.get("item_type") or "").upper() == "WEAPON":
        candidates = ["MainHand", "OffHand"]
    if not candidates and normalize_slot(item.get("slot")):
        candidates = [normalize_slot(item.get("slot"))]
    free = [slot for slot in candidates if slot not in equipment]
    return (free or candidates or [None])[0]


def equip_item(
    entity_states: dict[str, Any], npc_id: str, item_id: str, slot: str
) -> Optional[str]:
    """Puts a carried item into ``slot``; returns the item it replaced (if any)."""
    equipment = {s: i for s, i in read_equipment(entity_states, npc_id).items() if i != item_id}
    replaced = equipment.get(slot)
    equipment[slot] = item_id
    _store(entity_states, npc_id, equipment)
    return replaced


def unequip_slot(entity_states: dict[str, Any], npc_id: str, slot: str) -> Optional[str]:
    """Empties ``slot``; returns the item that was in it (it stays carried)."""
    equipment = read_equipment(entity_states, npc_id)
    item_id = equipment.pop(slot, None)
    if item_id:
        _store(entity_states, npc_id, equipment)
    return item_id


def equipment_modifiers(items: list[dict[str, Any]]) -> dict[str, int]:
    """Summed stat modifiers of equipped item dicts (attributes and armor class)."""
    totals = dict.fromkeys(STAT_MODIFIER_FIELDS, 0)
    for item in items:
        for stat, field in STAT_MODIFIER_FIELDS.items():
            value = item.get(field)
            if value is None:
                value = item.get(stat)
            totals[stat] += value if isinstance(value, int) else 0
    return totals
