"""Hidden NPC reveal guards: a hidden NPC appears once its ``reveal_guard_expression`` is True.

Hidden NPCs are never discovered by the Game Master (``reveal_policy.entity_is_script_only``).
Besides scripts, their only way into the scene is this deterministic guard, evaluated on every
pass of the reveal guardrail while the NPC is hidden in the protagonist's scene.
"""

from __future__ import annotations

import logging

from backend.engine.interaction.switch_service import SwitchService
from backend.engine.rules.reveal_policy import is_npc, npc_reveal_guard
from backend.engine.rules.rule_engine import GameEvent
from backend.models.world_entity import WorldEntity

logger = logging.getLogger(__name__)


def _revealed_this_turn(event: GameEvent, entity_id: str) -> bool:
    return any(
        (up.entity_id or "").upper() == entity_id.upper() and up.is_hidden is False
        for up in event.updated_entities or []
    )


class NpcRevealGuardMixin:
    """Reveals hidden NPCs in the current scene whose reveal guard holds."""

    def _guarded_hidden_npcs(self, entities: list[WorldEntity]) -> list[WorldEntity]:
        scene_id = self.state.current_scene_id
        return [
            e
            for e in entities
            if e.id
            and is_npc(e)
            and e.current_scene_id == scene_id
            and npc_reveal_guard(e)
            and self._is_entity_hidden_now(e)
        ]

    async def _reveal_guarded_npcs(
        self, event: GameEvent, entities: list[WorldEntity], revealed: list[str]
    ) -> None:
        """Adds a reveal update for every guarded hidden NPC whose guard is True now."""
        candidates = [
            npc
            for npc in self._guarded_hidden_npcs(entities)
            if not _revealed_this_turn(event, npc.id)
        ]
        if not candidates:
            return
        ctx = await self.manager._build_script_context()
        for npc in candidates:
            passed, detail = SwitchService.evaluate_gate_expression(npc_reveal_guard(npc), ctx)
            if not passed:
                logger.debug(
                    "[Turn %s] Reveal guard of '%s' unmet: %s", self.game_id, npc.id, detail
                )
                continue
            self._reveal(event, npc, revealed)
