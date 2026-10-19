"""
Switch transition resolution, gate evaluation, and trigger execution service.

Handles deterministic transition lookup, soft and scripted gate validations
(including sandboxed boolean expressions), and on_success / on_failure script triggers.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from backend.engine.scripting.context import GameContext
from backend.engine.scripting.runner import ScriptRunner
from backend.engine.scripting.sandbox import (
    SafeAstInterpreter,
    ScriptExecutionError,
    ScriptSecurityError,
    ScriptTimeoutError,
)

logger = logging.getLogger(__name__)


class SwitchService:
    """Service for managing switch mechanics, transition guards, and script triggers."""

    interpreter = SafeAstInterpreter()

    @staticmethod
    def resolve_switch_config(entity: Any) -> dict[str, Any]:
        """Extracts normalized switch configuration from an entity or metadata dict."""
        metadata = getattr(entity, "metadata_json", None)
        if isinstance(entity, dict):
            metadata = entity.get("metadata_json") or entity

        if not isinstance(metadata, dict):
            return {}

        config = metadata.get("switch")
        if isinstance(config, dict):
            return dict(config)

        # Fallback for flat metadata representations
        states = metadata.get("switch_states")
        if isinstance(states, list):
            return {
                "states": states,
                "initial_state": metadata.get("switch_initial_state", ""),
                "transitions": metadata.get("switch_transitions", []),
                "outcomes": metadata.get("switch_outcomes", []),
                "on_success_script": metadata.get("on_success_script", ""),
                "on_failure_script": metadata.get("on_failure_script", ""),
            }
        return {}

    @staticmethod
    def resolve_transition(
        config: dict[str, Any],
        current_state: str,
        target_state: str,
    ) -> dict[str, Any] | None:
        """
        Finds matching transition definition for current_state -> target_state.
        Exact match (both from and to specified) takes precedence over wildcard (from empty).
        """
        transitions = config.get("transitions")
        if not isinstance(transitions, list):
            return None

        curr = current_state.strip().upper()
        target = target_state.strip().upper()
        wildcard_match: dict[str, Any] | None = None

        for t in transitions:
            if not isinstance(t, dict):
                continue
            to_s = str(t.get("to") or t.get("to_state") or "").strip().upper()
            if not to_s or to_s != target:
                continue

            from_s = str(t.get("from") or t.get("from_state") or "").strip().upper()
            if from_s and from_s == curr:
                return t
            if not from_s and wildcard_match is None:
                wildcard_match = t

        return wildcard_match

    @classmethod
    def evaluate_gate_expression(
        cls,
        expression: str,
        context: GameContext,
    ) -> tuple[bool, str | None]:
        """
        Evaluates a sandboxed Python boolean expression using the script context.
        Returns (is_satisfied, error_reason).
        """
        code = expression.strip()
        if not code:
            return True, None

        scope = {"tw": context, "game": context}
        try:
            result = cls.interpreter.evaluate_expression(code, scope)
            if not bool(result):
                return False, f"Guard condition evaluated to false: '{code}'"
            return True, None
        except (ScriptSecurityError, ScriptTimeoutError, ScriptExecutionError) as exc:
            logger.warning(f"[SwitchService] Script guard evaluation error for '{code}': {exc}")
            return False, f"Guard expression failed: {exc}"
        except Exception as exc:
            logger.exception(f"[SwitchService] Unexpected error evaluating guard '{code}': {exc}")
            return False, f"Guard expression error: {exc}"

    @classmethod
    def evaluate_transition_gates(
        cls,
        transition: dict[str, Any],
        context: GameContext,
        provided_code: Optional[str] = None,
        avatar_inventory_ids: Optional[set[str]] = None,
        story_flags: Optional[dict[str, bool]] = None,
        user_prompt: str = "",
        switch_name: str = "Switch",
    ) -> tuple[bool, str]:
        """
        Validates all lock gates on a transition.
        Checks key item, code / PIN, story flag, and scripted boolean expression.
        Returns (is_allowed, failure_message).
        """
        gates = transition.get("gates")
        if not isinstance(gates, dict):
            gates = {}

        fail_msg = str(transition.get("fail_message") or "").strip()
        inv_ids = avatar_inventory_ids or set()
        flags = story_flags or {}
        lowered_prompt = (user_prompt or "").lower()

        # 1. Required item gate
        required_item = (
            str(gates.get("item") or transition.get("required_item") or "").strip().upper()
        )
        if required_item and required_item not in inv_ids:
            return False, fail_msg or f"{switch_name} requires a specific item to operate."

        # 2. Required code gate
        required_code = str(gates.get("code") or transition.get("code") or "").strip()
        if required_code:
            code_matches = (
                provided_code is not None
                and str(provided_code).strip().lower() == required_code.lower()
            ) or (lowered_prompt and required_code.lower() in lowered_prompt)
            if not code_matches:
                return False, fail_msg or f"Incorrect code for {switch_name}."

        # 3. Soft rule / story flag gate
        required_rule = str(gates.get("rule") or transition.get("required_rule") or "").strip()
        if required_rule and not flags.get(required_rule, False):
            return False, fail_msg or f"{switch_name} requirements are not met."

        # 4. Deterministic boolean expression guard (Scripting Engine)
        expr = str(gates.get("expression") or gates.get("condition") or "").strip()
        if expr:
            passed, err_detail = cls.evaluate_gate_expression(expr, context)
            if not passed:
                return False, fail_msg or err_detail or f"{switch_name} guard condition not met."

        return True, ""

    @staticmethod
    def execute_transition_triggers(
        runner: ScriptRunner,
        config: dict[str, Any],
        transition: Optional[dict[str, Any]],
        success: bool,
        context: GameContext,
        switch_id: str,
    ) -> None:
        """
        Executes on_success or on_failure script triggers for the switch.
        Runs transition-specific script first, then switch-level script.
        """
        scope = {"tw": context, "game": context}

        if getattr(context, "is_debug_enabled", False):
            trig_name = "on_success" if success else "on_failure"
            context.changeset.system_messages.append(
                f"[DEBUG: Trigger fired] {trig_name} on switch {switch_id}"
            )

        if success:
            # Transition-level on_success
            if transition:
                t_script = str(transition.get("on_success_script") or "").strip()
                if t_script:
                    runner.execute_code(
                        t_script, scope, script_id=f"switch_{switch_id}_trans_success"
                    )

            # Switch-level on_success
            s_script = str(config.get("on_success_script") or "").strip()
            if s_script:
                runner.execute_code(s_script, scope, script_id=f"switch_{switch_id}_on_success")
            return

        # Transition-level on_failure
        if transition:
            t_script = str(transition.get("on_failure_script") or "").strip()
            if t_script:
                runner.execute_code(t_script, scope, script_id=f"switch_{switch_id}_trans_failure")

        # Switch-level on_failure
        s_script = str(config.get("on_failure_script") or "").strip()
        if s_script:
            runner.execute_code(s_script, scope, script_id=f"switch_{switch_id}_on_failure")

