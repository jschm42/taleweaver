"""NPC aggression: attack on sight, configured attack rules and script-requested attacks."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm.attributes import flag_modified

from backend.engine.rules.hard_rule_evaluator import HardRuleEvaluator
from backend.models.world_entity import WorldEntity

logger = logging.getLogger(__name__)

LAST_SCENE_KEY = "__last_scene_id__"
TRIGGER_FIRED_KEY = "attack_trigger_fired"
ATTACK_ON_SIGHT = "ATTACK_ON_SIGHT"


class CombatTriggerMixin:
    """Starts enemy-initiated fights after a turn when an NPC's attack condition is met."""

    def _consume_scene_entry(self) -> bool:
        """Returns True when the protagonist is in a different scene than after the last turn."""
        states = dict(self.state.entity_states or {})
        current = self.state.current_scene_id
        if states.get(LAST_SCENE_KEY) == current:
            return False
        states[LAST_SCENE_KEY] = current
        self.state.entity_states = states
        flag_modified(self.state, "entity_states")
        return True

    def _pop_script_attack_requests(self) -> list[str]:
        requested = list(getattr(self.manager, "pending_npc_attacks", None) or [])
        self.manager.pending_npc_attacks = []
        return requested

    async def _hostile_candidates(self) -> list[WorldEntity]:
        return [
            npc
            for npc in await self._scene_npcs()
            if self._is_eligible_npc(npc)
            and not self._is_npc_defeated(npc)
            and self._is_npc_attackable(npc)
        ]

    async def _attack_rule_met(self, npc: WorldEntity) -> bool:
        meta = npc.metadata_json if isinstance(npc.metadata_json, dict) else {}
        rule = meta.get("attack_trigger")
        fired = self._entity_override(npc.id, TRIGGER_FIRED_KEY)
        if not isinstance(rule, dict) or fired or not HardRuleEvaluator.has_hard_rules(rule):
            return False
        script_context = None
        if str(rule.get("guard_expression") or "").strip():
            script_context = await self.manager._build_script_context()
        met, _reason = HardRuleEvaluator.evaluate_hard_rules(
            rule, self.avatar, self.state, script_context=script_context
        )
        if met:
            # Configured attack rules fire once; afterwards the NPC behaves normally again.
            self._update_entity_state(npc.id, **{TRIGGER_FIRED_KEY: True})
        return met

    async def _find_aggressor(
        self, entered_scene: bool, requested: list[str]
    ) -> tuple[WorldEntity, str] | None:
        candidates = await self._hostile_candidates()
        by_id = {npc.id: npc for npc in candidates}
        for npc_id in requested:
            if npc_id in by_id:
                return by_id[npc_id], f"{by_id[npc_id].name} attacks you!"
            logger.info(
                "[Turn %s] Script attack ignored: %s is not in the scene", self.game_id, npc_id
            )
        for npc in candidates:
            meta: dict[str, Any] = npc.metadata_json if isinstance(npc.metadata_json, dict) else {}
            if entered_scene and meta.get("attack_mode") == ATTACK_ON_SIGHT:
                return npc, f"{npc.name} spots you and attacks on sight!"
            if await self._attack_rule_met(npc):
                return npc, f"{npc.name} turns hostile and attacks!"
        return None

    async def check_npc_attack_triggers(self) -> str | None:
        """Starts a fight if an NPC in the scene wants to attack. Returns the announcement."""
        entered_scene = self._consume_scene_entry()
        requested = self._pop_script_attack_requests()
        if self._has_combat_phase() or int(self.avatar.hp or 0) <= 0:
            return None
        if self._combat_blocked_reason(initiated_by_enemy=True):
            return None

        found = await self._find_aggressor(entered_scene, requested)
        if not found:
            return None
        npc, message = found
        async for _chunk in self._handle_fight_start(f"/fight {npc.id}", initiated_by_enemy=True):
            pass
        if not self._is_combat_active():
            return None
        await self._save_chat_message("system", message)
        return message
