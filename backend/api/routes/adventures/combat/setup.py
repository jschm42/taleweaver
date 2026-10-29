"""Encounter setup: target lookup, multi-NPC encounters and GM-triggered fights."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import select

from backend.engine.combat.initiative import PLAYER_ID
from backend.engine.rules.rule_engine import GameEvent
from backend.models.world_entity import WorldEntity

MAX_ENCOUNTER_ENEMIES = 6


class CombatSetupMixin:
    """Starts fights against one target plus every other attackable NPC in the scene."""

    async def _scene_npcs(self) -> list[WorldEntity]:
        ent_res = await self.db.execute(
            select(WorldEntity).where(
                WorldEntity.session_id == self.game_id,
                WorldEntity.current_scene_id == self.state.current_scene_id,
                WorldEntity.entity_type.in_(["NPC", "npc"]),
                WorldEntity.is_hidden.is_(False),
                WorldEntity.is_in_inventory.is_(False),
            )
        )
        return list(ent_res.scalars().all())

    def _is_eligible_npc(self, npc: WorldEntity) -> bool:
        return not (
            self._entity_override(npc.id, "is_defeated")
            or self._entity_override(npc.id, "is_hidden")
        )

    async def _find_fight_target(self, target_hint: str) -> WorldEntity | None:
        eligible = [npc for npc in await self._scene_npcs() if self._is_eligible_npc(npc)]
        if not eligible:
            return None
        low = (target_hint or "").strip().lower()
        if low:
            match = next((n for n in eligible if low in (n.id.lower(), n.name.lower())), None)
            if match:
                return match
        alive = next((n for n in eligible if self._entity_stat(n, "hp", 1) > 0), None)
        return alive or eligible[0]

    async def _find_scene_npc_by_hint(self, target_hint: str) -> WorldEntity | None:
        low = (target_hint or "").strip().lower()
        if not low:
            return None
        return next(
            (n for n in await self._scene_npcs() if low in (n.id.lower(), n.name.lower())), None
        )

    def _combat_blocked_reason(self, initiated_by_enemy: bool) -> str | None:
        if (self.adventure.rule_enforcement_mode or "rpg") != "rpg":
            return "Turn-based combat is only available in RPG mode."
        if initiated_by_enemy and not bool(
            getattr(self.adventure, "npcs_can_damage_protagonist", True)
        ):
            return "Combat auto-start blocked: NPC damage to the protagonist is disabled for this adventure."
        if not initiated_by_enemy and not bool(getattr(self.adventure, "can_damage_npcs", True)):
            return "Combat is disabled for this adventure: the protagonist cannot damage NPCs."
        if self._is_combat_active():
            return "A fight is already active. Use Attack, Run, or a consumable."
        return None

    def _target_unavailable_reason(self, target: WorldEntity) -> str | None:
        if self._entity_override(target.id, "is_defeated"):
            return f"{target.name} has already been defeated."
        if not self._is_npc_attackable(target):
            return f"You cannot attack {target.name}."
        if self._entity_stat(target, "hp", 50) <= 0:
            return f"{target.name} is already defeated."
        return None

    async def _collect_encounter_npcs(self, target: WorldEntity) -> list[WorldEntity]:
        others = [
            npc
            for npc in await self._scene_npcs()
            if npc.id != target.id
            and self._is_eligible_npc(npc)
            and self._is_npc_attackable(npc)
            and self._entity_stat(npc, "hp", 50) > 0
        ]
        return [target, *others][:MAX_ENCOUNTER_ENEMIES]

    @staticmethod
    def _starts_engaged(npc: WorldEntity, target: WorldEntity) -> bool:
        attack_mode = (
            (npc.metadata_json or {}).get("attack_mode")
            if isinstance(npc.metadata_json, dict)
            else None
        )
        return npc.id == target.id or attack_mode == "ATTACK_ON_SIGHT"

    async def _create_encounter(self, target: WorldEntity) -> dict[str, Any]:
        npcs = await self._collect_encounter_npcs(target)
        enemies = [await self._build_enemy_entry(n, self._starts_engaged(n, target)) for n in npcs]
        combat: dict[str, Any] = {
            "active": True,
            "round": 1,
            "turn": "player",
            "player": {},
            "enemies": enemies,
            "target_id": target.id,
            "initiative": [],
            "turn_index": 0,
            "xp_gained": 0,
            "loot_pending": False,
            "loot_items": [],
            "outcome": None,
            "status_note": None,
            "log": [],
        }
        self._sync_combat_player_snapshot(combat)
        self._roll_round_initiative(combat)
        first = combat["initiative"][0]
        starts = (
            f"{self.avatar.name} starts the fight."
            if first["id"] == PLAYER_ID
            else f"{first['name']} is faster and starts."
        )
        self._append_combat_log(combat, starts, "turn")
        return combat

    async def _handle_fight_start(
        self, user_msg: str, initiated_by_enemy: bool = False
    ) -> AsyncGenerator[str, None]:
        reason = self._combat_blocked_reason(initiated_by_enemy)
        target_hint = user_msg.split(" ", 1)[1].strip() if " " in user_msg else ""
        target = None if reason else await self._find_fight_target(target_hint)
        if not reason and not target:
            reason = "No enemy is available in this scene."
        if not reason and target:
            reason = self._target_unavailable_reason(target)
        if reason or not target:
            async for chunk in self._reply(reason or "No enemy is available in this scene."):
                yield chunk
            return

        combat = await self._create_encounter(target)
        async for chunk in self._advance_until_player(combat, skip_current=False):
            yield chunk

        others = len(combat["enemies"]) - 1
        crowd = f" {others} other combatant(s) are watching closely." if others else ""
        if initiated_by_enemy:
            msg = f"{target.name} attacks as you enter the scene. Combat starts immediately.{crowd}"
        else:
            msg = f"Combat started against {target.name}.{crowd}"
        async for chunk in self._reply(msg):
            yield chunk

    @staticmethod
    def _gm_attack_target(game_event: GameEvent) -> tuple[str, bool]:
        """Returns (target hint, enemy_initiated) from the GM's requested attacks."""
        target_hint = ""
        for req in game_event.requested_attacks:
            attacker_id = str(req.attacker_id or "").strip()
            target_id = str(req.target_id or "").strip()
            attacker_is_player = attacker_id.upper() == PLAYER_ID
            if attacker_id and not attacker_is_player and target_id.upper() == PLAYER_ID:
                return attacker_id, True
            if not target_hint and target_id and target_id.upper() != PLAYER_ID:
                target_hint = target_id
            if not target_hint and attacker_id and not attacker_is_player:
                target_hint = attacker_id
        return target_hint, False

    async def _auto_trigger_combat_from_gm(self, game_event: GameEvent) -> bool:
        """Starts combat automatically when the mechanics pass requests combat attacks."""
        if self._has_combat_phase() or not game_event.requested_attacks:
            return False
        if (self.adventure.rule_enforcement_mode or "rpg") != "rpg":
            return False
        target_hint, enemy_initiated = self._gm_attack_target(game_event)
        if self._combat_blocked_reason(enemy_initiated):
            return False
        target = await self._find_fight_target(target_hint)
        if not target:
            return False
        async for _chunk in self._handle_fight_start(
            f"/fight {target.id}", initiated_by_enemy=enemy_initiated
        ):
            pass
        return True
