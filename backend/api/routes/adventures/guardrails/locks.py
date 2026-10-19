"""One unlock engine for containers and exits.

Requirements are checked in order: rule, code, key item, guard expression. Containers and
exits differ only in the policy flags on ``LockSpec``:

* ``explicit_unlock_required``: containers only open when the GM unlocks them this turn;
  for exits, walking through is enough once every requirement is met.
* ``rule_uses_switch_flags``: a container rule naming a switch story flag needs that flag;
  exit rules always need the GM's explicit unlock.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.api.routes.adventures.guardrails.base import inventory_ids_upper
from backend.engine.switch_service import SwitchService


@dataclass
class LockSpec:
    """Everything needed to judge one locked container or exit for this turn."""

    script_target_id: str
    name: str
    code: str = ""
    item_id: str = ""
    rule: str = ""
    expression: str = ""
    failure_script: str = ""
    failure_text: str = ""
    being_unlocked: bool = False
    explicit_unlock_required: bool = True
    rule_uses_switch_flags: bool = True
    code_failure_text: str = ""
    rule_failure_text: str = ""


class LockEngineMixin:
    """Evaluates lock requirements and runs failure hooks."""

    def _rule_failure(self, spec: LockSpec, switch_flags: set[str]) -> str | None:
        if not spec.rule:
            return None
        if spec.rule_uses_switch_flags and spec.rule in switch_flags:
            if self._switch_story_flags().get(spec.rule, False):
                return None
            return f"{spec.name} stays shut. It seems to require some mechanism to trigger."
        if spec.being_unlocked:
            return None
        return spec.rule_failure_text or f"{spec.name} is locked."

    @staticmethod
    def _code_failure(spec: LockSpec, lowered_msg: str) -> str | None:
        if not spec.code:
            return None
        missing_unlock = spec.explicit_unlock_required and not spec.being_unlocked
        if missing_unlock or spec.code.lower() not in lowered_msg:
            return spec.code_failure_text or f"{spec.name} won't accept that code."
        return None

    async def _item_failure(self, spec: LockSpec, lowered_msg: str) -> str | None:
        if not spec.item_id:
            return None
        if spec.item_id not in inventory_ids_upper(self.avatar.inventory):
            return f"You need a specific item to unlock {spec.name}."
        if not await self._is_key_item_referenced(spec.item_id, lowered_msg, spec.name):
            return f"You must specify which item you are using to unlock {spec.name}."
        if spec.explicit_unlock_required and not spec.being_unlocked:
            return f"You try using the item to unlock {spec.name}."
        return None

    async def _expression_failure(self, spec: LockSpec) -> str | None:
        if not spec.expression:
            return None
        ctx = await self.manager._build_script_context()
        passed, detail = SwitchService.evaluate_gate_expression(spec.expression, ctx)
        if passed:
            return None
        return spec.failure_text or detail or f"{spec.name} stays locked."

    async def _lock_failure(
        self, spec: LockSpec, lowered_msg: str, switch_flags: set[str]
    ) -> str | None:
        """Returns why the lock stays closed this turn, or None when it may open."""
        reason = (
            self._rule_failure(spec, switch_flags)
            or self._code_failure(spec, lowered_msg)
            or await self._item_failure(spec, lowered_msg)
            or await self._expression_failure(spec)
        )
        if reason is None and spec.explicit_unlock_required and not spec.being_unlocked:
            reason = ""
        return reason

    async def _run_lock_failure_hooks(self, spec: LockSpec, reason: str) -> str:
        """Runs the failure script; the configured failure text replaces the engine's reason."""
        if spec.failure_script:
            await self.manager._execute_inline_script(
                spec.failure_script, "on_unlock_failure", spec.script_target_id
            )
        return spec.failure_text or reason or f"{spec.name} stays locked."
