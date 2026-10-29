"""NPC turn resolution: weapon attacks, resting and special attacks."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

import backend.api.routes.adventures.gameplay_logic as gl
from backend.api.routes.adventures.combat.attacks import (
    apply_strength_bonus,
    attack_event_data,
    attack_log_text,
    on_hit_suffix,
)
from backend.api.routes.adventures.combat.context import (
    engaged_enemies,
    find_enemy,
    is_enemy_alive,
    system_event,
)
from backend.engine.combat.special_attacks import (
    can_afford,
    describe_special_result,
    effective_ac,
    resolve_special_attack,
)
from backend.engine.combat.weapons import apply_on_hit_effects
from backend.engine.rules.rule_engine import GameOverException
from backend.models.avatar import Avatar
from backend.models.world_entity import WorldEntity

ENEMY_REST_AMOUNT = 40
HEAL_THRESHOLD = 0.4
HEAL_CHANCE = 0.8
DEFAULT_SPECIAL_CHANCE = 40  # percent per turn, configurable per NPC (metadata "special_chance")


def _is_self_heal(action: dict[str, Any]) -> bool:
    return not action["targets_enemy"] and any(
        e["target"] == "self" and e["stat"] == "hp" and not e["amount"].startswith("-")
        for e in action["effects"]
    )


def npc_can_afford(action: dict[str, Any], enemy: dict[str, Any]) -> bool:
    """NPCs without a pool for the cost resource (max 0) use the special for free."""
    if int(enemy.get(f"max_{action['cost_type']}") or 0) <= 0:
        return True
    return can_afford(action, enemy)


def special_chance(enemy: dict[str, Any]) -> float:
    raw = enemy.get("special_chance")
    percent = raw if isinstance(raw, (int, float)) else DEFAULT_SPECIAL_CHANCE
    return max(0.0, min(100.0, float(percent))) / 100


class CombatEnemyMixin:
    """Decides and resolves what an engaged NPC does on its turn."""

    def _choose_enemy_special(self, enemy: dict[str, Any]) -> dict[str, Any] | None:
        damage_allowed = bool(getattr(self.adventure, "npcs_can_damage_protagonist", True))
        specials = [
            a
            for a in enemy.get("special_actions") or []
            if npc_can_afford(a, enemy) and (damage_allowed or not a["targets_enemy"])
        ]
        if not specials:
            return None

        heals = [a for a in specials if _is_self_heal(a)]
        hp_ratio = int(enemy.get("hp") or 0) / max(1, int(enemy.get("max_hp") or 1))
        if hp_ratio < HEAL_THRESHOLD and heals and gl.random.random() < HEAL_CHANCE:
            return gl.random.choice(heals)

        # Offensive and utility specials are used at random with the NPC's special chance.
        others = [a for a in specials if a not in heals]
        if others and gl.random.random() < special_chance(enemy):
            return gl.random.choice(others)
        return None

    async def _enemy_special(
        self, combat: dict[str, Any], enemy: dict[str, Any], action: dict[str, Any]
    ) -> tuple[str, dict[str, Any]]:
        caster = dict(enemy)
        target = self._player_view(combat)
        result = resolve_special_attack(action, caster, target)
        self._apply_enemy_view(enemy, caster)
        self._apply_player_view(combat, target)
        text = describe_special_result(enemy["name"], self.avatar.name, result)
        if result["success"] and action.get("outcome_description"):
            await self._save_chat_message(
                "system", f"{enemy['name']} Special Action outcome: {action['outcome_description']}"
            )
        return text, result

    def _enemy_rest(self, enemy: dict[str, Any], reason: str) -> tuple[str, dict[str, Any]]:
        max_stamina = int(enemy.get("max_stamina") or 0)
        max_mana = int(enemy.get("max_mana") or 0)
        before = {k: int(enemy.get(k) or 0) for k in ("stamina", "mana")}
        enemy["stamina"] = min(max_stamina, before["stamina"] + ENEMY_REST_AMOUNT)
        restores_mana = reason == "mana" or max_mana > 0
        if restores_mana:
            enemy["mana"] = min(max_mana, before["mana"] + ENEMY_REST_AMOUNT)
        self._persist_enemy_resources(enemy)

        if reason == "mana":
            text = f"{enemy['name']} is out of mana and rests to recover (+40 Stamina, +40 Mana)."
        else:
            mana_note = ", +40 Mana" if max_mana > 0 else ""
            text = f"{enemy['name']} is exhausted and rests to recover (+40 Stamina{mana_note})."
        effects = [
            {
                "entity": enemy["id"],
                "name": enemy["name"],
                "stat": k,
                "delta": int(enemy.get(k) or 0) - v,
            }
            for k, v in before.items()
            if int(enemy.get(k) or 0) != v
        ]
        return text, {"kind": "rest", "actor": enemy["id"], "effects": effects}

    def _enemy_pay_weapon_cost(
        self, enemy: dict[str, Any], weapon: dict[str, Any]
    ) -> tuple[str, dict[str, Any]] | None:
        """Pays the weapon cost or returns the rest action the NPC takes instead."""
        cost = int(weapon["cost"])
        if weapon["cost_type"] == "mana":
            if int(enemy.get("mana") or 0) < cost:
                return self._enemy_rest(enemy, "mana")
            enemy["mana"] = max(0, int(enemy.get("mana") or 0) - cost)
        else:
            stamina = int(enemy.get("stamina") or 0)
            if int(enemy.get("max_stamina") or 0) > 0 and stamina < cost:
                return self._enemy_rest(enemy, "stamina")
            enemy["stamina"] = max(0, stamina - cost)
        self._persist_enemy_resources(enemy)
        return None

    def _enemy_avatar(self, enemy: dict[str, Any]) -> Avatar:
        stats = enemy.get("stats") or {}
        mods = enemy.get("modifiers") or {}
        return Avatar(
            name=enemy["name"],
            hp=int(enemy.get("hp") or 0),
            strength=int(stats.get("strength", 0)) + int(mods.get("strength", 0)),
            dexterity=int(stats.get("dexterity", 10)) + int(mods.get("dexterity", 0)),
            intelligence=int(stats.get("intelligence", 0)) + int(mods.get("intelligence", 0)),
            wisdom=int(stats.get("wisdom", 0)) + int(mods.get("wisdom", 0)),
            charisma=int(stats.get("charisma", 0)) + int(mods.get("charisma", 0)),
            armor_class=int(enemy.get("ac") or 10),
            stats={},
            equipment={},
            inventory=[],
        )

    async def _enemy_weapon_attack(
        self, combat: dict[str, Any], enemy: dict[str, Any], enemy_ent: WorldEntity
    ) -> tuple[str, dict[str, Any]]:
        weapon = await self._enemy_weapon_profile(enemy_ent)
        rest = self._enemy_pay_weapon_cost(enemy, weapon)
        if rest:
            return rest

        player = self._player_view(combat)
        if not bool(getattr(self.adventure, "npcs_can_damage_protagonist", True)):
            text = f"{enemy['name']} attacks, but this adventure disables NPC damage to the protagonist."
            return text, {
                "kind": "attack",
                "actor": enemy["id"],
                "target": "PLAYER",
                "success": False,
            }

        player_ac = effective_ac(player)
        roll = gl.roll_attack(
            self._enemy_avatar(enemy), weapon["hit_stat"], player_ac, weapon["dice"]
        )
        roll = apply_strength_bonus(roll, int((enemy.get("modifiers") or {}).get("strength", 0)))
        damage = 0
        on_hit: list[dict[str, Any]] = []
        if roll.get("is_hit"):
            hp_before = int(self.avatar.hp or 0)
            self.avatar.hp = max(0, hp_before - int(roll.get("damage_total") or 0))
            damage = hp_before - self.avatar.hp
            on_hit = self._apply_enemy_on_hit(combat, enemy, weapon)
        self._sync_combat_player_snapshot(combat)
        data = attack_event_data(enemy, player, roll, player_ac, weapon["name"], damage)
        data["effects"].extend(on_hit)
        return attack_log_text(enemy["name"], roll, player_ac) + on_hit_suffix(on_hit), data

    def _apply_enemy_on_hit(
        self, combat: dict[str, Any], enemy: dict[str, Any], weapon: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Weapon on-hit effects of an NPC: drains on the protagonist, boosts on itself."""
        if not weapon["effects"]:
            return []
        player = self._player_view(combat)
        applied = apply_on_hit_effects(weapon["effects"], enemy, player)
        self._apply_player_view(combat, player)
        self._persist_enemy_resources(enemy)
        return applied

    async def _resolve_enemy_turn(
        self, enemy_id: str | None = None, combat: dict[str, Any] | None = None
    ) -> AsyncGenerator[str, None]:
        combat = combat if combat is not None else self._read_combat_state()
        if not combat.get("active"):
            return
        enemy = find_enemy(combat, enemy_id) if enemy_id else None
        enemy = enemy or next(iter(engaged_enemies(combat)), None)
        if not enemy or not is_enemy_alive(enemy):
            return

        enemy_ent = await self._load_session_entity(enemy["id"])
        if not enemy_ent:
            enemy["fled"] = True
            self._append_combat_log(combat, f"{enemy['name']} vanished from the scene.", "outcome")
            self._check_victory(combat)
            return

        special = self._choose_enemy_special(enemy)
        if special:
            text, data = await self._enemy_special(combat, enemy, special)
        else:
            text, data = await self._enemy_weapon_attack(combat, enemy, enemy_ent)
        self._append_combat_log(combat, text, "enemy_action", data)
        yield system_event(text)
        if special:
            async for chunk in self._special_script_events(combat, data):
                yield chunk

        if self.avatar.hp <= 0:
            await self._handle_player_defeat(combat, "The protagonist falls. Game Over.")
            return
        if special or data.get("kind") != "attack":
            return
        async for chunk in self._run_special_event(combat):
            yield chunk

    async def _run_special_event(self, combat: dict[str, Any]) -> AsyncGenerator[str, None]:
        try:
            special_text = await self._maybe_trigger_special_event(combat)
        except GameOverException as goe:
            self._sync_combat_player_snapshot(combat)
            await self._handle_player_defeat(combat, str(goe), log_outcome=False)
            return
        self._sync_combat_player_snapshot(combat)
        if special_text:
            yield system_event(special_text)
