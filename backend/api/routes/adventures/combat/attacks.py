"""Formatting helpers for weapon attack rolls (log text and animation payload)."""

from __future__ import annotations

from typing import Any

from backend.engine.combat.special_attacks import format_effects
from backend.engine.combat.weapons import DEFAULT_CATEGORY, WEAPON_CATEGORIES


def apply_strength_bonus(roll: dict[str, Any], strength_mod: int) -> dict[str, Any]:
    """Applies combat strength modifiers (buffs/debuffs) to the damage of a hit."""
    if not roll.get("is_hit") or not strength_mod:
        return roll
    adjusted = dict(roll)
    adjusted["damage_total"] = max(0, int(roll.get("damage_total") or 0) + strength_mod)
    adjusted["damage_bonus"] = int(roll.get("damage_bonus") or 0) + strength_mod
    return adjusted


def attack_log_text(
    attacker_name: str,
    roll: dict[str, Any],
    target_ac: int,
    weapon_name: str | None = None,
    target_name: str | None = None,
) -> str:
    """Chronicle line of a weapon attack, e.g. 'Batlin attacks Goblin with Practice Sword: ...'."""
    who = attacker_name
    if target_name or weapon_name:
        who = f"{attacker_name} attacks"
        who += f" {target_name}" if target_name else ""
        who += f" with {weapon_name}" if weapon_name else ""
        who += ":"
    head = (
        f"{who} ATTACK ROLL: {roll['hit_roll']} + {roll['hit_modifier']} = "
        f"{roll['hit_total']} vs AC {target_ac}"
    )
    if not roll.get("is_hit"):
        return f"{head} -> MISS"

    hit_status = "CRITICAL HIT" if roll.get("is_crit") else "HIT"
    dmg_bonus = int(roll.get("damage_bonus") or 0)
    bonus_str = (
        f" + {dmg_bonus}" if dmg_bonus > 0 else (f" - {abs(dmg_bonus)}" if dmg_bonus < 0 else "")
    )
    rolls = " + ".join(str(r) for r in roll.get("damage_rolls") or [])
    return (
        f"{head} -> {hit_status} | DMG {roll.get('damage_dice_str', '?')} ({rolls}{bonus_str})"
        f" = {roll.get('damage_total', 0)}"
    )


def on_hit_suffix(applied: list[dict[str, Any]]) -> str:
    """Chronicle text for a weapon's extra on-hit effects, e.g. ' On hit: Orc Stamina -3.'"""
    return f" On hit: {format_effects(applied)}." if applied else ""


def attack_event_data(
    actor: dict[str, Any],
    target: dict[str, Any],
    roll: dict[str, Any],
    target_ac: int,
    weapon_name: str,
    damage_applied: int,
    category: str = DEFAULT_CATEGORY,
) -> dict[str, Any]:
    """Animation payload of a weapon attack; ``category`` picks its animation and sounds."""
    effects = []
    if roll.get("is_hit"):
        effects.append(
            {
                "entity": target.get("id"),
                "name": target.get("name"),
                "stat": "hp",
                "delta": -damage_applied,
            }
        )
    return {
        "kind": "attack",
        "actor": actor.get("id"),
        "target": target.get("id"),
        "label": weapon_name,
        "category": category if category in WEAPON_CATEGORIES else DEFAULT_CATEGORY,
        "d20": roll.get("hit_roll"),
        "modifier": roll.get("hit_modifier"),
        "total": roll.get("hit_total"),
        "dc": target_ac,
        "success": bool(roll.get("is_hit")),
        "crit": bool(roll.get("is_crit")),
        "fumble": roll.get("hit_roll") == 1,
        "effects": effects,
    }
