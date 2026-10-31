"""Resolves one step of a nested NPC dialogue (``tw.dialog.tree``).

A step records the NPC's line in the chat, runs the picked response's ``script`` and its
``action`` (through the tree's ``on_action`` handler), then shows the response's next node.
When the conversation ends (``next_node`` is None, or the next node offers no visible
response) the ``on_end`` handler runs with the visited path. A script that opens another
dialog or ends the adventure stops the conversation without calling ``on_end``.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy.orm.attributes import flag_modified

from backend.engine.rules.rule_engine import GameOverError
from backend.engine.scripting.dialog import pending_dialog, store_pending_dialog
from backend.engine.scripting.dialog_tree import chosen_response, node_dialog, record_step
from backend.engine.scripting.runner import SCRIPT_ERROR_PREFIX

logger = logging.getLogger(__name__)


class DialogTreeStep:
    """Applies the player's answer in a tree dialog for a session."""

    def __init__(self, manager: Any):
        self.manager = manager
        self._ended = False

    async def save_npc_line(self, dialog: dict[str, Any]) -> str:
        """Writes the node's NPC line to the chat, so the story feed reads as a conversation."""
        text = str(dialog.get("prompt") or "").strip()
        if not text:
            return ""
        speaker = str(dialog.get("speaker") or "").strip()
        line = f'{speaker}: "{text}"' if speaker else text
        await self.manager._save_chat_message("assistant", line)
        return line

    async def run(self, dialog: dict[str, Any], option: dict[str, Any]) -> tuple[list[Any], bool]:
        """Runs the step; returns (messages, adventure_ended)."""
        response = chosen_response(dialog, option["index"])
        path = record_step(dialog, option["index"])
        choice = {**option, "dialog_id": dialog["id"], "node": dialog["node"]}
        choice["action"] = response["action"]
        scope = {"dialog_choice": choice, "dialog_path": path}
        try:
            messages = await self._run_response(dialog, response, scope)
            if self._ended or self._dialog_opened():
                return messages, False
            next_node = response["next_node"]
            if next_node and await self._show_node(dialog, next_node, path):
                return messages, False
            handler = dialog.get("end_handler")
            messages.extend(await self._run_handler(handler, "dialog_path", scope, "end"))
            return messages, False
        except GameOverError as goe:
            await self.manager._finalize_session("game_over", str(goe))
            return [], True

    async def _run_response(
        self, dialog: dict[str, Any], response: dict[str, Any], scope: dict[str, Any]
    ) -> list[Any]:
        messages = await self._run_code(response["script"], scope, "response")
        if response["action"] and not self._ended:
            handler = dialog.get("action_handler")
            arg = "dialog_choice['action']"
            messages.extend(await self._run_handler(handler, arg, scope, "action"))
        return messages

    async def _run_handler(
        self, handler: Optional[str], arg: str, scope: dict[str, Any], phase: str
    ) -> list[Any]:
        if not handler:
            return []
        definitions: dict[str, Any] = {}
        self.manager._get_script_runner().load_init_definitions(definitions)
        if not callable(definitions.get(handler)):
            return [await self._missing_note(handler, phase)]
        return await self._run_code(f"{handler}({arg})", scope, phase)

    async def _run_code(self, code: str, extra_scope: dict[str, Any], phase: str) -> list[Any]:
        if not code:
            return []
        context = await self.manager._build_script_context()
        scope = {**extra_scope, "tw": context, "game": context}
        self.manager._get_script_runner().execute_code(
            code, scope, script_id=f"dialog_tree_{phase}"
        )
        changeset = context.changeset
        self._ended = self._ended or changeset.game_completed or changeset.game_over
        return await self.manager._apply_script_changeset(changeset)

    async def _missing_note(self, handler: str, phase: str) -> str:
        logger.warning("[Dialog] Tree handler '%s' is not defined.", handler)
        # Shown even without debug mode: otherwise this part of the dialogue silently fails.
        note = (
            f"{SCRIPT_ERROR_PREFIX} in 'dialog_tree_{phase}': the handler '{handler}' is not "
            "defined in the adventure's init_script, so this part of the dialogue has no effect."
        )
        await self.manager._save_chat_message("system", note)
        return note

    def _dialog_opened(self) -> bool:
        return pending_dialog(self.manager.state.entity_states) is not None

    async def _show_node(self, dialog: dict[str, Any], node_id: str, path: list[dict]) -> bool:
        """Stores the next node as the pending dialog; False when it has no visible response."""
        # Guards see the state after the response's script ran.
        context = await self.manager._build_script_context()
        next_dialog = node_dialog({**dialog, "path": path}, node_id, context)
        if next_dialog is None:
            return False
        state = self.manager.state
        entity_states = dict(state.entity_states or {})
        store_pending_dialog(entity_states, next_dialog)
        state.entity_states = entity_states
        flag_modified(state, "entity_states")
        return True
