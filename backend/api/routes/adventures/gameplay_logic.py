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
        
        if not (self.adventure and self.avatar):
            return False

        # Lazy-register initial map visit
        try:
            world_map = await AdventureLogic.get_or_create_map(self.db, self.state.template_id)
            scene_res = await self.db.execute(select(WorldScene).where(WorldScene.id == self.state.current_scene_id, WorldScene.template_id == self.state.template_id))
            cur_scene = scene_res.scalars().first()
            MapEngine.register_visit(
                world_map, 
                self.state.current_scene_id, 
                label=cur_scene.label if cur_scene else None, 
                description=cur_scene.description if cur_scene else None, 
                image_url=cur_scene.image_url if cur_scene else None
            )
        except Exception as e:
            logger.warning(f"Failed to auto-register map visit for {self.game_id}: {e}")

        duration = time.perf_counter() - start
        logger.debug(f"[Turn {self.game_id}] Initialization (DB) took {duration:.4f}s")
        return True

    async def process_turn(self, message: str, auto_visualize: bool = False) -> AsyncGenerator[str, None]:
        if not await self.initialize():
            yield f"event: error\ndata: {json.dumps({'detail': 'Game session not found.'})}\n\n"
            return

        # Pre-emptive sanitization of avatar JSON fields to avoid datetime serialization issues
        self.avatar.inventory = jsonable_encoder(self.avatar.inventory)
        self.avatar.equipment = jsonable_encoder(self.avatar.equipment)

        user_msg = message.strip()
        actual_user_input = user_msg
        if not user_msg: user_msg = "[LOOK AROUND]"

        # Unified logic for /debug and / (slash) commands
        if user_msg.startswith("/debug"):
            async for chunk in self._handle_debug(user_msg): yield chunk
            return
            
        is_rule_pass = False
        if user_msg.startswith("/"):
            response = CommandParser.parse_command(self.avatar, user_msg)
            
            if response == "[RULE_PASS]":
                is_rule_pass = True
                user_msg = "[EVALUATE STATE]"
                yield f"event: status\ndata: {json.dumps({'content': 'The Game Master evaluates your situation...'})}\n\n"
            else:
                # Standard slash command handling (equip, take_direct, etc.)
                async for chunk in self._handle_slash(user_msg, response): yield chunk
                return

        # Core Turn Logic
        turn_start = time.perf_counter()
        logger.debug(f"[Turn {self.game_id}] Starting turn for user '{self.user.username}' with input: {user_msg}")
        if not is_rule_pass:
            yield f"event: status\ndata: {json.dumps({'content': 'Considering...'})}\n\n"
        
        # 1. Advance Time & Apply Ticks (Only for normal turns, NOT for rule passes)
        if not is_rule_pass:
            self.state.in_game_time += self.adventure.time_per_turn
            tick_msgs = RuleEngine.apply_ticks(self.avatar)
            for tm in tick_msgs:
                yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': tm})}\n\n"

        # 2. Record User Message
        silent_commands = ['/take_direct', '/rule-pass', '/equip', '/unequip', '/consume']
        is_silent = any(actual_user_input.lower().startswith(cmd) for cmd in silent_commands)

        if actual_user_input and not is_silent:
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
        
        # Handle status overrides from debug engine
        if debug_info.startswith("[TRIGGER_GAME_OVER]"):
            await self._finalize_session("game_over", debug_info)
            debug_info = "DEBUG: Session forced to GAME OVER."
        elif debug_info.startswith("[TRIGGER_GAME_COMPLETED]"):
            await self._finalize_session("completed", debug_info)
            debug_info = "DEBUG: Session forced to COMPLETED."

        await self.db.commit()
        yield f"event: final\ndata: {json.dumps(jsonable_encoder({
            'messages': [{'role': 'system', 'content': debug_info}],
            'sheet': await AdventureLogic.build_sheet_snapshot(self.avatar, self.state, self.db),
            'awards': self.adventure.awards,
            'game_over': (self.state.session.status == 'game_over') if self.state.session else False,
            'game_completed': (self.state.session.status == 'completed') if self.state.session else False,
            'game_over_reason': self.state.session.status_note if self.state.session else None,
            'status_note': self.state.session.status_note if self.state.session else None,
            'status': 'success'
        }))}\n\n"

    async def _handle_slash(self, user_msg: str, response: str) -> AsyncGenerator[str, None]:
        # Handle /map specifically (doesn't use CommandParser)
        if user_msg.lower() == "/map":
            map_res = await self.db.execute(select(WorldMap).where(WorldMap.template_id == self.state.template_id))
            world_map = map_res.scalars().first()
            yield f"event: final\ndata: {json.dumps(jsonable_encoder({'mermaid': MapEngine.to_mermaid(world_map) if world_map else None, 'sheet': await AdventureLogic.build_sheet_snapshot(self.avatar, self.state, self.db)}))}\n\n"
            return
            
        if response.startswith("[TRIGGER_TAKE_DIRECT]"):
            entity_id_or_name = response[21:].strip()
            # Find entity in current scene
            ent_res = await self.db.execute(
                select(WorldEntity).where(
                    WorldEntity.template_id == self.state.template_id,
                    WorldEntity.current_scene_id == self.state.current_scene_id,
                    (WorldEntity.id == entity_id_or_name) | (WorldEntity.name == entity_id_or_name)
                )
            )
            ent = ent_res.scalars().first()
            if ent and ent.is_portable:
                # Move to inventory
                new_inv = list(self.avatar.inventory)
                item_dict = jsonable_encoder({c.name: getattr(ent, c.name) for c in ent.__table__.columns})
                new_inv.append(item_dict)
                self.avatar.inventory = new_inv
                
                # Update session state instead of global entity
                states = dict(self.state.entity_states or {})
                if ent.id not in states: states[ent.id] = {}
                states[ent.id]["is_in_inventory"] = True
                self.state.entity_states = states
                flag_modified(self.state, "entity_states")
                response = f"Added {ent.name} to your inventory."
            else:
                response = f"You cannot take that."

        # PERSIST AND YIELD RESPONSE (For all commands including equip/unequip)
        if response and not response.startswith("[TRIGGER_"):
            self.db.add(ChatMessage(session_id=self.state.session_id, role="system", content=response))
            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': response})}\n\n"

        await self.db.commit()
        yield f"event: final\ndata: {json.dumps(jsonable_encoder({'sheet': await AdventureLogic.build_sheet_snapshot(self.avatar, self.state, self.db), 'entities': await AdventureLogic.build_session_entities(self.db, self.state)}))}\n\n"
        self.stop_requested = True # Stop after direct slash response

    async def _run_llm_cycle(self, user_msg: str, auto_visualize: bool) -> AsyncGenerator[str, None]:
        # Load Context and LLM Settings
        db_start = time.perf_counter()
        hist_res = await self.db.execute(select(ChatMessage).where(ChatMessage.session_id == self.state.session_id).order_by(ChatMessage.created_at.asc()))
        history = [{"role": m.role, "content": m.content} for m in hist_res.scalars().all()]
        
        scene_res = await self.db.execute(select(WorldScene).where(WorldScene.id == self.state.current_scene_id, WorldScene.template_id == self.state.template_id))
        current_scene = scene_res.scalars().first()

        # Fetch dynamic scene context (entities and exits)
        ent_res = await self.db.execute(select(WorldEntity).where(
            WorldEntity.template_id == self.state.template_id, 
            WorldEntity.current_scene_id == self.state.current_scene_id,
            WorldEntity.is_hidden == False,
            WorldEntity.is_in_inventory == False
        ))
        entities = ent_res.scalars().all()
        exit_res = await self.db.execute(select(WorldExit).where(
            WorldExit.from_scene_id == self.state.current_scene_id,
            WorldExit.template_id == self.state.template_id
        ))
        exits = exit_res.scalars().all()
        
        # Apply session overrides to entities so LLM sees current HP/state
        overrides = self.state.entity_states or {}
        for ent in entities:
            if ent.id in overrides:
                ov = overrides[ent.id]
                if "hp" in ov: ent.hp = ov["hp"]
                if "mana" in ov: ent.mana = ov["mana"]
                if "stamina" in ov: ent.stamina = ov["stamina"]
                if "spatial_position" in ov: ent.spatial_position = ov["spatial_position"]
                if "name" in ov: ent.name = ov["name"]
                if "description" in ov: ent.description = ov["description"]
        
        db_duration = time.perf_counter() - db_start
        logger.debug(f"[Turn {self.game_id}] LLM Context DB prep took {db_duration:.4f}s")

        # Build prompt using MemoryManager
        system_prompt = MemoryManager.build_context(
            self.avatar, self.adventure.context or "", history, 
            current_scene=current_scene,
            entities=entities,
            exits=exits,
            in_game_time=self.state.in_game_time,
            awards=self.adventure.awards
        )[0]["content"]

        # Override for technical state evaluation (e.g. closing character sheet)
        if user_msg == "[EVALUATE STATE]":
            system_prompt += (
                "\n\nIMPORTANT: The player just synchronized their character sheet or world state (e.g., closing a menu). "
                "This is a TECHNICAL turn. Respond only if something meaningful changed (e.g., equipment effects). "
                "Do NOT list available actions, do NOT provide suggestions, and do NOT use meta-formatting like '---' or 'You can:'. "
                "Keep the narrative flow natural if you speak at all."
            )
        
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
            
            # 2. Resolve Skill Checks
            if game_event.requested_skill_checks:
                results = []
                for req in game_event.requested_skill_checks:
                    roll = roll_skill_check(self.avatar, req.stat, req.dc)
                    res = SkillCheckResult(
                        stat=req.stat,
                        dc=req.dc,
                        roll=roll["d20"],
                        modifier=roll["modifier"],
                        total=roll["total"],
                        success=roll["success"],
                        reason=req.reason
                    )
                    results.append(res)
                    
                    # Output as system message for transparency
                    success_label = "SUCCESS" if res.success else "FAILURE"
                    roll_msg = (
                        f"🎲 **{req.stat.upper()} CHECK**: {res.reason}\n"
                        f"Roll: {res.roll} + {res.modifier} = **{res.total}** (vs DC {res.dc}) -> **{success_label}**"
                    )
                    self.db.add(ChatMessage(session_id=self.state.session_id, role="system", content=roll_msg))
                    yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': roll_msg})}\n\n"
                
                game_event.skill_check_results = results

            # 3. Apply Changes
            try:
                await self._apply_game_event(game_event)
                if game_event.game_completed:
                    await self._finalize_session("completed", game_event.status_note)
            except GameOverException as goe:
                await self._finalize_session("game_over", str(goe))
                # Ensure the narration knows about the game over
                game_event.game_over = True
                game_event.status_note = str(goe)

        # Pass 2: Narration
        yield f"event: status\ndata: {json.dumps({'content': 'Generating narrative...'})}\n\n"
        try:
            llm = GameMasterLLM(self.user, provider=complex_model_provider, model_category="complex")
        except ValueError as e:
            yield f"event: error\ndata: {json.dumps({'detail': str(e)})}\n\n"
            return
        narration_prompt = (
            system_prompt + "\n\n" + 
            prompts.GM_NARRATION_TECHNICAL_OUTCOME_PREFIX.format(
                outcome_json=game_event.model_dump_json() if game_event else "{}"
            ) + "\n\n" +
            prompts.GM_NARRATION_MANDATORY_FORMATTING
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
        
        # Add system messages for stat changes and items
        if game_event:
            # 1. Protagonist changes
            if game_event.hp_change != 0:
                verb = "gain" if game_event.hp_change > 0 else "lose"
                msg = f"You {verb} {abs(game_event.hp_change)} HP."
                self.db.add(ChatMessage(session_id=self.state.session_id, role="system", content=msg))
                yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"
            
            if game_event.stamina_change != 0:
                verb = "gain" if game_event.stamina_change > 0 else "lose"
                msg = f"You {verb} {abs(game_event.stamina_change)} Stamina."
                self.db.add(ChatMessage(session_id=self.state.session_id, role="system", content=msg))
                yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"

            if game_event.mana_change != 0:
                verb = "gain" if game_event.mana_change > 0 else "lose"
                msg = f"You {verb} {abs(game_event.mana_change)} Mana."
                self.db.add(ChatMessage(session_id=self.state.session_id, role="system", content=msg))
                yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"

            # 2. NPC/Entity changes
            if game_event.updated_entities:
                for update in game_event.updated_entities:
                    eid = update.entity_id
                    # Find name
                    ent_name = "Someone"
                    # Try to find in current entities list (from start of turn)
                    match = next((e for e in entities if e.id == eid), None)
                    if match:
                        ent_name = match.name
                    
                    if update.hp is not None and match and match.hp is not None:
                        diff = update.hp - match.hp
                        if diff != 0:
                            verb = "healed for" if diff > 0 else "takes"
                            msg = f"{ent_name} {verb} {abs(diff)} damage." if diff < 0 else f"{ent_name} {verb} {diff} HP."
                            self.db.add(ChatMessage(session_id=self.state.session_id, role="system", content=msg))
                            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"

            # 3. Items
            if game_event.new_inventory_items:
                for item in game_event.new_inventory_items:
                    msg_text = f"Added {item.name} to your inventory."
                    self.db.add(ChatMessage(session_id=self.state.session_id, role="system", content=msg_text))
                    yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg_text})}\n\n"

        await self.db.commit()
        
        yield f"event: final\ndata: {json.dumps(jsonable_encoder({
            'sheet': await AdventureLogic.build_sheet_snapshot(self.avatar, self.state, self.db), 
            'entities': await AdventureLogic.build_session_entities(self.db, self.state),
            'game_over': (self.state.session.status == 'game_over') if self.state.session else False,
            'game_completed': (self.state.session.status == 'completed') if self.state.session else False,
            'status_note': self.state.session.status_note if self.state.session else None,
            'status': 'success'
        }))}\n\n"

    async def _apply_game_event(self, event: GameEvent):
        """Applies technical mutations from a GameEvent to the database and session state."""
        RuleEngine.apply_event(self.avatar, event)
        
        state_dirty = False
        if event.new_scene_id:
            old_scene_id = self.state.current_scene_id
            self.state.current_scene_id = event.new_scene_id
            state_dirty = True
            
            # Map Update
            try:
                world_map = await AdventureLogic.get_or_create_map(self.db, self.state.template_id)
                # 1. Register exit between scenes
                MapEngine.register_exit(world_map, old_scene_id, event.new_scene_id, exit_label=event.exit_label or "")
                # 2. Register visit to the new scene
                # If we have scene data in DB, use it, otherwise use LLM provided label
                scene_res = await self.db.execute(select(WorldScene).where(WorldScene.id == event.new_scene_id, WorldScene.template_id == self.state.template_id))
                new_scene_db = scene_res.scalars().first()
                MapEngine.register_visit(
                    world_map, 
                    event.new_scene_id, 
                    label=new_scene_db.label if new_scene_db else event.scene_label,
                    description=new_scene_db.description if new_scene_db else None,
                    image_url=new_scene_db.image_url if new_scene_db else None
                )
            except Exception as e:
                logger.error(f"Map update failed during turn: {e}")
            
        # Entity State Overrides (Movement, Stats, Visibility)
        states = dict(self.state.entity_states or {})
        
        if event.moved_entities:
            for move in event.moved_entities:
                eid = move.entity_id
                if eid not in states: states[eid] = {}
                if move.to_scene_id: states[eid]["current_scene_id"] = move.to_scene_id
                if move.to_spatial_position: states[eid]["spatial_position"] = move.to_spatial_position
                state_dirty = True

        if event.updated_entities:
            for update in event.updated_entities:
                eid = update.entity_id
                if eid not in states: states[eid] = {}
                if update.name is not None: states[eid]["name"] = update.name
                if update.description is not None: states[eid]["description"] = update.description
                if update.spatial_position is not None: states[eid]["spatial_position"] = update.spatial_position
                if update.is_hidden is not None: states[eid]["is_hidden"] = update.is_hidden
                if update.hp is not None: states[eid]["hp"] = update.hp
                if update.mana is not None: states[eid]["mana"] = update.mana
                if update.stamina is not None: states[eid]["stamina"] = update.stamina
                state_dirty = True
        
        if event.deleted_entities:
            for eid in event.deleted_entities:
                if eid not in states: states[eid] = {}
                states[eid]["is_hidden"] = True
                state_dirty = True

        # Quest Updates
        if event.completed_quest_ids:
            new_quests = deepcopy(self.state.quests or [])
            modified = False
            for qid in event.completed_quest_ids:
                for q in new_quests:
                    if q.get("id") == qid and q.get("status") != "completed":
                        q["status"] = "completed"
                        modified = True
            
            # RPG Completion Logic: Check if all main quests are finished
            all_main_done = True
            main_quest_exists = False
            for q in new_quests:
                if q.get("is_main"):
                    main_quest_exists = True
                    if q.get("status") != "completed":
                        all_main_done = False
                        break
            
            if main_quest_exists and all_main_done:
                event.game_completed = True
                if not event.status_note:
                    event.status_note = "Congratulations! You have completed all main objectives."

            if modified:
                self.state.quests = new_quests
                state_dirty = True

        # Process Explicit Map Updates (Exits)
        if event.updated_exits:
            try:
                world_map = await AdventureLogic.get_or_create_map(self.db, self.state.template_id)
                for up_exit in event.updated_exits:
                    MapEngine.register_exit(
                        world_map, 
                        up_exit.from_scene_id, 
                        up_exit.to_scene_id, 
                        is_locked=up_exit.is_locked
                    )
            except Exception as e:
                logger.error(f"Manual map exit update failed: {e}")

        if state_dirty:
            self.state.entity_states = states
            flag_modified(self.state, "entity_states")
            
        await self.db.flush()
    async def _finalize_session(self, status: str, note: Optional[str] = None):
        """Updates the session status and records the outcome in the user's game log."""
        if self.state.session:
            self.state.session.status = status
            self.state.session.status_note = note
        
        if status == "completed":
            self.state.is_completed = True
        
        # Add to User game log
        log_entry = {
            "session_id": self.game_id,
            "adventure_title": (self.state.session.adventure_title if self.state.session else None) or self.adventure.title,
            "status": status,
            "outcome_note": note,
            "completed_at": datetime.utcnow().isoformat()
        }
        
        current_log = list(self.user.game_log or [])
        # Avoid duplicate entries for same session
        current_log = [entry for entry in current_log if entry.get("session_id") != self.game_id]
        current_log.append(log_entry)
        self.user.game_log = current_log
        flag_modified(self.user, "game_log")
        logger.info(f"Session {self.game_id} finalized with status {status}")
