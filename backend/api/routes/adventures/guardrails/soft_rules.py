"""Soft rule guard: runs the scripts of active-sequence soft rules the GM reported as fulfilled."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm.attributes import flag_modified

from backend.engine.interaction.switch_service import SwitchService
from backend.engine.rules.rule_engine import GameEvent
from backend.engine.rules.soft_rules import (
    SOFT_RULE_COUNTS_KEY,
    SoftRule,
    fired_counts,
    is_exhausted,
    sequence_soft_rules,
)


class SoftRuleGuardMixin:
    """Validates GM-reported soft rules (scope, trigger limit, guard) and executes them."""

    async def _enforce_soft_rules(
        self, event: GameEvent, sequence: dict[str, Any] | None
    ) -> list[str]:
        """Fires the reported rules of ``sequence`` in report order; returns messages to show.

        ``event.triggered_soft_rule_ids`` is narrowed to the rules that actually fired.
        """
        reported = [str(rule_id).strip() for rule_id in event.triggered_soft_rule_ids or []]
        event.triggered_soft_rule_ids = None
        if not reported:
            return []

        rules_by_id = {rule.id: rule for rule in sequence_soft_rules(sequence)}
        fired: list[str] = []
        messages: list[str] = []
        for rule_id in dict.fromkeys(reported):
            rule = rules_by_id.get(rule_id)
            if rule is None:
                await self._debug_soft_rule(rule_id, "not part of the active sequence")
                continue
            rejection = await self._soft_rule_rejection(rule)
            if rejection is not None:
                await self._debug_soft_rule(rule_id, rejection)
                continue
            messages.extend(await self._fire_soft_rule(rule))
            fired.append(rule.id)
        event.triggered_soft_rule_ids = fired or None
        return messages

    async def _soft_rule_rejection(self, rule: SoftRule) -> str | None:
        """Returns why the rule may not fire this message, or None when it may."""
        if is_exhausted(rule, fired_counts(self.state.entity_states)):
            return "trigger limit reached"
        if not rule.guard_expression:
            return None
        ctx = await self.manager._build_script_context()
        passed, detail = SwitchService.evaluate_gate_expression(rule.guard_expression, ctx)
        return None if passed else detail or "guard not met"

    async def _fire_soft_rule(self, rule: SoftRule) -> list[str]:
        messages = await self.manager._execute_inline_script(rule.script, "on_soft_rule", rule.id)
        self._count_soft_rule(rule.id)
        if rule.text:
            await self._save_chat_message("system", rule.text)
            messages.append(rule.text)
        return messages

    def _count_soft_rule(self, rule_id: str) -> None:
        entity_states = dict(self.state.entity_states or {})
        counts = fired_counts(entity_states)
        counts[rule_id] = counts.get(rule_id, 0) + 1
        entity_states[SOFT_RULE_COUNTS_KEY] = counts
        self.state.entity_states = entity_states
        flag_modified(self.state, "entity_states")

    async def _debug_soft_rule(self, rule_id: str, reason: str) -> None:
        ctx = await self.manager._build_script_context()
        if not ctx.is_debug_enabled:
            return
        await self._save_chat_message("system", f"[DEBUG soft_rule {rule_id}: {reason}]")
