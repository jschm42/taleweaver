from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from typing import TYPE_CHECKING, Any, AsyncGenerator, Awaitable, Callable

from fastapi import HTTPException
from sqlalchemy.orm.attributes import flag_modified

from backend.core.llm_router import GameMasterLLM
from backend.core.prompts import (
    FINAL_REPORT_COMPLETED_FALLBACK,
    FINAL_REPORT_COMPLETED_SYSTEM_PROMPT,
    FINAL_REPORT_GAMEOVER_FALLBACK,
    FINAL_REPORT_GAMEOVER_SYSTEM_PROMPT,
)
from backend.engine.adventure_generator_service import AdventureGeneratorService
from backend.engine.rule_engine import (
    AdventureGenerationRequest,
    ToolResults,
)

if TYPE_CHECKING:
    from backend.api.routes.adventures.gameplay_logic import GameTurnManager

logger = logging.getLogger(__name__)

AG_IMAGE_CONFIRMATION_STATE_KEY = "__ag_image_confirmation__"
AG_LAST_REQUEST_STATE_KEY = "__ag_last_generation_request__"
AG_LAST_ERROR_STATE_KEY = "__ag_last_generation_error__"


class TurnAdventureGenManager:
    """Handles adventure generator tools, image confirmations, retry detection, and terminal epilogues."""

    def __init__(self, manager: GameTurnManager) -> None:
        self.manager = manager

    @staticmethod
    def _normalize_target_token(token: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9_\-\s]", " ", token or "")
        return re.sub(r"\s+", " ", cleaned).strip().lower()

    @staticmethod
    def _parse_json_object(text: str) -> dict[str, Any] | None:
        raw = (text or "").strip()
        if not raw:
            return None
        try:
            val = json.loads(raw)
            return val if isinstance(val, dict) else None
        except Exception:
            match = re.search(r"\{[\s\S]*\}", raw)
            if not match:
                return None
            try:
                val = json.loads(match.group(0))
                return val if isinstance(val, dict) else None
            except Exception:
                return None

    def get_pending_ag_image_confirmation(self) -> dict[str, Any] | None:
        exit_states = dict(self.manager.state.exit_states or {})
        pending = exit_states.get(AG_IMAGE_CONFIRMATION_STATE_KEY)
        if not isinstance(pending, dict):
            return None
        if not isinstance(pending.get("request"), dict):
            return None
        return pending

    def set_pending_ag_image_confirmation(self, request: AdventureGenerationRequest) -> None:
        exit_states = dict(self.manager.state.exit_states or {})
        exit_states[AG_IMAGE_CONFIRMATION_STATE_KEY] = {
            "request_id": str(uuid.uuid4()),
            "request": request.model_dump(),
        }
        self.manager.state.exit_states = exit_states
        flag_modified(self.manager.state, "exit_states")

    def clear_pending_ag_image_confirmation(self) -> None:
        exit_states = dict(self.manager.state.exit_states or {})
        if AG_IMAGE_CONFIRMATION_STATE_KEY in exit_states:
            exit_states.pop(AG_IMAGE_CONFIRMATION_STATE_KEY, None)
            self.manager.state.exit_states = exit_states
            flag_modified(self.manager.state, "exit_states")

    async def classify_short_intent(self, user_msg: str, system_prompt: str, phase: str) -> dict[str, Any] | None:
        """Run a tiny intent classification call and parse a strict JSON object response."""
        text = (user_msg or "").strip()
        if not text:
            return None

        llm_settings = self.manager.user.llm_settings or {}
        small_model_provider = (
            llm_settings.get("small_model_provider")
            or llm_settings.get("complex_model_provider")
            or llm_settings.get("preferred_provider")
            or "openai"
        )
        small_model = llm_settings.get("small_model") or "gpt-4o-mini"

        try:
            llm = GameMasterLLM(self.manager.user, provider=small_model_provider, model_category="small")
            raw = await llm.aexecute_simple_task(
                system_prompt,
                text,
                small_model,
                adventure_id=self.manager.adventure.id,
                game_id=self.manager.game_id,
                operation="chat_turn",
                phase=phase,
            )
            parsed = self._parse_json_object(raw)
            return parsed if isinstance(parsed, dict) else None
        except Exception as exc:
            logger.debug("[Turn %s] Intent classifier skipped (%s): %s", self.manager.game_id, phase, exc)
            return None

    async def parse_ag_image_confirmation_decision(self, user_msg: str) -> str:
        text = (user_msg or "").strip().lower()
        if not text:
            return "unknown"

        intent_prompt = (
            "Classify the user's response to an image-mode confirmation question. "
            "Return ONLY strict JSON with schema: {\"decision\":\"with_images\"|\"without_images\"|\"cancel\"|\"unknown\"}."
        )
        parsed = await self.classify_short_intent(user_msg, intent_prompt, "ag_image_confirmation_intent")
        decision = str((parsed or {}).get("decision") or "").strip().lower()
        if decision in {"with_images", "without_images", "cancel", "unknown"}:
            return decision

        without_images_patterns = [
            r"\bohne\b",
            r"\bwithout\b",
            r"\bno images?\b",
            r"\bkeine bilder\b",
            r"\bohne bilder?\b",
        ]
        cancel_patterns = [
            r"\bcancel\b",
            r"\babbrechen\b",
            r"\bstop\b",
            r"\bstopp\b",
            r"^nein$",
            r"^no$",
        ]
        with_images_patterns = [
            r"\bja\b",
            r"\byes\b",
            r"\bwith images?\b",
            r"\bmit bilder?\b",
            r"\bmit bild\b",
        ]

        if any(re.search(p, text) for p in without_images_patterns):
            return "without_images"
        if any(re.search(p, text) for p in cancel_patterns):
            return "cancel"
        if any(re.search(p, text) for p in with_images_patterns):
            return "with_images"
        return "unknown"

    async def is_generation_retry_request(self, user_msg: str) -> bool:
        text = (user_msg or "").strip().lower()
        if not text:
            return False

        intent_prompt = (
            "Determine if the user asks to retry the last generation attempt. "
            "Return ONLY strict JSON with schema: {\"retry\": true|false}."
        )
        parsed = await self.classify_short_intent(user_msg, intent_prompt, "ag_retry_intent")
        retry_val = (parsed or {}).get("retry")
        if isinstance(retry_val, bool):
            return retry_val

        retry_patterns = (
            r"\bnochmal\b",
            r"\bnoch einmal\b",
            r"\berneut\b",
            r"\bwieder\b",
            r"\bagain\b",
            r"\bretry\b",
            r"\btry again\b",
            r"\bplease retry\b",
        )
        return any(re.search(p, text) for p in retry_patterns)

    @staticmethod
    def contains_transition_movement_cue(text: str) -> bool:
        lowered = (text or "").strip().lower()
        if not lowered:
            return False

        movement_patterns = (
            r"\b(go|going|move|moving|walk|walking|run|running|head|enter|proceed|travel|leave)\b",
            r"\b(go to|walk to|move to|head to|enter the|step into)\b",
            r"\b(gehe|geh|laufe|renne|betrete|bewege|reise|verlasse)\b",
            r"\b(gehe in|gehe zu|betrete den|betrete die|ins|in den|in die)\b",
        )
        return any(re.search(p, lowered) for p in movement_patterns)

    def message_mentions_transition_target(
        self,
        *,
        user_msg: str,
        target_scene_id: str,
        exit_label: str | None,
        reduced_scenes: list[dict],
        reduced_exits: list[dict],
    ) -> bool:
        lowered = (user_msg or "").strip().lower()
        if not lowered:
            return False

        normalized_message = self._normalize_target_token(lowered)
        if not normalized_message:
            return False

        aliases: set[str] = set()

        def _add_alias(raw: Any) -> None:
            token = self._normalize_target_token(str(raw or ""))
            if token and len(token) >= 3:
                aliases.add(token)

        target_scene_id = str(target_scene_id or "").strip()
        _add_alias(target_scene_id)
        _add_alias(exit_label)

        for scene in reduced_scenes or []:
            if str(scene.get("id") or "").strip() == target_scene_id:
                _add_alias(scene.get("label"))
                break

        for ex in reduced_exits or []:
            if str(ex.get("to_scene_id") or "").strip() == target_scene_id:
                _add_alias(ex.get("label"))

        if any(alias in normalized_message for alias in aliases):
            return True

        # With exactly one open destination, allow directional movement phrasing without explicit label mention.
        open_destinations = {
            str(ex.get("to_scene_id") or "").strip()
            for ex in (reduced_exits or [])
            if not bool(ex.get("is_locked")) and str(ex.get("to_scene_id") or "").strip()
        }
        directional_patterns = (
            r"\b(into|inside|outside|out|downstairs|upstairs|north|south|east|west|left|right)\b",
            r"\b(rein|hinein|hinaus|raus|runter|hinunter|hoch|hinauf)\b",
            r"\bnach\s+(links|rechts|oben|unten)\b",
        )
        if len(open_destinations) == 1 and target_scene_id in open_destinations:
            return any(re.search(p, lowered) for p in directional_patterns)

        return False

    async def is_explicit_scene_transition_request(self, user_msg: str) -> bool:
        text = (user_msg or "").strip().lower()
        if not text:
            return False

        intent_prompt = (
            "Decide whether the user is explicitly requesting immediate physical movement to another scene now "
            "(not hypothetical/planning talk). "
            "Return ONLY strict JSON with schema: {\"explicit_transition\": true|false}."
        )
        parsed = await self.classify_short_intent(user_msg, intent_prompt, "scene_transition_intent")
        transition_val = (parsed or {}).get("explicit_transition")
        if isinstance(transition_val, bool):
            return transition_val and self.contains_transition_movement_cue(text)

        # Ignore hypothetical/planning phrasing that should not immediately move the player.
        hypothetical_patterns = (
            r"\bif\b",
            r"\bwould\b",
            r"\bcould\b",
            r"\bmight\b",
            r"\bmaybe\b",
            r"\bplan\b",
            r"\bint(en)?d\b",
            r"\bwenn\b",
            r"\bfalls\b",
            r"\bvielleicht\b",
            r"\bwürde\b",
            r"\bkönnte\b",
        )
        if any(re.search(p, text) for p in hypothetical_patterns):
            return False

        return self.contains_transition_movement_cue(text)

    def set_last_ag_generation_request(self, request: AdventureGenerationRequest) -> None:
        exit_states = dict(self.manager.state.exit_states or {})
        exit_states[AG_LAST_REQUEST_STATE_KEY] = request.model_dump()
        self.manager.state.exit_states = exit_states
        flag_modified(self.manager.state, "exit_states")

    def get_last_ag_generation_request(self) -> AdventureGenerationRequest | None:
        exit_states = dict(self.manager.state.exit_states or {})
        raw = exit_states.get(AG_LAST_REQUEST_STATE_KEY)
        if not isinstance(raw, dict):
            return None
        try:
            return AdventureGenerationRequest.model_validate(raw)
        except Exception:
            return None

    def set_last_ag_generation_error(self, error_type: str | None) -> None:
        exit_states = dict(self.manager.state.exit_states or {})
        if error_type:
            exit_states[AG_LAST_ERROR_STATE_KEY] = error_type
        else:
            exit_states.pop(AG_LAST_ERROR_STATE_KEY, None)
        self.manager.state.exit_states = exit_states
        flag_modified(self.manager.state, "exit_states")

    def get_last_ag_generation_error(self) -> str | None:
        exit_states = dict(self.manager.state.exit_states or {})
        value = exit_states.get(AG_LAST_ERROR_STATE_KEY)
        return value if isinstance(value, str) and value else None

    async def stream_adventure_generator_tools(self, event: Any) -> AsyncGenerator[str, None]:
        progress_queue: asyncio.Queue[str] = asyncio.Queue()

        async def _stream_progress_message(message: str) -> None:
            await progress_queue.put(message)

        tool_task = asyncio.create_task(
            self.apply_adventure_generator_tools(
                event,
                stream_callback=_stream_progress_message,
            )
        )

        while True:
            try:
                msg = await asyncio.wait_for(progress_queue.get(), timeout=0.1)
                yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"
            except asyncio.TimeoutError:
                if tool_task.done():
                    break

        await tool_task
        while not progress_queue.empty():
            msg = progress_queue.get_nowait()
            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"

    async def apply_adventure_generator_tools(
        self,
        event: Any,
        stream_callback: Callable[[str], Awaitable[None] | None] = None,
    ) -> None:
        """Executes adventure-generator tool requests from a structured event/intent model."""
        if not self.manager.adventure.is_adventure_generator:
            return

        if event.request_available_image_styles:
            styles = await AdventureGeneratorService.get_available_image_styles(self.manager.user)
            if not event.tool_results:
                event.tool_results = ToolResults()
            event.tool_results.available_image_styles = styles

            msg = f"SYSTEM: Available Image Styles: {', '.join(styles)}"
            await self.manager._emit_system_message(msg, stream_callback=stream_callback)

        if event.request_available_tones:
            tones = await AdventureGeneratorService.get_available_tones(self.manager.user)
            if not event.tool_results:
                event.tool_results = ToolResults()
            event.tool_results.available_tones = tones

            msg = f"SYSTEM: Available Tones: {', '.join(tones)}"
            await self.manager._emit_system_message(msg, stream_callback=stream_callback)

        if event.requested_adventure_generation:
            self.set_last_ag_generation_request(event.requested_adventure_generation)

            async def _post_generation_system_message(status: str) -> None:
                msg = f"SYSTEM: Adventure Generator: {status}"
                await self.manager._emit_system_message(msg, stream_callback=stream_callback)

            try:
                await _post_generation_system_message(
                    f"Preparing generation for '{event.requested_adventure_generation.title}'..."
                )

                new_adv_id = await AdventureGeneratorService.generate_adventure(
                    self.manager.db,
                    self.manager.user,
                    event.requested_adventure_generation,
                    progress_callback=_post_generation_system_message,
                )
                if not event.tool_results:
                    event.tool_results = ToolResults()
                event.tool_results.generation_success = True
                event.tool_results.new_adventure_id = new_adv_id
                self.set_last_ag_generation_error(None)

                await _post_generation_system_message("Generation finished successfully.")

                msg = f"SYSTEM: Adventure '{event.requested_adventure_generation.title}' generated successfully and added to library (ID: {new_adv_id})."
                await self.manager._emit_system_message(msg, stream_callback=stream_callback)
            except Exception as e:
                logger.exception("Adventure generation tool failed")
                if not event.tool_results:
                    event.tool_results = ToolResults()
                from backend.api.routes.adventures.gameplay_logic import (
                    _friendly_llm_error_message,
                    _llm_error_type,
                )
                user_safe_error = _friendly_llm_error_message(e)
                event.tool_results.generation_success = False
                event.tool_results.generation_error = user_safe_error or "Adventure generation failed."
                self.set_last_ag_generation_error(_llm_error_type(e))

                await _post_generation_system_message("Generation aborted due to an error.")

                if user_safe_error:
                    msg = f"SYSTEM: {user_safe_error}"
                else:
                    msg = "SYSTEM: Adventure generation failed due to an unexpected error."
                await self.manager._emit_system_message(msg, stream_callback=stream_callback)

    async def generate_terminal_epilogue_text(self, language: str | None = None) -> str:
        status = self.manager.state.session.status if self.manager.state and self.manager.state.session else None
        status_note = self.manager.state.session.status_note if self.manager.state and self.manager.state.session else None

        quests = list(self.manager.state.quests or []) if self.manager.state else []
        main_quests = [q for q in quests if q.get("is_main")]
        completed_main = [q for q in main_quests if q.get("status") == "completed"]
        side_quests = [q for q in quests if not q.get("is_main")]
        completed_side = [q for q in side_quests if q.get("status") == "completed"]

        adventure_awards = list(self.manager.adventure.awards or []) if self.manager.adventure else []
        earned_awards = list(self.manager.user.earned_awards or []) if self.manager.user else []
        earned_for_adventure = [
            ea
            for ea in earned_awards
            if (ea.get("template_id") == self.manager.adventure.id or ea.get("adventure_id") == self.manager.adventure.id)
        ] if self.manager.adventure else []

        report_payload = {
            "session_id": self.manager.game_id,
            "adventure_title": self.manager.adventure.title if self.manager.adventure else "Adventure",
            "status": status,
            "status_note": status_note,
            "quests": {
                "main_completed": len(completed_main),
                "main_total": len(main_quests),
                "side_completed": len(completed_side),
                "side_total": len(side_quests),
            },
            "awards": {
                "earned": len(earned_for_adventure),
                "total": len(adventure_awards),
            },
            "exp": self.manager.avatar.exp if self.manager.avatar else 0,
            "in_game_time_minutes": self.manager.state.in_game_time if self.manager.state else 0,
        }

        llm_settings = self.manager.user.llm_settings or {}
        model_provider = (
            llm_settings.get("complex_model_provider")
            or llm_settings.get("small_model_provider")
            or llm_settings.get("preferred_provider")
            or "openai"
        )
        model_name = llm_settings.get("complex_model") or llm_settings.get("small_model") or "gpt-4o"

        if status == "completed":
            system_prompt = FINAL_REPORT_COMPLETED_SYSTEM_PROMPT
            fallback = FINAL_REPORT_COMPLETED_FALLBACK
        else:
            system_prompt = FINAL_REPORT_GAMEOVER_SYSTEM_PROMPT
            fallback = FINAL_REPORT_GAMEOVER_FALLBACK

        if language:
            system_prompt += f" Respond only in {language.upper()}."

        user_prompt = "Create the final narrative from this session report JSON:\n" + json.dumps(report_payload)

        try:
            llm = GameMasterLLM(self.manager.user, provider=model_provider, model_category="complex")
            stream = await llm.stream_simple_task(system_prompt, user_prompt, model_name)
            content = ""
            async for chunk in stream:
                content += chunk.choices[0].delta.content or ""
            content = content.strip()
            return content or fallback
        except Exception:
            return fallback

    async def create_terminal_epilogue(self, language: str | None = None) -> dict[str, Any]:
        if not await self.manager.initialize():
            raise HTTPException(status_code=404, detail="Game session not found.")

        if not self.manager.state or not self.manager.state.session:
            raise HTTPException(status_code=404, detail="Session state not found.")

        if self.manager.state.session.status not in {"completed", "game_over"}:
            raise HTTPException(
                status_code=400,
                detail="Terminal epilogue is only available for completed or game-over sessions.",
            )

        if not self.manager._is_terminal_epilogue_pending():
            return {
                "content": None,
                **self.manager._build_terminal_flags_payload(),
            }

        epilogue_text = await self.manager._generate_terminal_epilogue_text(language=language)
        if epilogue_text:
            await self.manager._save_chat_message("assistant", epilogue_text)

        self.manager._set_terminal_epilogue_sent(self.manager.state.session.status, sent=True)
        await self.manager.db.commit()

        return {
            "content": epilogue_text,
            **self.manager._build_terminal_flags_payload(),
        }
