"""Builds combatant snapshots for the protagonist and NPC enemies."""

from __future__ import annotations

import re
from typing import Any

from backend.engine.combat.initiative import PLAYER_ID
from backend.engine.combat.special_attacks import normalize_special_actions
from backend.engine.combat.weapons import normalize_weapon_config
from backend.engine.rules.rule_engine import RESOURCE_CAP
from backend.engine.rules.stat_aggregator import calculate_total_stats
from backend.models.world_entity import WorldEntity

DICE_RX = re.compile(r"^\d+d\d+([+-]\d+)?$")
DEFAULT_WEAPON_COST = 20
ATTRIBUTE_KEYS = ("strength", "dexterity", "intelligence", "wisdom", "charisma")
_ITEM_STAT_FIELDS = {
    "strength": "stat_modifier_strength",
    "dexterity": "stat_modifier_dexterity",
    "intelligence": "stat_modifier_intelligence",
    "wisdom": "stat_modifier_wisdom",
    "charisma": "stat_modifier_charisma",
    "armor_class": "stat_modifier_armor_class",
}


def _valid_dice(value: Any) -> bool:
    return isinstance(value, str) and bool(DICE_RX.match(value.replace(" ", "").lower()))


def _weapon_profile(name: str, meta: dict[str, Any], fallback_dice: str) -> dict[str, Any]:
    cost = meta.get("weapon_cost_value")
    dice = meta.get("damage_dice")
    return {
        "name": name,
        "cost_type": meta.get("weapon_cost_type") or "stamina",
        "cost": DEFAULT_WEAPON_COST if cost is None else int(cost),
        "dice": dice if _valid_dice(dice) else fallback_dice,
        **normalize_weapon_config(meta),
    }


