"""
Script runner for dispatching and executing adventure event triggers.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from backend.engine.scripting.context import GameContext, ScriptChangeset
from backend.engine.scripting.sandbox import (
    SafeAstInterpreter,
    ScriptExecutionError,
    ScriptSecurityError,
    ScriptTimeoutError,
)

logger = logging.getLogger(__name__)


class ScriptRunner:
    """Dispatches and evaluates scripts attached to an adventure."""

    def __init__(self, scripts: list[dict[str, Any]] | None = None):
        self.scripts = scripts or []
        self.interpreter = SafeAstInterpreter()

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
            if not isinstance(script, dict):
                continue

            s_trigger = script.get("trigger")
            if s_trigger != trigger:
                continue

            s_target = script.get("target_id")
            if s_target and target_id and s_target != target_id:
                continue
            elif s_target and not target_id:
                continue

            code = script.get("code", "").strip()
            if not code:
                continue

            script_id = script.get("id", "UNKNOWN_SCRIPT")
            logger.info(
                f"[ScriptRunner] Executing script '{script_id}' on trigger '{trigger}' (target={target_id})"
            )

            # Build script scope with tw and game aliases
            scope = {
                "tw": context,
                "game": context,
            }

            try:
                self.interpreter.execute(code, scope)
            except ScriptSecurityError as sse:
                logger.error(
                    f"[ScriptRunner] Security violation in script '{script_id}': {sse}"
                )
            except ScriptTimeoutError as ste:
                logger.error(
                    f"[ScriptRunner] Timeout/instruction limit exceeded in script '{script_id}': {ste}"
                )
            except ScriptExecutionError as see:
                logger.error(
                    f"[ScriptRunner] Runtime error in script '{script_id}': {see}"
                )
            except Exception as exc:
                logger.exception(
                    f"[ScriptRunner] Unexpected error executing script '{script_id}': {exc}"
                )

        return context.changeset
