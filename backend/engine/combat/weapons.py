"""Weapon attack configuration: category, attack-roll stat and on-hit effects.

Stored in a WEAPON item's ``metadata_json`` next to ``damage_dice`` and ``weapon_cost_*``:

* ``weapon_category``: ``MELEE`` (default), ``RANGED`` or ``MAGIC`` (flavour and UI icon).
* ``weapon_hit_stat``: stat added to the d20 attack roll. Defaults to ``dexterity``, which is
  what every weapon used before the setting existed, so older adventures keep their balance.
* ``weapon_effects``: extra effects applied when the attack hits, in the special-attack
  effect format (``{target: 'target'|'self', stat, amount}``), e.g. a poisoned dagger that
  drains stamina or a vampiric blade that heals its wielder.
"""

from __future__ import annotations

import re
from typing import Any

from backend.engine.combat.special_attacks import (
    SUCCESS_STATS,
    apply_stat_delta,
    normalize_effects,
    roll_amount,
)

WEAPON_DICE_RX = re.compile(r"^\d+d\d+([+-]\d+)?$")
WEAPON_CATEGORIES = ("MELEE", "RANGED", "MAGIC")
DEFAULT_CATEGORY = "MELEE"
DEFAULT_HIT_STAT = "dexterity"
MAX_WEAPON_EFFECTS = 4


def normalize_weapon_config(meta: dict[str, Any]) -> dict[str, Any]:
    """Category, attack-roll stat and on-hit effects of a weapon's metadata."""
    category = str(meta.get("weapon_category") or "").strip().upper()
    hit_stat = str(meta.get("weapon_hit_stat") or "").strip().lower()
    return {
        "category": category if category in WEAPON_CATEGORIES else DEFAULT_CATEGORY,
        "hit_stat": hit_stat if hit_stat in SUCCESS_STATS else DEFAULT_HIT_STAT,
        "effects": normalize_effects(meta.get("weapon_effects"))[:MAX_WEAPON_EFFECTS],
    }


def apply_on_hit_effects(
    effects: list[dict[str, str]], attacker: dict[str, Any], target: dict[str, Any]
) -> list[dict[str, Any]]:
    """Applies a hit's extra effects to the combatant dicts and returns what changed."""
    applied: list[dict[str, Any]] = []
    for effect in effects:
        recipient = attacker if effect["target"] == "self" else target
        value, detail = roll_amount(effect["amount"])
        delta = apply_stat_delta(recipient, effect["stat"], value)
        if not delta:
            continue
        applied.append(
            {
                "entity": recipient.get("id"),
                "name": recipient.get("name"),
                "stat": effect["stat"],
                "delta": delta,
                "roll": detail,
            }
        )
    return applied
