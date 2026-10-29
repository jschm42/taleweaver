"""World rules: switch transitions and NPC movement constraints."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from backend.api.routes.adventures.guardrails.base import inventory_ids_upper
from backend.engine.interaction.switch_service import SwitchService
from backend.engine.rules.rule_engine import GameEvent
from backend.models.world_entity import WorldEntity


def _switch_flag_keys(metadata: dict[str, Any]) -> set[str]:
    config = metadata.get("switch") or {}
    outcomes = metadata.get("switch_outcomes") or config.get("outcomes") or []
    return {
        str(effect.get("key")).strip()
        for outcome in outcomes
        if isinstance(outcome, dict)
        for effect in outcome.get("effects") or []
        if isinstance(effect, dict) and effect.get("type") == "story_flag" and effect.get("key")
    }


def _required_transition_item(transition: dict[str, Any]) -> str:
    gates = transition.get("gates") if isinstance(transition.get("gates"), dict) else {}
    return str(gates.get("item") or transition.get("required_item") or "").strip().upper()


class WorldRulesMixin:
    """Switch transition gates and NPC movement limits."""

    async def _get_switch_story_flags(self) -> set[str]:
        """Returns all story flag keys configured as switch outcomes in this adventure."""
        res = await self.db.execute(
            select(WorldEntity).where(
                WorldEntity.session_id == self.game_id,
                WorldEntity.entity_type == "OBJECT",
                WorldEntity.item_type == "SWITCH",
            )
        )
        flags: set[str] = set()
        for switch in res.scalars().all():
            flags |= _switch_flag_keys(switch.metadata_json or {})
        return flags

    async def _load_switch(self, entity_id: str) -> WorldEntity | None:
        res = await self.db.execute(
            select(WorldEntity).where(
                WorldEntity.id == entity_id, WorldEntity.session_id == self.game_id
            )
        )
        switch = res.scalars().first()
        return switch if switch and str(switch.item_type or "").upper() == "SWITCH" else None

    async def _transition_failure(
        self,
        transition: dict[str, Any] | None,
        switch: WorldEntity,
        lowered: str,
        script_context: Any,
    ) -> str | None:
        """Returns why the transition is blocked, or None when it may happen."""
        if transition is None:
            return None
        allowed, reason = SwitchService.evaluate_transition_gates(
            transition=transition,
            context=script_context,
            avatar_inventory_ids=inventory_ids_upper(self.avatar.inventory),
            story_flags=self._switch_story_flags(),
            user_prompt=lowered,
            switch_name=switch.name,
        )
        if not allowed:
            return reason or ""
        required_item = _required_transition_item(transition)
        if required_item and not await self._is_key_item_referenced(
            required_item, lowered, switch.name
        ):
            return str(transition.get("fail_message") or "").strip() or (
                f"You must specify which item you are using on {switch.name}."
            )
        return None

    async def _guard_switch_update(self, event: GameEvent, update: Any, lowered: str) -> str | None:
        switch = await self._load_switch(update.entity_id)
        if not switch:
            return None
        metadata = switch.metadata_json or {}
        config = metadata.get("switch") or {}
        entry = dict((self.state.entity_states or {}).get(switch.id) or {})
        configured = config.get("initial_state") or metadata.get("switch_initial_state") or ""
        current_state = str(entry.get("switch_state") or configured).strip().upper()
        target_state = str(update.switch_state).strip().upper()
        if current_state == target_state:
            return None

        transition = SwitchService.resolve_transition(config, current_state, target_state)
        script_context = await self.manager._build_script_context()
        runner = self.manager._get_script_runner()
        failure = await self._transition_failure(transition, switch, lowered, script_context)
        if failure is not None:
            # Revoke first so rewards granted by the failure scripts below survive.
            update.switch_state = current_state
            self._revoke_turn_rewards(event)
        SwitchService.execute_transition_triggers(
            runner=runner,
            config=config,
            transition=transition,
            success=failure is None,
            context=script_context,
            switch_id=switch.id,
        )
        await self.manager._apply_script_changeset(script_context.changeset, game_event=event)
        if failure is not None:
            return failure or f"{switch.name} cannot be flipped."
        outcomes = config.get("outcomes") if isinstance(config.get("outcomes"), list) else []
        await self.manager._apply_switch_outcomes(outcomes, target_state)
        return None

    async def _enforce_switch_transition_guardrails(
        self, event: GameEvent, user_msg: str
    ) -> list[str]:
        """Reverts switch changes whose transition gates are not satisfied."""
        if not event.updated_entities:
            return []
        lowered = (user_msg or "").strip().lower()
        reasons = []
        for update in list(event.updated_entities):
            if not update.switch_state:
                continue
            reason = await self._guard_switch_update(event, update, lowered)
            if reason is not None:
                reasons.append(reason)
        return reasons

    @staticmethod
    def _npc_is_moveable(ent: WorldEntity, override: dict[str, Any]) -> bool:
        moveable = override.get("moveable")
        if moveable is not None:
            return bool(moveable)
        return bool(getattr(ent, "moveable", False)) or (
            str(getattr(ent, "movement_type", "") or "").upper() == "MOVABLE"
        )

    def _npc_move_violation(self, ent: WorldEntity, move: Any) -> str | None:
        override = (self.state.entity_states or {}).get(ent.id, {})
        current_scene = override.get("current_scene_id") or ent.current_scene_id
        if move.to_scene_id == current_scene:
            return None  # Changing only the spatial position is always fine.
        if not self._npc_is_moveable(ent, override):
            return f"Rule Violation: NPC '{ent.name}' ({ent.id}) is not moveable and cannot change scenes to '{move.to_scene_id}'."
        allowed = override.get("allowed_scenes")
        if allowed is None:
            allowed = getattr(ent, "allowed_scenes", None) or []
        if (
            isinstance(allowed, list)
            and allowed
            and move.to_scene_id.upper() not in {str(s).upper() for s in allowed if s}
        ):
            return (
                f"Rule Violation: NPC '{ent.name}' ({ent.id}) is not permitted to move to scene "
                f"'{move.to_scene_id}'. Allowed scenes: {', '.join(allowed)}."
            )
        return None

    async def _enforce_npc_movement_guardrails(self, event: GameEvent) -> list[str]:
        """NPCs only change scenes if moveable and the destination is in allowed_scenes."""
        if not event.moved_entities:
            return []
        entities = await self._session_entities()
        by_id = {e.id.upper(): e for e in entities if e.id}
        by_name = {(e.name or "").strip().lower(): e for e in entities if e.name}
        messages: list[str] = []
        valid_moves = []
        for move in event.moved_entities:
            raw_id = str(move.entity_id or "").strip()
            ent = by_id.get(raw_id.upper()) or by_name.get(raw_id.lower())
            violation = None
            if ent and ent.entity_type == "NPC" and move.to_scene_id:
                violation = self._npc_move_violation(ent, move)
            if violation:
                messages.append(violation)
            else:
                valid_moves.append(move)
        event.moved_entities = valid_moves
        return messages
