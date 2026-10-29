"""Special attack definitions and resolution for turn-based combat.

A special attack is configured on the protagonist (``avatar.stats["special_actions"]``)
or on an NPC (``metadata_json["special_actions"]``). Every attack costs mana or stamina,
is resolved with a d20 success roll and applies a list of stat effects either to the
caster (``self``) or to the attacked combatant (``target``). Effects can be anything from
classic fire damage to an absurd insult that drains the target's charisma.

Combatants are plain dicts (see ``combatant_view`` in the combat route package):
``{"id", "name", "hp", "max_hp", "mana", "max_mana", "stamina", "max_stamina",
"stats": {...}, "ac": int, "modifiers": {...}}``.
"""

from __future__ import annotations

import random
import re
from typing import Any, Optional

RESOURCE_STATS = ("hp", "mana", "stamina")
ATTRIBUTE_STATS = ("strength", "dexterity", "intelligence", "wisdom", "charisma", "armor_class")
EFFECT_STATS = RESOURCE_STATS + ATTRIBUTE_STATS
SUCCESS_STATS = ("strength", "dexterity", "intelligence", "wisdom", "charisma")
CATEGORIES = ("MAGIC", "MELEE", "RANGED", "SOCIAL", "OTHER")
COST_TYPES = ("mana", "stamina")
ACTION_TYPES = ("ATTACK", "HEAL", "UTILITY")
EFFECT_TARGETS = ("target", "self")
TARGET_SCOPES = ("SINGLE", "SPLASH", "ALL_ENEMIES")
MAX_SPLASH_RADIUS = 2

CATEGORY_DEFAULT_STAT = {
    "MAGIC": "intelligence",
    "MELEE": "strength",
    "RANGED": "dexterity",
    "SOCIAL": "charisma",
    "OTHER": "wisdom",
}
SELF_ONLY_DEFAULT_DC = 10
MODIFIER_CAP = 20
LEGACY_DEFAULT_VALUE = "10"

STAT_LABELS = {
    "hp": "HP",
    "mana": "Mana",
    "stamina": "Stamina",
    "strength": "Strength",
    "dexterity": "Dexterity",
    "intelligence": "Intelligence",
    "wisdom": "Wisdom",
    "charisma": "Charisma",
    "armor_class": "AC",
}

_AMOUNT_RX = re.compile(r"^([+-])?(?:(\d+)d(\d+)([+-]\d+)?|(\d+))$")


def _as_int(value: Any, fallback: int = 0) -> int:
    if isinstance(value, bool):
        return fallback
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str) and re.fullmatch(r"-?\d+", value.strip()):
        return int(value.strip())
    return fallback


def _pick(value: Any, allowed: tuple[str, ...], fallback: str, upper: bool = True) -> str:
    text = str(value or "").strip()
    text = text.upper() if upper else text.lower()
    return text if text in allowed else fallback


def is_valid_amount(expr: Any) -> bool:
    return bool(_AMOUNT_RX.match(str(expr or "").replace(" ", "").lower()))


def roll_amount(expr: str) -> tuple[int, str]:
    """Rolls a signed amount like ``-2d6+1``, ``+5`` or ``3``. Returns (value, detail)."""
    match = _AMOUNT_RX.match(str(expr or "").replace(" ", "").lower())
    if not match:
        return 0, "0"
    sign = -1 if match.group(1) == "-" else 1
    if match.group(5) is not None:
        value = int(match.group(5))
        return sign * value, str(value)

    count = min(int(match.group(2)), 50)
    sides = max(1, int(match.group(3)))
    bonus = int(match.group(4) or 0)
    rolls = [random.randint(1, sides) for _ in range(count)]
    value = max(0, sum(rolls) + bonus)
    bonus_str = f"{bonus:+d}" if bonus else ""
    detail = f"{count}d{sides}{bonus_str} ({'+'.join(str(r) for r in rolls)}{bonus_str}) = {value}"
    return sign * value, detail


def _normalize_effect(raw: Any) -> Optional[dict[str, str]]:
    if not isinstance(raw, dict):
        return None
    stat = str(raw.get("stat") or "").strip().lower()
    amount = str(raw.get("amount") or "").replace(" ", "")
    if stat not in EFFECT_STATS or not is_valid_amount(amount):
        return None
    target = _pick(raw.get("target"), EFFECT_TARGETS, "target", upper=False)
    return {"target": target, "stat": stat, "amount": amount}


