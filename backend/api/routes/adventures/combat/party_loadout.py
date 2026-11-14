"""The companion's loadout in combat: equipped weapon, equipment bonuses and abilities.

* The item in ``MainHand`` (hero dialog) is the companion's weapon; without one it uses its
  NPC main attack.
* Attribute and armor bonuses of all equipped items add to its combat stats.
* Its abilities are the NPC's special actions (editor), minus the ones the player switched off.
  V1 uses single-target and self abilities; area abilities stay with the enemies.
"""

from __future__ import annotations

from typing import Any

import backend.api.routes.adventures.gameplay_logic as gl
from backend.api.routes.adventures.combat.combatants import ATTRIBUTE_KEYS, _weapon_profile
from backend.api.routes.adventures.combat.enemy_ai import npc_can_afford, special_chance
from backend.api.routes.adventures.companion_sheet import held_entries, held_items
from backend.engine.combat.special_attacks import (
    describe_special_result,
    heals_ally,
    resolve_special_attack,
)
from backend.engine.party.equipment import carried_equipment, equipment_modifiers
from backend.engine.party.party_state import PartyState
from backend.engine.rules.rule_engine import RESOURCE_CAP
from backend.models.world_entity import WorldEntity

LOW_HP_RATIO = 0.4
# Below this share of max HP the companion heals the protagonist with an "ally" ability.
ALLY_HEAL_BELOW = 0.5


def _is_self_heal(action: dict[str, Any]) -> bool:
    return not action["targets_enemy"] and any(
        e["target"] == "self" and e["stat"] == "hp" and not e["amount"].startswith("-")
        for e in action["effects"]
    )


def apply_equipment_bonuses(entry: dict[str, Any], modifiers: dict[str, int]) -> None:
    """Adds equipment bonuses to a combat entry (attributes, initiative, armor class)."""
    stats = dict(entry.get("stats") or {})
    for key in ATTRIBUTE_KEYS:
        stats[key] = int(stats.get(key, 10)) + modifiers.get(key, 0)
    entry["stats"] = stats
    entry["dexterity_mod"] = int(entry.get("dexterity_mod") or 0) + modifiers.get("dexterity", 0)
    entry["ac"] = int(entry.get("ac") or 10) + modifiers.get("armor_class", 0)
    entry["armor_mod"] = entry["ac"] - 10


class CombatPartyLoadoutMixin:
    """Equipment, weapon and abilities of the companion during a fight."""

    async def _apply_member_loadout(
        self, entry: dict[str, Any], row: WorldEntity, party: PartyState
    ) -> None:
        states = dict(self.state.entity_states or {})
        items = await held_items(self.db, self.game_id, held_entries(states, row), {})
        by_id = {str(item.get("id", "")).upper(): item for item in items}
        equipped = carried_equipment(states, row.id, set(by_id))
        apply_equipment_bonuses(
            entry, equipment_modifiers([by_id[i.upper()] for i in equipped.values()])
        )
        entry["weapon_item_id"] = equipped.get("MainHand")
        entry["special_actions"] = [
            action
            for action in entry.get("special_actions") or []
            if action.get("target_scope", "SINGLE") == "SINGLE"
            and party.ability_enabled(row.id, action["id"])
        ]

    async def _member_weapon(self, member: dict[str, Any], row: WorldEntity) -> dict[str, Any]:
        """The equipped MainHand weapon, else the NPC's own main attack."""
        item = await self._load_session_entity(member.get("weapon_item_id"))
        if item is None:
            return await self._enemy_weapon_profile(row)
        return _weapon_profile(item.name, dict(item.metadata_json or {}), "1d8")

    def _choose_member_special(self, member: dict[str, Any]) -> dict[str, Any] | None:
        """Heal the protagonist when they are low, itself when it is low, else maybe attack."""
        specials = [a for a in member.get("special_actions") or [] if npc_can_afford(a, member)]
        ally_heals = [a for a in specials if heals_ally(a)]
        player_ratio = int(self.avatar.hp or 0) / max(1, int(self.avatar.max_hp or RESOURCE_CAP))
        if ally_heals and player_ratio < ALLY_HEAL_BELOW:
            return gl.random.choice(ally_heals)
        heals = [a for a in specials if _is_self_heal(a)]
        hp_ratio = int(member.get("hp") or 0) / max(1, int(member.get("max_hp") or 1))
        if heals and hp_ratio < LOW_HP_RATIO:
            return gl.random.choice(heals)
        # Support abilities are kept for when they are needed, not used at random.
        others = [a for a in specials if a not in heals and a not in ally_heals]
        if others and gl.random.random() < special_chance(member):
            return gl.random.choice(others)
        return None

    def _member_special(
        self, combat: dict[str, Any], member: dict[str, Any]
    ) -> tuple[str, dict[str, Any]] | None:
        """One of the companion's abilities on the chosen enemy (or itself), if it uses one."""
        action = self._choose_member_special(member)
        if action is None:
            return None
        target = self._member_target(combat, member) if action["targets_enemy"] else None
        caster = dict(member)
        target_view = dict(target) if target else None
        # "ally" effects of the companion reach the protagonist.
        ally_view = self._player_view(combat)
        result = resolve_special_attack(action, caster, target_view, ally_view)
        self._apply_enemy_view(member, caster)
        if target is not None and target_view is not None:
            self._apply_enemy_view(target, target_view)
        self._apply_player_view(combat, ally_view)
        text = describe_special_result(member["name"], target["name"] if target else None, result)
        return text, result
