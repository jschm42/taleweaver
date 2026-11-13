"""The protagonist's companion in turn-based combat (``combat["party"]``).

The active companion fights on the protagonist's side when it stands in the fight scene and
is not defeated (rpg mode only, like all turn-based combat). It acts on its own initiative
turn according to its tactics:

* ``OFFENSIVE``: attacks the weakest engaged enemy.
* ``DEFENSIVE``: attacks the current target; enemies attack it more often.
* ``SUPPORT``: heals a badly wounded protagonist with a healing consumable it carries,
  otherwise attacks the current target.
* ``BALANCED``: attacks the current target.

At 0 HP the companion is *downed*, never killed: it sits out the rest of the fight and gets
``downed_recovery`` of its max HP back afterwards. The fight is still lost when the
protagonist falls. ``combat["allies"]`` is a different thing: enemy-side helpers.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

import backend.api.routes.adventures.gameplay_logic as gl
from backend.api.routes.adventures.combat.attacks import (
    apply_strength_bonus,
    attack_event_data,
    attack_log_text,
)
from backend.api.routes.adventures.combat.context import (
    engaged_enemies,
    find_enemy,
    system_event,
)
from backend.api.routes.adventures.sheet_snapshot import entity_to_item_dict
from backend.engine.party.companion_config import (
    DEFAULT_DOWNED_RECOVERY,
    TACTICS,
    companion_config,
)
from backend.engine.party.follow import companion_scene_id
from backend.engine.party.party_state import read_party
from backend.engine.rules.consumable_effects import resource_delta
from backend.engine.rules.rule_engine import RESOURCE_CAP
from backend.engine.scripting.item_ops import DESTROYED_SCENE_ID
from backend.engine.scripting.item_transfer import ref_id
from backend.models.world_entity import WorldEntity

PARTY_KEY = "party"
# Chance per enemy attack to go for the companion instead of the protagonist.
COMPANION_TARGET_CHANCE = {"DEFENSIVE": 0.6}
DEFAULT_COMPANION_TARGET_CHANCE = 0.3
SUPPORT_HEAL_BELOW = 0.5


def party_members(combat: dict[str, Any]) -> list[dict[str, Any]]:
    return [m for m in combat.get(PARTY_KEY) or [] if isinstance(m, dict)]


def is_member_standing(member: dict[str, Any]) -> bool:
    return not member.get("downed") and int(member.get("hp") or 0) > 0


def find_member(combat: dict[str, Any], member_id: str | None) -> dict[str, Any] | None:
    low = str(member_id or "").lower()
    return next((m for m in party_members(combat) if str(m.get("id", "")).lower() == low), None)


class CombatPartyMixin:
    """Builds the party side of a fight and resolves the companion's turns."""

    # --- setup --------------------------------------------------------------------

    def _party_ids(self) -> set[str]:
        """Every recruited companion: never an enemy, never a fight target."""
        return set(read_party(self.state.entity_states).recruited)

    async def _companion_named(self, hint: str) -> WorldEntity | None:
        """The companion in this scene that ``hint`` names (ID or name), if any."""
        low = (hint or "").strip().lower()
        party_ids = self._party_ids()
        if not low or not party_ids:
            return None
        return next(
            (
                npc
                for npc in await self._scene_npcs()
                if npc.id in party_ids and low in (npc.id.lower(), npc.name.lower())
            ),
            None,
        )

    async def _fighting_companion(self) -> WorldEntity | None:
        """The active companion when it can fight here: in this scene and still standing."""
        active_id = read_party(self.state.entity_states).active_id
        row = await self._load_session_entity(active_id)
        if row is None or self._is_npc_defeated(row):
            return None
        states = dict(self.state.entity_states or {})
        if companion_scene_id(states, row) != str(self.state.current_scene_id or ""):
            return None
        return row

    async def _build_party(self, combat: dict[str, Any]) -> None:
        """Puts the fighting companion on the protagonist's side (``combat["party"]``)."""
        row = await self._fighting_companion()
        if row is None:
            combat[PARTY_KEY] = []
            return
        entry = await self._build_enemy_entry(row, engaged=True)
        config = companion_config(row.metadata_json if isinstance(row.metadata_json, dict) else {})
        party = read_party(self.state.entity_states)
        entry.update(
            side="party",
            tactics=party.tactics.get(row.id) or (config.tactics if config else TACTICS[0]),
            downed=False,
            downed_recovery=config.downed_recovery if config else DEFAULT_DOWNED_RECOVERY,
            inventory=[],
        )
        await self._apply_member_loadout(entry, row, party)
        combat[PARTY_KEY] = [entry]
        self._append_combat_log(
            combat, f"{row.name} fights at your side!", "turn", {"kind": "engage", "entity": row.id}
        )

    def _party_can_act(self, combat: dict[str, Any], actor_id: str | None) -> bool:
        member = find_member(combat, actor_id)
        return bool(member and is_member_standing(member))

    async def _player_mark(self, combat: dict[str, Any], arg: str) -> dict[str, Any]:
        """Free action: the companion attacks only the marked enemy; ``mark`` alone lifts it."""
        member = next((m for m in party_members(combat) if is_member_standing(m)), None)
        if member is None:
            return {"error": "Mark needs a companion fighting at your side."}
        if not arg.strip():
            member["mark_id"] = None
            text = (
                f"{self.avatar.name} lifts the mark. {member['name']} fights by its tactics again."
            )
            return {"text": text, "type": "player_action", "data": None, "free": True}
        target = find_enemy(combat, arg.strip())
        if target is None or target not in engaged_enemies(combat):
            return {"error": "Mark an enemy that is in the fight."}
        member["mark_id"] = target["id"]
        text = (
            f"{self.avatar.name} marks {target['name']}: {member['name']} attacks only that target."
        )
        data = {"kind": "mark", "actor": "PLAYER", "target": target["id"]}
        return {"text": text, "type": "player_action", "data": data, "free": True}

    # --- enemy targeting -----------------------------------------------------------

    def _enemy_target_member(self, combat: dict[str, Any]) -> dict[str, Any] | None:
        """The companion an enemy attacks this turn, or None for the protagonist."""
        standing = [m for m in party_members(combat) if is_member_standing(m)]
        if not standing:
            return None
        member = standing[0]
        chance = COMPANION_TARGET_CHANCE.get(
            str(member.get("tactics")), DEFAULT_COMPANION_TARGET_CHANCE
        )
        return member if gl.random.random() < chance else None

    def _enemy_attacks_member(
        self,
        enemy: dict[str, Any],
        member: dict[str, Any],
        weapon: dict[str, Any],
        combat: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        """An enemy weapon attack on the companion; at 0 HP the companion is downed."""
        member_ac = int(member.get("ac") or 10)
        roll = gl.roll_attack(
            self._enemy_avatar(enemy), weapon["hit_stat"], member_ac, weapon["dice"]
        )
        roll = apply_strength_bonus(roll, int((enemy.get("modifiers") or {}).get("strength", 0)))
        damage = (
            self._damage_member(member, int(roll.get("damage_total") or 0))
            if roll.get("is_hit")
            else 0
        )
        data = attack_event_data(
            enemy, member, roll, member_ac, weapon["name"], damage, weapon["category"]
        )
        text = attack_log_text(enemy["name"], roll, member_ac, weapon["name"], member["name"])
        if member.get("downed"):
            text += f" {member['name']} is downed!"
        return text, data

    def _damage_member(self, member: dict[str, Any], amount: int) -> int:
        hp_before = int(member.get("hp") or 0)
        member["hp"] = max(0, hp_before - amount)
        if member["hp"] <= 0:
            member["downed"] = True
        self._persist_enemy_resources(member)
        return hp_before - member["hp"]

    # --- the companion's turn -------------------------------------------------------

    def _member_target(self, combat: dict[str, Any], member: dict[str, Any]) -> dict[str, Any]:
        engaged = engaged_enemies(combat)
        marked = find_enemy(combat, member.get("mark_id"))
        if marked in engaged:
            return marked
        member["mark_id"] = None  # the marked enemy is down or gone: back to the tactics
        if member.get("tactics") == "OFFENSIVE":
            return min(engaged, key=lambda e: int(e.get("hp") or 0))
        target = find_enemy(combat, combat.get("target_id"))
        return target if target in engaged else engaged[0]

    async def _member_attack(
        self, combat: dict[str, Any], member: dict[str, Any], row: WorldEntity
    ) -> tuple[str, dict[str, Any]]:
        weapon = await self._member_weapon(member, row)
        rest = self._enemy_pay_weapon_cost(member, weapon)
        if rest:
            return rest
        target = self._member_target(combat, member)
        target_ac = int(target.get("ac") or 10)
        roll = gl.roll_attack(
            self._enemy_avatar(member), weapon["hit_stat"], target_ac, weapon["dice"]
        )
        roll = apply_strength_bonus(roll, int((member.get("modifiers") or {}).get("strength", 0)))
        damage = 0
        if roll.get("is_hit"):
            hp_before = int(target.get("hp") or 0)
            target["hp"] = max(0, hp_before - int(roll.get("damage_total") or 0))
            damage = hp_before - target["hp"]
            self._persist_enemy_resources(target)
        data = attack_event_data(
            member, target, roll, target_ac, weapon["name"], damage, weapon["category"]
        )
        text = attack_log_text(member["name"], roll, target_ac, weapon["name"], target["name"])
        return text, data

    async def _healing_item(self, member: dict[str, Any]) -> dict[str, Any] | None:
        """A consumable the companion carries that restores HP."""
        entry = (self.state.entity_states or {}).get(member["id"]) or {}
        held = entry.get("inventory") if isinstance(entry.get("inventory"), list) else []
        for ref in held:
            item = await self._load_session_entity(ref_id(ref) or None)
            if item is None or str(item.item_type or "").upper() != "CONSUMABLE":
                continue
            data = entity_to_item_dict(item)
            if resource_delta(data, "hp") > 0:
                return data
        return None

    async def _member_heal(
        self, combat: dict[str, Any], member: dict[str, Any]
    ) -> tuple[str, dict[str, Any]] | None:
        """SUPPORT: heals a badly wounded protagonist with a carried healing consumable."""
        max_hp = int(self.avatar.max_hp or RESOURCE_CAP)
        if (
            member.get("tactics") != "SUPPORT"
            or int(self.avatar.hp or 0) >= max_hp * SUPPORT_HEAL_BELOW
        ):
            return None
        item = await self._healing_item(member)
        if item is None:
            return None
        hp_before = int(self.avatar.hp or 0)
        self.avatar.hp = min(max_hp, hp_before + resource_delta(item, "hp"))
        self._use_up_member_item(member, item["id"])
        self._sync_combat_player_snapshot(combat)
        healed = self.avatar.hp - hp_before
        text = f"{member['name']} uses {item['name']} on {self.avatar.name} (+{healed} HP)."
        effect = {"entity": "PLAYER", "name": self.avatar.name, "stat": "hp", "delta": healed}
        return text, {
            "kind": "consume",
            "actor": member["id"],
            "label": item["name"],
            "effects": [effect],
        }

    def _use_up_member_item(self, member: dict[str, Any], item_id: str) -> None:
        entry = (self.state.entity_states or {}).get(member["id"]) or {}
        held = list(entry.get("inventory") or [])
        target = str(item_id).upper()
        index = next((i for i, ref in enumerate(held) if ref_id(ref) == target), None)
        if index is not None:
            held.pop(index)
        self._update_entity_state(member["id"], inventory=held)
        self._update_entity_state(
            item_id, current_scene_id=DESTROYED_SCENE_ID, is_hidden=True, is_in_inventory=False
        )

    async def _resolve_companion_turn(
        self, member_id: str | None, combat: dict[str, Any]
    ) -> AsyncGenerator[str, None]:
        member = find_member(combat, member_id)
        if not member or not is_member_standing(member) or not engaged_enemies(combat):
            return
        row = await self._load_session_entity(member["id"])
        if row is None:
            member["downed"] = True
            return
        action = (
            await self._member_heal(combat, member)
            or self._member_special(combat, member)
            or await self._member_attack(combat, member, row)
        )
        text, data = action
        self._append_combat_log(combat, text, "party_action", data)
        yield system_event(text)
        if data.get("kind") == "special":
            async for chunk in self._special_script_events(combat, data):
                yield chunk
        if data.get("kind") not in ("attack", "special") or not data.get("target"):
            return
        async for chunk in self._resolve_casualties(combat, data.get("target")):
            yield chunk
        self._check_victory(combat)

    # --- after the fight --------------------------------------------------------------

    def _recover_party(self, combat: dict[str, Any]) -> None:
        """A downed companion gets ``downed_recovery`` of its max HP back after the fight."""
        for member in party_members(combat):
            if not member.get("downed"):
                continue
            max_hp = int(member.get("max_hp") or 1)
            share = float(member.get("downed_recovery") or DEFAULT_DOWNED_RECOVERY)
            member["hp"] = max(1, round(max_hp * share))
            member["downed"] = False
            self._persist_enemy_resources(member)
            self._append_combat_log(
                combat, f"{member['name']} gets back on their feet ({member['hp']} HP).", "outcome"
            )