def _legacy_effects(raw: dict[str, Any], action_type: str) -> list[dict[str, str]]:
    """Maps the original ATTACK/HEAL damage fields onto the generic effect model."""
    value = str(raw.get("damage_value") or LEGACY_DEFAULT_VALUE).replace(" ", "").lstrip("+-")
    if not is_valid_amount(value):
        value = LEGACY_DEFAULT_VALUE
    if action_type == "ATTACK":
        return [{"target": "target", "stat": "hp", "amount": f"-{value}"}]
    if action_type == "HEAL":
        return [{"target": "self", "stat": "hp", "amount": f"+{value}"}]
    return []


def normalize_special_action(raw: Any) -> Optional[dict[str, Any]]:
    """Normalizes legacy and extended special action definitions into one shape."""
    if not isinstance(raw, dict) or not str(raw.get("id") or "").strip():
        return None

    action_type = _pick(raw.get("action_type"), ACTION_TYPES, "ATTACK")
    category = _pick(raw.get("category"), CATEGORIES, "MAGIC")
    cost_type = _pick(raw.get("cost_type"), COST_TYPES, "mana", upper=False)
    legacy_cost = _as_int(raw.get("mana_cost")) if cost_type == "mana" else 0
    cost = max(0, _as_int(raw.get("cost"), legacy_cost))

    effects = [e for e in (_normalize_effect(item) for item in raw.get("effects") or []) if e]
    if not effects:
        effects = _legacy_effects(raw, action_type)

    difficulty = _as_int(raw.get("difficulty"))
    success_stat = _pick(
        raw.get("success_stat"), SUCCESS_STATS, CATEGORY_DEFAULT_STAT[category], upper=False
    )
    save_stat = _pick(raw.get("save_stat"), SUCCESS_STATS, "", upper=False) or None
    return {
        "id": str(raw.get("id")).strip(),
        "name": str(raw.get("name") or raw.get("id")).strip(),
        "description": str(raw.get("description") or ""),
        "action_type": action_type,
        "category": category,
        "cost_type": cost_type,
        "cost": cost,
        "success_stat": success_stat,
        "difficulty": difficulty if difficulty > 0 else None,
        "effects": effects,
        "targets_enemy": any(e["target"] == "target" for e in effects),
        "target_scope": _pick(raw.get("target_scope"), TARGET_SCOPES, "SINGLE"),
        "splash_radius": max(1, min(MAX_SPLASH_RADIUS, _as_int(raw.get("splash_radius"), 1))),
        "save_stat": save_stat,
        "spares_passive": bool(raw.get("spares_passive")),
        "outcome_description": str(raw.get("outcome_description") or ""),
        "is_locked": bool(raw.get("is_locked")),
        "unlock_condition_type": raw.get("unlock_condition_type"),
        "unlock_condition_target": raw.get("unlock_condition_target"),
        # Unlock hints for the UI; guard code and scripts stay server-side.
        "unlock_required_item_id": raw.get("unlock_required_item_id") or None,
        "unlock_required_scene_id": raw.get("unlock_required_scene_id") or None,
        "unlock_required_defeated_npc_id": raw.get("unlock_required_defeated_npc_id") or None,
        "has_unlock_guard": bool(str(raw.get("unlock_guard_expression") or "").strip()),
    }


def normalize_special_actions(raw_list: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_list, list):
        return []
    return [a for a in (normalize_special_action(item) for item in raw_list) if a]


