"""Script-driven choice dialogs (``tw.dialog``).

A script opens a dialog with ``tw.dialog.choose(prompt, options, on_choice=...)``. Scripts run
to completion inside one request, so the call does not block: it records a pending dialog in
the changeset, the engine stores it in the session state, and the client shows the options.
Once the player picks one, the choice endpoint runs the ``on_choice`` handler (a function from
the global init script) with the index of the chosen option.

Only scripts can open dialogs; the LLM never sees this API.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any, Optional
from uuid import uuid4

if TYPE_CHECKING:
    from backend.engine.scripting.context import GameContext, ScriptChangeset

logger = logging.getLogger(__name__)

# Session-state key (inside ``entity_states``) holding the dialog awaiting the player's choice.
PENDING_DIALOG_KEY = "__pending_dialog__"
MAX_DIALOG_OPTIONS = 8
MAX_LABEL_LENGTH = 200
MAX_PROMPT_LENGTH = 2000
_HANDLER_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


def handler_name(on_choice: Any) -> Optional[str]:
    """Returns the handler function name for a string or a script function, else None."""
    name = on_choice if isinstance(on_choice, str) else getattr(on_choice, "__name__", "")
    name = str(name or "").strip()
    return name if _HANDLER_NAME.match(name) else None


class DialogProxy:
    """Safe proxy exposed to scripts as ``tw.dialog``."""

    def __init__(self, changeset: ScriptChangeset, context: GameContext):
        self._changeset = changeset
        self._context = context

    def choose(
        self,
        prompt: str,
        options: list[Any],
        on_choice: Any,
        speaker: Optional[str] = None,
        narrate: bool = False,
    ) -> bool:
        """Opens a choice dialog; returns False when it could not be opened."""
        if self._changeset.pending_dialog is not None:
            self._context.debug("tw.dialog.choose ignored: another dialog is already open.")
            return False
        handler = handler_name(on_choice)
        if handler is None:
            self._context.debug("tw.dialog.choose ignored: on_choice must name a function.")
            return False
        visible = self._visible_options(options)
        if not visible:
            self._context.debug("tw.dialog.choose ignored: no visible options.")
            return False
        self._changeset.pending_dialog = {
            "id": uuid4().hex,
            "prompt": str(prompt or "").strip()[:MAX_PROMPT_LENGTH],
            "speaker": str(speaker or "").strip() or None,
            "handler": handler,
            "narrate": bool(narrate),
            "options": visible,
        }
        return True

    def ask(self, *args: Any, **kwargs: Any) -> bool:
        """Alias for choose()."""
        return self.choose(*args, **kwargs)

    def tree(
        self,
        tree: Any,
        on_end: Any = None,
        on_action: Any = None,
        speaker: Optional[str] = None,
        start_node: Optional[str] = None,
    ) -> bool:
        """Opens a nested NPC dialogue (see ``dialog_tree``); returns False when it could not."""
        # Lazy import: dialog_tree builds on this module's limits and helpers.
        from backend.engine.scripting.dialog_tree import open_tree

        if self._changeset.pending_dialog is not None:
            self._context.debug("tw.dialog.tree ignored: another dialog is already open.")
            return False
        dialog, problem = open_tree(self._context, tree, on_end, on_action, speaker, start_node)
        if dialog is None:
            self._context.debug(f"tw.dialog.tree ignored: {problem}")
            return False
        self._changeset.pending_dialog = dialog
        return True

    def _visible_options(self, options: Any) -> list[dict[str, Any]]:
        if not isinstance(options, (list, tuple)):
            return []
        if len(options) > MAX_DIALOG_OPTIONS:
            self._context.debug(f"tw.dialog.choose: only the first {MAX_DIALOG_OPTIONS} options.")
        visible: list[dict[str, Any]] = []
        for index, raw in enumerate(options[:MAX_DIALOG_OPTIONS]):
            label = _option_label(raw)
            if label and self._is_visible(raw):
                visible.append({"index": index, "label": label})
        return visible

    def _is_visible(self, raw: Any) -> bool:
        expr = str(raw.get("visible_if") or "").strip() if isinstance(raw, dict) else ""
        if not expr:
            return True
        # Lazy import: switch_service depends on the scripting context module.
        from backend.engine.interaction.switch_service import SwitchService

        passed, _detail = SwitchService.evaluate_gate_expression(expr, self._context)
        return passed


def _option_label(raw: Any) -> str:
    label = raw.get("label") if isinstance(raw, dict) else raw
    return str(label or "").strip()[:MAX_LABEL_LENGTH]


def pending_dialog(entity_states: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """Returns the dialog awaiting the player's choice, if any."""
    dialog = (entity_states or {}).get(PENDING_DIALOG_KEY)
    return dialog if isinstance(dialog, dict) and dialog.get("options") else None


def store_pending_dialog(entity_states: dict[str, Any], dialog: Optional[dict[str, Any]]) -> bool:
    """Stores ``dialog`` unless another one is still open (the first dialog wins)."""
    if not dialog:
        return False
    if pending_dialog(entity_states) is not None:
        logger.warning("[Dialog] Ignoring dialog '%s': another dialog is open.", dialog.get("id"))
        return False
    entity_states[PENDING_DIALOG_KEY] = dialog
    return True


def clear_pending_dialog(entity_states: dict[str, Any]) -> None:
    entity_states.pop(PENDING_DIALOG_KEY, None)


def find_option(dialog: dict[str, Any], index: int) -> Optional[dict[str, Any]]:
    """Returns the visible option with the given (author-defined) index."""
    return next((o for o in dialog.get("options") or [] if o.get("index") == index), None)


def client_dialog(dialog: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """The dialog as sent to the client: the handler name stays on the server."""
    if not dialog:
        return None
    return {
        "id": dialog.get("id"),
        "prompt": dialog.get("prompt") or "",
        "speaker": dialog.get("speaker"),
        "options": [{"index": o["index"], "label": o["label"]} for o in dialog["options"]],
    }
