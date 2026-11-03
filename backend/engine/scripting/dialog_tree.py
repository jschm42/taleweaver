"""Nested NPC dialogues (``tw.dialog.tree``): a conversation as a tree of nodes.

Each node has the NPC's line (``npc_text``) and up to 8 player ``responses``. A response leads
to ``next_node`` (``None`` ends the conversation) and may carry a ``condition`` (guard
expression that hides it), ``once`` (hide it after it was picked), a ``script`` (inline code
run when picked) and an ``action`` (a string passed to the ``on_action`` handler).

The whole normalized tree travels in the pending dialog, so every step is resolved on the
server without the script that opened it. The client only ever sees the current node.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional
from uuid import uuid4

from backend.engine.scripting.dialog import (
    MAX_DIALOG_OPTIONS,
    MAX_LABEL_LENGTH,
    MAX_PROMPT_LENGTH,
    handler_name,
)

if TYPE_CHECKING:
    from backend.engine.scripting.context import GameContext

TREE_KIND = "tree"
MAX_TREE_NODES = 100
MAX_PATH_LENGTH = 200
MAX_SCRIPT_LENGTH = 5000
MAX_ACTION_LENGTH = 100
MAX_ID_LENGTH = 64


def _text(raw: Any, limit: int) -> str:
    return str(raw or "").strip()[:limit]


def _node_ref(raw: Any) -> Optional[str]:
    ref = _text(raw, MAX_ID_LENGTH)
    return ref or None


def _response(raw: Any) -> Optional[dict[str, Any]]:
    if isinstance(raw, str):
        raw = {"text": raw}
    if not isinstance(raw, dict):
        return None
    text = _text(raw.get("text") or raw.get("label"), MAX_LABEL_LENGTH)
    if not text:
        return None
    return {
        "text": text,
        "next_node": _node_ref(raw.get("next_node")),
        "condition": _text(raw.get("condition") or raw.get("visible_if"), MAX_PROMPT_LENGTH),
        "script": _text(raw.get("script"), MAX_SCRIPT_LENGTH),
        "action": _text(raw.get("action"), MAX_ACTION_LENGTH),
        "once": bool(raw.get("once")),
    }


def _node(raw: Any) -> Optional[dict[str, Any]]:
    if not isinstance(raw, dict):
        return None
    responses = [r for r in map(_response, raw.get("responses") or []) if r]
    return {
        "npc_text": _text(raw.get("npc_text") or raw.get("text"), MAX_PROMPT_LENGTH),
        "speaker": _text(raw.get("speaker"), MAX_LABEL_LENGTH) or None,
        "responses": responses[:MAX_DIALOG_OPTIONS],
    }


def normalize_tree(tree: Any) -> tuple[Optional[dict[str, Any]], str]:
    """Validates a dialogue tree: (normalized tree, "") or (None, reason)."""
    if not isinstance(tree, dict) or not isinstance(tree.get("nodes"), dict):
        return None, "the tree needs a 'nodes' dict."
    raw_nodes = list(tree["nodes"].items())
    if len(raw_nodes) > MAX_TREE_NODES:
        return None, f"at most {MAX_TREE_NODES} nodes are allowed."
    nodes = {_text(k, MAX_ID_LENGTH): n for k, n in ((k, _node(v)) for k, v in raw_nodes) if n}
    initial = _node_ref(tree.get("initial_node")) or next(iter(nodes), None)
    if initial not in nodes:
        return None, f"initial node '{initial}' does not exist."
    dangling = sorted(
        {r["next_node"] for n in nodes.values() for r in n["responses"]} - set(nodes) - {None}
    )
    if dangling:
        return None, f"responses point to unknown nodes: {', '.join(dangling)}."
    normalized = {
        "dialogue_id": _text(tree.get("dialogue_id"), MAX_ID_LENGTH) or None,
        "npc_id": _text(tree.get("npc_id"), MAX_ID_LENGTH) or None,
        "initial_node": initial,
        "nodes": nodes,
    }
    return normalized, ""


def _picked_once(path: list[dict[str, Any]], node_id: str, index: int) -> bool:
    return any(step.get("node") == node_id and step.get("response") == index for step in path)


def visible_responses(
    dialog: dict[str, Any], node_id: str, context: GameContext
) -> list[dict[str, Any]]:
    """The node's responses the player may pick now, with their position as ``index``."""
    # Lazy import: switch_service depends on the scripting context module.
    from backend.engine.interaction.switch_service import SwitchService

    path = dialog.get("path") or []
    visible: list[dict[str, Any]] = []
    for index, response in enumerate(dialog["tree"]["nodes"][node_id]["responses"]):
        if response["once"] and _picked_once(path, node_id, index):
            continue
        expr = response["condition"]
        if expr and not SwitchService.evaluate_gate_expression(expr, context)[0]:
            continue
        visible.append({"index": index, "label": response["text"]})
    return visible


