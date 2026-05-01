import json
import logging
import uuid
import re
import time
import random
from copy import deepcopy
from backend.engine.quest_manager import QuestManager
from datetime import datetime
from typing import Optional, Dict, Any, AsyncGenerator

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
from backend.engine.rule_engine import RuleEngine, GameEvent, GameOverException, SkillCheckResult, AttackResult, WorldEntityUpdate, RESOURCE_CAP
from backend.engine.map_engine import MapEngine
from backend.engine.memory_manager import MemoryManager
from backend.engine.command_parser import CommandParser
from backend.engine.skill_check import roll_skill_check, roll_attack
from backend.engine.stat_aggregator import calculate_total_stats
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
        self.stop_requested = False
        self.turn_language: Optional[str] = None

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
            async for chunk in self._handle_debug(user_msg): yield chunk
            return

        # Dedicated encounter entry point for RPG mode.
        if user_msg.lower().startswith("/fight"):
            async for chunk in self._handle_fight_start(user_msg):
                yield chunk
            return

        # Route turn-based combat actions while combat is active.
        if self._has_combat_phase():
            async for chunk in self._handle_combat_turn(user_msg):
                yield chunk
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
        async def _run_llm_cycle_with_lang(msg, av):
            async for c in self._run_llm_cycle(msg, av, language=language):
                yield c
        
        async for chunk in _run_llm_cycle_with_lang(user_msg, auto_visualize):
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
        final_data = jsonable_encoder({
            'messages': [{'role': 'system', 'content': debug_info}],
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
                response = "You cannot take that."

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
        return bool(combat.get("active") or combat.get("loot_pending"))

    def _set_combat_state(self, combat: Dict[str, Any]) -> None:
        states = dict(self.state.entity_states or {})
        states["__combat__"] = combat
        self.state.entity_states = states
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

        target_hint = user_msg.split(" ", 1)[1].strip() if " " in user_msg else ""
        target = await self._find_fight_target(target_hint)
        if not target:
            msg = "No enemy is available in this scene."
            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"
            async for chunk in self._emit_combat_final(msg):
                yield chunk
            return

        enemy_hp = self._entity_stat(target, "hp", 50)
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
        if random.random() < 0.5:
            bonus = 20
            self.avatar.hp = max(0, self.avatar.hp - bonus)
            text = f"Special Event: {enemy_name} performs a special attack for +{bonus} damage!"
            self._append_combat_log(combat, text, "special")
            if self.avatar.hp <= 0:
                raise GameOverException(f"{self.avatar.name} has fallen! Game Over.")
            return text

        text = f"Special Event: {enemy_name} reels in visible pain. The Game Master shifts the scene tone."
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

        entity = WorldEntity(
            id=safe_id,
            session_id=self.game_id,
            template_id=None,
            entity_type="OBJECT",
            name=name,
            description=str(item.get("description") or f"Loot from battle: {name}"),
            current_scene_id=self.state.current_scene_id,
            spatial_position="on the ground",
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
        )
        self.db.add(entity)

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
            combat["status_note"] = "Combat resolved. Remaining loot has been moved to the scene."
            self._append_combat_log(combat, combat["status_note"], "loot")
            self._set_combat_state(combat)
            return combat["status_note"]

        return "Loot commands: /loot take <item>, /loot leave <item>, /loot done"

    async def _handle_combat_turn(self, user_msg: str) -> AsyncGenerator[str, None]:
        combat = self._read_combat_state()
        if not combat.get("active") and combat.get("loot_pending"):
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

        action_msg = None
        if cmd in {"attack", "/attack", "a"}:
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

        if enemy_hp <= max(1, int(combat.get("enemy", {}).get("max_hp") or 1) // 4):
            flee_roll = random.randint(1, 20) + int(combat.get("enemy", {}).get("dexterity_mod") or 0)
            if flee_roll >= 16:
                combat["active"] = False
                combat["outcome"] = "victory"
                combat["status_note"] = f"{enemy_ent.name} flees in panic."
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

        # Build prompt using MemoryManager with session-local plot/rules
        system_prompt = MemoryManager.build_context(
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
            time_config=self.state.time_config or self.adventure.time_config
        )[0]["content"]

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
            system_prompt += translation_instruction

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
        
        small_model = llm_settings.get("small_model") or "gpt-4o-mini"
        complex_model = llm_settings.get("complex_model") or "gpt-4o"

        game_event = None
        pre_inventory_ids = set()
        response_text = ""

        # Pass 1: Mechanics
        if self.adventure.strict_rules:
            yield f"event: status\ndata: {json.dumps({'content': 'Validating rules...'})}\n\n"
            try:
                llm = GameMasterLLM(self.user, provider=small_model_provider, model_category="small")
            except ValueError as e:
                yield f"event: error\ndata: {json.dumps({'detail': str(e)})}\n\n"
                return
            
            mechanics_suffix = prompts.GM_MECHANICS_SUFFIX
            if self.adventure.rule_enforcement_mode == "story":
                mechanics_suffix = prompts.GM_STORY_MECHANICS_SUFFIX
            
            mechanics_prompt = system_prompt + "\n\n" + mechanics_suffix.format(
                quests_json=json.dumps(self.state.quests or [], indent=2),
                awards_json=json.dumps(self.adventure.awards or [], indent=2)
            )
            
            pass1_start = time.perf_counter()
            logger.debug(f"[Turn {self.game_id}] [Pass 1] Calling small model: {small_model} via {small_model_provider}")
            game_event = await llm.aexecute_complex_task(mechanics_prompt, user_msg, response_model=GameEvent, model=small_model)
            pass1_duration = time.perf_counter() - pass1_start
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
        
        if language:
            narration_prompt += f"\n\nREMINDER: Respond in {language.upper()} only."
        
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
