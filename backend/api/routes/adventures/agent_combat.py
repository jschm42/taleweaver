"""Deterministic combat tactician for the play-agent.

While a fight or its loot phase is running, the play-agent does not ask the LLM. It picks
the move with the best expected value instead:

1. Loot phase: take every item, then finish with ``/loot done``.
2. Badly wounded: drink the strongest healing consumable or cast the strongest heal.
3. Otherwise focus the enemy that can be defeated in the fewest turns, using the
   attack (weapon or special) with the highest expected damage.
4. Out of resources: restore them with a consumable, rest for stamina, or run.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

from backend.api.routes.adventures.agent_combat_math import (
    expected_special_effect,
    expected_weapon_damage,
)
from backend.api.routes.adventures.agent_logic import AgentDecision

HEAL_HP_RATIO = 0.4
FLEE_HP_RATIO = 0.15
RESOURCES = ("hp", "mana", "stamina")


@dataclass
class ConsumableOption:
    name: str
    deltas: dict[str, int]


@dataclass
class CombatSituation:
    combat: dict[str, Any]
    player: dict[str, Any]
    weapon: dict[str, Any]
    consumables: list[ConsumableOption] = field(default_factory=list)
    can_damage: bool = True


@dataclass
class AttackOption:
    command: str
    label: str
    damage: float
    cost: int


async def build_combat_situation(manager: Any) -> CombatSituation:
    """Collects a side-effect free snapshot of the fight from the turn manager."""
    combat_engine = manager.combat
    combat = copy.deepcopy(combat_engine._read_combat_state())
    player = combat_engine._player_view(combat)
    consumables = [
        ConsumableOption(
            name=str(item.get("name")),
            deltas={
                res: combat_engine._resource_delta_from_consumable(item, res) for res in RESOURCES
            },
        )
        for item in manager.avatar.inventory or []
        if isinstance(item, dict) and item.get("item_type") == "CONSUMABLE" and item.get("name")
    ]
    return CombatSituation(
        combat=combat,
        player=player,
        weapon=await combat_engine._player_weapon_profile(),
        consumables=consumables,
        can_damage=bool(getattr(manager.adventure, "can_damage_npcs", True)),
    )


def _is_alive(enemy: dict[str, Any]) -> bool:
    # Same rule as combat.context.is_enemy_alive; importing the combat package here is circular.
    return not enemy.get("defeated") and not enemy.get("fled") and int(enemy.get("hp") or 0) > 0


def _affordable(player: dict[str, Any], cost_type: str, cost: int) -> bool:
    return int(player.get(cost_type) or 0) >= int(cost or 0)


def _usable_specials(player: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        a
        for a in player.get("special_actions") or []
        if not a.get("locked") and _affordable(player, a["cost_type"], a["cost"])
    ]


def _enemy_ref(combat: dict[str, Any], enemy: dict[str, Any]) -> str:
    """Prefers the readable name; falls back to the id when names are ambiguous."""
    name = str(enemy.get("name") or "")
    same_name = [e for e in combat.get("enemies") or [] if str(e.get("name") or "") == name]
    return name if name and len(same_name) == 1 else str(enemy.get("id"))


def _attack_options(situation: CombatSituation, enemy: dict[str, Any]) -> list[AttackOption]:
    player, weapon = situation.player, situation.weapon
    ref = _enemy_ref(situation.combat, enemy)
    options = []
    if _affordable(player, weapon["cost_type"], weapon["cost"]):
        options.append(
            AttackOption(
                command=f"Attack {ref}",
                label=weapon["name"],
                damage=expected_weapon_damage(player, enemy, weapon),
                cost=int(weapon["cost"]),
            )
        )
    for action in _usable_specials(player):
        if not action.get("targets_enemy"):
            continue
        damage = -expected_special_effect(action, player, enemy, "target")
        if damage <= 0:
            continue
        options.append(
            AttackOption(
                command=f"/special {action['id']} {ref}",
                label=action["name"],
                damage=damage,
                cost=int(action["cost"]),
            )
        )
    return options


def _best_attack(situation: CombatSituation) -> tuple[dict[str, Any], AttackOption] | None:
    """Focus target = fewest expected turns to defeat; ties go to the cheaper option."""
    combat = situation.combat
    alive = [e for e in combat.get("enemies") or [] if _is_alive(e)]
    enemies = [e for e in alive if e.get("engaged")] or alive
    candidates = [
        (enemy, option) for enemy in enemies for option in _attack_options(situation, enemy)
    ]
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda c: (int(c[0].get("hp") or 0) / max(c[1].damage, 0.01), c[1].cost),
    )


def _best_heal(situation: CombatSituation) -> tuple[str, str, float] | None:
    """Returns (command, label, effective heal) of the strongest available heal."""
    player = situation.player
    missing = int(player.get("max_hp") or 0) - int(player.get("hp") or 0)
    options = [
        (f"/consume {c.name}", c.name, min(c.deltas.get("hp", 0), missing))
        for c in situation.consumables
        if c.deltas.get("hp", 0) > 0
    ]
    for action in _usable_specials(player):
        heal = expected_special_effect(action, player, None, "self")
        if heal > 0 and not action.get("targets_enemy"):
            options.append((f"/special {action['id']}", action["name"], min(heal, missing)))
    return max(options, key=lambda o: o[2]) if options else None


def _restore_resources(situation: CombatSituation) -> tuple[str, str]:
    weapon = situation.weapon
    cost_type = weapon["cost_type"]
    for consumable in situation.consumables:
        if consumable.deltas.get(cost_type, 0) > 0:
            return (
                f"/consume {consumable.name}",
                f"Out of {cost_type} for {weapon['name']}; drinking {consumable.name} to restore it.",
            )
    if cost_type == "stamina":
        return "Rest", f"Out of stamina for {weapon['name']}; resting to recover."
    return "Run", f"No {cost_type} left and no way to restore it; trying to escape."


def _loot_choice(combat: dict[str, Any]) -> tuple[str, str]:
    loot = list(combat.get("loot_items") or [])
    if not loot:
        return "/loot done", "Loot phase: nothing left to take, finishing the fight."
    item = loot[0]
    ref = item.get("id") or item.get("name")
    return f"/loot take {ref}", f"Loot phase: taking {item.get('name') or ref}."


def _hp_ratio(player: dict[str, Any]) -> float:
    max_hp = int(player.get("max_hp") or 0)
    return int(player.get("hp") or 0) / max_hp if max_hp > 0 else 1.0


def _active_combat_choice(situation: CombatSituation) -> tuple[str, str]:
    if not situation.can_damage:
        return "Run", "Enemies cannot be damaged in this adventure; trying to escape."

    hp_ratio = _hp_ratio(situation.player)
    heal = _best_heal(situation) if hp_ratio <= HEAL_HP_RATIO else None
    if heal:
        return heal[0], f"HP at {hp_ratio:.0%}; healing with {heal[1]} (~{heal[2]:.0f} HP)."
    if hp_ratio <= FLEE_HP_RATIO:
        return "Run", f"HP at {hp_ratio:.0%} and no healing available; trying to escape."

    best = _best_attack(situation)
    if not best:
        return _restore_resources(situation)
    enemy, option = best
    reason = (
        f"Focusing {enemy.get('name')} ({enemy.get('hp')}/{enemy.get('max_hp')} HP) with "
        f"{option.label}: ~{option.damage:.1f} expected damage for {option.cost} cost."
    )
    return option.command, reason


def choose_combat_action(situation: CombatSituation) -> tuple[str, str]:
    """Returns (combat command, tactical reasoning) for the current fight state."""
    if not situation.combat.get("active"):
        return _loot_choice(situation.combat)
    return _active_combat_choice(situation)


async def decide_combat_turn(manager: Any) -> AgentDecision:
    """Builds the play-agent decision for a running fight without any LLM call."""
    situation = await build_combat_situation(manager)
    action, reason = choose_combat_action(situation)
    return AgentDecision(
        thoughts=f"[Combat tactician] {reason}",
        action=action,
        is_stuck_or_bug=False,
        issue_description="",
    )