def node_dialog(
    base: dict[str, Any], node_id: str, context: GameContext
) -> Optional[dict[str, Any]]:
    """The pending dialog showing ``node_id``; None when it offers no visible response."""
    dialog = {**base, "node": node_id, "id": uuid4().hex}
    options = visible_responses(dialog, node_id, context)
    if not options:
        return None
    node = base["tree"]["nodes"][node_id]
    dialog.update(
        prompt=node["npc_text"],
        speaker=node["speaker"] or base.get("speaker"),
        options=options,
    )
    return dialog


def speaker_name(tree: dict[str, Any], speaker: Optional[str], context: GameContext) -> str:
    """The dialog title: the given speaker, else the name of the tree's NPC."""
    if speaker:
        return _text(speaker, MAX_LABEL_LENGTH)
    npc_id = tree.get("npc_id")
    return context.npcs.get(npc_id).name if npc_id and context.npcs.exists(npc_id) else ""


def open_tree(
    context: GameContext,
    tree: Any,
    on_end: Any = None,
    on_action: Any = None,
    speaker: Optional[str] = None,
    start_node: Optional[str] = None,
) -> tuple[Optional[dict[str, Any]], str]:
    """Builds the pending dialog for a new conversation: (dialog, "") or (None, reason)."""
    normalized, problem = normalize_tree(tree)
    if normalized is None:
        return None, problem
    handlers = {"on_end": on_end, "on_action": on_action}
    names = {key: handler_name(value) if value else None for key, value in handlers.items()}
    invalid = [key for key, value in handlers.items() if value and names[key] is None]
    if invalid:
        return None, f"{', '.join(invalid)} must name a function."
    start = _node_ref(start_node) or normalized["initial_node"]
    if start not in normalized["nodes"]:
        return None, f"start node '{start}' does not exist."
    base = {
        "kind": TREE_KIND,
        "tree": normalized,
        "path": [],
        "handler": None,
        "end_handler": names["on_end"],
        "action_handler": names["on_action"],
        "speaker": speaker_name(normalized, speaker, context) or None,
        "narrate": False,
    }
    dialog = node_dialog(base, start, context)
    return (dialog, "") if dialog else (None, "the start node has no visible response.")


def is_tree(dialog: Optional[dict[str, Any]]) -> bool:
    return bool(dialog) and dialog.get("kind") == TREE_KIND  # type: ignore[union-attr]


def chosen_response(dialog: dict[str, Any], index: int) -> dict[str, Any]:
    return dialog["tree"]["nodes"][dialog["node"]]["responses"][index]


def record_step(dialog: dict[str, Any], index: int) -> list[dict[str, Any]]:
    """The conversation path including the response the player just picked."""
    response = chosen_response(dialog, index)
    step = {"node": dialog["node"], "response": index, "text": response["text"]}
    if response["action"]:
        step["action"] = response["action"]
    return [*(dialog.get("path") or []), step][-MAX_PATH_LENGTH:]
