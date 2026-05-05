import json
import asyncio
import logging
import uuid
import re
import time
import random
from copy import deepcopy
from backend.engine.quest_manager import QuestManager
from datetime import datetime
from typing import Optional, Dict, Any, AsyncGenerator, Callable, Awaitable, List

from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from backend.models.user import User
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.session_state import SessionState
from backend.models.chat import ChatMessage
from backend.models.world_entity import WorldScene, WorldEntity, WorldExit
from backend.models.world_map import WorldMap
from backend.engine.rule_engine import RuleEngine, GameEvent, GameOverException, SkillCheckResult, AttackResult, WorldEntityUpdate, RESOURCE_CAP, ToolResults, AdventureGeneratorToolIntent, AdventureGenerationRequest
from backend.engine.map_engine import MapEngine
from backend.engine.memory_manager import MemoryManager
from backend.engine.command_parser import CommandParser
from backend.engine.skill_check import roll_skill_check, roll_attack
from backend.engine.stat_aggregator import calculate_total_stats
from backend.engine.debug_engine import DebugEngine
from backend.core.llm_router import GameMasterLLM
from backend.core.llm_logger import log_structured_event
from backend.core import prompts
from backend.core.config import settings
from backend.api.routes.adventures.logic import AdventureLogic

logger = logging.getLogger(__name__)

# Constants
WALKTHROUGH_REVEAL_COST = 200
WALKTHROUGH_HINT_COST = 50
AG_IMAGE_CONFIRMATION_STATE_KEY = "__ag_image_confirmation__"
AG_LAST_REQUEST_STATE_KEY = "__ag_last_generation_request__"
AG_LAST_ERROR_STATE_KEY = "__ag_last_generation_error__"
GM_NOTES_STATE_KEY = "__gm_notes__"
GM_NOTES_MAX_ITEMS = 20
GM_NOTES_PROMPT_MAX_ITEMS = 12
GM_CHAT_RULE_PASS_NPCS_MAX_ITEMS = 10


def _is_token_limit_error(exc: Exception) -> bool:
    text = str(exc or "").lower()
    patterns = (
        "token limit",
        "too many tokens",
        "maximum context length",
        "context length exceeded",
        "context window",
        "prompt is too long",
        "max_tokens",
    )
    return any(p in text for p in patterns)


def _friendly_token_limit_message() -> str:
    return "The Game Master needs a shorter context right now. Please try again with a shorter request."


def _is_rate_limit_error(exc: Exception) -> bool:
    text = str(exc or "").lower()
    patterns = (
        "rate limit",
        "too many requests",
        "quota exceeded",
        "429",
    )
    return any(p in text for p in patterns)


def _is_timeout_error(exc: Exception) -> bool:
    text = str(exc or "").lower()
    patterns = (
        "timeout",
        "timed out",
        "read timeout",
        "request timeout",
        "deadline exceeded",
    )
    return any(p in text for p in patterns)


def _is_service_unavailable_error(exc: Exception) -> bool:
    text = str(exc or "").lower()
    patterns = (
        "service unavailable",
        "temporarily unavailable",
        "overloaded",
        "bad gateway",
        "502",
        "503",
        "504",
    )
    return any(p in text for p in patterns)


def _friendly_llm_error_message(exc: Exception) -> Optional[str]:
    if _is_token_limit_error(exc):
        return _friendly_token_limit_message()
    if _is_rate_limit_error(exc):
        return "The Game Master is busy right now. Please try again in a moment."
    if _is_timeout_error(exc):
        return "The Game Master took too long to respond. Please try again."
    if _is_service_unavailable_error(exc):
        return "The Game Master is temporarily unavailable. Please try again shortly."
    return None


def _llm_error_type(exc: Exception) -> Optional[str]:
    if _is_token_limit_error(exc):
        return "token_limit"
    if _is_rate_limit_error(exc):
        return "rate_limit"
    if _is_timeout_error(exc):
        return "timeout"
    if _is_service_unavailable_error(exc):
        return "service_unavailable"
    return None

