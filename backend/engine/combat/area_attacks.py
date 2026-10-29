"""Area-of-effect resolution for special attacks (``target_scope`` SPLASH / ALL_ENEMIES).

An area attack pays its cost once and rolls each ``target`` effect amount once. Without a
``save_stat`` the caster makes one d20 roll that is compared against every target's AC (or
the fixed ``difficulty``). With a ``save_stat`` the attack always goes off and every target
rolls a saving throw against ``difficulty`` (default 12), taking half on a success. Splash
neighbours of the primary target receive half of what they would otherwise take.

See ``docs/specs/combat-aoe-abilities.md``.
"""

from __future__ import annotations

import random
from typing import Any, Optional

from backend.engine.combat.special_attacks import (
    STAT_LABELS,
    apply_stat_delta,
    effective_ac,
    format_effects,
    roll_amount,
    stat_modifier,
)

DEFAULT_SAVE_DC = 12
REDUCED_FACTOR = 0.5


def is_area_attack(attack: dict[str, Any]) -> bool:
    return bool(attack.get("targets_enemy")) and attack.get("target_scope", "SINGLE") != "SINGLE"


def select_area_targets(
    attack: dict[str, Any], candidates: list[dict[str, Any]], primary_id: Optional[str]
) -> list[dict[str, Any]]:
    """Picks the hit combatants from the alive encounter enemies (in encounter order).

    Passive (not engaged) enemies are hit too unless the attack ``spares_passive``; the
    primary target always is.
    """
    pool = [
        c
        for c in candidates
        if c.get("engaged") or not attack.get("spares_passive") or c.get("id") == primary_id
    ]
    if attack.get("target_scope") == "ALL_ENEMIES":
        return pool
    ids = [c.get("id") for c in pool]
    if primary_id not in ids:
        return []
    idx = ids.index(primary_id)
    radius = int(attack.get("splash_radius") or 1)
    return pool[max(0, idx - radius) : idx + radius + 1]


def _caster_roll(attack: dict[str, Any], caster: dict[str, Any]) -> dict[str, Any]:
    if attack.get("save_stat"):
        return {"rolled": False, "success": True, "crit": False, "fumble": False}
    modifier = stat_modifier(caster, attack["success_stat"])
    d20 = random.randint(1, 20)
    return {
        "rolled": True,
        "d20": d20,
        "modifier": modifier,
        "total": d20 + modifier,
        "crit": d20 == 20,
        "fumble": d20 == 1,
    }


def _saving_throw(attack: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    dc = attack.get("difficulty") or DEFAULT_SAVE_DC
    d20 = random.randint(1, 20)
    modifier = stat_modifier(target, attack["save_stat"])
    total = d20 + modifier
    saved = d20 == 20 or (d20 != 1 and total >= dc)
    return {"d20": d20, "modifier": modifier, "total": total, "dc": dc, "success": saved}


def _target_outcome(
    attack: dict[str, Any], roll: dict[str, Any], target: dict[str, Any], primary_id: Optional[str]
) -> tuple[float, dict[str, Any]]:
    """Returns the share of the effects the target takes (0, 0.5, 1) and its log entry."""
    entry: dict[str, Any] = {"id": target.get("id"), "name": target.get("name")}
    if attack.get("save_stat"):
        save = _saving_throw(attack, target)
        entry["save"] = save
        factor = REDUCED_FACTOR if save["success"] else 1.0
    else:
        dc = attack.get("difficulty") or effective_ac(target)
        hit = roll["crit"] or (not roll["fumble"] and roll["total"] >= dc)
        entry.update(hit=hit, dc=dc)
        factor = 1.0 if hit else 0.0
    if attack.get("target_scope") == "SPLASH" and target.get("id") != primary_id:
        factor *= REDUCED_FACTOR
    return factor, entry


def _effect_entry(recipient: dict[str, Any], stat: str, delta: int, detail: str) -> dict[str, Any]:
    return {
        "entity": recipient.get("id"),
        "name": recipient.get("name"),
        "stat": stat,
        "delta": delta,
        "roll": detail,
    }


def resolve_area_attack(
    attack: dict[str, Any],
    caster: dict[str, Any],
    targets: list[dict[str, Any]],
    primary_id: Optional[str],
) -> dict[str, Any]:
    """Pays the cost, resolves every target and applies effects. Mutates the combatant dicts."""
    caster[attack["cost_type"]] = max(0, int(caster.get(attack["cost_type"]) or 0) - attack["cost"])
    roll = _caster_roll(attack, caster)
    target_effects = [e for e in attack["effects"] if e["target"] == "target"]
    amounts = [roll_amount(e["amount"]) for e in target_effects]
    crit_factor = 2 if roll["crit"] else 1

    applied: list[dict[str, Any]] = []
    outcomes: list[dict[str, Any]] = []
    for target in targets:
        factor, entry = _target_outcome(attack, roll, target, primary_id)
        outcomes.append(entry)
        if factor <= 0:
            continue
        for effect, (value, detail) in zip(target_effects, amounts, strict=True):
            delta = apply_stat_delta(target, effect["stat"], int(value * crit_factor * factor))
            applied.append(_effect_entry(target, effect["stat"], delta, detail))

    success = any(o.get("hit", True) for o in outcomes)
    if success:
        for effect in (e for e in attack["effects"] if e["target"] == "self"):
            value, detail = roll_amount(effect["amount"])
            delta = apply_stat_delta(caster, effect["stat"], value)
            applied.append(_effect_entry(caster, effect["stat"], delta, detail))

    return {
        **roll,
        "dc": next((o["dc"] for o in outcomes if o.get("id") == primary_id and "dc" in o), None),
        "success": success,
        "kind": "special",
        "scope": attack["target_scope"],
        "save_stat": attack.get("save_stat"),
        "action_id": attack["id"],
        "action_name": attack["name"],
        "category": attack["category"],
        "stat": attack["success_stat"],
        "actor": caster.get("id"),
        "target": primary_id,
        "targets": outcomes,
        "cost": {"type": attack["cost_type"], "amount": attack["cost"]},
        "effects": applied,
    }


def _outcome_text(outcome: dict[str, Any], save_label: str, effects: list[dict[str, Any]]) -> str:
    hits = [e for e in effects if e["entity"] == outcome["id"]]
    damage = f": {format_effects(hits)}" if hits else ""
    if "save" in outcome:
        save = outcome["save"]
        verb = "makes" if save["success"] else "fails"
        return f"{outcome['name']} {verb} the {save_label} save ({save['total']} vs DC {save['dc']}){damage}"
    return f"{outcome['name']} {'HIT' if outcome['hit'] else 'MISS'}{damage}"


def describe_area_result(caster_name: str, result: dict[str, Any]) -> str:
    cost = result["cost"]
    text = f"{caster_name} uses {result['action_name']}"
    if cost["amount"]:
        text += f" ({STAT_LABELS[cost['type']]} -{cost['amount']})"
    text += "."
    if result["rolled"]:
        stat_label = STAT_LABELS.get(result["stat"], result["stat"])
        verdict = " CRITICAL!" if result["crit"] else " FUMBLE!" if result["fumble"] else ""
        text += f" {stat_label} roll: {result['d20']} + {result['modifier']} = {result['total']}.{verdict}"
    if not result["targets"]:
        return text + " Nobody is caught in the area."
    save_label = STAT_LABELS.get(result.get("save_stat") or "", "")
    parts = [_outcome_text(o, save_label, result["effects"]) for o in result["targets"]]
    return f"{text} {'. '.join(parts)}."
