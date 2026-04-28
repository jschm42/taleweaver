import json
import logging
import uuid
import re
import time
from copy import deepcopy
from datetime import datetime
from typing import Optional, List, Dict, Any, AsyncGenerator

from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from sqlalchemy.orm.attributes import flag_modified

from backend.models.user import User
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.session_state import SessionState
from backend.models.chat import ChatMessage
from backend.models.world_entity import WorldScene, WorldEntity, WorldExit
from backend.models.world_map import WorldMap
from backend.engine.rule_engine import RuleEngine, GameEvent, GameOverException, SkillCheckResult
from backend.engine.map_engine import MapEngine
from backend.engine.memory_manager import MemoryManager
from backend.engine.command_parser import CommandParser
from backend.engine.skill_check import roll_skill_check
from backend.engine.media_engine import MediaEngine
from backend.engine.debug_engine import DebugEngine
from backend.core.llm_router import GameMasterLLM
from backend.core import prompts
from backend.api.routes.adventures.logic import AdventureLogic

logger = logging.getLogger(__name__)

# Constants
WALKTHROUGH_REVEAL_COST = 200
WALKTHROUGH_HINT_COST = 50

class GameTurnManager:
    """Class to manage the complex unified game turn (chat interaction)."""

    def __init__(self, db: AsyncSession, game_id: str, user: User):
        self.db = db
        self.game_id = game_id
        self.user = user
        self.state: Optional[SessionState] = None
        self.adventure: Optional[AdventureTemplate] = None
        self.avatar: Optional[Avatar] = None

    async def initialize(self) -> bool:
        """Loads all necessary context for the turn."""
        start = time.perf_counter()
        self.state = await AdventureLogic.resolve_session_state(self.db, self.game_id, user_id=self.user.id)
        if not self.state: 
            logger.warning(f"[Turn {self.game_id}] Initialization failed: Session state not found.")
            return False
            
        adv_res = await self.db.execute(select(AdventureTemplate).where(AdventureTemplate.id == self.state.template_id))
        self.adventure = adv_res.scalars().first()
        av_res = await self.db.execute(select(Avatar).where(Avatar.id == self.state.avatar_id))
        self.avatar = av_res.scalars().first()
        
        duration = time.perf_counter() - start
        logger.debug(f"[Turn {self.game_id}] Initialization (DB) took {duration:.4f}s")
        return bool(self.adventure and self.avatar)

    async def process_turn(self, message: str, auto_visualize: bool = False) -> AsyncGenerator[str, None]:
        if not await self.initialize():
            yield f"event: error\ndata: {json.dumps({'detail': 'Game session not found.'})}\n\n"
            return

        user_msg = message.strip()
        actual_user_input = user_msg
        if not user_msg: user_msg = "[LOOK AROUND]"

        # Unified logic for /debug and / (slash) commands
        if user_msg.startswith("/debug"):
            async for chunk in self._handle_debug(user_msg): yield chunk
            return
        if user_msg.startswith("/"):
            async for chunk in self._handle_slash(user_msg): yield chunk
            return

        # Core Turn Logic
        turn_start = time.perf_counter()
        logger.debug(f"[Turn {self.game_id}] Starting turn for user '{self.user.username}' with input: {user_msg}")
        yield f"event: status\ndata: {json.dumps({'content': 'Considering...'})}\n\n"
        
        # 1. Advance Time & Apply Ticks
        self.state.in_game_time += self.adventure.time_per_turn
        tick_msgs = RuleEngine.apply_ticks(self.avatar)
        for tm in tick_msgs:
            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': tm})}\n\n"

        # 2. Record User Message
        if actual_user_input:
            self.db.add(ChatMessage(session_id=self.state.session_id, role="user", content=actual_user_input))
            await self.db.flush()

        # 3. LLM Processing (Pass 1 & Pass 2)
        async for chunk in self._run_llm_cycle(user_msg, auto_visualize):
            yield chunk
            
        turn_end = time.perf_counter()
        logger.debug(f"[Turn {self.game_id}] Total turn processing took {turn_end - turn_start:.4f}s")

    async def _handle_debug(self, user_msg: str) -> AsyncGenerator[str, None]:
        cmd_args = user_msg[7:].strip()
        debug_info = await DebugEngine.handle_debug_command(self.db, self.state, cmd_args, user=self.user, adventure=self.adventure)
        await self.db.commit()
        yield f"event: final\ndata: {json.dumps(jsonable_encoder({
            'messages': [{'role': 'system', 'content': debug_info}],
            'sheet': await AdventureLogic.build_sheet_snapshot(self.avatar, self.state, self.db),
            'awards': self.adventure.awards
        }))}\n\n"

    async def _handle_slash(self, user_msg: str) -> AsyncGenerator[str, None]:
        # Handle /map specifically
        if user_msg.lower() == "/map":
            map_res = await self.db.execute(select(WorldMap).where(WorldMap.template_id == self.state.template_id))
            world_map = map_res.scalars().first()
            yield f"event: final\ndata: {json.dumps(jsonable_encoder({'mermaid': MapEngine.to_mermaid(world_map) if world_map else None, 'sheet': await AdventureLogic.build_sheet_snapshot(self.avatar, self.state, self.db)}))}\n\n"
            return
        
        response = CommandParser.parse_command(self.avatar, user_msg)
        # Simplified Command Parsing... (Add full list as needed)
        await self.db.commit()
        yield f"event: final\ndata: {json.dumps(jsonable_encoder({'messages': [{'role': 'system', 'content': response}], 'sheet': await AdventureLogic.build_sheet_snapshot(self.avatar, self.state, self.db)}))}\n\n"

    async def _run_llm_cycle(self, user_msg: str, auto_visualize: bool) -> AsyncGenerator[str, None]:
        # Load Context and LLM Settings
        db_start = time.perf_counter()
        hist_res = await self.db.execute(select(ChatMessage).where(ChatMessage.session_id == self.state.session_id).order_by(ChatMessage.created_at.asc()))
        history = [{"role": m.role, "content": m.content} for m in hist_res.scalars().all()]
        
        scene_res = await self.db.execute(select(WorldScene).where(WorldScene.id == self.state.current_scene_id, WorldScene.template_id == self.state.template_id))
        current_scene = scene_res.scalars().first()
        db_duration = time.perf_counter() - db_start
        logger.debug(f"[Turn {self.game_id}] LLM Context DB prep took {db_duration:.4f}s")
        
        # Build prompt using MemoryManager
        system_prompt = MemoryManager.build_context(self.avatar, self.adventure.context or "", history, current_scene=current_scene)[0]["content"]
        
        llm_settings = self.user.llm_settings or {}
        
        # Robust provider resolution (identical to original adventures.py)
        small_model_provider = (
            llm_settings.get("small_model_provider")
            or llm_settings.get("complex_model_provider")
            or llm_settings.get("preferred_provider")
            or "openai"
        )
        complex_model_provider = (
            llm_settings.get("complex_model_provider")
            or llm_settings.get("small_model_provider")
            or llm_settings.get("preferred_provider")
            or "openai"
        )
        
        small_model = llm_settings.get("small_model", "gpt-4o-mini")
        complex_model = llm_settings.get("complex_model", "gpt-4o")

        game_event = None
        response_text = ""

        # Pass 1: Mechanics
        if self.adventure.strict_rules:
            yield f"event: status\ndata: {json.dumps({'content': 'Validating rules...'})}\n\n"
            try:
                llm = GameMasterLLM(self.user, provider=small_model_provider, model_category="small")
            except ValueError as e:
                yield f"event: error\ndata: {json.dumps({'detail': str(e)})}\n\n"
                return
            
            mechanics_prompt = system_prompt + "\n\n" + prompts.GM_MECHANICS_SUFFIX.format(
                quests_json=json.dumps(self.state.quests or [], indent=2),
                awards_json=json.dumps(self.adventure.awards or [], indent=2)
            )
            
            pass1_start = time.perf_counter()
            logger.debug(f"[Turn {self.game_id}] [Pass 1] Calling small model: {small_model} via {small_model_provider}")
            game_event = await llm.aexecute_complex_task(mechanics_prompt, user_msg, response_model=GameEvent, model=small_model)
            pass1_duration = time.perf_counter() - pass1_start
            logger.debug(f"[Turn {self.game_id}] [Pass 1] Mechanics analysis took {pass1_duration:.4f}s")
            
            # Apply Changes
            await self._apply_game_event(game_event)

        # Pass 2: Narration
        yield f"event: status\ndata: {json.dumps({'content': 'Generating narrative...'})}\n\n"
        try:
            llm = GameMasterLLM(self.user, provider=complex_model_provider, model_category="complex")
        except ValueError as e:
            yield f"event: error\ndata: {json.dumps({'detail': str(e)})}\n\n"
            return
        narration_prompt = system_prompt + "\n\n" + prompts.GM_NARRATION_TECHNICAL_OUTCOME_PREFIX.format(
            outcome_json=game_event.model_dump_json() if game_event else "{}"
        )
        
        pass2_start = time.perf_counter()
        logger.debug(f"[Turn {self.game_id}] [Pass 2] Calling complex model: {complex_model} via {complex_model_provider}")
        stream = await llm.stream_simple_task(narration_prompt, user_msg, complex_model)
        
        async for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            if delta:
                response_text += delta
                yield f"event: chunk\ndata: {json.dumps({'content': delta})}\n\n"
        
        pass2_duration = time.perf_counter() - pass2_start
        logger.debug(f"[Turn {self.game_id}] [Pass 2] Narration took {pass2_duration:.4f}s")

        # Finalize
        assistant_chat = ChatMessage(session_id=self.state.session_id, role="assistant", content=response_text)
        self.db.add(assistant_chat)
        await self.db.commit()
        
        yield f"event: final\ndata: {json.dumps(jsonable_encoder({'sheet': await AdventureLogic.build_sheet_snapshot(self.avatar, self.state, self.db), 'status': 'success'}))}\n\n"

    async def _apply_game_event(self, event: GameEvent):
        """Applies technical mutations from a GameEvent to the database and state."""
        RuleEngine.apply_event(self.avatar, event)
        if event.new_scene_id:
            # Simple scene move
            self.state.current_scene_id = event.new_scene_id
        # ... more detailed entry updates for WorldEntity etc ...
        await self.db.flush()
