"""``/script <code>``: runs script statements in the current session (debug mode only).

The code runs in the same sandbox and with the same ``tw`` API as event scripts, and its changes
are applied like any other script. Script output (narration, NPC lines, errors) shows up as usual;
the command answers with one debug message holding the code, the value of a single expression
(``/script tw.npcs.get('BRAM').hp``) and any script errors. Several statements can be separated
with ``;`` or written on separate lines.
"""

from __future__ import annotations

import ast
import json
from collections.abc import AsyncGenerator
from typing import Any

from backend.api.routes.adventures.turn_pass_flow import sse_role_message
from backend.core.config import settings
from backend.engine.scripting.runner import SCRIPT_ERROR_PREFIX
from backend.engine.scripting.sandbox import SafeAstInterpreter

SCRIPT_COMMAND = "/script"
RESULT_NAME = "script_result"
MAX_RESULT_LENGTH = 2000
USAGE = (
    "Usage: /script <code>, e.g. /script tw.npcs.get('BRAM').hp or "
    "/script tw.player.heal(10); tw.vars.set('door', 'open')"
)


def is_script_command(user_msg: str) -> bool:
    parts = user_msg.strip().split(None, 1)
    return bool(parts) and parts[0].lower() == SCRIPT_COMMAND


def script_debug_allowed(manager: Any) -> bool:
    return bool(settings.TALEWEAVER_DEBUG_ENABLED or manager.state.is_debug_enabled)


def _command_code(user_msg: str) -> str:
    parts = user_msg.strip().split(None, 1)
    return parts[1].strip() if len(parts) > 1 else ""


def _single_expression(code: str) -> bool:
    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError:
        return False
    return len(tree.body) == 1 and isinstance(tree.body[0], ast.Expr)


def _format_result(value: Any) -> str:
    text = repr(value)
    return text if len(text) <= MAX_RESULT_LENGTH else f"{text[:MAX_RESULT_LENGTH]}..."


def debug_report(code: str, result: str | None, errors: list[str]) -> str:
    """The debug message: status line, the code and the expression value or errors."""
    status = "FAILED" if errors else "OK"
    lines = [f"[DEBUG SCRIPT] {status}", f">>> {code}"]
    if result is not None and not errors:
        lines.append(f"= {result}")
    lines.extend(errors)
    return "\n".join(lines)


async def _run(manager: Any, code: str) -> tuple[list[Any], str | None, list[str]]:
    """Runs the code; returns (applied script messages, expression value, errors)."""
    syntax_errors = SafeAstInterpreter.check_syntax(code)
    if syntax_errors:
        return [], None, syntax_errors
    is_expression = _single_expression(code)
    context = await manager._build_script_context()
    scope: dict[str, Any] = {"tw": context, "game": context}
    source = f"{RESULT_NAME} = {code}" if is_expression else code
    manager._get_script_runner().execute_code(source, scope, script_id="debug_script")
    messages = await manager._apply_script_changeset(context.changeset)
    errors = [str(m) for m in messages if str(m).startswith(SCRIPT_ERROR_PREFIX)]
    applied = [m for m in messages if not str(m).startswith(SCRIPT_ERROR_PREFIX)]
    result = _format_result(scope.get(RESULT_NAME)) if is_expression else None
    return applied, result, errors


async def handle_script_command(manager: Any, user_msg: str) -> AsyncGenerator[str, None]:
    """Runs ``/script <code>`` and streams its messages plus one debug report."""
    code = _command_code(user_msg)
    if not script_debug_allowed(manager):
        content = "Unknown command: /script. Type /help for a list of commands."
        yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': content})}\n\n"
        return
    if not code:
        yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': USAGE})}\n\n"
        return

    applied, result, errors = await _run(manager, code)
    for message in applied:
        yield sse_role_message(message)
    report = debug_report(code, result, errors)
    saved = await manager._save_chat_message("system", report)
    await manager.db.commit()
    payload = {"role": "system", "content": report, "is_debug": True, "id": str(saved.id)}
    yield f"event: system\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
