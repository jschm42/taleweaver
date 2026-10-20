"""Expected-value math for the play-agent combat tactician.

Mirrors the dice rules of the combat engine (weapon attack rolls in ``skill_check.roll_attack``
and special attack resolution in ``engine.combat.special_attacks``) without rolling anything.
"""

from __future__ import annotations

import re
from typing import Any

from backend.engine.combat.special_attacks import effective_ac, stat_modifier

D20_FACES = range(1, 21)
_AMOUNT_RX = re.compile(r"^([+-])?(?:(\d+)d(\d+)([+-]\d+)?|(\d+))$")


def average_amount(expr: Any) -> float:
    """Average signed value of an amount like ``-2d6+1``, ``+5``, ``1d8`` or ``3``."""
    match = _AMOUNT_RX.match(str(expr or "").replace(" ", "").lower())
    if not match:
        return 0.0
    sign = -1 if match.group(1) == "-" else 1
    if match.group(5) is not None:
        return float(sign * int(match.group(5)))
    count = min(int(match.group(2)), 50)
    sides = max(1, int(match.group(3)))
    bonus = int(match.group(4) or 0)
    return float(sign * max(0.0, count * (sides + 1) / 2 + bonus))


def weapon_hit_chances(player: dict[str, Any], target: dict[str, Any]) -> tuple[float, float]:
    """Returns (hit chance incl. crits, crit chance) of a weapon attack against ``target``."""
    stats = player.get("stats") or {}
    mods = player.get("modifiers") or {}
    dexterity = int(stats.get("dexterity", 10))
    target_ac = max(1, effective_ac(target) - int(mods.get("dexterity", 0)))
    crit_threshold = max(15, 20 - max(0, (dexterity - 10) // 4))
    crits = sum(1 for d20 in D20_FACES if d20 >= crit_threshold)
    hits = sum(1 for d20 in D20_FACES if d20 >= crit_threshold or d20 + dexterity >= target_ac)
    return hits / 20, crits / 20


def expected_weapon_damage(
    player: dict[str, Any], target: dict[str, Any], weapon: dict[str, Any]
) -> float:
    hit_chance, crit_chance = weapon_hit_chances(player, target)
    dice_avg = average_amount(weapon.get("dice"))
    strength_mod = int((player.get("modifiers") or {}).get("strength", 0))
    normal_hit = hit_chance - crit_chance
    return max(0.0, normal_hit * dice_avg + crit_chance * 2 * dice_avg + hit_chance * strength_mod)


def special_success_chances(
    action: dict[str, Any], caster: dict[str, Any], target: dict[str, Any] | None
) -> tuple[float, float]:
    """Returns (success chance incl. crits, crit chance) of a special action."""
    needs_roll = action.get("targets_enemy") or action.get("difficulty") is not None
    if not needs_roll:
        return 1.0, 0.0
    modifier = stat_modifier(caster, action.get("success_stat") or "intelligence")
    dc = action.get("difficulty")
    if dc is None:
        dc = effective_ac(target) if target else 10
    successes = sum(1 for d20 in D20_FACES if d20 == 20 or (d20 != 1 and d20 + modifier >= dc))
    return successes / 20, 1 / 20


def expected_special_effect(
    action: dict[str, Any],
    caster: dict[str, Any],
    target: dict[str, Any] | None,
    recipient: str,
    stat: str = "hp",
) -> float:
    """Expected signed change of ``stat`` on the effect ``recipient`` ("target" or "self")."""
    success, crit = special_success_chances(action, caster, target)
    total = 0.0
    for effect in action.get("effects") or []:
        if effect.get("target") != recipient or effect.get("stat") != stat:
            continue
        avg = average_amount(effect.get("amount"))
        crit_bonus = crit * avg if recipient == "target" else 0.0
        total += success * avg + crit_bonus
    return total
