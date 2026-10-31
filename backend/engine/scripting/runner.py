"""
Script runner for dispatching and executing adventure event triggers.
"""

from __future__ import annotations

import ast
import logging
from typing import Any, Optional

from backend.engine.scripting.context import GameContext, ScriptChangeset
from backend.engine.scripting.sandbox import (
    SAFE_BUILTINS,
    SafeAstInterpreter,
    ScriptExecutionError,
    ScriptSecurityError,
    ScriptTimeoutError,
)

logger = logging.getLogger(__name__)

SCRIPT_ERROR_PREFIX = "Script error"


def report_script_error(context: Any, script_id: str, exc: Exception) -> None:
    """Shows a failed script to the player as a system message, whether or not debug mode is on."""
    changeset = getattr(context, "changeset", None)
    messages = getattr(changeset, "system_messages", None)
    if not isinstance(messages, list):
        return
    messages.append(f"{SCRIPT_ERROR_PREFIX} in '{script_id}': {exc}")


class ScriptRunner:
    """Dispatches and evaluates scripts attached to an adventure."""

    def __init__(
        self,
        scripts: list[dict[str, Any]] | None = None,
        init_script: Optional[str] = None,
        helpers: Optional[list[tuple[str, str]]] = None,
    ):
        self.scripts = scripts or []
        self.init_script = str(init_script or "").strip()
        # (source_id, code) of scene helper blocks, loaded after init_script in this order.
        self.helpers = [
            (sid, str(code).strip()) for sid, code in (helpers or []) if str(code).strip()
        ]
        self.interpreter = SafeAstInterpreter()

    @staticmethod
    def _should_run_script(script: Any, trigger: str, target_id: Optional[str]) -> bool:
        if not isinstance(script, dict):
            return False
        if script.get("is_active") is False:
            return False
        if script.get("trigger") != trigger:
            return False
        s_target = script.get("target_id") or script.get("target")
        if s_target and (not target_id or s_target != target_id):
            return False
        return bool(script.get("code", "").strip())

    def load_init_definitions(self, scope: dict[str, Any]) -> None:
        """
        Loads function definitions and constant assignments from init_script and the scene
        helper blocks into the target scope (later blocks shadow earlier names).
        Top-level expressions and mutable API calls are skipped to prevent state resets.
        """
        # Definitions get their own step/time budget: without it the step counter and the
        # deadline of the interpreter's previous run (or the initial 0.0) would apply here.
        self.interpreter._start_budget()
        for source_id, code in [("init_script", self.init_script), *self.helpers]:
            if code:
                self._load_definitions(code, source_id, scope)

    def _load_definitions(self, code: str, source_id: str, scope: dict[str, Any]) -> None:
        try:
            tree = ast.parse(code, mode="exec")
        except Exception as exc:
            logger.error(f"[ScriptRunner] Failed to parse {source_id} definitions: {exc}")
            report_script_error(scope.get("tw"), source_id, exc)
            return

        def_body: list[ast.stmt] = []
        for stmt in tree.body:
            is_valid_assign = isinstance(stmt, ast.Assign) and isinstance(
                stmt.value, (ast.Constant, ast.List, ast.Tuple, ast.Dict)
            )
            if isinstance(stmt, ast.FunctionDef) or is_valid_assign:
                def_body.append(stmt)

        if not def_body:
            return

        filtered_module = ast.Module(body=def_body, type_ignores=[])
        try:
            self.interpreter.validate_ast(filtered_module)
            temp_env = {**SAFE_BUILTINS, **scope}
            prev_env = self.interpreter.env
            self.interpreter.env = temp_env
            try:
                for s in def_body:
                    self.interpreter._eval_stmt(s)
                for k, v in self.interpreter.env.items():
                    if k not in SAFE_BUILTINS and k not in ("tw", "game"):
                        scope[k] = v
            finally:
                self.interpreter.env = prev_env
        except Exception as exc:
            logger.error(
                f"[ScriptRunner] Error executing {source_id} definitions into scope: {exc}"
            )
            report_script_error(scope.get("tw"), source_id, exc)

    def run_init_script(self, context: GameContext) -> ScriptChangeset:
        """
        Executes the entire init_script once (including variables and state mutations).
        Also dispatches any modular scripts with trigger == 'on_init'.
        """
        scope = {"tw": context, "game": context}
        if self.init_script:
            logger.info("[ScriptRunner] Executing adventure init_script...")
            try:
                self.interpreter.execute(self.init_script, scope)
            except Exception as exc:
                logger.exception(f"[ScriptRunner] Error executing init_script: {exc}")
                report_script_error(context, "init_script", exc)

        # Also dispatch any modular scripts configured with 'on_init'
        self.run_trigger("on_init", context)
        return context.changeset

    def _run_single_script(
        self,
        script: dict[str, Any],
        trigger: str,
        target_id: Optional[str],
        context: GameContext,
    ) -> None:
        code = script.get("code", "").strip()
        script_id = script.get("id", "UNKNOWN_SCRIPT")
        logger.info(
            f"[ScriptRunner] Executing script '{script_id}' on trigger '{trigger}' (target={target_id})"
        )
        scope = {"tw": context, "game": context}
        self.load_init_definitions(scope)
        try:
            self.interpreter.execute(code, scope)
        except ScriptSecurityError as sse:
            logger.error(f"[ScriptRunner] Security violation in script '{script_id}': {sse}")
            report_script_error(context, script_id, sse)
        except ScriptTimeoutError as ste:
            logger.error(
                f"[ScriptRunner] Timeout/instruction limit exceeded in script '{script_id}': {ste}"
            )
            report_script_error(context, script_id, ste)
        except ScriptExecutionError as see:
            logger.error(f"[ScriptRunner] Runtime error in script '{script_id}': {see}")
            report_script_error(context, script_id, see)
        except Exception as exc:
            logger.exception(
                f"[ScriptRunner] Unexpected error executing script '{script_id}': {exc}"
            )
            report_script_error(context, script_id, exc)

    def run_trigger(
        self,
        trigger: str,
        context: GameContext,
        target_id: Optional[str] = None,
    ) -> ScriptChangeset:
        """
        Finds and executes all scripts matching the specified trigger and optional target_id.
        Mutations are accumulated directly in context.changeset.
        """
        for script in self.scripts:
            if not self._should_run_script(script, trigger, target_id):
                continue
            self._run_single_script(script, trigger, target_id, context)

        return context.changeset

    def execute_code(self, code: str, scope: dict[str, Any], script_id: str = "INLINE") -> None:
        """Executes a single inline code block directly."""
        self.load_init_definitions(scope)
        try:
            self.interpreter.execute(code, scope)
        except Exception as exc:
            logger.exception(
                f"[ScriptRunner] Unexpected error executing inline script '{script_id}': {exc}"
            )
            report_script_error(scope.get("tw") or scope.get("game"), script_id, exc)
