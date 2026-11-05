"""Runs the callbacks scripts attached to a GM direction once the narration is done.

``tw.story.direct(..., after="handler", after_args={...})`` and ``tw.npcs.say_directed(...)``
queue an init-script function next to the direction. The direction shapes the next narration;
the callback runs right after it, so its messages and state changes follow the narrated scene.
Called after a turn's narration and after a choice dialog's narration.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from backend.engine.rules.rule_engine import GameOverError
from backend.engine.scripting.gm_directions import take_after_narration
from backend.engine.scripting.runner import SCRIPT_ERROR_PREFIX

logger = logging.getLogger(__name__)

_PARAM_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


async def _missing_handler(manager: Any, handler: str) -> str:
    logger.warning("[Narration] Callback '%s' is not defined in the init script.", handler)
    # Shown even without debug mode: otherwise the follow-up silently never happens.
    note = (
        f"{SCRIPT_ERROR_PREFIX} in 'after_{handler}': the callback '{handler}' is not defined "
        "in the adventure's init_script, so it did not run after the narration."
    )
    await manager._save_chat_message("system", note)
    return note


def _call_code(handler: str, args: dict[str, Any]) -> str:
    """``handler(key=after_args['key'], ...)``; keys are validated parameter names.

    The sandbox does not unpack ``**kwargs``, so each argument is spelled out. Values are read
    from ``after_args`` in the scope and never become code.
    """
    params = ", ".join(f"{key}=after_args[{key!r}]" for key in args if _PARAM_NAME.match(key))
    return f"{handler}({params})"


async def run_after_narration(manager: Any) -> tuple[list[Any], bool]:
    """Runs and clears the queued callbacks; returns (messages, adventure_ended)."""
    callbacks = take_after_narration(manager.state)
    if not callbacks:
        return [], False
    runner = manager._get_script_runner()
    definitions: dict[str, Any] = {}
    runner.load_init_definitions(definitions)
    messages: list[Any] = []
    for callback in callbacks:
        handler = str(callback.get("handler") or "")
        if not callable(definitions.get(handler)):
            messages.append(await _missing_handler(manager, handler))
            continue
        context = await manager._build_script_context()
        args = dict(callback.get("args") or {})
        scope = {"tw": context, "game": context, "after_args": args}
        runner.execute_code(_call_code(handler, args), scope, script_id=f"after_{handler}")
        try:
            messages.extend(await manager._apply_script_changeset(context.changeset))
        except GameOverError as goe:
            await manager._finalize_session("game_over", str(goe))
            return messages, True
    return messages, False