class GameTurnManager:
    """Class to manage the complex unified game turn (chat interaction)."""

    def __init__(self, db: AsyncSession, game_id: str, user: User):
        self.db = db
        self.game_id = game_id
        self.user = user
        self.state: Optional[SessionState] = None
        self.adventure: Optional[AdventureTemplate] = None
        self.avatar: Optional[Avatar] = None
        self.stop_requested = False
        self.turn_language: Optional[str] = None

    @staticmethod
    def _compact_json(payload: object) -> str:
        return json.dumps(payload, separators=(",", ":"))

    def _build_mechanics_awards(self) -> list[dict]:
        awards = list(self.adventure.awards or [])
        earned_awards = list(self.user.earned_awards or [])
        earned_keys = {
            entry.get("key")
            for entry in earned_awards
            if entry.get("key") and (entry.get("template_id") == self.adventure.id or entry.get("adventure_id") == self.adventure.id)
        }
        return [a for a in awards if not a.get("key") or a.get("key") not in earned_keys]

    def _build_chat_progression_quests(self) -> list[dict]:
        reduced_quests = []
        for quest in list(self.state.quests or []):
            status = quest.get("status")
            if status == "completed":
                continue
            if not quest.get("id"):
                continue
            reduced_quests.append(
                {
                    "id": quest.get("id"),
                    "title": quest.get("title"),
                    "status": status,
                    "is_main": bool(quest.get("is_main")),
                }
            )
        return reduced_quests

    @staticmethod
    def _build_chat_progression_awards(unearned_awards: list[dict]) -> list[dict]:
        reduced_awards = []
        for award in unearned_awards:
            key = award.get("key")
            if not key:
                continue
            reduced_awards.append(
                {
                    "key": key,
                    "title": award.get("title"),
                    "tier": award.get("tier"),
                }
            )
        return reduced_awards

    @staticmethod
    def _build_chat_progression_npcs(entities: list[WorldEntity]) -> list[dict]:
        reduced_npcs = []
        for entity in entities:
            if (entity.entity_type or "").upper() != "NPC":
                continue
            reduced_npcs.append(
                {
                    "id": entity.id,
                    "name": entity.name,
                    "position": entity.spatial_position,
                }
            )
            if len(reduced_npcs) >= GM_CHAT_RULE_PASS_NPCS_MAX_ITEMS:
                break
        return reduced_npcs

    def _build_chat_rule_pass_prompt(self, quests: list[dict], awards: list[dict], npcs: list[dict]) -> str:
        notes = self._get_gm_notes()
        if len(notes) > GM_NOTES_PROMPT_MAX_ITEMS:
            notes = notes[-GM_NOTES_PROMPT_MAX_ITEMS:]
        return prompts.GM_CHAT_MINIMAL_RULE_PASS_PROMPT.format(
            quests_json=self._compact_json(quests),
            awards_json=self._compact_json(awards),
            npcs_json=self._compact_json(npcs),
            notes_json=self._compact_json(notes),
        )

    def _get_gm_notes(self) -> List[str]:
        exit_states = self.state.exit_states or {}
        notes = exit_states.get(GM_NOTES_STATE_KEY)
        if not isinstance(notes, list):
            return []
        return [str(n).strip() for n in notes if str(n).strip()]

    def _apply_gm_notes_update(
        self,
        remember_notes: Optional[List[str]],
        forget_notes: Optional[List[str]],
        clear_notes: bool,
    ) -> None:
        existing = self._get_gm_notes()
        if clear_notes:
            existing = []

        forget_set = {
            str(note).strip().lower()
            for note in (forget_notes or [])
            if str(note).strip()
        }
        if forget_set:
            existing = [n for n in existing if n.strip().lower() not in forget_set]

        for note in (remember_notes or []):
            normalized = str(note).strip()
            if not normalized:
                continue
            if any(n.strip().lower() == normalized.lower() for n in existing):
                continue
            existing.append(normalized)

        if len(existing) > GM_NOTES_MAX_ITEMS:
            existing = existing[-GM_NOTES_MAX_ITEMS:]

        exit_states = dict(self.state.exit_states or {})
        if existing:
            exit_states[GM_NOTES_STATE_KEY] = existing
        else:
            exit_states.pop(GM_NOTES_STATE_KEY, None)
        self.state.exit_states = exit_states
        flag_modified(self.state, "exit_states")

    def _build_gm_notes_prompt_block(self) -> str:
        notes = self._get_gm_notes()
        if not notes:
            return "\n\nSESSION NOTES:\n- none"
        lines = "\n".join(f"- {note}" for note in notes)
        return "\n\nSESSION NOTES:\n" + lines

    @staticmethod
    def _build_progression_event(intent: AdventureGeneratorToolIntent) -> GameEvent:
        return GameEvent(
            narrative_description=intent.narrative_description or "",
            hp_change=0,
            stamina_change=0,
            mana_change=0,
            new_status_effects=[],
            new_inventory_items=[],
            completed_quest_ids=intent.completed_quest_ids,
            earned_award_keys=intent.earned_award_keys,
            remember_notes=intent.remember_notes,
            forget_notes=intent.forget_notes,
            clear_notes=bool(intent.clear_notes),
            game_over=bool(intent.game_over),
            game_completed=bool(intent.game_completed),
            status_note=intent.status_note,
            instant_narrative=intent.instant_narrative,
        )

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
            # Use session_id to find the scene (snapshot)
            scene_res = await self.db.execute(select(WorldScene).where(WorldScene.id == self.state.current_scene_id, WorldScene.session_id == self.game_id))
            cur_scene = scene_res.scalars().first()
            
            # Fallback to template if not found (though it should be there after deep clone)
            if not cur_scene:
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

    async def process_turn(self, message: str, auto_visualize: bool = False, language: Optional[str] = None) -> AsyncGenerator[str, None]:
        self.turn_language = language
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
            if settings.TALEWEAVER_DEBUG_ENABLED:
                async for chunk in self._handle_debug(user_msg): yield chunk
                return
            else:
                logger.warning(f"[Turn {self.game_id}] Debug command ignored: TALEWEAVER_DEBUG_ENABLED is False.")

        # 1. Combat & Loot Handling (Active Phase)
        if self._has_combat_phase():
            async for chunk in self._handle_combat_turn(user_msg):
                yield chunk
            return

        # 2. Fight Trigger / Attack
        if user_msg.lower().startswith("/fight") or user_msg.lower().startswith("/attack"):
            async for chunk in self._handle_fight_start(user_msg):
                yield chunk
            return
            
        is_rule_pass = False
        if user_msg.startswith("/"):
            response = CommandParser.parse_command(self.avatar, user_msg)
            
            if response == "[RULE_PASS]":
                is_rule_pass = True
                user_msg = "[EVALUATE STATE]"
                yield f"event: status\ndata: {json.dumps({'content': 'The Game Master evaluates your situation...'})}\n\n"
            elif response.startswith("[TRIGGER_TALK]"):
                user_msg = f"Talk to {response[14:].strip()}"
                # Continue turn as normal
            elif response.startswith("[TRIGGER_INSPECT]"):
                user_msg = f"Inspect {response[17:].strip()}"
                # Continue turn as normal
            elif response.startswith("[TRIGGER_TAKE]"):
                user_msg = f"Take {response[14:].strip()}"
                # Continue turn as normal
            elif response.startswith("[TRIGGER_COMBINE]"):
                user_msg = f"Use {response[17:].strip()}"
                # Continue turn as normal
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
        async def _run_llm_cycle_with_lang(msg, av):
            async for c in self._run_llm_cycle(msg, av, language=language):
                yield c
        
        async for chunk in _run_llm_cycle_with_lang(user_msg, auto_visualize):
            yield chunk
            
        turn_end = time.perf_counter()
        log_structured_event(
            "gm.turn.pipeline.total",
            adventure_id=self.adventure.id,
            game_id=self.game_id,
            operation="chat_turn",
            phase="total",
            duration_ms=round((turn_end - turn_start) * 1000, 2),
            strict_rules=bool(self.adventure.strict_rules),
            is_adventure_generator=bool(self.adventure.is_adventure_generator),
            user_input_chars=len(actual_user_input or ""),
        )
        logger.debug(f"[Turn {self.game_id}] Total turn processing took {turn_end - turn_start:.4f}s")

    async def _handle_debug(self, user_msg: str) -> AsyncGenerator[str, None]:
        cmd_args = user_msg[7:].strip()
        debug_info = await DebugEngine.handle_debug_command(self.db, self.state, cmd_args, user=self.user, adventure=self.adventure, avatar=self.avatar)
        
        # Handle status overrides from debug engine
        if debug_info.startswith("[TRIGGER_GAME_OVER]"):
            await self._finalize_session("game_over", debug_info)
            debug_info = "DEBUG: Session forced to GAME OVER."
        elif debug_info.startswith("[TRIGGER_GAME_COMPLETED]"):
            await self._finalize_session("completed", debug_info)
            debug_info = "DEBUG: Session forced to COMPLETED."
        elif debug_info.startswith("[TRIGGER_WALKTHROUGH_REVEAL_FREE]"):
            self.state.is_walkthrough_revealed = True
            debug_info = debug_info[33:].strip()
        elif debug_info.startswith("[TRIGGER_GEN_ITEM]"):
            prompt = debug_info.replace("[TRIGGER_GEN_ITEM]", "").strip()
            async for chunk in self._handle_debug_gen_item(prompt):
                yield chunk
            return
        
        # New: Combat Debug Commands
        elif cmd_args == "win_fight":
            combat = self._read_combat_state()
            if combat and combat.get("active"):
                combat["active"] = False
                combat["outcome"] = "victory"
                combat["enemy"]["hp"] = 0
                combat["status_note"] = "Combat won via debug command."
                
                # Sync back to world entity state
                enemy_id = combat["enemy"]["id"]
                states = dict(self.state.entity_states or {})
                if enemy_id not in states: states[enemy_id] = {}
                states[enemy_id]["hp"] = 0
                self.state.entity_states = states
                flag_modified(self.state, "entity_states")
                
                self._append_combat_log(combat, combat["status_note"], "outcome")
                self._set_combat_state(combat)
                debug_info = "DEBUG: Combat forced to VICTORY."
        
        elif cmd_args == "loose_fight":
            combat = self._read_combat_state()
            if combat and combat.get("active"):
                combat["active"] = False
                combat["outcome"] = "defeat"
                combat["player"]["hp"] = 0
                combat["status_note"] = "Combat lost via debug command."
                
                # Sync back to avatar
                self.avatar.hp = 0
                
                self._append_combat_log(combat, combat["status_note"], "outcome")
                self._set_combat_state(combat)
                debug_info = "DEBUG: Combat forced to DEFEAT."

        # Send debug info as a system message so it appears in chat
        self.db.add(ChatMessage(session_id=self.state.session_id, role="system", content=debug_info))
        await self.db.commit()
        yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': debug_info, 'is_debug': True})}\n\n"

    async def _handle_debug_gen_item(self, prompt: str) -> AsyncGenerator[str, None]:
        """Debug helper to force-generate an item based on a prompt."""
        instruction = f"DEBUG COMMAND: The user wants you to generate an item now. Instruction: {prompt}"
        # We temporarily set the prompt as if it was the user message
        async for chunk in self._run_llm_cycle(instruction, self.avatar):
            yield chunk

        world_map = await AdventureLogic.get_or_create_map(self.db, self.state.template_id)
        final_data = jsonable_encoder({
            'mermaid': MapEngine.to_mermaid(world_map),
            'sheet': await AdventureLogic.build_sheet_snapshot(self.avatar, self.state, self.db),
            'combat': AdventureLogic.get_combat_snapshot(self.state),
            'awards': self.adventure.awards,
            'game_over': (self.state.session.status == 'game_over') if self.state.session else False,
            'game_completed': (self.state.session.status == 'completed') if self.state.session else False,
            'game_over_reason': self.state.session.status_note if self.state.session else None,
            'status_note': self.state.session.status_note if self.state.session else None,
            'status': 'success'
        })
        yield f"event: final\ndata: {json.dumps(final_data)}\n\n"

    async def _handle_slash(self, user_msg: str, response: str) -> AsyncGenerator[str, None]:
        # Handle /map specifically (doesn't use CommandParser)
        if user_msg.lower() == "/map":
            map_res = await self.db.execute(select(WorldMap).where(WorldMap.template_id == self.state.template_id))
            world_map = map_res.scalars().first()
            final_data = jsonable_encoder({'mermaid': MapEngine.to_mermaid(world_map) if world_map else None, 'sheet': await AdventureLogic.build_sheet_snapshot(self.avatar, self.state, self.db)})
            yield f"event: final\ndata: {json.dumps(final_data)}\n\n"
            return
            
        if response.startswith("[TRIGGER_TAKE_DIRECT]"):
            entity_id_or_name = response[21:].strip()
            # Find entity in current scene (snapshot)
            ent_res = await self.db.execute(
                select(WorldEntity).where(
                    WorldEntity.session_id == self.game_id,
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
        
        elif response.startswith("[TRIGGER_WALKTHROUGH_REVEAL]"):
            if self.avatar.exp >= WALKTHROUGH_REVEAL_COST:
                self.avatar.exp -= WALKTHROUGH_REVEAL_COST
                self.state.is_walkthrough_revealed = True
                response = f"Walkthrough revealed! You spent {WALKTHROUGH_REVEAL_COST} XP. You can now open it via the menu."
            else:
                response = f"You do not have enough XP to reveal the walkthrough ({self.avatar.exp}/{WALKTHROUGH_REVEAL_COST})."

        elif response.startswith("[TRIGGER_WALKTHROUGH_HINT]"):
            if self.avatar.exp >= WALKTHROUGH_HINT_COST:
                # For now, hint just reveals the whole thing or we could implement a smarter hint system.
                # User specifically asked for walkthrough reveal, so let's stick to that for now.
                self.avatar.exp -= WALKTHROUGH_HINT_COST
                response = f"Hint: Look closer at the surroundings. (Cost: {WALKTHROUGH_HINT_COST} XP)"
            else:
                response = f"You do not have enough XP for a hint ({self.avatar.exp}/{WALKTHROUGH_HINT_COST})."

        if response.startswith("[TRIGGER_CONSUME]"):
            item_name = response.replace("[TRIGGER_CONSUME]", "").strip()
            action_msg = self._consume_item_now(item_name)
            self.db.add(ChatMessage(session_id=self.state.session_id, role="system", content=action_msg))
            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': action_msg})}\n\n"
            response = action_msg # Allow it to fall through to persist and yield final state

        # PERSIST AND YIELD RESPONSE (For all commands including equip/unequip)
        if response and not response.startswith("[TRIGGER_"):
            self.db.add(ChatMessage(session_id=self.state.session_id, role="system", content=response))
            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': response})}\n\n"

        await self.db.commit()
        final_data = jsonable_encoder({'sheet': await AdventureLogic.build_sheet_snapshot(self.avatar, self.state, self.db), 'entities': await AdventureLogic.build_session_entities(self.db, self.state), 'combat': AdventureLogic.get_combat_snapshot(self.state)})
        yield f"event: final\ndata: {json.dumps(final_data)}\n\n"
        self.stop_requested = True # Stop after direct slash response

    def _read_combat_state(self) -> Dict[str, Any]:
        states = self.state.entity_states or {}
        combat = states.get("__combat__")
        if isinstance(combat, dict):
            return combat
        return {}

    def _is_combat_active(self) -> bool:
        combat = self._read_combat_state()
        return bool(combat.get("active"))

    def _has_combat_phase(self) -> bool:
        combat = self._read_combat_state()
        return bool(combat.get("active") or combat.get("loot_pending") or combat.get("outcome"))

    def _set_combat_state(self, combat: Dict[str, Any]) -> None:
        # Sync to both locations to ensure compatibility across the engine
        states = dict(self.state.entity_states or {})
        states["__combat__"] = combat
        self.state.entity_states = states
        # Also set the dynamic attribute used by some snapshots
        self.state.combat_json = combat
        flag_modified(self.state, "entity_states")

    async def _find_fight_target(self, target_hint: str) -> Optional[WorldEntity]:
        ent_res = await self.db.execute(
            select(WorldEntity).where(
                WorldEntity.session_id == self.game_id,
                WorldEntity.current_scene_id == self.state.current_scene_id,
                WorldEntity.entity_type.in_(["NPC", "npc"]),
                WorldEntity.is_hidden == False,
                WorldEntity.is_in_inventory == False,
            )
        )
        npcs = ent_res.scalars().all()
        if not npcs:
            return None

        target_hint = (target_hint or "").strip()
        if target_hint:
            low = target_hint.lower()
            for npc in npcs:
                if npc.id.lower() == low or npc.name.lower() == low:
                    return npc

        states = self.state.entity_states or {}
        for npc in npcs:
            hp = (states.get(npc.id, {}) or {}).get("hp")
            if hp is None:
                hp = npc.hp
            if hp is None or hp > 0:
                return npc
        return npcs[0]

    def _entity_stat(self, ent: WorldEntity, stat_key: str, fallback: int = 0) -> int:
        states = self.state.entity_states or {}
        override = (states.get(ent.id, {}) or {}).get(stat_key)
        if isinstance(override, int):
            return override
        ent_val = getattr(ent, stat_key, None)
        if isinstance(ent_val, int):
            return ent_val
        return fallback

    def _player_damage_dice(self) -> str:
        eq = self.avatar.equipment or {}
        main_hand = eq.get("MainHand")
        if isinstance(main_hand, dict):
            dice = main_hand.get("damage_dice")
            if isinstance(dice, str) and re.match(r"^\d+d\d+([+-]\d+)?$", dice.replace(" ", "").lower()):
                return dice
        return "1d8"

    def _enemy_damage_dice(self, enemy: WorldEntity) -> str:
        if isinstance(enemy.metadata_json, dict):
            dice = enemy.metadata_json.get("damage_dice")
            if isinstance(dice, str) and re.match(r"^\d+d\d+([+-]\d+)?$", dice.replace(" ", "").lower()):
                return dice
        return "1d6"

    def _append_combat_log(self, combat: Dict[str, Any], text: str, entry_type: str = "log") -> None:
        logs = list(combat.get("log") or [])
        logs.append({
            "round": combat.get("round", 1),
            "type": entry_type,
            "text": text,
            "timestamp": datetime.utcnow().isoformat(),
        })
        combat["log"] = logs[-80:]

    async def _emit_combat_final(self, status_note: Optional[str] = None) -> AsyncGenerator[str, None]:
        await self.db.commit()
        final_data = jsonable_encoder({
            'sheet': await AdventureLogic.build_sheet_snapshot(self.avatar, self.state, self.db),
            'entities': await AdventureLogic.build_session_entities(self.db, self.state),
            'combat': AdventureLogic.get_combat_snapshot(self.state),
            'game_over': (self.state.session.status == 'game_over') if self.state.session else False,
            'game_completed': (self.state.session.status == 'completed') if self.state.session else False,
            'status_note': status_note or (self.state.session.status_note if self.state.session else None),
            'status': 'success'
        })
        yield f"event: final\ndata: {json.dumps(final_data)}\n\n"

    async def _emit_combat_aftermath_narration(self, combat: Dict[str, Any]) -> AsyncGenerator[str, None]:
        outcome = str(combat.get("outcome") or "").lower()
        if outcome not in {"victory", "escaped"}:
            return

        enemy_name = (combat.get("enemy") or {}).get("name") or "the enemy"
        outcome_note = combat.get("status_note") or "The combat has ended."

        llm_settings = self.user.llm_settings or {}
        complex_model_provider = (
            llm_settings.get("complex_model_provider")
            or llm_settings.get("small_model_provider")
            or llm_settings.get("preferred_provider")
            or "openai"
        )
        complex_model = llm_settings.get("complex_model") or "gpt-4o"

        try:
            llm = GameMasterLLM(self.user, provider=complex_model_provider, model_category="complex")
        except ValueError:
            return

        prompt = (
            "You are the Game Master. Write a short aftermath narration after combat ends. "
            "Use 2-4 sentences, stay in-world, no mechanics, no bullet points, no command suggestions."
        )
        if self.turn_language:
            prompt += f" Respond only in {self.turn_language.upper()}."

        user_prompt = (
            f"Protagonist: {self.avatar.name}. "
            f"Enemy: {enemy_name}. "
            f"Combat outcome: {outcome}. "
            f"Outcome note: {outcome_note}. "
            "Narrate the immediate atmosphere and next beat from the Game Master's perspective."
        )

        response_text = ""
        yield f"event: status\ndata: {json.dumps({'content': 'Game Master reflects on the battle outcome...'})}\n\n"
        stream = await llm.stream_simple_task(prompt, user_prompt, complex_model)
        async for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            if delta:
                response_text += delta
                yield f"event: chunk\ndata: {json.dumps({'content': delta})}\n\n"

        response_text = response_text.strip()
        if response_text:
            self.db.add(ChatMessage(session_id=self.state.session_id, role="assistant", content=response_text))
            self._append_combat_log(combat, response_text, "aftermath")
            self._set_combat_state(combat)

    async def _handle_fight_start(self, user_msg: str) -> AsyncGenerator[str, None]:
        if (self.adventure.rule_enforcement_mode or "rpg") != "rpg":
            msg = "Turn-based combat is only available in RPG mode."
            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"
            async for chunk in self._emit_combat_final(msg):
                yield chunk
            return

        if self._is_combat_active():
            msg = "A fight is already active. Use Attack, Run, or a consumable."
            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"
            async for chunk in self._emit_combat_final(msg):
                yield chunk
            return

        target_hint = ""
        if " " in user_msg:
            target_hint = user_msg.split(" ", 1)[1].strip()
        
        target = await self._find_fight_target(target_hint)
        if not target:
            msg = "No enemy is available in this scene."
            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"
            async for chunk in self._emit_combat_final(msg):
                yield chunk
            return

        enemy_hp = self._entity_stat(target, "hp", 50)
        if enemy_hp <= 0:
            msg = f"{target.name} is already defeated."
            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"
            async for chunk in self._emit_combat_final(msg):
                yield chunk
            return

        enemy_max_hp = self._entity_stat(target, "max_hp", enemy_hp if enemy_hp > 0 else 50)
        # If no NPC dexterity value is provided, use a neutral baseline so enemies can act reliably.
        enemy_dex = self._entity_stat(target, "stat_modifier_dexterity", 10)
        enemy_ac_mod = self._entity_stat(target, "stat_modifier_armor_class", 0)
        player_stats = calculate_total_stats(self.avatar)
        player_dex = int(player_stats.get("dexterity", self.avatar.dexterity))

        player_init = random.randint(1, 20) + max(0, player_dex // 2)
        enemy_init = random.randint(1, 20) + max(0, enemy_dex // 2)
        player_starts = player_init >= enemy_init

        combat = {
            "active": True,
            "round": 1,
            "turn": "player" if player_starts else "enemy",
            "player": {
                "name": self.avatar.name,
                "image_url": self.avatar.profile_image,
                "hp": self.avatar.hp,
                "max_hp": self.avatar.max_hp,
                "ac": int(player_stats.get("armor_class", self.avatar.armor_class)),
            },
            "enemy": {
                "id": target.id,
                "name": target.name,
                "image_url": target.image_url,
                "hp": enemy_hp,
                "max_hp": enemy_max_hp,
                "dexterity_mod": enemy_dex,
                "armor_mod": enemy_ac_mod,
                "inventory": list(target.inventory or []),
            },
            "loot_pending": False,
            "loot_items": [],
            "outcome": None,
            "status_note": None,
            "log": [],
        }
        self._append_combat_log(combat, f"Initiative: {self.avatar.name} {player_init} vs {target.name} {enemy_init}.", "initiative")
        if player_starts:
            self._append_combat_log(combat, f"{self.avatar.name} starts the fight.", "turn")
        else:
            self._append_combat_log(combat, f"{target.name} is faster and starts.", "turn")
        self._set_combat_state(combat)

        # If enemy starts, immediately resolve one enemy action.
        if not player_starts:
            async for chunk in self._resolve_enemy_turn():
                yield chunk

        msg = f"Combat started against {target.name}."
        yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"
        async for chunk in self._emit_combat_final(msg):
            yield chunk

    async def _auto_trigger_combat_from_gm(self, game_event: GameEvent) -> bool:
        """Starts combat automatically when mechanics pass requests combat attacks."""
        if self._is_combat_active() or self._has_combat_phase():
            return False
        if (self.adventure.rule_enforcement_mode or "rpg") != "rpg":
            return False
        if not game_event.requested_attacks:
            return False

        target_hint = ""
        for req in game_event.requested_attacks:
            if req.target_id and req.target_id.upper() != "PLAYER":
                target_hint = req.target_id
                break
            if req.attacker_id and req.attacker_id.upper() != "PLAYER":
                target_hint = req.attacker_id
                break

        target = await self._find_fight_target(target_hint)
        if not target:
            return False

        async for _chunk in self._handle_fight_start(f"/fight {target.id}"):
            pass
        return True

    def _find_consumable(self, item_name: str) -> Optional[Dict[str, Any]]:
        for item in list(self.avatar.inventory or []):
            if isinstance(item, dict) and item.get("name", "").lower() == item_name.lower() and item.get("item_type") == "CONSUMABLE":
                return item
        return None

    def _sync_combat_player_snapshot(self, combat: Dict[str, Any]) -> None:
        player = dict(combat.get("player") or {})
        player_stats = calculate_total_stats(self.avatar)
        player["name"] = self.avatar.name
        player["image_url"] = self.avatar.profile_image
        player["hp"] = int(self.avatar.hp or 0)
        player["max_hp"] = int(self.avatar.max_hp or RESOURCE_CAP)
        player["ac"] = int(player_stats.get("armor_class", self.avatar.armor_class))
        combat["player"] = player

    @staticmethod
    def _description_delta(description: str, resource: str) -> int:
        if not description:
            return 0

        aliases = {
            "hp": r"(?:hp|health|lebenspunkte?)",
            "mana": r"(?:mana|magie|magiekraft)",
            "stamina": r"(?:stamina|ausdauer|energie)",
        }
        resource_rx = aliases.get(resource)
        if not resource_rx:
            return 0

        desc = description.lower()
        pos_words = (
            "stellt", "wieder her", "heilt", "regeneriert", "restores", "restore", "heals", "heal", "regains", "regain",
            "replenish", "replenishes", "recover", "recovers", "gain", "gains", "boost"
        )
        neg_words = (
            "kostet", "verliert", "schaden", "schadet", "entzieht", "senkt", "reduziert", "damage", "damages",
            "lose", "loses", "losing", "drain", "drains", "reduces", "reduce", "consumes", "consume"
        )

        total = 0
        for match in re.finditer(rf"([+-]?\d+)\s*{resource_rx}", desc):
            raw = match.group(1)
            magnitude = abs(int(raw))
            start = max(0, match.start() - 40)
            end = min(len(desc), match.end() + 40)
            ctx = desc[start:end]

            if raw.startswith("-"):
                total -= magnitude
            elif raw.startswith("+"):
                total += magnitude
            elif any(word in ctx for word in neg_words):
                total -= magnitude
            elif any(word in ctx for word in pos_words):
                total += magnitude

        return total

    def _resource_delta_from_consumable(self, item: Dict[str, Any], resource: str) -> int:
        key_map = {
            "hp": ["hp_change", "health_change", "heal", "heal_amount", "restore_hp", "restore_health", "hp_delta"],
            "mana": ["mana_change", "restore_mana", "mana_restore", "mana_delta"],
            "stamina": ["stamina_change", "restore_stamina", "stamina_restore", "stamina_delta"],
        }
        keys = key_map.get(resource, [])

        for k in keys:
            val = item.get(k)
            if isinstance(val, (int, float)):
                return int(val)

        effects = item.get("effects")
        if isinstance(effects, dict):
            val = effects.get(resource)
            if isinstance(val, (int, float)):
                return int(val)

        metadata_json = item.get("metadata_json")
        if isinstance(metadata_json, dict):
            for k in keys:
                val = metadata_json.get(k)
                if isinstance(val, (int, float)):
                    return int(val)

            meta_effects = metadata_json.get("effects")
            if isinstance(meta_effects, dict):
                val = meta_effects.get(resource)
                if isinstance(val, (int, float)):
                    return int(val)

        description = item.get("description")
        if isinstance(description, str):
            return self._description_delta(description, resource)

        return 0

    @staticmethod
    def _parse_json_object(raw: str) -> Optional[Dict[str, Any]]:
        text = (raw or "").strip()
        if not text:
            return None

        try:
            data = json.loads(text)
            return data if isinstance(data, dict) else None
        except Exception:
            pass

        fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.IGNORECASE | re.DOTALL)
        if fence:
            try:
                data = json.loads(fence.group(1))
                return data if isinstance(data, dict) else None
            except Exception:
                pass

        obj_match = re.search(r"(\{.*\})", text, re.DOTALL)
        if obj_match:
            try:
                data = json.loads(obj_match.group(1))
                return data if isinstance(data, dict) else None
            except Exception:
                return None
        return None

    async def _request_llm_combat_special_event(self, combat: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        llm_settings = self.user.llm_settings or {}
        complex_model_provider = (
            llm_settings.get("complex_model_provider")
            or llm_settings.get("small_model_provider")
            or llm_settings.get("preferred_provider")
            or "openai"
        )
        complex_model = llm_settings.get("complex_model") or "gpt-4o"

        try:
            llm = GameMasterLLM(self.user, provider=complex_model_provider, model_category="complex")
        except ValueError:
            return None

        enemy = combat.get("enemy") or {}
        player = combat.get("player") or {}
        enemy_name = str(enemy.get("name") or "Enemy")
        player_name = str(player.get("name") or self.avatar.name or "Protagonist")
        enemy_hp = int(enemy.get("hp") or 0)
        enemy_max_hp = int(enemy.get("max_hp") or max(enemy_hp, 1))
        player_hp = int(player.get("hp") or self.avatar.hp or 0)
        player_max_hp = int(player.get("max_hp") or self.avatar.max_hp or max(player_hp, 1))

        system_prompt = (
            "You are the Game Master deciding a combat special event. "
            "Return ONLY valid JSON with this schema: "
            "{\"mode\":\"story\"|\"special_attack\",\"text\":string,\"damage\":number}. "
            "Rules: Keep text to 1-2 short in-world sentences. "
            "If mode is story, set damage to 0. "
            "If mode is special_attack, damage must be an integer between 5 and 40. "
            "No markdown, no code fences, no extra keys."
        )
        if self.turn_language:
            system_prompt += f" Text must be in {self.turn_language.upper()}."

        user_prompt = (
            f"Round: {int(combat.get('round') or 1)}. "
            f"Attacker: {enemy_name} HP {enemy_hp}/{enemy_max_hp}. "
            f"Target: {player_name} HP {player_hp}/{player_max_hp}. "
            "Decide if this special event becomes narrative flavor or a special attack. "
            "Return only the JSON object."
        )

        try:
            raw = await llm.aexecute_simple_task(
                system_prompt,
                user_prompt,
                complex_model,
                adventure_id=self.state.template_id,
                game_id=self.game_id,
                operation="combat.special_event",
                phase="decision",
            )
        except Exception as exc:
            logger.warning("[Turn %s] Special-event LLM call failed: %s", self.game_id, exc)
            return None

        data = self._parse_json_object(raw)
        if not data:
            logger.warning("[Turn %s] Special-event LLM returned unparsable payload: %r", self.game_id, raw)
            return None

        mode = str(data.get("mode") or "").strip().lower()
        text = str(data.get("text") or "").strip()
        damage_raw = data.get("damage")
        damage = 0
        if isinstance(damage_raw, (int, float)):
            damage = int(damage_raw)

        if mode not in {"story", "special_attack"}:
            return None

        if mode == "special_attack":
            damage = max(5, min(40, damage))
            if not text:
                text = f"Special Event: {enemy_name} unleashes a sudden devastating strike!"
        else:
            damage = 0
            if not text:
                text = f"Special Event: {enemy_name} alters the tone of battle with a chilling presence."

        return {"mode": mode, "text": text, "damage": damage}

    def _consume_item_now(self, item_name: str) -> str:
        item = self._find_consumable(item_name)
        if not item:
            return f"You do not have the consumable '{item_name}'."

        hp_delta = self._resource_delta_from_consumable(item, "hp")
        mana_delta = self._resource_delta_from_consumable(item, "mana")
        stamina_delta = self._resource_delta_from_consumable(item, "stamina")

        if hp_delta:
            max_hp = self.avatar.max_hp or RESOURCE_CAP
            self.avatar.hp = max(0, min(max_hp, self.avatar.hp + hp_delta))
        if mana_delta:
            max_mana = self.avatar.max_mana or RESOURCE_CAP
            self.avatar.mana = max(0, min(max_mana, self.avatar.mana + mana_delta))
        if stamina_delta:
            max_stamina = self.avatar.max_stamina or RESOURCE_CAP
            self.avatar.stamina = max(0, min(max_stamina, self.avatar.stamina + stamina_delta))

        new_inventory = []
        removed = False
        for inv_item in list(self.avatar.inventory or []):
            if not removed and isinstance(inv_item, dict) and inv_item.get("name", "").lower() == item_name.lower() and inv_item.get("item_type") == "CONSUMABLE":
                removed = True
                continue
            new_inventory.append(inv_item)
        self.avatar.inventory = new_inventory

        changes = []
        if hp_delta:
            changes.append(f"HP {hp_delta:+d}")
        if mana_delta:
            changes.append(f"Mana {mana_delta:+d}")
        if stamina_delta:
            changes.append(f"Stamina {stamina_delta:+d}")

        if changes:
            return f"{self.avatar.name} uses {item.get('name', item_name)} ({', '.join(changes)})."
        return f"{self.avatar.name} uses {item.get('name', item_name)}."

    async def _maybe_trigger_special_event(self, combat: Dict[str, Any]) -> Optional[str]:
        if random.random() > 0.25:
            return None

        enemy_name = combat.get("enemy", {}).get("name", "Enemy")
        event_data = await self._request_llm_combat_special_event(combat)

        # Safe fallback if LLM is unavailable or returns invalid payload.
        if not event_data:
            if random.random() < 0.5:
                bonus = 20
                self.avatar.hp = max(0, self.avatar.hp - bonus)
                text = f"Special Event: {enemy_name} performs a special attack for {bonus} damage!"
                self._append_combat_log(combat, text, "special")
                if self.avatar.hp <= 0:
                    raise GameOverException(f"{self.avatar.name} has fallen! Game Over.")
                return text

            text = f"Special Event: {enemy_name} bends the battlefield mood to its advantage."
            self._append_combat_log(combat, text, "special")
            return text

        if event_data.get("mode") == "special_attack":
            bonus = int(event_data.get("damage") or 0)
            self.avatar.hp = max(0, self.avatar.hp - bonus)
            text = str(event_data.get("text") or f"Special Event: {enemy_name} performs a special attack for {bonus} damage!")
            self._append_combat_log(combat, text, "special")
            if self.avatar.hp <= 0:
                raise GameOverException(f"{self.avatar.name} has fallen! Game Over.")
            return text

        text = str(event_data.get("text") or f"Special Event: {enemy_name} bends the battlefield mood to its advantage.")
        self._append_combat_log(combat, text, "special")
        return text

    async def _resolve_enemy_turn(self) -> AsyncGenerator[str, None]:
        combat = self._read_combat_state()
        if not combat.get("active"):
            return

        enemy = combat.get("enemy", {})
        enemy_id = enemy.get("id")
        if not enemy_id:
            return

        enemy_res = await self.db.execute(select(WorldEntity).where(WorldEntity.id == enemy_id, WorldEntity.session_id == self.game_id))
        enemy_ent = enemy_res.scalars().first()
        if not enemy_ent:
            combat["active"] = False
            combat["outcome"] = "victory"
            combat["status_note"] = "Enemy vanished from the scene."
            self._append_combat_log(combat, combat["status_note"], "outcome")
            self._set_combat_state(combat)
            return

        enemy_hp = int(combat.get("enemy", {}).get("hp") or 0)
        if enemy_hp <= 0:
            combat["active"] = False
            combat["outcome"] = "victory"
            combat["status_note"] = f"{enemy.get('name', 'Enemy')} was defeated."
            self._set_combat_state(combat)
            return

        player_stats = calculate_total_stats(self.avatar)
        player_ac = int(player_stats.get("armor_class", self.avatar.armor_class))

        enemy_avatar = Avatar(
            name=enemy_ent.name,
            hp=enemy_hp,
            strength=self._entity_stat(enemy_ent, "stat_modifier_strength", 0),
            dexterity=self._entity_stat(enemy_ent, "stat_modifier_dexterity", 10),
            intelligence=self._entity_stat(enemy_ent, "stat_modifier_intelligence", 0),
            wisdom=self._entity_stat(enemy_ent, "stat_modifier_wisdom", 0),
            charisma=self._entity_stat(enemy_ent, "stat_modifier_charisma", 0),
            armor_class=10 + self._entity_stat(enemy_ent, "stat_modifier_armor_class", 0),
            stats={},
            equipment={},
            inventory=[]
        )
        roll = roll_attack(enemy_avatar, "dexterity", player_ac, self._enemy_damage_dice(enemy_ent))
        if roll["is_hit"]:
            self.avatar.hp = max(0, self.avatar.hp - roll["damage_total"])
            dmg_bonus = int(roll.get("damage_bonus") or 0)
            dmg_bonus_str = f" + {dmg_bonus}" if dmg_bonus > 0 else (f" - {abs(dmg_bonus)}" if dmg_bonus < 0 else "")
            text = (
                f"{enemy_ent.name} ATTACK ROLL: {roll['hit_roll']} + {roll['hit_modifier']} = {roll['hit_total']} vs AC {player_ac} -> HIT | "
                f"DMG {roll['damage_dice_str']} ({' + '.join(str(r) for r in roll['damage_rolls'])}"
                f"{dmg_bonus_str})"
                f" = {roll['damage_total']}"
            )
        else:
            text = f"{enemy_ent.name} ATTACK ROLL: {roll['hit_roll']} + {roll['hit_modifier']} = {roll['hit_total']} vs AC {player_ac} -> MISS"
        self._sync_combat_player_snapshot(combat)
        self._append_combat_log(combat, text, "enemy_action")
        yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': text})}\n\n"

        if self.avatar.hp <= 0:
            await self._finalize_session("game_over", f"{self.avatar.name} has fallen in battle.")
            combat["active"] = False
            combat["outcome"] = "defeat"
            combat["status_note"] = "Game Over"
            self._append_combat_log(combat, "The protagonist falls. Game Over.", "outcome")
            self._set_combat_state(combat)
            return

        try:
            special_text = await self._maybe_trigger_special_event(combat)
            self._sync_combat_player_snapshot(combat)
            if special_text:
                yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': special_text})}\n\n"
        except GameOverException as goe:
            await self._finalize_session("game_over", str(goe))
            self._sync_combat_player_snapshot(combat)
            combat["active"] = False
            combat["outcome"] = "defeat"
            combat["status_note"] = str(goe)
            self._set_combat_state(combat)
            return

        combat["turn"] = "player"
        combat["round"] = int(combat.get("round", 1)) + 1
        self._append_combat_log(combat, f"Round {combat['round']}: {self.avatar.name}'s turn.", "turn")
        self._set_combat_state(combat)

    async def _spawn_scene_item(self, item: Dict[str, Any]) -> None:
        name = str(item.get("name") or "Unknown Loot")
        raw_id = str(item.get("id") or f"LOOT_{uuid.uuid4().hex[:8]}")
        safe_id = re.sub(r"[^A-Za-z0-9_\-]", "_", raw_id)[:50]
        if not safe_id:
            safe_id = f"LOOT_{uuid.uuid4().hex[:8]}"

        # Prevent duplicate IDs in the same running session by suffixing collisions.
        base_id = safe_id
        counter = 1
        while await self._session_entity_id_exists(safe_id):
            suffix = f"_{counter}"
            safe_id = f"{base_id[: max(1, 50 - len(suffix))]}{suffix}"
            counter += 1

        entity = WorldEntity(
            id=safe_id,
            session_id=self.game_id,
            template_id=None,
            entity_type="OBJECT",
            name=name,
            description=str(item.get("description") or f"Loot from battle: {name}"),
            current_scene_id=self.state.current_scene_id,
            spatial_position=item.get("spatial_position") or "on the ground",
            image_url=item.get("image_url"),
            item_type=item.get("item_type") or "PICKABLE",
            wearable_slots=item.get("wearable_slots"),
            is_in_inventory=False,
            is_hidden=False,
            is_portable=True,
            stat_modifier_strength=item.get("stat_modifier_strength"),
            stat_modifier_dexterity=item.get("stat_modifier_dexterity"),
            stat_modifier_intelligence=item.get("stat_modifier_intelligence"),
            stat_modifier_wisdom=item.get("stat_modifier_wisdom"),
            stat_modifier_charisma=item.get("stat_modifier_charisma"),
            stat_modifier_armor_class=item.get("stat_modifier_armor_class"),
            metadata_json={
                "hp_change": item.get("hp_change"),
                "mana_change": item.get("mana_change"),
                "stamina_change": item.get("stamina_change"),
            }
        )
        self.db.add(entity)

    async def _session_entity_id_exists(self, entity_id: str) -> bool:
        res = await self.db.execute(
            select(WorldEntity.pk).where(
                WorldEntity.session_id == self.game_id,
                WorldEntity.id == entity_id,
            ).limit(1)
        )
        return res.first() is not None

    async def _collect_existing_item_ids(self) -> set[str]:
        existing_ids: set[str] = {
            str(item.get("id"))
            for item in (self.avatar.inventory or [])
            if isinstance(item, dict) and item.get("id")
        }

        res = await self.db.execute(
            select(WorldEntity.id).where(WorldEntity.session_id == self.game_id)
        )
        existing_ids.update({row.id for row in res.all() if row.id})
        return existing_ids

    async def _resolve_loot_command(self, user_msg: str, combat: Dict[str, Any]) -> Optional[str]:
        low = user_msg.lower().strip()
        if not low.startswith("/loot"):
            return None

        parts = user_msg.split(" ", 2)
        action = parts[1].lower() if len(parts) > 1 else ""
        arg = parts[2].strip() if len(parts) > 2 else ""

        loot_items = list(combat.get("loot_items") or [])

        if action == "take":
            if not arg:
                return "Usage: /loot take <item id or item name>"
            idx = next((i for i, it in enumerate(loot_items) if str(it.get("id", "")).lower() == arg.lower() or str(it.get("name", "")).lower() == arg.lower()), -1)
            if idx < 0:
                return "Item not found in loot."
            picked = loot_items.pop(idx)
            inv = list(self.avatar.inventory or [])
            inv.append(picked)
            self.avatar.inventory = inv
            combat["loot_items"] = loot_items
            self._append_combat_log(combat, f"Loot taken: {picked.get('name', 'Unknown Item')}", "loot")
            self._set_combat_state(combat)
            return f"Added {picked.get('name', 'item')} to your inventory."

        if action in {"leave", "drop"}:
            if not arg:
                return "Usage: /loot leave <item id or item name>"
            idx = next((i for i, it in enumerate(loot_items) if str(it.get("id", "")).lower() == arg.lower() or str(it.get("name", "")).lower() == arg.lower()), -1)
            if idx < 0:
                return "Item not found in loot."
            dropped = loot_items.pop(idx)
            await self._spawn_scene_item(dropped)
            combat["loot_items"] = loot_items
            self._append_combat_log(combat, f"Loot dropped to scene: {dropped.get('name', 'Unknown Item')}", "loot")
            self._set_combat_state(combat)
            return f"{dropped.get('name', 'Item')} dropped to the current scene."

        if action == "done":
            for item in loot_items:
                await self._spawn_scene_item(item)
            combat["loot_items"] = []
            combat["loot_pending"] = False
            combat.pop("outcome", None)
            combat["status_note"] = "Combat resolved."
            
            # If nothing is left to do, clear the combat state entirely from all sources
            if not combat.get("active") and not combat.get("loot_pending") and not combat.get("outcome"):
                self.state.combat_json = None
                states = dict(self.state.entity_states or {})
                states.pop("__combat__", None)
                self.state.entity_states = states
                flag_modified(self.state, "entity_states")
                # Force commit to ensure state is persisted before final event
                await self.db.commit()
            else:
                self._set_combat_state(combat)
                
            self._append_combat_log(combat, combat["status_note"], "loot")
            return "Combat finished."

        return "Loot commands: /loot take <item>, /loot leave <item>, /loot done"

    async def _handle_combat_turn(self, user_msg: str) -> AsyncGenerator[str, None]:
        combat = self._read_combat_state()
        if not combat.get("active") and (combat.get("loot_pending") or combat.get("outcome")):
            loot_msg = await self._resolve_loot_command(user_msg, combat)
            if loot_msg:
                yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': loot_msg})}\n\n"
                if user_msg.lower().strip().startswith("/loot done"):
                    combat_after_loot = self._read_combat_state()
                    async for chunk in self._emit_combat_aftermath_narration(combat_after_loot):
                        yield chunk
                async for chunk in self._emit_combat_final(loot_msg):
                    yield chunk
                return
            msg = "Loot phase active. Use /loot take, /loot leave, or /loot done."
            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"
            async for chunk in self._emit_combat_final(msg):
                yield chunk
            return

        if not combat.get("active"):
            msg = "No active combat. Use /fight to start."
            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"
            async for chunk in self._emit_combat_final(msg):
                yield chunk
            return

        if combat.get("turn") != "player":
            msg = "Wait for your turn."
            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"
            async for chunk in self._emit_combat_final(msg):
                yield chunk
            return

        cmd = user_msg.strip().lower()
        enemy = combat.get("enemy", {})
        enemy_id = enemy.get("id")
        enemy_res = await self.db.execute(select(WorldEntity).where(WorldEntity.id == enemy_id, WorldEntity.session_id == self.game_id))
        enemy_ent = enemy_res.scalars().first()
        if not enemy_ent:
            combat["active"] = False
            combat["outcome"] = "victory"
            combat["status_note"] = "Enemy no longer exists."
            self._append_combat_log(combat, combat["status_note"], "outcome")
            self._set_combat_state(combat)
            async for chunk in self._emit_combat_final(combat["status_note"]):
                yield chunk
            return

        enemy_hp = int(combat.get("enemy", {}).get("hp") or 0)
        enemy_ac = 10 + int(combat.get("enemy", {}).get("armor_mod") or 0)

        if enemy_hp <= 0:
            msg = f"{enemy_ent.name} is already defeated."
            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"
            async for chunk in self._emit_combat_final(msg):
                yield chunk
            return

        action_msg = None
        if cmd == "attack" or cmd == "/attack" or cmd == "a" or cmd.startswith("attack ") or cmd.startswith("/attack "):
            roll = roll_attack(self.avatar, "dexterity", enemy_ac, self._player_damage_dice())
            if roll["is_hit"]:
                enemy_hp = max(0, enemy_hp - roll["damage_total"])
                dmg_bonus = int(roll.get("damage_bonus") or 0)
                dmg_bonus_str = f" + {dmg_bonus}" if dmg_bonus > 0 else (f" - {abs(dmg_bonus)}" if dmg_bonus < 0 else "")
                action_msg = (
                    f"{self.avatar.name} ATTACK ROLL: {roll['hit_roll']} + {roll['hit_modifier']} = {roll['hit_total']} vs AC {enemy_ac} -> HIT | "
                    f"DMG {roll['damage_dice_str']} ({' + '.join(str(r) for r in roll['damage_rolls'])}"
                    f"{dmg_bonus_str})"
                    f" = {roll['damage_total']}"
                )
            else:
                action_msg = f"{self.avatar.name} ATTACK ROLL: {roll['hit_roll']} + {roll['hit_modifier']} = {roll['hit_total']} vs AC {enemy_ac} -> MISS"
            self._append_combat_log(combat, action_msg, "player_action")
        elif cmd in {"run", "/run", "r"}:
            player_stats = calculate_total_stats(self.avatar)
            player_roll = random.randint(1, 20) + int(player_stats.get("dexterity", self.avatar.dexterity))
            enemy_roll = random.randint(1, 20) + int(combat.get("enemy", {}).get("dexterity_mod") or 0)
            if player_roll >= enemy_roll:
                combat["active"] = False
                combat["outcome"] = "escaped"
                combat["status_note"] = f"{self.avatar.name} escapes from combat."
                self._append_combat_log(combat, f"Run check: {player_roll} vs {enemy_roll}. Escape successful.", "run")
                self._set_combat_state(combat)
                yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': combat['status_note']})}\n\n"
                async for chunk in self._emit_combat_aftermath_narration(combat):
                    yield chunk
                async for chunk in self._emit_combat_final(combat["status_note"]):
                    yield chunk
                return
            action_msg = f"Run check failed ({player_roll} vs {enemy_roll}). {enemy_ent.name} keeps you in combat."
            self._append_combat_log(combat, action_msg, "run")
        elif cmd.startswith("/consume "):
            item_name = user_msg.split(" ", 1)[1].strip()
            action_msg = self._consume_item_now(item_name)
            self._sync_combat_player_snapshot(combat)
            self._append_combat_log(combat, action_msg, "consume")
        else:
            msg = "Combat active. Valid actions: Attack, Run, or /consume <item>."
            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"
            async for chunk in self._emit_combat_final(msg):
                yield chunk
            return

        if action_msg:
            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': action_msg})}\n\n"

        combat["enemy"]["hp"] = enemy_hp
        states = dict(self.state.entity_states or {})
        if enemy_id not in states:
            states[enemy_id] = {}
        states[enemy_id]["hp"] = enemy_hp
        self.state.entity_states = states
        flag_modified(self.state, "entity_states")

        if enemy_hp <= 0:
            combat["active"] = False
            combat["outcome"] = "victory"
            combat["status_note"] = f"{enemy_ent.name} is defeated."
            combat["loot_pending"] = True
            combat["loot_items"] = list(enemy.get("inventory") or enemy_ent.inventory or [])
            states = dict(self.state.entity_states or {})
            if enemy_id not in states:
                states[enemy_id] = {}
            states[enemy_id]["inventory"] = []
            self.state.entity_states = states
            flag_modified(self.state, "entity_states")
            self._append_combat_log(combat, combat["status_note"], "outcome")
            if combat.get("loot_items"):
                loot_msg = "Victory! Loot available. Use /loot take <item>, /loot leave <item>, /loot done"
                self._append_combat_log(combat, loot_msg, "loot")
                yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': loot_msg})}\n\n"
            self._set_combat_state(combat)
            async for chunk in self._emit_combat_final(combat["status_note"]):
                yield chunk
            return

        # NPC Fleeing logic (Improved: 10% chance if HP < 20%)
        enemy_max_hp_val = int(combat.get("enemy", {}).get("max_hp") or 100)
        if enemy_hp > 0 and enemy_hp <= (enemy_max_hp_val * 0.2):
            if random.random() < 0.10: # 10% chance
                combat["active"] = False
                combat["outcome"] = "victory"
                combat["status_note"] = f"{enemy_ent.name} flees in panic! You won the battle."
                self._append_combat_log(combat, combat["status_note"], "outcome")
                self._set_combat_state(combat)
                yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': combat['status_note']})}\n\n"
                async for chunk in self._emit_combat_aftermath_narration(combat):
                    yield chunk
                async for chunk in self._emit_combat_final(combat["status_note"]):
                    yield chunk
                return

        combat["turn"] = "enemy"
        self._set_combat_state(combat)
        async for chunk in self._resolve_enemy_turn():
            yield chunk
        async for chunk in self._emit_combat_final(None):
            yield chunk
        return

    async def _run_llm_cycle(self, user_msg: str, auto_visualize: bool, language: Optional[str] = None) -> AsyncGenerator[str, None]:
        _ = auto_visualize
        cycle_start = time.perf_counter()
        # Load Context and LLM Settings
        db_start = time.perf_counter()
        hist_res = await self.db.execute(select(ChatMessage).where(ChatMessage.session_id == self.state.session_id).order_by(ChatMessage.created_at.asc()))
        history = [{"role": m.role, "content": m.content} for m in hist_res.scalars().all()]
        
        # Fetch dynamic scene context (entities and exits) from the session snapshot
        scene_res = await self.db.execute(select(WorldScene).where(WorldScene.id == self.state.current_scene_id, WorldScene.session_id == self.game_id))
        current_scene = scene_res.scalars().first()

        ent_res = await self.db.execute(select(WorldEntity).where(
            WorldEntity.session_id == self.game_id, 
            WorldEntity.current_scene_id == self.state.current_scene_id,
            WorldEntity.is_hidden == False,
            WorldEntity.is_in_inventory == False
        ))
        entities = ent_res.scalars().all()
        exit_res = await self.db.execute(select(WorldExit).where(
            WorldExit.from_scene_id == self.state.current_scene_id,
            WorldExit.session_id == self.game_id
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

        # Build prompts using MemoryManager with session-local plot/rules
        mechanics_system_prompt = MemoryManager.build_context(
            self.avatar, self.adventure.original_prompt or "", history, 
            current_scene=current_scene,
            entities=entities,
            exits=exits,
            in_game_time=self.state.in_game_time,
            awards=self.adventure.awards,
            plot=self.state.plot or self.adventure.plot,
            rules=self.state.rules or self.adventure.rules,
            walkthrough=self.state.walkthrough or self.adventure.walkthrough,
            completed_condition=self.state.completed_condition or self.adventure.completed_condition,
            gameover_condition=self.state.gameover_condition or self.adventure.gameover_condition,
            time_system=self.state.time_system or self.adventure.time_system or "calendar",
            time_config=self.state.time_config or self.adventure.time_config,
            is_adventure_generator=self.adventure.is_adventure_generator,
            location_detail_level="concise",
        )[0]["content"]

        narration_system_prompt = MemoryManager.build_context(
            self.avatar, self.adventure.original_prompt or "", history,
            current_scene=current_scene,
            entities=entities,
            exits=exits,
            in_game_time=self.state.in_game_time,
            awards=self.adventure.awards,
            plot=self.state.plot or self.adventure.plot,
            rules=self.state.rules or self.adventure.rules,
            walkthrough=self.state.walkthrough or self.adventure.walkthrough,
            completed_condition=self.state.completed_condition or self.adventure.completed_condition,
            gameover_condition=self.state.gameover_condition or self.adventure.gameover_condition,
            time_system=self.state.time_system or self.adventure.time_system or "calendar",
            time_config=self.state.time_config or self.adventure.time_config,
            is_adventure_generator=self.adventure.is_adventure_generator,
            location_detail_level="full",
        )[0]["content"]
        notes_prompt_block = self._build_gm_notes_prompt_block()
        mechanics_system_prompt += notes_prompt_block
        narration_system_prompt += notes_prompt_block
        mechanics_awards = self._build_mechanics_awards()
        mechanics_prompt_chars = len(mechanics_system_prompt or "")
        narration_prompt_chars = len(narration_system_prompt or "")
        prompt_delta_chars = narration_prompt_chars - mechanics_prompt_chars
        prompt_reduction_pct = round((prompt_delta_chars / narration_prompt_chars) * 100, 2) if narration_prompt_chars else 0.0

        log_structured_event(
            "gm.turn.pipeline.context",
            adventure_id=self.adventure.id,
            game_id=self.game_id,
            operation="chat_turn",
            phase="context",
            db_prep_ms=round(db_duration * 1000, 2),
            history_count=len(history),
            history_chars=sum(len((m.get("content") or "")) for m in history),
            mechanics_system_prompt_chars=mechanics_prompt_chars,
            narration_system_prompt_chars=narration_prompt_chars,
            prompt_delta_chars=prompt_delta_chars,
            prompt_reduction_pct=prompt_reduction_pct,
            entities_count=len(entities),
            exits_count=len(exits),
            mechanics_awards_count=len(mechanics_awards),
            strict_rules=bool(self.adventure.strict_rules),
            is_adventure_generator=bool(self.adventure.is_adventure_generator),
        )


        # Bable Fish / Translation logic
        if language:
            logger.info(f"[Turn {self.game_id}] Bable Fish Active: Target Language = {language}")
            translation_instruction = (
                f"\n\n--- BABLE FISH TRANSLATION PROTOCOL ---\n"
                f"TARGET LANGUAGE: {language.upper()}\n"
                f"INSTRUCTION: You MUST translate ALL your output (narration, dialogue, descriptions) into {language}. "
                f"Do NOT respond in English or the original world language if it differs. "
                f"Note: The chat history may contain messages in various languages due to previous Bable Fish settings. "
                f"IGNORE those languages and strictly use {language} for the current turn. "
                f"The player has activated their Bable Fish, so everything they hear/see must be in {language}."
                f"\n----------------------------------------\n"
            )
            mechanics_system_prompt += translation_instruction
            narration_system_prompt += translation_instruction

        # Override for technical state evaluation (e.g. closing character sheet)
        if user_msg == "[EVALUATE STATE]":
            mechanics_system_prompt += (
                "\n\nIMPORTANT: The player just synchronized their character sheet or world state (e.g., closing a menu). "
                "This is a TECHNICAL turn. Respond only if something meaningful changed (e.g., equipment effects). "
                "Do NOT list available actions, do NOT provide suggestions, and do NOT use meta-formatting like '---' or 'You can:'. "
                "Keep the narrative flow natural if you speak at all."
            )
            narration_system_prompt += (
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
        
        small_model = llm_settings.get("small_model") or "gpt-4o-mini"
        complex_model = llm_settings.get("complex_model") or "gpt-4o"

        game_event = None
        pre_inventory_ids = set()
        response_text = ""

        # Pass 1: Mechanics (strict adventures), chat progression intent (normal chat),
        # or adventure-generator tool-intent pass (generator chat mode).
        run_mechanics_pass = self.adventure.strict_rules
        run_chat_progression_pass = not self.adventure.strict_rules and not self.adventure.is_adventure_generator
        run_generator_tool_intent_pass = self.adventure.is_adventure_generator and not self.adventure.strict_rules
        handled_generator_confirmation = False

        if run_generator_tool_intent_pass:
            pending_confirmation = self._get_pending_ag_image_confirmation()
            if pending_confirmation:
                handled_generator_confirmation = True
                decision = self._parse_ag_image_confirmation_decision(user_msg)
                pending_request = AdventureGenerationRequest.model_validate(
                    pending_confirmation.get("request") or {}
                )

                if decision == "unknown":
                    game_event = AdventureGeneratorToolIntent(
                        instant_narrative=(
                            "Before I start generation, confirm image mode: "
                            "reply with 'yes with images', 'yes without images', or 'cancel'."
                        )
                    )
                elif decision == "cancel":
                    self._clear_pending_ag_image_confirmation()
                    game_event = AdventureGeneratorToolIntent(
                        instant_narrative="Understood. Adventure generation was cancelled."
                    )
                else:
                    self._clear_pending_ag_image_confirmation()
                    if decision == "with_images":
                        pending_request.generate_scene_images = True
                    if decision == "without_images":
                        pending_request.generate_scene_images = False
                        msg = "SYSTEM: Image generation disabled by user confirmation. Continuing with text-only world generation."
                        self.db.add(ChatMessage(session_id=self.state.session_id, role="system", content=msg))
                        yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"

                    game_event = AdventureGeneratorToolIntent(
                        requested_adventure_generation=pending_request,
                        instant_narrative=(
                            "The Architect inclines his head and begins weaving your requested world."
                            if decision == "with_images"
                            else "The Architect inclines his head and begins weaving your world without auto-generated images."
                        ),
                    )
                    async for tool_chunk in self._stream_adventure_generator_tools(game_event):
                        yield tool_chunk

        if run_mechanics_pass:
            yield f"event: status\ndata: {json.dumps({'content': 'Validating rules...'})}\n\n"
            try:
                llm = GameMasterLLM(self.user, provider=small_model_provider, model_category="small")
            except ValueError as e:
                yield f"event: error\ndata: {json.dumps({'detail': str(e)})}\n\n"
                return
            
            mechanics_suffix = prompts.GM_MECHANICS_SUFFIX
            if self.adventure.rule_enforcement_mode == "story":
                mechanics_suffix = prompts.GM_STORY_MECHANICS_SUFFIX
            
            dynamic_instr = ""
            if self.adventure.allow_dynamic_items:
                dynamic_instr = (
                    "- To add an item directly to the player (even if it's not in the pre-generated world), use `new_inventory_items`. You can create new items on-the-fly.\n"
                    "- To place a new item in the current scene (e.g., something the player finds but hasn't taken yet), use `spawned_items`.\n"
                )

            mechanics_prompt = mechanics_system_prompt + "\n\n" + mechanics_suffix.format(
                quests_json=self._compact_json(self.state.quests or []),
                awards_json=self._compact_json(mechanics_awards),
                dynamic_items_instruction=dynamic_instr
            )
            
            pass1_start = time.perf_counter()
            logger.debug(f"[Turn {self.game_id}] [Pass 1] Calling small model: {small_model} via {small_model_provider}")
            try:
                game_event = await llm.aexecute_complex_task(
                    mechanics_prompt,
                    user_msg,
                    response_model=GameEvent,
                    model=small_model,
                )
            except Exception as e:
                user_safe_error = _friendly_llm_error_message(e)
                if user_safe_error:
                    yield f"event: error\ndata: {json.dumps({'detail': user_safe_error})}\n\n"
                    return
                raise
            pass1_duration = time.perf_counter() - pass1_start
            log_structured_event(
                "gm.turn.pipeline.pass",
                adventure_id=self.adventure.id,
                game_id=self.game_id,
                operation="chat_turn",
                phase="mechanics",
                duration_ms=round(pass1_duration * 1000, 2),
                model=small_model,
                provider=small_model_provider,
            )
            logger.debug(f"[Turn {self.game_id}] [Pass 1] Mechanics analysis took {pass1_duration:.4f}s")

            # Auto-trigger turn-based combat dialog when mechanics detect combat start.
            auto_combat_started = await self._auto_trigger_combat_from_gm(game_event)
            if auto_combat_started:
                msg = "Combat was detected by the Game Master. Turn-based combat has started."
                self.db.add(ChatMessage(session_id=self.state.session_id, role="system", content=msg))
                yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"
                async for chunk in self._emit_combat_final(msg):
                    yield chunk
                return
            
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
            
            # 2.5 Resolve Attack Rolls
            if game_event.requested_attacks:
                attack_results = []
                for req in game_event.requested_attacks:
                    # Fetch target AC
                    target_ac = 10
                    ac_reason = "Base AC 10"
                    target_id = req.target_id
                    
                    # Look in session state entities first
                    entity_states = self.state.entity_states or {}
                    target_state = entity_states.get(target_id, {})
                    
                    if "stat_modifier_armor_class" in target_state and target_state["stat_modifier_armor_class"] is not None:
                        mod = target_state["stat_modifier_armor_class"]
                        target_ac += mod
                        ac_reason = f"Base 10 + {mod} Mod"
                    else:
                        # Fetch from template if not in state
                        target_res = await self.db.execute(select(WorldEntity).where(WorldEntity.id == target_id, WorldEntity.session_id == self.game_id))
                        target_ent = target_res.scalars().first()
                        if target_ent and target_ent.stat_modifier_armor_class is not None:
                            mod = target_ent.stat_modifier_armor_class
                            target_ac += mod
                            ac_reason = f"Base 10 + {mod} Mod"
                    
                    roll = roll_attack(self.avatar, req.hit_stat, target_ac, req.damage_dice)
                    res = AttackResult(
                        attacker_id=req.attacker_id,
                        target_id=req.target_id,
                        hit_roll=roll["hit_roll"],
                        hit_modifier=roll["hit_modifier"],
                        hit_total=roll["hit_total"],
                        target_ac=target_ac,
                        is_hit=roll["is_hit"],
                        damage_dice_str=roll["damage_dice_str"],
                        damage_rolls=roll["damage_rolls"],
                        damage_dice_total=roll["damage_dice_total"],
                        damage_bonus=roll["damage_bonus"],
                        damage_total=roll["damage_total"],
                        reason=req.reason
                    )
                    attack_results.append(res)
                    
                    # Output as system message
                    hit_label = "HIT" if res.is_hit else "MISS"
                    roll_msg = (
                        f"⚔️ **ATTACK**: {res.reason}\n"
                        f"To-Hit: {res.hit_roll} + {res.hit_modifier} = **{res.hit_total}** (vs AC {res.target_ac}, {ac_reason}) -> **{hit_label}**"
                    )
                    if res.is_hit:
                        rolls_str = " + ".join(str(r) for r in res.damage_rolls)
                        bonus_str = f" + {res.damage_bonus}" if res.damage_bonus > 0 else (f" - {abs(res.damage_bonus)}" if res.damage_bonus < 0 else "")
                        roll_msg += f"\nDamage: {res.damage_dice_str} ({rolls_str}{bonus_str}) = **{res.damage_total}** HP dealt to {target_id}."
                        
                        # Apply damage to NPC HP in GameEvent for _apply_game_event to pick up
                        if not game_event.updated_entities:
                            game_event.updated_entities = []
                        
                        # Find current HP
                        current_hp = 50 # Default
                        if "hp" in target_state:
                            current_hp = target_state["hp"]
                        else:
                            # Re-fetch entity to get baseline HP if needed
                            target_res = await self.db.execute(select(WorldEntity).where(WorldEntity.id == target_id, WorldEntity.session_id == self.game_id))
                            target_ent = target_res.scalars().first()
                            if target_ent and target_ent.hp is not None:
                                current_hp = target_ent.hp
                        
                        new_hp = max(0, current_hp - res.damage_total)
                        game_event.updated_entities.append(WorldEntityUpdate(
                            entity_id=target_id,
                            hp=new_hp
                        ))
                    
                    self.db.add(ChatMessage(session_id=self.state.session_id, role="system", content=roll_msg))
                    yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': roll_msg})}\n\n"
                
                game_event.attack_results = attack_results

            # 3. Apply Changes
            pre_inventory_ids = {item.get("id") for item in (self.avatar.inventory or []) if item.get("id")}
            try:
                await self._apply_game_event(game_event)
                if game_event.game_completed:
                    await self._finalize_session("completed", game_event.status_note)
            except GameOverException as goe:
                await self._finalize_session("game_over", str(goe))
                # Ensure the narration knows about the game over
                game_event.game_over = True
                game_event.status_note = str(goe)

        elif run_generator_tool_intent_pass and not handled_generator_confirmation:
            yield f"event: status\ndata: {json.dumps({'content': 'Checking generator tools...'})}\n\n"
            try:
                llm = GameMasterLLM(self.user, provider=small_model_provider, model_category="small")
            except ValueError as e:
                yield f"event: error\ndata: {json.dumps({'detail': str(e)})}\n\n"
                return

            # Provide compact prior chat context so tool parameters can be derived from discussed details.
            history_lines = []
            for msg in history[-12:]:
                role = msg.get("role")
                if role not in ("user", "assistant"):
                    continue
                content = (msg.get("content") or "").strip()
                if not content:
                    continue
                history_lines.append(f"{role.upper()}: {content[:400]}")

            tool_context_block = ""
            if history_lines:
                tool_context_block = (
                    "\n\nRECENT CHAT CONTEXT (use this to infer generation parameters):\n"
                    + "\n".join(history_lines)
                )

            tool_intent_prompt = (
                mechanics_system_prompt
                + "\n\n"
                + prompts.GM_ADVENTURE_GENERATOR_TOOL_INTENT_SUFFIX
                + tool_context_block
            )
            try:
                generator_intent_start = time.perf_counter()
                game_event = await llm.aexecute_complex_task(
                    tool_intent_prompt,
                    user_msg,
                    response_model=AdventureGeneratorToolIntent,
                    model=small_model,
                )
                log_structured_event(
                    "gm.turn.pipeline.pass",
                    adventure_id=self.adventure.id,
                    game_id=self.game_id,
                    operation="chat_turn",
                    phase="generator_tool_intent",
                    duration_ms=round((time.perf_counter() - generator_intent_start) * 1000, 2),
                    model=small_model,
                    provider=small_model_provider,
                )
            except Exception as e:
                user_safe_error = _friendly_llm_error_message(e)
                if user_safe_error:
                    yield f"event: error\ndata: {json.dumps({'detail': user_safe_error})}\n\n"
                    return
                raise

            if (
                not game_event.requested_adventure_generation
                and self._is_generation_retry_request(user_msg)
            ):
                last_request = self._get_last_ag_generation_request()
                if last_request:
                    if self._get_last_ag_generation_error() == "token_limit":
                        last_request.generate_scene_images = False
                    game_event.requested_adventure_generation = last_request
                    if not game_event.instant_narrative:
                        game_event.instant_narrative = "Understood. I will retry the last adventure generation now."

            if game_event.requested_adventure_generation:
                self._set_pending_ag_image_confirmation(game_event.requested_adventure_generation)
                confirmation_msg = (
                    "SYSTEM: Before I start generation, please confirm image mode: "
                    "reply with 'yes with images', 'yes without images', or 'cancel'."
                )
                self.db.add(ChatMessage(session_id=self.state.session_id, role="system", content=confirmation_msg))
                yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': confirmation_msg})}\n\n"
                game_event.requested_adventure_generation = None
                game_event.instant_narrative = "The Architect pauses at the threshold, awaiting your confirmation."

            if (
                game_event.request_available_image_styles
                or game_event.request_available_tones
                or game_event.requested_adventure_generation
            ):
                async for tool_chunk in self._stream_adventure_generator_tools(game_event):
                    yield tool_chunk

        elif run_chat_progression_pass:
            yield f"event: status\ndata: {json.dumps({'content': 'Checking progression...'})}\n\n"
            try:
                llm = GameMasterLLM(self.user, provider=small_model_provider, model_category="small")
            except ValueError as e:
                yield f"event: error\ndata: {json.dumps({'detail': str(e)})}\n\n"
                return

            reduced_quests = self._build_chat_progression_quests()
            reduced_awards = self._build_chat_progression_awards(mechanics_awards)
            reduced_npcs = self._build_chat_progression_npcs(entities)

            progression_prompt = self._build_chat_rule_pass_prompt(
                quests=reduced_quests,
                awards=reduced_awards,
                npcs=reduced_npcs,
            )

            if language:
                progression_prompt += f"\n\nLANGUAGE CONTEXT: Current player language is {language}."

            progression_start = time.perf_counter()
            try:
                progression_intent = await llm.aexecute_complex_task(
                    progression_prompt,
                    user_msg,
                    response_model=AdventureGeneratorToolIntent,
                    model=small_model,
                )
            except Exception as e:
                user_safe_error = _friendly_llm_error_message(e)
                if user_safe_error:
                    yield f"event: error\ndata: {json.dumps({'detail': user_safe_error})}\n\n"
                    return
                raise

            log_structured_event(
                "gm.turn.pipeline.pass",
                adventure_id=self.adventure.id,
                game_id=self.game_id,
                operation="chat_turn",
                phase="chat_progression",
                duration_ms=round((time.perf_counter() - progression_start) * 1000, 2),
                model=small_model,
                provider=small_model_provider,
                reduced_payload_chars=len(progression_prompt),
                quest_count=len(reduced_quests),
                award_count=len(reduced_awards),
                npc_count=len(reduced_npcs),
                notes_count=min(len(self._get_gm_notes()), GM_NOTES_PROMPT_MAX_ITEMS),
            )

            game_event = self._build_progression_event(progression_intent)

            try:
                await self._apply_game_event(game_event)
                if game_event.game_completed:
                    await self._finalize_session("completed", game_event.status_note)
                elif game_event.game_over:
                    await self._finalize_session("game_over", game_event.status_note or "Game over.")
            except GameOverException as goe:
                await self._finalize_session("game_over", str(goe))
                game_event.game_over = True
                game_event.status_note = str(goe)

        # Pass 2: Narration
        if game_event and game_event.instant_narrative:
            logger.info(f"[Turn {self.game_id}] Short-circuit active: Using instant_narrative from Pass 1.")
            response_text = game_event.instant_narrative
            # Stream the instant narrative back as chunks to maintain UI consistency
            words = response_text.split(" ")
            for i, word in enumerate(words):
                chunk_str = word + (" " if i < len(words)-1 else "")
                yield f"event: chunk\ndata: {json.dumps({'content': chunk_str})}\n\n"
                # Small delay to simulate "typing" but much faster than an actual LLM pass
                await asyncio.sleep(0.02)
        else:
            yield f"event: status\ndata: {json.dumps({'content': 'Generating narrative...'})}\n\n"
            try:
                llm = GameMasterLLM(self.user, provider=complex_model_provider, model_category="complex")
            except ValueError as e:
                yield f"event: error\ndata: {json.dumps({'detail': str(e)})}\n\n"
                return
            narration_prompt = (
                narration_system_prompt + "\n\n" + 
                prompts.GM_NARRATION_TECHNICAL_OUTCOME_PREFIX.format(
                    outcome_json=game_event.model_dump_json() if game_event else "{}"
                ) + "\n\n" +
                prompts.GM_NARRATION_MANDATORY_FORMATTING
            )

            if run_chat_progression_pass:
                narration_prompt += "\n\n" + prompts.GM_CHAT_NARRATION_SUFFIX
            
            if language:
                narration_prompt += f"\n\nREMINDER: Respond in {language.upper()} only."
            
            pass2_start = time.perf_counter()
            logger.debug(f"[Turn {self.game_id}] [Pass 2] Calling complex model: {complex_model} via {complex_model_provider}")
            try:
                stream = await llm.stream_simple_task(narration_prompt, user_msg, complex_model)

                async for chunk in stream:
                    delta = chunk.choices[0].delta.content or ""
                    if delta:
                        response_text += delta
                        yield f"event: chunk\ndata: {json.dumps({'content': delta})}\n\n"
            except Exception as e:
                user_safe_error = _friendly_llm_error_message(e)
                if user_safe_error:
                    yield f"event: error\ndata: {json.dumps({'detail': user_safe_error})}\n\n"
                    return
                raise
            
            pass2_duration = time.perf_counter() - pass2_start
            log_structured_event(
                "gm.turn.pipeline.pass",
                adventure_id=self.adventure.id,
                game_id=self.game_id,
                operation="chat_turn",
                phase="narration",
                duration_ms=round(pass2_duration * 1000, 2),
                model=complex_model,
                provider=complex_model_provider,
            )
            logger.debug(f"[Turn {self.game_id}] [Pass 2] Narration took {pass2_duration:.4f}s")

        log_structured_event(
            "gm.turn.pipeline.cycle_total",
            adventure_id=self.adventure.id,
            game_id=self.game_id,
            operation="chat_turn",
            phase="cycle_total",
            duration_ms=round((time.perf_counter() - cycle_start) * 1000, 2),
        )

        if run_generator_tool_intent_pass and not (response_text or "").strip():
            fallback = "The Architect inclines his head, the Construct awaiting your next directive."
            if game_event and getattr(game_event, "requested_adventure_generation", None):
                tool_results = getattr(game_event, "tool_results", None)
                generation_success = getattr(tool_results, "generation_success", None) if tool_results else None
                if generation_success is True:
                    fallback = "The Architect steps aside as your new world settles into the library archives."
                elif generation_success is False:
                    fallback = "The Architect frowns as unstable code dissipates from the unfinished world."
                else:
                    fallback = "The Architect watches the Construct flare to life as your requested world takes shape."
            elif game_event and (
                getattr(game_event, "request_available_image_styles", False)
                or getattr(game_event, "request_available_tones", False)
            ):
                fallback = "The Architect gestures toward the floating catalogs, inviting your selection."

            response_text = fallback
            yield f"event: chunk\ndata: {json.dumps({'content': fallback})}\n\n"

        # Finalize
        assistant_chat = ChatMessage(session_id=self.state.session_id, role="assistant", content=response_text)
        self.db.add(assistant_chat)
        
        # Add system messages for stat changes and items
        if isinstance(game_event, GameEvent):
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

                    if update.stamina is not None and match and match.stamina is not None:
                        diff = update.stamina - match.stamina
                        if diff != 0:
                            verb = "gains" if diff > 0 else "loses"
                            msg = f"{ent_name} {verb} {abs(diff)} Stamina."
                            self.db.add(ChatMessage(session_id=self.state.session_id, role="system", content=msg))
                            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"

                    if update.mana is not None and match and match.mana is not None:
                        diff = update.mana - match.mana
                        if diff != 0:
                            verb = "gains" if diff > 0 else "loses"
                            msg = f"{ent_name} {verb} {abs(diff)} Mana."
                            self.db.add(ChatMessage(session_id=self.state.session_id, role="system", content=msg))
                            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"

            # 3. Items
            if game_event.new_inventory_items:
                for item in game_event.new_inventory_items:
                    # Only announce if it's a new item (not already in pre-inventory)
                    if item.id and item.id in pre_inventory_ids:
                        continue
                        
                    msg_text = f"Added {item.name} to your inventory."
                    self.db.add(ChatMessage(session_id=self.state.session_id, role="system", content=msg_text))
                    yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg_text})}\n\n"

            if game_event.removed_inventory_item_ids:
                for item_id in game_event.removed_inventory_item_ids:
                    # Resolve item name from pre-turn inventory (where the item actually was)
                    item_name = item_id
                    
                    # 1. Look in avatar's current inventory (which still has items before commit)
                    match = next((i for i in (self.avatar.inventory or []) if i.get("id") == item_id), None)
                    if match:
                        item_name = match.get("name", item_id)
                    else:
                        # 2. Fallback: search in template entities if it was a starting object
                        target_res = await self.db.execute(select(WorldEntity).where(WorldEntity.id == item_id, WorldEntity.template_id == self.state.template_id))
                        target_ent = target_res.scalars().first()
                        if target_ent:
                            item_name = target_ent.name
                    
                    msg_text = f"Removed {item_name} from your inventory."
                    self.db.add(ChatMessage(session_id=self.state.session_id, role="system", content=msg_text))
                    yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg_text})}\n\n"

        await self.db.commit()
        
        final_data = jsonable_encoder({
            'sheet': await AdventureLogic.build_sheet_snapshot(self.avatar, self.state, self.db), 
            'entities': await AdventureLogic.build_session_entities(self.db, self.state),
            'combat': AdventureLogic.get_combat_snapshot(self.state),
            'game_over': (self.state.session.status == 'game_over') if self.state.session else False,
            'game_completed': (self.state.session.status == 'completed') if self.state.session else False,
            'status_note': self.state.session.status_note if self.state.session else None,
            'status': 'success'
        })
        yield f"event: final\ndata: {json.dumps(final_data)}\n\n"

    async def _apply_game_event(self, event: GameEvent):
        """Applies technical mutations from a GameEvent to the database and session state."""
        existing_item_ids = await self._collect_existing_item_ids()

        if event.new_inventory_items:
            filtered_inventory_items = []
            for item in event.new_inventory_items:
                if item.id and item.id in existing_item_ids:
                    logger.info(
                        "[Turn %s] Skipping duplicate generated inventory item id: %s",
                        self.game_id,
                        item.id,
                    )
                    continue
                filtered_inventory_items.append(item)
                if item.id:
                    existing_item_ids.add(item.id)
            event.new_inventory_items = filtered_inventory_items

        if event.spawned_items:
            filtered_spawned_items = []
            for item in event.spawned_items:
                if item.id and item.id in existing_item_ids:
                    logger.info(
                        "[Turn %s] Skipping duplicate generated spawned item id: %s",
                        self.game_id,
                        item.id,
                    )
                    continue
                filtered_spawned_items.append(item)
                if item.id:
                    existing_item_ids.add(item.id)
            event.spawned_items = filtered_spawned_items

        RuleEngine.apply_event(self.avatar, event)
        
        state_dirty = False
        if event.new_scene_id and event.new_scene_id != self.state.current_scene_id:
            old_scene_id = self.state.current_scene_id
            self.state.current_scene_id = event.new_scene_id
            state_dirty = True
            
            # Map Update
            try:
                world_map = await AdventureLogic.get_or_create_map(self.db, self.state.template_id)
                # 1. Register exit between scenes
                MapEngine.register_exit(world_map, old_scene_id, event.new_scene_id, exit_label=event.exit_label or "")
                # 2. Register visit to the new scene
                # Use session snapshot for scene data
                scene_res = await self.db.execute(select(WorldScene).where(WorldScene.id == event.new_scene_id, WorldScene.session_id == self.game_id))
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
                if update.inventory is not None: 
                    states[eid]["inventory"] = [i.model_dump(exclude_none=True) for i in update.inventory]
                state_dirty = True
        
        if event.deleted_entities:
            for eid in event.deleted_entities:
                if eid not in states: states[eid] = {}
                states[eid]["is_hidden"] = True
                state_dirty = True
        
        if event.spawned_items:
            for item in event.spawned_items:
                await self._spawn_scene_item(item.model_dump(exclude_none=True))
            state_dirty = True

        if event.remember_notes or event.forget_notes or event.clear_notes:
            self._apply_gm_notes_update(event.remember_notes, event.forget_notes, bool(event.clear_notes))

        # Quest Updates
        if event.completed_quest_ids:
            new_quests = deepcopy(self.state.quests or [])
            modified = False
            for qid in event.completed_quest_ids:
                for q in new_quests:
                    if q.get("id") == qid and q.get("status") != "completed":
                        q["status"] = "completed"
                        modified = True
            
            if modified:
                self.state.quests = new_quests
                state_dirty = True

        if event.earned_award_keys:
            now = datetime.utcnow().isoformat()
            award_defs = {
                (aw.get("key") or ""): aw
                for aw in (self.adventure.awards or [])
                if aw.get("key")
            }
            user_awards = list(self.user.earned_awards or [])
            modified = False
            for key in event.earned_award_keys:
                if not key:
                    continue
                already_earned = any(
                    ea.get("key") == key
                    and (ea.get("template_id") == self.adventure.id or ea.get("adventure_id") == self.adventure.id)
                    for ea in user_awards
                )
                if already_earned:
                    continue

                aw = award_defs.get(key, {})
                user_awards.append(
                    {
                        "key": key,
                        "title": aw.get("title") or key,
                        "description": aw.get("description"),
                        "tier": aw.get("tier"),
                        "template_id": self.adventure.id,
                        "adventure_id": self.adventure.id,
                        "adventure_title": self.adventure.title,
                        "session_id": self.state.session_id,
                        "earned_at": now,
                    }
                )
                modified = True

            if modified:
                self.user.earned_awards = user_awards
                flag_modified(self.user, "earned_awards")

        # Deterministic Quest Sync (Post-LLM check)
        det_completed = QuestManager.evaluate_quests(self.avatar, self.state)
        if det_completed:
            new_quests = deepcopy(self.state.quests or [])
            modified = False
            for qid in det_completed:
                for q in new_quests:
                    if q.get("id") == qid and q.get("status") != "completed":
                        q["status"] = "completed"
                        logger.info(f"[Turn {self.game_id}] Deterministic Quest Completion: {qid}")
                        modified = True
            if modified:
                self.state.quests = new_quests
                state_dirty = True

        # RPG Completion Logic: Check if all main quests are finished
        if state_dirty:
            all_main_done = True
            main_quest_exists = False
            for q in (self.state.quests or []):
                if q.get("is_main"):
                    main_quest_exists = True
                    if q.get("status") != "completed":
                        all_main_done = False
                        break
            
            if main_quest_exists and all_main_done:
                event.game_completed = True
                if not event.status_note:
                    event.status_note = "Congratulations! You have completed all main objectives."

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
            
        await self._apply_adventure_generator_tools(event)

        await self.db.flush()

    async def _emit_system_message(
        self,
        message: str,
        stream_callback: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> None:
        """Persist a system message and optionally stream it via callback."""
        self.db.add(ChatMessage(session_id=self.state.session_id, role="system", content=message))
        await self.db.flush()
        if stream_callback:
            await stream_callback(message)

    def _get_pending_ag_image_confirmation(self) -> Optional[Dict[str, Any]]:
        exit_states = dict(self.state.exit_states or {})
        pending = exit_states.get(AG_IMAGE_CONFIRMATION_STATE_KEY)
        if not isinstance(pending, dict):
            return None
        if not isinstance(pending.get("request"), dict):
            return None
        return pending

    def _set_pending_ag_image_confirmation(self, request: AdventureGenerationRequest) -> None:
        exit_states = dict(self.state.exit_states or {})
        exit_states[AG_IMAGE_CONFIRMATION_STATE_KEY] = {
            "request_id": str(uuid.uuid4()),
            "request": request.model_dump(),
        }
        self.state.exit_states = exit_states
        flag_modified(self.state, "exit_states")

    def _clear_pending_ag_image_confirmation(self) -> None:
        exit_states = dict(self.state.exit_states or {})
        if AG_IMAGE_CONFIRMATION_STATE_KEY in exit_states:
            exit_states.pop(AG_IMAGE_CONFIRMATION_STATE_KEY, None)
            self.state.exit_states = exit_states
            flag_modified(self.state, "exit_states")

    def _parse_ag_image_confirmation_decision(self, user_msg: str) -> str:
        text = (user_msg or "").strip().lower()
        if not text:
            return "unknown"

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

    def _is_generation_retry_request(self, user_msg: str) -> bool:
        text = (user_msg or "").strip().lower()
        if not text:
            return False
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

    def _set_last_ag_generation_request(self, request: AdventureGenerationRequest) -> None:
        exit_states = dict(self.state.exit_states or {})
        exit_states[AG_LAST_REQUEST_STATE_KEY] = request.model_dump()
        self.state.exit_states = exit_states
        flag_modified(self.state, "exit_states")

    def _get_last_ag_generation_request(self) -> Optional[AdventureGenerationRequest]:
        exit_states = dict(self.state.exit_states or {})
        raw = exit_states.get(AG_LAST_REQUEST_STATE_KEY)
        if not isinstance(raw, dict):
            return None
        try:
            return AdventureGenerationRequest.model_validate(raw)
        except Exception:
            return None

    def _set_last_ag_generation_error(self, error_type: Optional[str]) -> None:
        exit_states = dict(self.state.exit_states or {})
        if error_type:
            exit_states[AG_LAST_ERROR_STATE_KEY] = error_type
        else:
            exit_states.pop(AG_LAST_ERROR_STATE_KEY, None)
        self.state.exit_states = exit_states
        flag_modified(self.state, "exit_states")

    def _get_last_ag_generation_error(self) -> Optional[str]:
        exit_states = dict(self.state.exit_states or {})
        value = exit_states.get(AG_LAST_ERROR_STATE_KEY)
        return value if isinstance(value, str) and value else None

    async def _stream_adventure_generator_tools(self, event) -> AsyncGenerator[str, None]:
        progress_queue: asyncio.Queue[str] = asyncio.Queue()

        async def _stream_progress_message(message: str) -> None:
            await progress_queue.put(message)

        tool_task = asyncio.create_task(
            self._apply_adventure_generator_tools(
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

    async def _apply_adventure_generator_tools(
        self,
        event,
        stream_callback: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> None:
        """Executes adventure-generator tool requests from a structured event/intent model."""
        if not self.adventure.is_adventure_generator:
            return

        from backend.engine.adventure_generator_service import AdventureGeneratorService
        if event.request_available_image_styles:
            styles = await AdventureGeneratorService.get_available_image_styles(self.user)
            if not event.tool_results:
                event.tool_results = ToolResults()
            event.tool_results.available_image_styles = styles

            msg = f"SYSTEM: Available Image Styles: {', '.join(styles)}"
            await self._emit_system_message(msg, stream_callback=stream_callback)

        if event.request_available_tones:
            tones = await AdventureGeneratorService.get_available_tones(self.user)
            if not event.tool_results:
                event.tool_results = ToolResults()
            event.tool_results.available_tones = tones

            msg = f"SYSTEM: Available Tones: {', '.join(tones)}"
            await self._emit_system_message(msg, stream_callback=stream_callback)

        if event.requested_adventure_generation:
            self._set_last_ag_generation_request(event.requested_adventure_generation)

            async def _post_generation_system_message(status: str) -> None:
                msg = f"SYSTEM: Adventure Generator: {status}"
                await self._emit_system_message(msg, stream_callback=stream_callback)

            try:
                await _post_generation_system_message(
                    f"Preparing generation for '{event.requested_adventure_generation.title}'..."
                )

                new_adv_id = await AdventureGeneratorService.generate_adventure(
                    self.db,
                    self.user,
                    event.requested_adventure_generation,
                    progress_callback=_post_generation_system_message,
                )
                if not event.tool_results:
                    event.tool_results = ToolResults()
                event.tool_results.generation_success = True
                event.tool_results.new_adventure_id = new_adv_id
                self._set_last_ag_generation_error(None)

                await _post_generation_system_message("Generation finished successfully.")

                msg = f"SYSTEM: Adventure '{event.requested_adventure_generation.title}' generated successfully and added to library (ID: {new_adv_id})."
                await self._emit_system_message(msg, stream_callback=stream_callback)
            except Exception as e:
                if not event.tool_results:
                    event.tool_results = ToolResults()
                event.tool_results.generation_success = False
                event.tool_results.generation_error = str(e)
                self._set_last_ag_generation_error(_llm_error_type(e))

                await _post_generation_system_message("Generation aborted due to an error.")

                user_safe_error = _friendly_llm_error_message(e)
                if user_safe_error:
                    msg = f"SYSTEM: {user_safe_error}"
                else:
                    msg = f"SYSTEM ERROR: Adventure generation failed: {e}"
                await self._emit_system_message(msg, stream_callback=stream_callback)

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
