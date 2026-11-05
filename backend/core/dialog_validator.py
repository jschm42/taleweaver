"""Static check for script handlers: every dialog handler and direction callback must exist.

Covers ``on_choice`` / ``on_end`` / ``on_action`` of ``tw.dialog`` and the ``after=`` callback of
``tw.story.direct`` / ``tw.npcs.say_directed`` (run once the next narration is done).

``tw.dialog.choose(..., on_choice=handler)`` (and ``tw.dialog.tree``) resolve the handler in a later request, where only
functions from the global ``init_script`` and the sequence/scene helper blocks are in scope. A handler
defined in the opening script itself (or nowhere) would silently do nothing, so the editor
validation flags it.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from typing import Any

from backend.schemas.validation import ValidationFinding

_MARKERS = ("dialog.", "after=")
# Direction methods whose ``after=`` keyword names a callback.
_DIRECTION_METHODS = {"direct", "say_directed"}
# Dialog method -> (handler keyword, its position) pairs: choose(prompt, options, on_choice),
# tree(tree, on_end, on_action).
_HANDLER_PARAMS = {
    "choose": (("on_choice", 2),),
    "ask": (("on_choice", 2),),
    "tree": (("on_end", 1), ("on_action", 2)),
}


def _strings(value: Any) -> Iterator[str]:
    """Yields every string nested in dicts/lists that may contain a dialog call."""
    if isinstance(value, str) and any(marker in value for marker in _MARKERS):
        yield value
    elif isinstance(value, dict):
        yield from (code for child in value.values() for code in _strings(child))
    elif isinstance(value, (list, tuple)):
        yield from (code for child in value for code in _strings(child))


def _handler_name(call: ast.Call, keyword: str, position: int) -> str | None:
    node = next((kw.value for kw in call.keywords if kw.arg == keyword), None)
    if node is None and len(call.args) > position:
        node = call.args[position]
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value or None
    return node.id if isinstance(node, ast.Name) else None


def _handler_names(call: ast.Call) -> Iterator[str]:
    params = _HANDLER_PARAMS[call.func.attr]  # type: ignore[attr-defined]
    names = (_handler_name(call, keyword, position) for keyword, position in params)
    yield from (name for name in names if name)


def _is_dialog_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
        return False
    owner = node.func.value
    return (
        node.func.attr in _HANDLER_PARAMS
        and isinstance(owner, ast.Attribute)
        and owner.attr == "dialog"
    )


def dialog_handlers(code: str) -> set[str]:
    """Returns the handler names referenced by tw.dialog.choose/ask/tree calls in ``code``."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return set()
    calls = (node for node in ast.walk(tree) if _is_dialog_call(node))
    return {name for call in calls for name in _handler_names(call)}


def _is_direction_callback(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in _DIRECTION_METHODS
        and any(kw.arg == "after" for kw in node.keywords)
    )


def direction_callbacks(code: str) -> set[str]:
    """Returns the ``after=`` callback names of tw.story.direct / say_directed calls in ``code``."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return set()
    calls = (node for node in ast.walk(tree) if _is_direction_callback(node))
    names = (_handler_name(call, "after", len(call.args)) for call in calls)
    return {name for name in names if name}


def init_functions(init_script: Any) -> set[str]:
    if not isinstance(init_script, str) or not init_script.strip():
        return set()
    try:
        tree = ast.parse(init_script)
    except SyntaxError:
        return set()
    return {stmt.name for stmt in tree.body if isinstance(stmt, ast.FunctionDef)}


def check_dialog_handlers(
    sources: list[Any], init_script: Any, helper_scripts: tuple[str, ...] = ()
) -> list[ValidationFinding]:
    """Flags dialog handlers that no definition block defines (one finding per name)."""
    defined = init_functions(init_script)
    for code in helper_scripts:
        defined |= init_functions(code)
    referenced: set[str] = set()
    callbacks: set[str] = set()
    for source in sources:
        for code in _strings(source):
            referenced |= dialog_handlers(code)
            callbacks |= direction_callbacks(code)
    return [
        *_missing_dialog_handlers(referenced - defined),
        *_missing_callbacks(callbacks - defined),
    ]


def _missing_callbacks(names: set[str]) -> list[ValidationFinding]:
    return [
        ValidationFinding(
            severity="warn",
            code="direction_callback_missing",
            message=(
                f"Direction callback '{name}' (after=) is not defined in the global init_script "
                "or in any sequence or scene helpers; it will not run after the narration."
            ),
            location="adventure",
            context={"handler": name},
        )
        for name in sorted(names)
    ]


def _missing_dialog_handlers(names: set[str]) -> list[ValidationFinding]:
    return [
        ValidationFinding(
            severity="warn",
            code="dialog_handler_missing",
            message=(
                f"tw.dialog handler '{name}' is not defined in the global init_script "
                "or in any sequence or scene helpers; the choice will have no effect."
            ),
            location="adventure",
            context={"handler": name},
        )
        for name in sorted(names)
    ]
