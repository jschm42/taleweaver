"""Protagonist actions during an active fight: attack, special, rest, run and consume."""

from __future__ import annotations

import random
from typing import Any

import backend.api.routes.adventures.gameplay_logic as gl
from backend.api.routes.adventures.combat.attacks import (
    apply_strength_bonus,
    attack_event_data,
    attack_log_text,
)
from backend.api.routes.adventures.combat.context import engaged_enemies, find_enemy, is_enemy_alive
from backend.engine.combat.initiative import PLAYER_ID
from backend.engine.combat.special_attacks import (
    STAT_LABELS,
    can_afford,
    describe_special_result,
    effective_ac,
    resolve_special_attack,
)
from backend.engine.stat_aggregator import calculate_total_stats

REST_STAMINA = 40
NO_DAMAGE_MSG = "The protagonist cannot damage NPCs in this adventure. Use Run, Rest, or /consume."
INVALID_ACTION_MSG = (
    "Combat active. Valid actions: Attack [target], Run, Rest, /consume <item>, "
    "or /special <action_id> [target]."
)
_VERBS = {
    "attack": "attack",
    "a": "attack",
    "special": "special",
    "cast": "special",
    "rest": "rest",
    "wait": "rest",
    "recover": "rest",
    "skip": "rest",
    "run": "run",
    "r": "run",
    "consume": "consume",
}


def parse_combat_command(user_msg: str) -> tuple[str | None, str]:
    parts = user_msg.strip().split(" ", 1)
    head = parts[0].lower()
    verb = _VERBS.get(head.lstrip("/"))
    if head == "consume":
        verb = None  # Consumables require the explicit slash command.
    return verb, parts[1].strip() if len(parts) > 1 else ""


def action_result(text: str, entry_type: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"text": text, "type": entry_type, "data": data}


def action_error(text: str) -> dict[str, Any]:
    return {"error": text}


