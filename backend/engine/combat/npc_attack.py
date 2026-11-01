"""Configurable NPC main attack and combat profile (stats + armor class).

An NPC's main attack lives in ``metadata_json["main_attack"]`` and needs no item::

    {
        "name": "Longsword",          # shown in the combat log
        "category": "MELEE",          # MELEE | RANGED | MAGIC (flavour and UI icon)
        "damage_dice": "1d8+2",       # rolled on a hit
        "hit_stat": "strength",       # stat added to the d20 attack roll
        "cost_type": "stamina",       # stamina | mana
        "cost": 0,                    # paid per attack; 0 = free
        "effects": [...],             # on-hit effects, same format as weapon_effects
    }

The NPC attacks with, in this order: its ``main_attack``, the deprecated equipped weapon item
(``equipped_weapon_id``) and finally an unarmed ``1d6`` attack.

NPC attributes are stored in the entity's ``stat_modifier_*`` columns as absolute values
(default 10). The armor class is stored as an offset to the base of 10 in
``stat_modifier_armor_class``; :func:`armor_class_column` and :func:`armor_class_value` convert.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from backend.engine.combat.special_attacks import SUCCESS_STATS, normalize_effects
from backend.engine.combat.weapons import MAX_WEAPON_EFFECTS, WEAPON_CATEGORIES

ATTACK_DICE_RX = re.compile(r"^\d+d\d+([+-]\d+)?$")
COST_TYPES = ("stamina", "mana")
DEFAULT_ATTACK_DICE = "1d6"
DEFAULT_ATTACK_NAME = "Attack"
DEFAULT_HIT_STAT = "dexterity"
MAX_ATTACK_COST = 999
MAX_ATTACK_NAME = 60

NPC_BASE_ATTRIBUTE = 10
NPC_BASE_AC = 10
NPC_ATTRIBUTE_KEYS = ("strength", "dexterity", "intelligence", "wisdom", "charisma")
NPC_STAT_COLUMNS = {key: f"stat_modifier_{key}" for key in NPC_ATTRIBUTE_KEYS}
AC_COLUMN = "stat_modifier_armor_class"


def _clean_dice(value: Any) -> Optional[str]:
    dice = str(value or "").replace(" ", "").lower()
    return dice if ATTACK_DICE_RX.match(dice) else None


def _clean_cost(value: Any) -> int:
    try:
        cost = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, min(MAX_ATTACK_COST, cost))


def normalize_main_attack(raw: Any) -> Optional[dict[str, Any]]:
    """The stored main attack with defaults filled in, or None when none is configured."""
    if not isinstance(raw, dict):
        return None
    name = str(raw.get("name") or "").strip()[:MAX_ATTACK_NAME]
    dice = _clean_dice(raw.get("damage_dice") or raw.get("dice"))
    if not name and not dice:
        return None
    category = str(raw.get("category") or "").strip().upper()
    hit_stat = str(raw.get("hit_stat") or "").strip().lower()
    cost_type = str(raw.get("cost_type") or "").strip().lower()
    return {
        "name": name or DEFAULT_ATTACK_NAME,
        "category": category if category in WEAPON_CATEGORIES else "MELEE",
        "damage_dice": dice or DEFAULT_ATTACK_DICE,
        "hit_stat": hit_stat if hit_stat in SUCCESS_STATS else DEFAULT_HIT_STAT,
        "cost_type": cost_type if cost_type in COST_TYPES else "stamina",
        "cost": _clean_cost(raw.get("cost")),
        "effects": normalize_effects(raw.get("effects"))[:MAX_WEAPON_EFFECTS],
    }


def main_attack_profile(raw: Any) -> Optional[dict[str, Any]]:
    """The main attack in the weapon-profile shape the combat engine resolves."""
    attack = normalize_main_attack(raw)
    if attack is None:
        return None
    return {
        "name": attack["name"],
        "cost_type": attack["cost_type"],
        "cost": attack["cost"],
        "dice": attack["damage_dice"],
        "category": attack["category"],
        "hit_stat": attack["hit_stat"],
        "effects": attack["effects"],
    }


def armor_class_column(armor_class: int) -> int:
    """Absolute armor class -> value stored in ``stat_modifier_armor_class``."""
    return int(armor_class) - NPC_BASE_AC


def armor_class_value(column_value: Any) -> int:
    """Stored ``stat_modifier_armor_class`` -> absolute armor class."""
    return NPC_BASE_AC + (column_value if isinstance(column_value, int) else 0)


def _int_or_none(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    try:
        return None if value is None or value == "" else int(value)
    except (TypeError, ValueError):
        return None


def npc_stat_columns(npc: dict[str, Any]) -> dict[str, Optional[int]]:
    """Entity columns for a manifest NPC.

    Generated manifests and blueprints use absolute ``strength`` ... ``armor_class``;
    exported manifests carry the raw ``stat_modifier_*`` columns. Absolute values win.
    """
    columns: dict[str, Optional[int]] = {}
    for key, column in NPC_STAT_COLUMNS.items():
        value = _int_or_none(npc.get(key))
        columns[column] = value if value is not None else _int_or_none(npc.get(column))
    armor_class = _int_or_none(npc.get("armor_class"))
    columns[AC_COLUMN] = (
        armor_class_column(armor_class)
        if armor_class is not None
        else _int_or_none(npc.get(AC_COLUMN))
    )
    return columns