class CombatCombatantMixin:
    """Snapshots and engine views for everyone taking part in the fight."""

    async def _calculate_npc_total_stats(self, npc: WorldEntity) -> dict[str, Any]:
        """Calculates total stats for an NPC including equipment bonuses from metadata."""
        stats = {key: self._entity_stat(npc, field, 10) for key, field in _ITEM_STAT_FIELDS.items()}
        stats["armor_class"] = 10 + self._entity_stat(npc, "stat_modifier_armor_class", 0)
        meta = dict(npc.metadata_json or {})
        for item_id in (meta.get("equipped_weapon_id"), meta.get("equipped_armor_id")):
            item = await self._load_session_entity(item_id)
            if not item:
                continue
            for key, field in _ITEM_STAT_FIELDS.items():
                stats[key] += getattr(item, field, 0) or 0
        return stats

    async def _build_enemy_entry(self, npc: WorldEntity, engaged: bool) -> dict[str, Any]:
        npc_stats = await self._calculate_npc_total_stats(npc)
        hp = self._entity_stat(npc, "hp", 50)
        meta = dict(npc.metadata_json or {})
        return {
            "id": npc.id,
            "name": npc.name,
            "image_url": npc.image_url,
            "hp": hp,
            "max_hp": self._entity_stat(npc, "max_hp", hp if hp > 0 else 50),
            "stamina": self._entity_stat(npc, "stamina", 0),
            "max_stamina": self._entity_stat(npc, "max_stamina", 0),
            "mana": self._entity_stat(npc, "mana", 0),
            "max_mana": self._entity_stat(npc, "max_mana", 0),
            "dexterity_mod": npc_stats["dexterity"],
            "armor_mod": npc_stats["armor_class"] - 10,
            "ac": npc_stats["armor_class"],
            "stats": {key: npc_stats[key] for key in ATTRIBUTE_KEYS},
            "modifiers": {},
            "special_actions": normalize_special_actions(meta.get("special_actions")),
            "special_chance": meta.get("special_chance"),
            "inventory": await self._normalize_loot_items(list(npc.inventory or [])),
            "engaged": engaged,
            "defeated": False,
            "fled": False,
        }

    def _player_special_actions(self) -> list[dict[str, Any]]:
        stats = self.avatar.stats or {}
        unlocked = set(stats.get("unlocked_actions") or [])
        actions = normalize_special_actions(stats.get("special_actions"))
        for action in actions:
            action["locked"] = action["id"] not in unlocked
        return actions

    def _sync_combat_player_snapshot(self, combat: dict[str, Any]) -> None:
        player = dict(combat.get("player") or {})
        player_stats = calculate_total_stats(self.avatar)
        player.update(
            {
                "id": PLAYER_ID,
                "name": self.avatar.name,
                "image_url": self.avatar.profile_image,
                "hp": int(self.avatar.hp or 0),
                "max_hp": int(self.avatar.max_hp or RESOURCE_CAP),
                "stamina": int(self.avatar.stamina or 0),
                "max_stamina": int(self.avatar.max_stamina or RESOURCE_CAP),
                "mana": int(self.avatar.mana or 0),
                "max_mana": int(self.avatar.max_mana or RESOURCE_CAP),
                "ac": int(player_stats.get("armor_class", self.avatar.armor_class)),
                "stats": {k: int(player_stats.get(k, 10)) for k in ATTRIBUTE_KEYS},
                "special_actions": self._player_special_actions(),
            }
        )
        player.setdefault("modifiers", {})
        combat["player"] = player

    def _player_view(self, combat: dict[str, Any]) -> dict[str, Any]:
        self._sync_combat_player_snapshot(combat)
        return dict(combat["player"])

    def _apply_player_view(self, combat: dict[str, Any], view: dict[str, Any]) -> None:
        self.avatar.hp = int(view.get("hp", self.avatar.hp))
        self.avatar.mana = int(view.get("mana", self.avatar.mana))
        self.avatar.stamina = int(view.get("stamina", self.avatar.stamina))
        combat.setdefault("player", {})["modifiers"] = dict(view.get("modifiers") or {})
        self._sync_combat_player_snapshot(combat)

    def _apply_enemy_view(self, enemy: dict[str, Any], view: dict[str, Any]) -> None:
        for key in ("hp", "mana", "stamina", "modifiers"):
            if key in view:
                enemy[key] = view[key]
        self._persist_enemy_resources(enemy)

    def _player_damage_dice(self) -> str:
        main_hand = (self.avatar.equipment or {}).get("MainHand")
        dice = main_hand.get("damage_dice") if isinstance(main_hand, dict) else None
        return dice if _valid_dice(dice) else "1d8"

    def _enemy_damage_dice(self, enemy: WorldEntity) -> str:
        meta = enemy.metadata_json if isinstance(enemy.metadata_json, dict) else {}
        dice = meta.get("damage_dice")
        return dice if _valid_dice(dice) else "1d6"

    async def _player_weapon_profile(self) -> dict[str, Any]:
        main_hand = (self.avatar.equipment or {}).get("MainHand")
        if not isinstance(main_hand, dict):
            return _weapon_profile("Bare Fists", {}, "1d8")
        meta = dict(main_hand.get("metadata_json") or {})
        if not meta and "id" in main_hand:
            item_ent = await self._load_session_entity(main_hand["id"])
            meta = dict(item_ent.metadata_json or {}) if item_ent else {}
        if not _valid_dice(meta.get("damage_dice")) and _valid_dice(main_hand.get("damage_dice")):
            meta["damage_dice"] = main_hand["damage_dice"]
        return _weapon_profile(main_hand.get("name", "Weapon"), meta, "1d8")

    async def _enemy_weapon_profile(self, npc: WorldEntity) -> dict[str, Any]:
        weapon_id = (npc.metadata_json or {}).get("equipped_weapon_id")
        weapon = await self._load_session_entity(weapon_id)
        if not weapon:
            return _weapon_profile("unarmed attack", {}, "1d6")
        return _weapon_profile(weapon.name, dict(weapon.metadata_json or {}), "1d8")