class CombatPlayerMixin:
    """Resolves the protagonist's chosen action. Handlers return a result or an error dict."""

    def _resolve_target(self, combat: dict[str, Any], hint: str) -> dict[str, Any] | None:
        candidate = find_enemy(combat, hint) if hint else None
        if candidate and is_enemy_alive(candidate):
            return candidate
        current = find_enemy(combat, combat.get("target_id"))
        if current and is_enemy_alive(current):
            return current
        return next(iter(engaged_enemies(combat)), None)

    def _engage(self, combat: dict[str, Any], enemy: dict[str, Any]) -> None:
        combat["target_id"] = enemy["id"]
        if enemy.get("engaged"):
            return
        enemy["engaged"] = True
        self._append_combat_log(
            combat,
            f"{enemy['name']} joins the fight!",
            "turn",
            {"kind": "engage", "entity": enemy["id"]},
        )

    def _pay_player_cost(self, cost_type: str, cost: int, label: str) -> str | None:
        current = int(getattr(self.avatar, cost_type) or 0)
        if current < cost:
            return (
                f"Not enough {cost_type} to attack with {label}! You have {current} {cost_type}, "
                f"but attacks require {cost}. Use Rest to recover."
            )
        setattr(self.avatar, cost_type, max(0, current - cost))
        return None

    async def _player_attack(self, combat: dict[str, Any], arg: str) -> dict[str, Any]:
        if not bool(getattr(self.adventure, "can_damage_npcs", True)):
            return action_error(NO_DAMAGE_MSG)
        target = self._resolve_target(combat, arg)
        if not target:
            return action_error("There is no enemy left to attack.")

        weapon = await self._player_weapon_profile()
        cost_error = self._pay_player_cost(weapon["cost_type"], int(weapon["cost"]), weapon["name"])
        if cost_error:
            return action_error(cost_error)
        self._engage(combat, target)

        player = self._player_view(combat)
        mods = player.get("modifiers") or {}
        target_ac = max(1, effective_ac(target) - int(mods.get("dexterity", 0)))
        roll = gl.roll_attack(self.avatar, "dexterity", target_ac, weapon["dice"])
        roll = apply_strength_bonus(roll, int(mods.get("strength", 0)))
        damage = 0
        if roll.get("is_hit"):
            hp_before = int(target.get("hp") or 0)
            target["hp"] = max(0, hp_before - int(roll.get("damage_total") or 0))
            damage = hp_before - target["hp"]
            self._persist_enemy_resources(target)
        data = attack_event_data(player, target, roll, target_ac, weapon["name"], damage)
        return action_result(
            attack_log_text(self.avatar.name, roll, target_ac), "player_action", data
        )

    def _find_player_special(self, action_id: str) -> tuple[dict[str, Any] | None, str | None]:
        actions = self._player_special_actions()
        action = next((a for a in actions if a["id"].upper() == action_id.upper()), None)
        if not action:
            available = ", ".join(a["id"] for a in actions) or "none"
            return None, f"Special action '{action_id}' not found. Available: {available}"
        if action["locked"]:
            return None, f"Special action '{action['name']}' is locked. You must unlock it first!"
        current = int(getattr(self.avatar, action["cost_type"]) or 0)
        if not can_afford(action, {action["cost_type"]: current}):
            label = STAT_LABELS[action["cost_type"]]
            return None, (
                f"Not enough {label}! {action['name']} costs {action['cost']} {label}, "
                f"but you only have {current} {label}."
            )
        return action, None

    async def _player_special(self, combat: dict[str, Any], arg: str) -> dict[str, Any]:
        parts = arg.split(" ", 1)
        action, error = self._find_player_special(parts[0].strip())
        if error or not action:
            return action_error(error or "Unknown special action.")

        target = None
        if action["targets_enemy"]:
            if not bool(getattr(self.adventure, "can_damage_npcs", True)):
                return action_error(NO_DAMAGE_MSG)
            target = self._resolve_target(combat, parts[1].strip() if len(parts) > 1 else "")
            if not target:
                return action_error("There is no enemy left to target.")
            self._engage(combat, target)

        caster = self._player_view(combat)
        target_view = dict(target) if target else None
        result = resolve_special_attack(action, caster, target_view)
        self._apply_player_view(combat, caster)
        if target and target_view:
            self._apply_enemy_view(target, target_view)

        text = describe_special_result(self.avatar.name, target["name"] if target else None, result)
        if result["success"] and action.get("outcome_description"):
            await self._save_chat_message(
                "system",
                f"Special action used: {action['name']}. Outcome: {action['outcome_description']}",
            )
        return action_result(text, "player_action", result)

    async def _player_rest(self, combat: dict[str, Any], _arg: str) -> dict[str, Any]:
        before = int(self.avatar.stamina or 0)
        self.avatar.stamina = min(self.avatar.max_stamina or 100, before + REST_STAMINA)
        self._sync_combat_player_snapshot(combat)
        text = (
            f"{self.avatar.name} rests to recover stamina (+40 Stamina). "
            "Mana can only be restored outside of combat or by using a potion."
        )
        effect = {
            "entity": PLAYER_ID,
            "name": self.avatar.name,
            "stat": "stamina",
            "delta": self.avatar.stamina - before,
        }
        return action_result(
            text, "player_action", {"kind": "rest", "actor": PLAYER_ID, "effects": [effect]}
        )

    async def _player_consume(self, combat: dict[str, Any], arg: str) -> dict[str, Any]:
        if not self._find_consumable(arg):
            return action_error(f"You do not have the consumable '{arg}'.")
        text = self._consume_item_now(arg)
        self._sync_combat_player_snapshot(combat)
        deltas = getattr(self, "_last_consumable_deltas", {}) or {}
        effects = [
            {"entity": PLAYER_ID, "name": self.avatar.name, "stat": k, "delta": v}
            for k, v in deltas.items()
        ]
        return action_result(
            text, "consume", {"kind": "consume", "actor": PLAYER_ID, "effects": effects}
        )

    async def _player_run(self, combat: dict[str, Any], _arg: str) -> dict[str, Any]:
        player_stats = calculate_total_stats(self.avatar)
        player_roll = random.randint(1, 20) + int(
            player_stats.get("dexterity", self.avatar.dexterity)
        )
        best_name, best_roll = "The enemy", 0
        for enemy in engaged_enemies(combat):
            enemy_roll = random.randint(1, 20) + int(enemy.get("dexterity_mod") or 0)
            if enemy_roll > best_roll:
                best_name, best_roll = enemy["name"], enemy_roll

        data = {"kind": "run", "actor": PLAYER_ID, "total": player_roll, "dc": best_roll}
        if player_roll >= best_roll:
            data["success"] = True
            result = action_result(
                f"Run check: {player_roll} vs {best_roll}. Escape successful.", "run", data
            )
            result["escaped"] = True
            return result
        data["success"] = False
        text = f"Run check failed ({player_roll} vs {best_roll}). {best_name} keeps you in combat."
        return action_result(text, "run", data)

    def _player_action_handler(self, verb: str | None):
        handlers = {
            "attack": self._player_attack,
            "special": self._player_special,
            "rest": self._player_rest,
            "run": self._player_run,
            "consume": self._player_consume,
        }
        return handlers.get(verb or "")
