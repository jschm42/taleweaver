"""The companion's page of the hero dialog: ``sheet["companion"]``.

The hero dialog switches between the protagonist and the active companion. This builds the
companion's half: portrait, vitals, attributes (with equipment bonuses), party settings, the
items it carries (hydrated from the item rows, like the protagonist's inventory; equipped items
are listed under ``equipment`` instead) and its abilities with the player's on/off switches.
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.sheet_snapshot import entity_to_item_dict
from backend.engine.combat.npc_attack import NPC_ATTRIBUTE_KEYS, armor_class_value
from backend.engine.combat.special_attacks import normalize_special_actions
from backend.engine.party.companion_config import TACTICS, companion_config
from backend.engine.party.equipment import (
    EQUIPMENT_SLOTS,
    carried_equipment,
    equipment_modifiers,
)
from backend.engine.party.follow import companion_scene_id, is_out_of_action, session_npc
from backend.engine.party.party_state import read_party
from backend.engine.scripting.item_transfer import ref_id
from backend.models.session_state import SessionState
from backend.models.world_entity import WorldEntity


def held_entries(entity_states: dict[str, Any], row: WorldEntity) -> list[Any]:
    entry = entity_states.get(row.id) if isinstance(entity_states.get(row.id), dict) else {}
    held = entry.get("inventory")
    return list(held) if isinstance(held, list) else list(row.inventory or [])


async def held_items(
    db: AsyncSession, session_id: str, entries: list[Any], image_map: dict[str, Any]
) -> list[dict[str, Any]]:
    """Item dicts for the entries an NPC carries; the item rows supply name, type, image."""
    ids = [ref_id(entry) for entry in entries if ref_id(entry)]
    if not ids:
        return []
    res = await db.execute(
        select(WorldEntity).where(
            WorldEntity.session_id == session_id, func.upper(WorldEntity.id).in_(ids)
        )
    )
    rows = {str(row.id).upper(): row for row in res.scalars().all()}
    items: list[dict[str, Any]] = []
    for entry in entries:
        row = rows.get(ref_id(entry))
        item = entity_to_item_dict(row) if row is not None else dict(entry or {})
        if not isinstance(entry, dict) and row is None:
            item = {"id": str(entry), "name": str(entry)}
        item["image_url"] = image_map.get(item.get("id")) or item.get("image_url")
        items.append(item)
    return items


def _vitals(entity_states: dict[str, Any], row: WorldEntity) -> dict[str, Any]:
    entry = entity_states.get(row.id) if isinstance(entity_states.get(row.id), dict) else {}
    vitals = {}
    for key in ("hp", "max_hp", "mana", "max_mana", "stamina", "max_stamina"):
        value = entry.get(key, getattr(row, key, None))
        vitals[key] = value if isinstance(value, int) else None
    return vitals


def _attributes(row: WorldEntity, modifiers: dict[str, int]) -> dict[str, Any]:
    """Attributes and armor class including the bonuses of the equipped items."""
    stats = {}
    for key in NPC_ATTRIBUTE_KEYS:
        base = getattr(row, f"stat_modifier_{key}", None)
        stats[key] = (base if isinstance(base, int) else 10) + modifiers.get(key, 0)
    stats["armor_class"] = armor_class_value(row.stat_modifier_armor_class) + modifiers.get(
        "armor_class", 0
    )
    return stats


def _abilities(row: WorldEntity, party: Any) -> list[dict[str, Any]]:
    """The NPC's special actions (editor) with the player's on/off switch."""
    meta = row.metadata_json if isinstance(row.metadata_json, dict) else {}
    return [
        {
            "id": action["id"],
            "name": action["name"],
            "description": action["description"],
            "category": action["category"],
            "cost_type": action["cost_type"],
            "cost": action["cost"],
            "enabled": party.ability_enabled(row.id, action["id"]),
        }
        for action in normalize_special_actions(meta.get("special_actions"))
    ]


async def build_companion_sheet(
    db: AsyncSession, state: SessionState, image_map: dict[str, Any]
) -> Optional[dict[str, Any]]:
    """The active companion's sheet, or None without one."""
    party = read_party(state.entity_states)
    row = await session_npc(db, state.session_id, party.active_id) if party.active_id else None
    if row is None:
        return None
    states = dict(state.entity_states or {})
    config = companion_config(row.metadata_json if isinstance(row.metadata_json, dict) else {})
    default_tactics = config.tactics if config else TACTICS[0]
    items = await held_items(db, state.session_id, held_entries(states, row), image_map)
    by_id = {str(item.get("id", "")).upper(): item for item in items}
    equipped = carried_equipment(states, row.id, set(by_id))
    equipped_items = [by_id[item_id.upper()] for item_id in equipped.values()]
    equipped_ids = {item_id.upper() for item_id in equipped.values()}
    return {
        "id": row.id,
        "name": row.name,
        "description": row.description,
        "npc_type": row.npc_type,
        "image_url": image_map.get(row.id) or row.image_url,
        **_vitals(states, row),
        "stats": _attributes(row, equipment_modifiers(equipped_items)),
        "inventory": [i for i in items if str(i.get("id", "")).upper() not in equipped_ids],
        "equipment": {
            slot: by_id.get(equipped[slot].upper()) if slot in equipped else None
            for slot in EQUIPMENT_SLOTS
        },
        "abilities": _abilities(row, party),
        "present": companion_scene_id(states, row) == str(state.current_scene_id or ""),
        "following": party.following,
        "is_defeated": is_out_of_action(states, row),
        "tactics": party.tactics.get(row.id) or default_tactics,
        "banter": config.banter if config else "NORMAL",
    }
