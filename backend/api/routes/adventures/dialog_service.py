"""Resolves the player's answer to a script-opened choice dialog (``tw.dialog.choose``).

The pending dialog lives in ``entity_states``. Resolving it records the choice in the chat
(so the GM keeps continuity), runs the ``on_choice`` handler from the global init script with
the chosen option index, applies the resulting changeset and, when the dialog asked for it,
lets the small model narrate the outcome. The handler may open a follow-up dialog.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.api.routes.adventures.out_of_turn_progress import apply_out_of_turn_progress
from backend.api.routes.adventures.post_turn_hooks import PostTurnHooks
from backend.core.llm_router import GameMasterLLM
from backend.engine.rules.rule_engine import GameOverError
from backend.engine.scripting.dialog import (
    clear_pending_dialog,
    find_option,
    pending_dialog,
)
from backend.engine.scripting.gm_directions import pending_gm_directions, take_gm_directions
from backend.engine.scripting.runner import SCRIPT_ERROR_PREFIX
from backend.models.chat import ChatMessage
from backend.models.world_entity import WorldEntity

logger = logging.getLogger(__name__)

CHOICE_MESSAGE_PREFIX = "[Choice]"
_NARRATION_HISTORY_LIMIT = 6
_NARRATION_SYSTEM_PROMPT = (
    "You are the Game Master of a text adventure. The player just answered a choice dialog. "
    "Narrate the immediate outcome in 2-4 vivid sentences, in second person. The listed outcome "
    "facts were decided by the game engine and are binding: stay consistent with them and never "
    "invent additional state changes, items, damage or rewards. 'npcs_present' describes the "
    "current personality and goal of the NPCs in the scene: let them shape how those NPCs react. "
    "Work any 'author_directions' naturally into the narration; a direction that makes an NPC "
    "speak becomes its own dialogue line, in addition to the 2-4 sentences. "
    "Dialogue format (mandatory): every spoken line starts on a NEW line as "
    'Character Name: "Dialogue" (or Character Name: [tag] "Dialogue" with an emotion tag), '
    "separated from the prose by a blank line; never quote speech inside a prose sentence. "
    "Use colons only for this speaker attribution. No JSON, lists or headings."
)


class DialogChoiceResolver:
    """Applies one dialog choice for a session."""

    def __init__(self, manager: GameTurnManager):
        self.manager = manager

    @classmethod
    async def create(cls, db: Any, game_id: str, user: Any) -> DialogChoiceResolver:
        manager = GameTurnManager(db, game_id, user)
        if not await manager.initialize():
            raise HTTPException(status_code=404, detail="Session not found.")
        return cls(manager)

    async def resolve(self, dialog_id: str, index: int, language: Optional[str]) -> dict[str, Any]:
        state = self.manager.state
        if state.session and state.session.status in {"completed", "game_over"}:
            raise HTTPException(status_code=409, detail="The adventure has already ended.")
        dialog = pending_dialog(state.entity_states)
        if dialog is None or dialog.get("id") != dialog_id:
            raise HTTPException(status_code=409, detail="This choice is no longer available.")
        option = find_option(dialog, index)
        if option is None:
            raise HTTPException(status_code=400, detail="Unknown choice.")

        self._clear_dialog()
        await self.manager._save_chat_message("user", f"{CHOICE_MESSAGE_PREFIX} {option['label']}")
        messages, ended = await self._run_handler(dialog, option)
        if not ended:
            ended = await self._apply_follow_ups(messages)
        if ended:
            messages.extend(await self._announce_ending())
        elif dialog.get("narrate"):
            narration = await self._narrate(dialog, option, messages, language)
            if narration:
                # The directions were handed to this narration; on failure they wait for the next.
                take_gm_directions(self.manager.state)
                await self.manager._save_chat_message("assistant", narration)
                messages.append(narration)
        await self.manager.db.commit()
        return {"status": "ok", "messages": [str(m) for m in messages]}

    async def _apply_follow_ups(self, messages: list[Any]) -> bool:
        """What a turn would do after state changes; returns True when the adventure ended."""
        messages.extend(await PostTurnHooks(self.manager).run_checks())
        progress, terminal_status = await apply_out_of_turn_progress(self.manager)
        messages.extend(progress)
        return terminal_status is not None

    async def _announce_ending(self) -> list[str]:
        """Tells the outcome in the story; the end screen and final report follow on the client."""
        session = self.manager.state.session
        note = str(getattr(session, "status_note", "") or "").strip()
        if not note:
            return []
        await self.manager._save_chat_message("assistant", note)
        return [note]

    def _clear_dialog(self) -> None:
        state = self.manager.state
        entity_states = dict(state.entity_states or {})
        clear_pending_dialog(entity_states)
        state.entity_states = entity_states
        flag_modified(state, "entity_states")

    async def _run_handler(
        self, dialog: dict[str, Any], option: dict[str, Any]
    ) -> tuple[list[Any], bool]:
        """Runs the on_choice handler; returns (messages, adventure_ended)."""
        handler = str(dialog.get("handler") or "")
        runner = self.manager._get_script_runner()
        definitions: dict[str, Any] = {}
        runner.load_init_definitions(definitions)
        if not callable(definitions.get(handler)):
            logger.warning("[Dialog] Handler '%s' is not defined in the init script.", handler)
            # Shown even without debug mode: otherwise the choice silently does nothing.
            note = (
                f"{SCRIPT_ERROR_PREFIX} in 'dialog_{handler}': the choice handler '{handler}' "
                "is not defined in the adventure's init_script, so this choice has no effect."
            )
            await self.manager._save_chat_message("system", note)
            return [note], False

        context = await self.manager._build_script_context()
        choice = {"index": option["index"], "label": option["label"], "dialog_id": dialog["id"]}
        scope = {"tw": context, "game": context, "dialog_choice": choice}
        runner.execute_code(
            f"{handler}(dialog_choice['index'])", scope, script_id=f"dialog_{handler}"
        )
        try:
            return await self.manager._apply_script_changeset(context.changeset), False
        except GameOverError as goe:
            await self.manager._finalize_session("game_over", str(goe))
            return [], True

    async def _narrate(
        self,
        dialog: dict[str, Any],
        option: dict[str, Any],
        outcome: list[Any],
        language: Optional[str],
    ) -> str:
        user = self.manager.user
        settings = user.llm_settings or {}
        provider = (
            settings.get("small_model_provider")
            or settings.get("complex_model_provider")
            or settings.get("preferred_provider")
            or "openai"
        )
        model = settings.get("small_model") or "gpt-4o-mini"
        system_prompt = _NARRATION_SYSTEM_PROMPT
        if language:
            system_prompt += f" Respond only in {language}."
        payload = {
            "recent_story": await self._recent_history(),
            "speaker": dialog.get("speaker"),
            "question": dialog.get("prompt"),
            "player_choice": option["label"],
            "outcome_facts": [str(m) for m in outcome if not str(m).startswith("[DEBUG")],
            "npcs_present": await self._scene_npc_personas(),
            "author_directions": pending_gm_directions(self.manager.state.entity_states),
        }
        try:
            llm = GameMasterLLM(user, provider=provider, model_category="small")
            text = await llm.aexecute_simple_task(
                system_prompt,
                json.dumps(payload, ensure_ascii=False),
                model,
                adventure_id=self.manager.state.template_id,
                game_id=self.manager.state.session_id,
                operation="dialog_choice_narration",
                phase="narration",
            )
        except Exception:
            logger.exception("[Dialog] Narration failed for session %s", self.manager.game_id)
            return ""
        return str(text or "").strip()

    async def _scene_npc_personas(self) -> list[dict[str, str]]:
        """Visible NPCs in the player's scene with their (possibly script-changed) persona."""
        state = self.manager.state
        res = await self.manager.db.execute(
            select(WorldEntity).where(
                WorldEntity.session_id == state.session_id,
                WorldEntity.entity_type == "NPC",
                WorldEntity.current_scene_id == state.current_scene_id,
                WorldEntity.is_hidden.is_(False),
            )
        )
        return [
            {"name": npc.name, "character": npc.character or "", "goal": npc.goal or ""}
            for npc in res.scalars().all()
            if npc.character or npc.goal
        ]

    async def _recent_history(self) -> list[dict[str, str]]:
        res = await self.manager.db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == self.manager.state.session_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(_NARRATION_HISTORY_LIMIT)
        )
        rows = list(reversed(res.scalars().all()))
        return [{"role": r.role, "content": r.content} for r in rows if r.role != "system"]