def stat_modifier(combatant: dict[str, Any], stat: str) -> int:
    base = _as_int((combatant.get("stats") or {}).get(stat), 10)
    bonus = _as_int((combatant.get("modifiers") or {}).get(stat))
    return max(0, (base + bonus - 10) // 2)


def effective_ac(combatant: dict[str, Any]) -> int:
    bonus = _as_int((combatant.get("modifiers") or {}).get("armor_class"))
    return max(1, _as_int(combatant.get("ac"), 10) + bonus)


def can_afford(attack: dict[str, Any], caster: dict[str, Any]) -> bool:
    return _as_int(caster.get(attack["cost_type"])) >= int(attack["cost"])


def apply_stat_delta(combatant: dict[str, Any], stat: str, delta: int) -> int:
    """Applies a delta and returns the amount that actually changed."""
    if stat in RESOURCE_STATS:
        current = _as_int(combatant.get(stat))
        cap = _as_int(combatant.get(f"max_{stat}"), current) or max(current, 0)
        new_value = max(0, min(max(cap, current), current + delta))
        combatant[stat] = new_value
        return new_value - current

    modifiers = dict(combatant.get("modifiers") or {})
    current = _as_int(modifiers.get(stat))
    new_value = max(-MODIFIER_CAP, min(MODIFIER_CAP, current + delta))
    modifiers[stat] = new_value
    combatant["modifiers"] = modifiers
    return new_value - current


def _success_roll(
    attack: dict[str, Any], caster: dict[str, Any], target: Optional[dict[str, Any]]
) -> dict[str, Any]:
    needs_roll = attack["targets_enemy"] or attack["difficulty"] is not None
    if not needs_roll:
        return {"rolled": False, "success": True, "crit": False, "fumble": False}

    modifier = stat_modifier(caster, attack["success_stat"])
    dc = attack["difficulty"]
    if dc is None:
        dc = effective_ac(target) if target else SELF_ONLY_DEFAULT_DC
    d20 = random.randint(1, 20)
    total = d20 + modifier
    crit = d20 == 20
    fumble = d20 == 1
    return {
        "rolled": True,
        "d20": d20,
        "modifier": modifier,
        "total": total,
        "dc": dc,
        "crit": crit,
        "fumble": fumble,
        "success": crit or (not fumble and total >= dc),
    }


def _apply_effects(
    attack: dict[str, Any],
    caster: dict[str, Any],
    target: Optional[dict[str, Any]],
    crit: bool,
) -> list[dict[str, Any]]:
    applied: list[dict[str, Any]] = []
    for effect in attack["effects"]:
        recipient = caster if effect["target"] == "self" else target
        if recipient is None:
            continue
        value, detail = roll_amount(effect["amount"])
        if crit and effect["target"] == "target":
            value *= 2
        delta = apply_stat_delta(recipient, effect["stat"], value)
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


def resolve_special_attack(
    attack: dict[str, Any], caster: dict[str, Any], target: Optional[dict[str, Any]]
) -> dict[str, Any]:
    """Pays the cost, rolls for success and applies effects. Mutates the combatant dicts."""
    caster[attack["cost_type"]] = max(0, _as_int(caster.get(attack["cost_type"])) - attack["cost"])
    roll = _success_roll(attack, caster, target)
    effects = _apply_effects(attack, caster, target, roll["crit"]) if roll["success"] else []
    return {
        **roll,
        "kind": "special",
        "action_id": attack["id"],
        "action_name": attack["name"],
        "category": attack["category"],
        "stat": attack["success_stat"],
        "actor": caster.get("id"),
        "target": target.get("id") if target and attack["targets_enemy"] else None,
        "cost": {"type": attack["cost_type"], "amount": attack["cost"]},
        "effects": effects,
    }


def format_effects(effects: list[dict[str, Any]]) -> str:
    parts = []
    for eff in effects:
        label = STAT_LABELS.get(eff["stat"], eff["stat"])
        parts.append(f"{eff['name']} {label} {eff['delta']:+d}")
    return ", ".join(parts)


def _roll_verdict(result: dict[str, Any]) -> str:
    if result["crit"]:
        return "CRITICAL SUCCESS"
    if result["fumble"]:
        return "FUMBLE"
    return "SUCCESS" if result["success"] else "FAILED"


def describe_special_result(
    caster_name: str, target_name: Optional[str], result: dict[str, Any]
) -> str:
    cost = result["cost"]
    on_target = f" on {target_name}" if result.get("target") and target_name else ""
    head = f"{caster_name} uses {result['action_name']}{on_target}"
    if cost["amount"]:
        head += f" ({STAT_LABELS[cost['type']]} -{cost['amount']})"

    text = head + "."
    if result["rolled"]:
        stat_label = STAT_LABELS.get(result["stat"], result["stat"])
        text = (
            f"{head}. {stat_label} roll: {result['d20']} + {result['modifier']} = "
            f"{result['total']} vs DC {result['dc']} -> {_roll_verdict(result)}."
        )
    if result["effects"]:
        text += f" {format_effects(result['effects'])}."
    elif result["success"]:
        text += " No noticeable effect."
    return text
