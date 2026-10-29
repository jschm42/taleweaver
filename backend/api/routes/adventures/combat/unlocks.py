"""Rule-based unlocking of the protagonist's special attacks."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm.attributes import flag_modified

from backend.engine.rules.hard_rule_evaluator import HardRuleEvaluator

# Special action field -> hard rule key understood by HardRuleEvaluator.
UNLOCK_RULE_FIELDS = {
    "unlock_required_item_id": "required_item_id",
    "unlock_required_scene_id": "required_scene_id",
    "unlock_required_defeated_npc_id": "required_defeated_npc_id",
    "unlock_guard_expression": "guard_expression",
}


def unlock_rule(action: dict[str, Any]) -> dict[str, Any]:
    return {rule_key: action.get(field) for field, rule_key in UNLOCK_RULE_FIELDS.items()}


def unlock_message(action: dict[str, Any]) -> str:
    msg = f"✨ Special attack unlocked: {action.get('name') or action.get('id')}!"
    text = str(action.get("unlock_text") or "").strip()
    return f"{msg} {text}" if text else msg


class CombatUnlockMixin:
    """Evaluates unlock rules after every turn and announces new special attacks."""

    async def _rule_met(self, rule: dict[str, Any]) -> bool:
        script_context = None
        if str(rule.get("guard_expression") or "").strip():
            script_context = await self.manager._build_script_context()
        met, _reason = HardRuleEvaluator.evaluate_hard_rules(
            rule, self.avatar, self.state, script_context=script_context
        )
        return met

    async def _newly_unlocked(self, actions: list[Any], unlocked: set[str]) -> list[dict[str, Any]]:
        found = []
        for action in actions:
            if not isinstance(action, dict) or not action.get("is_locked"):
                continue
            if action.get("id") in unlocked:
                continue
            rule = unlock_rule(action)
            if HardRuleEvaluator.has_hard_rules(rule) and await self._rule_met(rule):
                found.append(action)
        return found

    async def check_special_unlocks(self) -> list[str]:
        """Unlocks special attacks whose rules are now met. Returns the announcements."""
        stats = dict(self.avatar.stats or {})
        unlocked = list(stats.get("unlocked_actions") or [])
        newly = await self._newly_unlocked(list(stats.get("special_actions") or []), set(unlocked))
        if not newly:
            return []

        stats["unlocked_actions"] = unlocked + [a["id"] for a in newly]
        self.avatar.stats = stats
        flag_modified(self.avatar, "stats")
        messages = [unlock_message(action) for action in newly]
        for msg in messages:
            await self._save_chat_message("system", msg)
        return messages
