from __future__ import annotations

import asyncio
import json
import logging
import random
import re
import time
import uuid
from copy import deepcopy
from typing import TYPE_CHECKING, Any, AsyncGenerator, Optional

from fastapi.encoders import jsonable_encoder
from sqlalchemy import and_, or_, select
from sqlalchemy.orm.attributes import flag_modified

from backend.api.routes.adventures.logic import AdventureLogic
from backend.core import prompts
from backend.core.config import settings
from backend.core.llm_logger import log_structured_event
import backend.api.routes.adventures.gameplay_logic as gl
from backend.core.prompts import (
    COMBAT_SPECIAL_EVENT_SYSTEM_PROMPT,
    COMBAT_SPECIAL_EVENT_USER_PROMPT_TEMPLATE,
)
from backend.engine.rule_engine import (
    RESOURCE_CAP,
    AttackResult,
    GameEvent,
    GameOverException,
    WorldEntityUpdate,
)
from backend.engine.stat_aggregator import calculate_total_stats
from backend.models.avatar import Avatar
from backend.models.chat import ChatMessage
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene

if TYPE_CHECKING:
    from backend.api.routes.adventures.gameplay_logic import GameTurnManager

logger = logging.getLogger(__name__)


class TurnCombatManager:
    """Manages combat encounters, fight turns, rolls, special events, and loot."""

    def __init__(self, manager: GameTurnManager) -> None:
        self.manager = manager

    @property
    def db(self):
        return self.manager.db

    @property
    def game_id(self):
        return self.manager.game_id

    @property
    def user(self):
        return self.manager.user

    @property
    def state(self):
        return self.manager.state

    @property
    def avatar(self):
        return self.manager.avatar

    @property
    def adventure(self):
        return self.manager.adventure

    @property
    def turn_language(self):
        return self.manager.turn_language

    @property
    def _combat_state_helper(self):
        return self.manager._combat_state_helper

    def _build_map_payload(self, *args, **kwargs):
        return self.manager._build_map_payload(*args, **kwargs)

    def _build_prompt_suggestions_payload(self, *args, **kwargs):
        return self.manager._build_prompt_suggestions_payload(*args, **kwargs)

    def _build_terminal_flags_payload(self, *args, **kwargs):
        return self.manager._build_terminal_flags_payload(*args, **kwargs)

    async def _finalize_session(self, *args, **kwargs):
        return await self.manager._finalize_session(*args, **kwargs)

    async def _generate_prompt_suggestions(self, *args, **kwargs):
        return await self.manager._generate_prompt_suggestions(*args, **kwargs)

    async def _load_last_assistant_message(self, *args, **kwargs):
        return await self.manager._load_last_assistant_message(*args, **kwargs)

    async def _save_chat_message(self, *args, **kwargs):
        return await self.manager._save_chat_message(*args, **kwargs)

    def _read_combat_state(self) -> dict[str, Any]:
        return self._combat_state_helper.read_combat_state()

    def _is_combat_active(self) -> bool:
        return self._combat_state_helper.is_combat_active()

    def _has_combat_phase(self) -> bool:
        return self._combat_state_helper.has_combat_phase()

    def _set_combat_state(self, combat: dict[str, Any]) -> None:
        self._combat_state_helper.set_combat_state(combat)

    async def _find_fight_target(self, target_hint: str) -> WorldEntity | None:
        ent_res = await self.db.execute(
            select(WorldEntity).where(
                WorldEntity.session_id == self.game_id,
                WorldEntity.current_scene_id == self.state.current_scene_id,
                WorldEntity.entity_type.in_(["NPC", "npc"]),
                WorldEntity.is_hidden.is_(False),
                WorldEntity.is_in_inventory.is_(False),
            )
        )
        npcs = ent_res.scalars().all()
        if not npcs:
            return None

        target_hint = (target_hint or "").strip()
        states = self.state.entity_states or {}

        # Filter out NPCs that are defeated in session state (permanent)
        def _is_npc_defeated(npc: WorldEntity) -> bool:
            npc_state = states.get(npc.id, {}) or {}
            if npc_state.get("is_defeated"):
                return True
            # Also respect is_hidden override from entity_states
            if npc_state.get("is_hidden"):
                return True
            return False

        eligible_npcs = [npc for npc in npcs if not _is_npc_defeated(npc)]
        if not eligible_npcs:
            return None

        if target_hint:
            low = target_hint.lower()
            for npc in eligible_npcs:
                if npc.id.lower() == low or npc.name.lower() == low:
                    return npc

        for npc in eligible_npcs:
            hp = (states.get(npc.id, {}) or {}).get("hp")
            if hp is None:
                hp = npc.hp
            if hp is None or hp > 0:
                return npc
        return eligible_npcs[0]

    async def _find_scene_npc_by_hint(self, target_hint: str) -> WorldEntity | None:
        target_hint = (target_hint or "").strip()
        if not target_hint:
            return None

        ent_res = await self.db.execute(
            select(WorldEntity).where(
                WorldEntity.session_id == self.game_id,
                WorldEntity.current_scene_id == self.state.current_scene_id,
                WorldEntity.entity_type.in_(["NPC", "npc"]),
                WorldEntity.is_hidden.is_(False),
                WorldEntity.is_in_inventory.is_(False),
            )
        )
        npcs = ent_res.scalars().all()
        low = target_hint.lower()
        for npc in npcs:
            if npc.id.lower() == low or npc.name.lower() == low:
                return npc
        return None

    def _is_npc_defeated(self, npc: WorldEntity) -> bool:
        states = self.state.entity_states or {}
        npc_state = (states.get(npc.id, {}) or {})
        if npc_state.get("is_defeated"):
            return True
        hp = npc_state.get("hp")
        if hp is None:
            hp = npc.hp
        return isinstance(hp, int) and hp <= 0


    def _entity_stat(self, ent: WorldEntity, stat_key: str, fallback: int = 0) -> int:
        states = self.state.entity_states or {}
        override = (states.get(ent.id, {}) or {}).get(stat_key)
        if isinstance(override, int):
            return override
        ent_val = getattr(ent, stat_key, None)
        if isinstance(ent_val, int):
            return ent_val
        return fallback

    def _is_npc_killable(self, npc: WorldEntity) -> bool:
        states = self.state.entity_states or {}
        override = (states.get(npc.id, {}) or {}).get("is_killable")
        if isinstance(override, bool):
            return override
        return bool(getattr(npc, "is_killable", True))

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

    def _append_combat_log(self, combat: dict[str, Any], text: str, entry_type: str = "log") -> None:
        self._combat_state_helper.append_combat_log(combat, text, entry_type)

    async def _emit_combat_final(self, status_note: str | None = None) -> AsyncGenerator[str, None]:
        await self.db.commit()
        combat_snap = AdventureLogic.get_combat_snapshot(self.state)
        # Ensure we don't send a zombie combat object that has no active phase
        if combat_snap and not combat_snap.get("active") and not combat_snap.get("loot_pending") and not combat_snap.get("outcome"):
            combat_snap = None

        map_payload = await self._build_map_payload()
        final_data = jsonable_encoder({
            **map_payload,
            'sheet': await AdventureLogic.build_sheet_snapshot(self.avatar, self.state, self.db),
            'entities': await AdventureLogic.build_session_entities(self.db, self.state),
            'combat': combat_snap,
            **self._build_prompt_suggestions_payload(),
            **self._build_terminal_flags_payload(),
            'status_note': status_note or (self.state.session.status_note if self.state.session else None),
            'status': 'success'
        })
        yield f"event: final\ndata: {json.dumps(final_data)}\n\n"

    async def _emit_combat_aftermath_narration(self, combat: dict[str, Any]) -> AsyncGenerator[str, None]:
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
            llm = gl.GameMasterLLM(self.user, provider=complex_model_provider, model_category="complex")
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
            await self._save_chat_message("assistant", response_text)
            # Only append to combat log if combat is still present in the state
            # Otherwise we'd accidentally resurrect a cleared combat state
            if self._read_combat_state():
                self._append_combat_log(combat, response_text, "aftermath")
                self._set_combat_state(combat)

    async def _calculate_npc_total_stats(self, npc: WorldEntity) -> dict[str, Any]:
        """Calculates total stats for an NPC including equipment bonuses from metadata."""
        stats = {
            "dexterity": self._entity_stat(npc, "stat_modifier_dexterity", 10),
            "armor_class": 10 + self._entity_stat(npc, "stat_modifier_armor_class", 0),
            "strength": self._entity_stat(npc, "stat_modifier_strength", 10),
            "intelligence": self._entity_stat(npc, "stat_modifier_intelligence", 10),
            "wisdom": self._entity_stat(npc, "stat_modifier_wisdom", 10),
            "charisma": self._entity_stat(npc, "stat_modifier_charisma", 10),
        }
        meta = dict(npc.metadata_json or {})
        eq_weapon_id = meta.get("equipped_weapon_id")
        eq_armor_id = meta.get("equipped_armor_id")
        
        for item_id in [eq_weapon_id, eq_armor_id]:
            if not item_id:
                continue
            item_res = await self.db.execute(
                select(WorldEntity).where(
                    WorldEntity.session_id == self.game_id,
                    WorldEntity.id == item_id
                )
            )
            item = item_res.scalars().first()
            if item:
                stats["strength"] += item.stat_modifier_strength or 0
                stats["dexterity"] += item.stat_modifier_dexterity or 0
                stats["intelligence"] += item.stat_modifier_intelligence or 0
                stats["wisdom"] += item.stat_modifier_wisdom or 0
                stats["charisma"] += item.stat_modifier_charisma or 0
                stats["armor_class"] += item.stat_modifier_armor_class or 0
        return stats


    async def _handle_fight_start(self, user_msg: str, initiated_by_enemy: bool = False) -> AsyncGenerator[str, None]:
        if (self.adventure.rule_enforcement_mode or "rpg") != "rpg":
            msg = "Turn-based combat is only available in RPG mode."
            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"
            async for chunk in self._emit_combat_final(msg):
                yield chunk
            return

        if initiated_by_enemy:
            if not bool(getattr(self.adventure, "npcs_can_damage_protagonist", True)):
                msg = "Combat auto-start blocked: NPC damage to the protagonist is disabled for this adventure."
                yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"
                async for chunk in self._emit_combat_final(msg):
                    yield chunk
                return
        elif not bool(getattr(self.adventure, "can_damage_npcs", True)):
            msg = "Combat is disabled for this adventure: the protagonist cannot damage NPCs."
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

        # Check if NPC is already defeated (permanent state)
        states = self.state.entity_states or {}
        is_defeated = (states.get(target.id, {}) or {}).get("is_defeated", False)
        if is_defeated:
            msg = f"{target.name} has already been defeated."
            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"
            async for chunk in self._emit_combat_final(msg):
                yield chunk
            return

        # Check if NPC is attackable
        is_attackable = (states.get(target.id, {}) or {}).get("is_attackable")
        if is_attackable is None:
            is_attackable = target.is_attackable
            
        if is_attackable is False:
            msg = f"You cannot attack {target.name}."
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
        
        # Calculate NPC stats based on equipment
        npc_stats = await self._calculate_npc_total_stats(target)
        enemy_dex = npc_stats["dexterity"]
        enemy_ac_mod = npc_stats["armor_class"] - 10
        
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
                "stamina": self.avatar.stamina,
                "max_stamina": self.avatar.max_stamina,
                "mana": self.avatar.mana,
                "max_mana": self.avatar.max_mana,
                "ac": int(player_stats.get("armor_class", self.avatar.armor_class)),
            },
            "enemy": {
                "id": target.id,
                "name": target.name,
                "image_url": target.image_url,
                "hp": enemy_hp,
                "max_hp": enemy_max_hp,
                "stamina": self._entity_stat(target, "stamina", 0),
                "max_stamina": self._entity_stat(target, "max_stamina", 0),
                "mana": self._entity_stat(target, "mana", 0),
                "max_mana": self._entity_stat(target, "max_mana", 0),
                "dexterity_mod": enemy_dex,
                "armor_mod": enemy_ac_mod,
                "inventory": await self._normalize_loot_items(list(target.inventory or [])),
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

        if initiated_by_enemy:
            msg = f"{target.name} attacks as you enter the scene. Combat starts immediately."
        else:
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

        enemy_initiated = False
        target_hint = ""
        for req in game_event.requested_attacks:
            attacker_id = str(req.attacker_id or "").strip()
            target_id = str(req.target_id or "").strip()
            attacker_is_player = attacker_id.upper() == "PLAYER"
            target_is_player = target_id.upper() == "PLAYER"

            if attacker_id and not attacker_is_player and target_is_player:
                enemy_initiated = True
                target_hint = attacker_id
                break

            if not target_hint and target_id and not target_is_player:
                target_hint = target_id
            if not target_hint and attacker_id and not attacker_is_player:
                target_hint = attacker_id

        if enemy_initiated:
            if not bool(getattr(self.adventure, "npcs_can_damage_protagonist", True)):
                return False
        elif not bool(getattr(self.adventure, "can_damage_npcs", True)):
            return False

        target = await self._find_fight_target(target_hint)
        if not target:
            return False

        async for _chunk in self._handle_fight_start(f"/fight {target.id}", initiated_by_enemy=enemy_initiated):
            pass
        return True

    def _find_consumable(self, item_name: str) -> dict[str, Any] | None:
        for item in list(self.avatar.inventory or []):
            if isinstance(item, dict) and item.get("name", "").lower() == item_name.lower() and item.get("item_type") == "CONSUMABLE":
                return item
        return None

    def _sync_combat_player_snapshot(self, combat: dict[str, Any]) -> None:
        player = dict(combat.get("player") or {})
        player_stats = calculate_total_stats(self.avatar)
        player["name"] = self.avatar.name
        player["image_url"] = self.avatar.profile_image
        player["hp"] = int(self.avatar.hp or 0)
        player["max_hp"] = int(self.avatar.max_hp or RESOURCE_CAP)
        player["stamina"] = int(self.avatar.stamina or 0)
        player["max_stamina"] = int(self.avatar.max_stamina or RESOURCE_CAP)
        player["mana"] = int(self.avatar.mana or 0)
        player["max_mana"] = int(self.avatar.max_mana or RESOURCE_CAP)
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

    def _resource_delta_from_consumable(self, item: dict[str, Any], resource: str) -> int:
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
    def _parse_json_object(raw: str) -> dict[str, Any] | None:
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

    async def _request_llm_combat_special_event(self, combat: dict[str, Any]) -> dict[str, Any] | None:
        llm_settings = self.user.llm_settings or {}
        complex_model_provider = (
            llm_settings.get("complex_model_provider")
            or llm_settings.get("small_model_provider")
            or llm_settings.get("preferred_provider")
            or "openai"
        )
        complex_model = llm_settings.get("complex_model") or "gpt-4o"

        try:
            llm = gl.GameMasterLLM(self.user, provider=complex_model_provider, model_category="complex")
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

        system_prompt = COMBAT_SPECIAL_EVENT_SYSTEM_PROMPT
        if self.turn_language:
            system_prompt += f" Text must be in {self.turn_language.upper()}."

        user_prompt = COMBAT_SPECIAL_EVENT_USER_PROMPT_TEMPLATE.format(
            round=int(combat.get('round') or 1),
            enemy_name=enemy_name,
            enemy_hp=enemy_hp,
            enemy_max_hp=enemy_max_hp,
            player_name=player_name,
            player_hp=player_hp,
            player_max_hp=player_max_hp,
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

        gained = []
        lost = []
        if hp_delta > 0: gained.append(f"+{hp_delta} HP")
        elif hp_delta < 0: lost.append(f"{hp_delta} HP")
        
        if mana_delta > 0: gained.append(f"+{mana_delta} Mana")
        elif mana_delta < 0: lost.append(f"{mana_delta} Mana")
        
        if stamina_delta > 0: gained.append(f"+{stamina_delta} Stamina")
        elif stamina_delta < 0: lost.append(f"{stamina_delta} Stamina")

        msg = f"{self.avatar.name} uses {item.get('name', item_name)}."
        stat_parts = []
        if gained:
            stat_parts.append(f"You gain: {', '.join(gained)}.")
        if lost:
            stat_parts.append(f"You lose: {', '.join(lost)}.")
            
        if stat_parts:
            return f"{msg} {' '.join(stat_parts)}"
        return msg

    async def _maybe_trigger_special_event(self, combat: dict[str, Any]) -> str | None:
        if gl.random.random() > 0.25:
            return None

        enemy_name = combat.get("enemy", {}).get("name", "Enemy")
        if not bool(getattr(self.adventure, "npcs_can_damage_protagonist", True)):
            text = f"Special Event: {enemy_name} shifts the pressure of battle, but no direct damage is dealt."
            self._append_combat_log(combat, text, "special")
            return text
        event_data = await self._request_llm_combat_special_event(combat)

        # Safe fallback if LLM is unavailable or returns invalid payload.
        if not event_data:
            if gl.random.random() < 0.5:
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

        meta = dict(enemy_ent.metadata_json or {})
        eq_weapon_id = meta.get("equipped_weapon_id")
        weapon_cost_type = "stamina"
        weapon_cost_value = 20
        weapon_dmg_dice = "1d6"
        weapon_name = "unarmed attack"
        
        if eq_weapon_id:
            w_res = await self.db.execute(
                select(WorldEntity).where(
                    WorldEntity.session_id == self.game_id,
                    WorldEntity.id == eq_weapon_id
                )
            )
            w_ent = w_res.scalars().first()
            if w_ent:
                w_meta = dict(w_ent.metadata_json or {})
                weapon_cost_type = w_meta.get("weapon_cost_type") or "stamina"
                weapon_cost_value = w_meta.get("weapon_cost_value") if w_meta.get("weapon_cost_value") is not None else 20
                weapon_dmg_dice = w_meta.get("damage_dice") or "1d8"
                weapon_name = w_ent.name

        enemy_stamina = self._entity_stat(enemy_ent, "stamina", 0)
        enemy_max_stamina = self._entity_stat(enemy_ent, "max_stamina", 0)
        enemy_mana = self._entity_stat(enemy_ent, "mana", 0)
        enemy_max_mana = self._entity_stat(enemy_ent, "max_mana", 0)

        # AI Special Action decision logic
        npc_specials = meta.get("special_actions") or []
        cast_action = None
        
        if enemy_hp > 0 and enemy_ent.max_hp and (enemy_hp / enemy_ent.max_hp) < 0.4:
            heal_actions = [a for a in npc_specials if a.get("action_type") == "HEAL" and int(a.get("mana_cost", 0)) <= enemy_mana]
            if heal_actions and gl.random.random() < 0.8:
                cast_action = gl.random.choice(heal_actions)
                
        if not cast_action and npc_specials and gl.random.random() < 0.3:
            damage_utility_actions = [a for a in npc_specials if a.get("action_type") in ("ATTACK", "UTILITY") and int(a.get("mana_cost", 0)) <= enemy_mana]
            if damage_utility_actions:
                cast_action = gl.random.choice(damage_utility_actions)

        if cast_action:
            # Execute special action
            mana_cost = int(cast_action.get("mana_cost") or 0)
            enemy_mana = max(0, enemy_mana - mana_cost)
            
            action_type = cast_action.get("action_type", "ATTACK").upper()
            action_name = cast_action.get("name", "Special Action")
            outcome_desc = cast_action.get("outcome_description") or ""
            
            text = ""
            if action_type == "ATTACK":
                from backend.engine.skill_check import roll_dice_detailed
                spell_modifier = max(
                    int(self._entity_stat(enemy_ent, "stat_modifier_intelligence", 10) - 10) // 2,
                    int(self._entity_stat(enemy_ent, "stat_modifier_wisdom", 10) - 10) // 2,
                    0
                )
                d20 = random.randint(1, 20)
                hit_total = d20 + spell_modifier
                is_hit = hit_total >= player_ac
                
                if is_hit:
                    damage_type = cast_action.get("damage_type", "FIXED").upper()
                    damage_val_str = cast_action.get("damage_value") or "10"
                    
                    damage = 0
                    rolls_str = ""
                    if damage_type == "FIXED":
                        damage = int(damage_val_str)
                        rolls_str = f"{damage} (fixed)"
                    else:
                        damage_info = roll_dice_detailed(damage_val_str)
                        damage = damage_info["total"]
                        rolls_str = f"{damage_info['dice_str']} ({' + '.join(str(r) for r in damage_info['rolls'])}{' + ' + str(damage_info['bonus']) if damage_info['bonus'] > 0 else ''}) = {damage}"
                    
                    self.avatar.hp = max(0, self.avatar.hp - damage)
                    text = f"{enemy_ent.name} casts {action_name} (Mana: -{mana_cost})! Attack Roll: {d20} + {spell_modifier} = {hit_total} vs AC {player_ac} -> HIT | Damage: {rolls_str}."
                else:
                    text = f"{enemy_ent.name} casts {action_name} (Mana: -{mana_cost})! Attack Roll: {d20} + {spell_modifier} = {hit_total} vs AC {player_ac} -> MISS."
                
            elif action_type == "HEAL":
                from backend.engine.skill_check import roll_dice_detailed
                damage_type = cast_action.get("damage_type", "FIXED").upper()
                damage_val_str = cast_action.get("damage_value") or "10"
                
                heal_amount = 0
                rolls_str = ""
                if damage_type == "FIXED":
                    heal_amount = int(damage_val_str)
                    rolls_str = f"{heal_amount} (fixed)"
                else:
                    damage_info = roll_dice_detailed(damage_val_str)
                    heal_amount = damage_info["total"]
                    rolls_str = f"{damage_info['dice_str']} ({' + '.join(str(r) for r in damage_info['rolls'])}{' + ' + str(damage_info['bonus']) if damage_info['bonus'] > 0 else ''}) = {heal_amount}"
                
                enemy_max_hp = int(combat.get("enemy", {}).get("max_hp") or max(enemy_hp, 1))
                enemy_hp = min(enemy_max_hp, enemy_hp + heal_amount)
                text = f"{enemy_ent.name} casts {action_name} (Mana: -{mana_cost})! Restores {rolls_str} HP."
                
            else:
                text = f"{enemy_ent.name} performs special action {action_name} (Mana: -{mana_cost}). Outcome: {outcome_desc}"
            
            combat["enemy"]["hp"] = enemy_hp
            combat["enemy"]["mana"] = enemy_mana
            
            states = dict(self.state.entity_states or {})
            if enemy_id not in states:
                states[enemy_id] = {}
            states[enemy_id]["hp"] = enemy_hp
            states[enemy_id]["mana"] = enemy_mana
            self.state.entity_states = states
            flag_modified(self.state, "entity_states")
            
            self._sync_combat_player_snapshot(combat)
            self._append_combat_log(combat, text, "enemy_action")
            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': text})}\n\n"
            
            if outcome_desc:
                await self._save_chat_message("system", f"{enemy_ent.name} Special Action outcome: {outcome_desc}")
            
            if self.avatar.hp <= 0:
                await self._finalize_session("game_over", f"{self.avatar.name} has fallen in battle.")
                combat["active"] = False
                combat["outcome"] = "defeat"
                combat["status_note"] = "Game Over"
                self._append_combat_log(combat, "The protagonist falls. Game Over.", "outcome")
                self._set_combat_state(combat)
                return
                
            combat["turn"] = "player"
            combat["round"] = int(combat.get("round", 1)) + 1
            self._append_combat_log(combat, f"Round {combat['round']}: {self.avatar.name}'s turn.", "turn")
            self._set_combat_state(combat)
            return

        # Regular Weapon Action (Stamina/Mana checks)
        if weapon_cost_type == "mana":
            if enemy_mana < weapon_cost_value:
                # Enemy rests (stamina + mana both recover)
                enemy_stamina = min(enemy_max_stamina, enemy_stamina + 40)
                enemy_mana = min(enemy_max_mana, enemy_mana + 40)

                combat["enemy"]["stamina"] = enemy_stamina
                combat["enemy"]["mana"] = enemy_mana
                states = dict(self.state.entity_states or {})
                if enemy_id not in states:
                    states[enemy_id] = {}
                states[enemy_id]["stamina"] = enemy_stamina
                states[enemy_id]["mana"] = enemy_mana
                self.state.entity_states = states
                flag_modified(self.state, "entity_states")

                text = f"{enemy_ent.name} is out of mana and rests to recover (+40 Stamina, +40 Mana)."
                self._sync_combat_player_snapshot(combat)
                self._append_combat_log(combat, text, "enemy_action")
                yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': text})}\n\n"

                combat["turn"] = "player"
                combat["round"] = int(combat.get("round", 1)) + 1
                self._append_combat_log(combat, f"Round {combat['round']}: {self.avatar.name}'s turn.", "turn")
                self._set_combat_state(combat)
                return
            enemy_mana = max(0, enemy_mana - weapon_cost_value)
        else:
            if enemy_max_stamina > 0 and enemy_stamina < weapon_cost_value:
                # Enemy rests (stamina + mana both recover)
                enemy_stamina = min(enemy_max_stamina, enemy_stamina + 40)
                if enemy_max_mana > 0:
                    enemy_mana = min(enemy_max_mana, enemy_mana + 40)

                combat["enemy"]["stamina"] = enemy_stamina
                combat["enemy"]["mana"] = enemy_mana
                states = dict(self.state.entity_states or {})
                if enemy_id not in states:
                    states[enemy_id] = {}
                states[enemy_id]["stamina"] = enemy_stamina
                states[enemy_id]["mana"] = enemy_mana
                self.state.entity_states = states
                flag_modified(self.state, "entity_states")

                text = f"{enemy_ent.name} is exhausted and rests to recover (+40 Stamina{', +40 Mana' if enemy_max_mana > 0 else ''})."
                self._sync_combat_player_snapshot(combat)
                self._append_combat_log(combat, text, "enemy_action")
                yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': text})}\n\n"

                combat["turn"] = "player"
                combat["round"] = int(combat.get("round", 1)) + 1
                self._append_combat_log(combat, f"Round {combat['round']}: {self.avatar.name}'s turn.", "turn")
                self._set_combat_state(combat)
                return
            enemy_stamina = max(0, enemy_stamina - weapon_cost_value)

        combat["enemy"]["stamina"] = enemy_stamina
        combat["enemy"]["mana"] = enemy_mana
        states = dict(self.state.entity_states or {})
        if enemy_id not in states:
            states[enemy_id] = {}
        states[enemy_id]["stamina"] = enemy_stamina
        states[enemy_id]["mana"] = enemy_mana
        self.state.entity_states = states
        flag_modified(self.state, "entity_states")

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

        if not bool(getattr(self.adventure, "npcs_can_damage_protagonist", True)):
            text = f"{enemy_ent.name} attacks, but this adventure disables NPC damage to the protagonist."
            self._sync_combat_player_snapshot(combat)
            self._append_combat_log(combat, text, "enemy_action")
            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': text})}\n\n"
            combat["turn"] = "player"
            combat["round"] = int(combat.get("round", 1)) + 1
            self._append_combat_log(combat, f"Round {combat['round']}: {self.avatar.name}'s turn.", "turn")
            self._set_combat_state(combat)
            return

        roll = gl.roll_attack(enemy_avatar, "dexterity", player_ac, weapon_dmg_dice)
        if roll["is_hit"]:
            self.avatar.hp = max(0, self.avatar.hp - roll["damage_total"])
            dmg_bonus = int(roll.get("damage_bonus") or 0)
            dmg_bonus_str = f" + {dmg_bonus}" if dmg_bonus > 0 else (f" - {abs(dmg_bonus)}" if dmg_bonus < 0 else "")
            hit_status = "CRITICAL HIT" if roll.get("is_crit") else "HIT"
            text = (
                f"{enemy_ent.name} ATTACK ROLL: {roll['hit_roll']} + {roll['hit_modifier']} = {roll['hit_total']} vs AC {player_ac} -> {hit_status} | "
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

    async def _spawn_scene_item(self, item: dict[str, Any]) -> None:
        name = str(item.get("name") or "").strip()
        raw_id = str(item.get("id") or item.get("entity_id") or "").strip()

        ent_res = await self.db.execute(
            select(WorldEntity).where(
                WorldEntity.session_id == self.game_id,
                WorldEntity.entity_type == "OBJECT"
            )
        )
        all_objs = ent_res.scalars().all()

        existing_ent: Optional[WorldEntity] = None
        # 1. Exact or case-insensitive ID match
        if raw_id:
            raw_upper = raw_id.upper()
            for obj in all_objs:
                if (obj.id or "").strip().upper() == raw_upper:
                    existing_ent = obj
                    break

        # 2. Match by exact or case-insensitive name
        if not existing_ent and name:
            name_low = name.lower()
            for obj in all_objs:
                if (obj.name or "").strip().lower() == name_low:
                    existing_ent = obj
                    break

        if existing_ent:
            existing_ent.current_scene_id = self.state.current_scene_id
            existing_ent.is_in_inventory = False
            existing_ent.is_hidden = False

            # Also update override in session state
            states = dict(self.state.entity_states or {})
            canon_id = existing_ent.id
            if canon_id not in states:
                states[canon_id] = {}
            states[canon_id]["is_in_inventory"] = False
            states[canon_id]["current_scene_id"] = self.state.current_scene_id
            states[canon_id]["is_hidden"] = False
            self.state.entity_states = states
            flag_modified(self.state, "entity_states")
            return

        logger.warning(
            "[Turn %s] Skipped spawning non-existent entity: ID=%s, Name=%s (dynamic item generation is disabled)",
            self.game_id,
            raw_id,
            name,
        )

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

    async def _normalize_loot_items(self, items: list[Any]) -> list[dict[str, Any]]:
        """Normalize various loot representations into dicts with at least `id` and `name`.

        Items can be:
        - dicts already containing item data
        - strings that reference a WorldEntity id (template or session)
        - other types (ignored)
        """
        normalized: list[dict[str, Any]] = []
        if not items:
            return normalized

        for it in items:
            # If already a dict, ensure it has id/name
            if isinstance(it, dict):
                entry = dict(it)
                if not entry.get("id") and entry.get("name"):
                    # generate a synthetic id when missing
                    entry["id"] = f"LOOT_{uuid.uuid4().hex[:8]}"
                normalized.append(entry)
                continue

            # If it's a string, try to resolve WorldEntity by id
            if isinstance(it, str) and it.strip():
                ent_id = it.strip()
                ent_res = await self.db.execute(
                    select(WorldEntity).where(
                        (WorldEntity.session_id == self.game_id) & (WorldEntity.id == ent_id)
                    )
                )
                ent = ent_res.scalars().first()

                # If not found in session, try template entities for this adventure
                if not ent and self.state and self.state.template_id:
                    ent_res = await self.db.execute(
                        select(WorldEntity).where(
                            (WorldEntity.template_id == self.state.template_id) & (WorldEntity.id == ent_id)
                        )
                    )
                    ent = ent_res.scalars().first()

                if ent:
                    normalized.append({
                        "id": ent.id,
                        "name": ent.name,
                        "description": ent.description,
                        "image_url": ent.image_url,
                        "item_type": ent.item_type,
                        "wearable_slots": ent.wearable_slots,
                        **(ent.metadata_json or {}),
                    })
                else:
                    # Unknown reference, keep minimal info
                    normalized.append({"id": ent_id, "name": ent_id})
                continue

            # Fallback: ignore unknown types
        return normalized

    async def _resolve_loot_command(self, user_msg: str, combat: dict[str, Any]) -> str | None:
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
            dropped_items = list(loot_items)
            for item in dropped_items:
                await self._spawn_scene_item(item)
            combat["loot_items"] = []
            combat["loot_pending"] = False
            combat.pop("outcome", None)
            combat["status_note"] = "Combat resolved."
            self._append_combat_log(combat, combat["status_note"], "loot")
            
            # If nothing is left to do, clear the combat state entirely from all sources
            if not combat.get("active") and not combat.get("loot_pending") and not combat.get("outcome"):
                self.state.combat_json = None
                # Aggressively clear combat state by creating a new filtered dict
                self.state.entity_states = {k: v for k, v in (self.state.entity_states or {}).items() if k != "__combat__"}
                flag_modified(self.state, "entity_states")
                last_msg = await self._load_last_assistant_message()
                await self._generate_prompt_suggestions(last_msg)
                await self.db.commit()
            else:
                self._set_combat_state(combat)

            if dropped_items:
                dropped_names = [str(item.get("name") or item.get("id") or "Unknown Item") for item in dropped_items]
                dropped_list = "\n".join(f"- {name}" for name in dropped_names)
                return f"Loot dropped to the scene:\n{dropped_list}"

            return "Combat finished. No loot remained to drop."

        return "Loot commands: /loot take <item>, /loot leave <item>, /loot done"

    def _award_combat_victory_xp(self, enemy_ent: WorldEntity) -> int:
        metadata = dict(enemy_ent.metadata_json or {})
        xp_gained = metadata.get("exp_reward") or metadata.get("xp_reward")
        if xp_gained is None:
            xp_gained = max(50, enemy_ent.max_hp or 100)
        self.avatar.exp = (self.avatar.exp or 0) + xp_gained
        return xp_gained

    async def _handle_combat_turn(self, user_msg: str) -> AsyncGenerator[str, None]:
        combat = self._read_combat_state()
        if not combat.get("active") and (combat.get("loot_pending") or combat.get("outcome")):
            pre_resolve_outcome = combat.get("outcome")
            loot_msg = await self._resolve_loot_command(user_msg, combat)
            if loot_msg:
                yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': loot_msg})}\n\n"
                if user_msg.lower().strip().startswith("/loot done"):
                    combat_after_loot = self._read_combat_state()
                    # Re-inject outcome for narration if it was just popped
                    if not combat_after_loot.get("outcome") and pre_resolve_outcome:
                        combat_after_loot["outcome"] = pre_resolve_outcome
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
        if (cmd == "attack" or cmd == "/attack" or cmd == "a" or cmd.startswith("attack ") or cmd.startswith("/attack ")) and not bool(getattr(self.adventure, "can_damage_npcs", True)):
            msg = "The protagonist cannot damage NPCs in this adventure. Use Run, Rest, or /consume."
            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"
            async for chunk in self._emit_combat_final(msg):
                yield chunk
            return

        if cmd == "attack" or cmd == "/attack" or cmd == "a" or cmd.startswith("attack ") or cmd.startswith("/attack "):
            eq = self.avatar.equipment or {}
            main_hand = eq.get("MainHand")
            weapon_cost_type = "stamina"
            weapon_cost_value = 20
            weapon_dmg_dice = "1d8"
            weapon_name = "Bare Fists"
            
            if isinstance(main_hand, dict):
                weapon_name = main_hand.get("name", "Weapon")
                meta = dict(main_hand.get("metadata_json") or {})
                if not meta and "id" in main_hand:
                    item_res = await self.db.execute(
                        select(WorldEntity).where(
                            WorldEntity.session_id == self.game_id,
                            WorldEntity.id == main_hand["id"]
                        )
                    )
                    item_ent = item_res.scalars().first()
                    if item_ent and item_ent.metadata_json:
                        meta = dict(item_ent.metadata_json)
                
                weapon_cost_type = meta.get("weapon_cost_type") or "stamina"
                weapon_cost_value = meta.get("weapon_cost_value") if meta.get("weapon_cost_value") is not None else 20
                weapon_dmg_dice = meta.get("damage_dice") or main_hand.get("damage_dice") or "1d8"

            if weapon_cost_type == "mana":
                if self.avatar.mana < weapon_cost_value:
                    msg = f"Not enough mana to attack with {weapon_name}! You have {self.avatar.mana} mana, but attacks require {weapon_cost_value}. Use Rest to recover."
                    yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"
                    async for chunk in self._emit_combat_final(msg):
                        yield chunk
                    return
                self.avatar.mana = max(0, self.avatar.mana - weapon_cost_value)
            else:
                if self.avatar.stamina < weapon_cost_value:
                    msg = f"Not enough stamina to attack with {weapon_name}! You have {self.avatar.stamina} stamina, but attacks require {weapon_cost_value}. Use Rest to recover."
                    yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"
                    async for chunk in self._emit_combat_final(msg):
                        yield chunk
                    return
                self.avatar.stamina = max(0, self.avatar.stamina - weapon_cost_value)

            self._sync_combat_player_snapshot(combat)
            
            # Roll attack
            roll = gl.roll_attack(self.avatar, "dexterity", enemy_ac, weapon_dmg_dice)
            hit_status = "CRITICAL HIT" if roll.get("is_crit") else "HIT"
            if roll["is_hit"]:
                enemy_hp = max(0, enemy_hp - roll["damage_total"])
                dmg_bonus = int(roll.get("damage_bonus") or 0)
                dmg_bonus_str = f" + {dmg_bonus}" if dmg_bonus > 0 else (f" - {abs(dmg_bonus)}" if dmg_bonus < 0 else "")
                action_msg = (
                    f"{self.avatar.name} ATTACK ROLL: {roll['hit_roll']} + {roll['hit_modifier']} = {roll['hit_total']} vs AC {enemy_ac} -> {hit_status} | "
                    f"DMG {roll['damage_dice_str']} ({' + '.join(str(r) for r in roll['damage_rolls'])}"
                    f"{dmg_bonus_str})"
                    f" = {roll['damage_total']}"
                )
            else:
                action_msg = f"{self.avatar.name} ATTACK ROLL: {roll['hit_roll']} + {roll['hit_modifier']} = {roll['hit_total']} vs AC {enemy_ac} -> MISS"
            self._append_combat_log(combat, action_msg, "player_action")
        elif cmd.startswith("special ") or cmd.startswith("/special ") or cmd.startswith("cast ") or cmd.startswith("/cast "):
            action_parts = user_msg.strip().split(" ", 1)
            action_id = action_parts[1].strip().upper() if len(action_parts) > 1 else ""
            
            player_specials = self.avatar.stats.get("special_actions") or []
            action = None
            for act in player_specials:
                if act.get("id", "").upper() == action_id:
                    action = act
                    break
            
            if not action:
                msg = f"Special action '{action_id}' not found. Available: " + ", ".join(act.get("id") for act in player_specials)
                yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"
                async for chunk in self._emit_combat_final(msg):
                    yield chunk
                return
            
            unlocked_actions = self.avatar.stats.get("unlocked_actions") or []
            if action.get("id") not in unlocked_actions:
                msg = f"Special action '{action.get('name')}' is locked. You must unlock it first!"
                yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"
                async for chunk in self._emit_combat_final(msg):
                    yield chunk
                return
                
            mana_cost = int(action.get("mana_cost") or 0)
            if self.avatar.mana < mana_cost:
                msg = f"Not enough mana! {action.get('name')} costs {mana_cost} Mana, but you only have {self.avatar.mana} Mana."
                yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"
                async for chunk in self._emit_combat_final(msg):
                    yield chunk
                return
                
            self.avatar.mana = max(0, self.avatar.mana - mana_cost)
            self._sync_combat_player_snapshot(combat)
            
            action_type = action.get("action_type", "ATTACK").upper()
            action_name = action.get("name", "Special Action")
            outcome_desc = action.get("outcome_description") or ""
            
            if action_type == "ATTACK":
                from backend.engine.skill_check import roll_dice_detailed
                player_stats = calculate_total_stats(self.avatar)
                spell_modifier = max(
                    int(player_stats.get("intelligence", self.avatar.intelligence) - 10) // 2,
                    int(player_stats.get("wisdom", self.avatar.wisdom) - 10) // 2,
                    0
                )
                d20 = random.randint(1, 20)
                hit_total = d20 + spell_modifier
                is_hit = hit_total >= enemy_ac
                
                if is_hit:
                    damage_type = action.get("damage_type", "FIXED").upper()
                    damage_val_str = action.get("damage_value") or "10"
                    
                    damage = 0
                    rolls_str = ""
                    if damage_type == "FIXED":
                        damage = int(damage_val_str)
                        rolls_str = f"{damage} (fixed)"
                    else:
                        damage_info = roll_dice_detailed(damage_val_str)
                        damage = damage_info["total"]
                        rolls_str = f"{damage_info['dice_str']} ({' + '.join(str(r) for r in damage_info['rolls'])}{' + ' + str(damage_info['bonus']) if damage_info['bonus'] > 0 else ''}) = {damage}"
                    
                    enemy_hp = max(0, enemy_hp - damage)
                    action_msg = f"{self.avatar.name} casts {action_name} (Mana: -{mana_cost})! Attack Roll: {d20} + {spell_modifier} = {hit_total} vs AC {enemy_ac} -> HIT | Damage: {rolls_str}."
                else:
                    action_msg = f"{self.avatar.name} casts {action_name} (Mana: -{mana_cost})! Attack Roll: {d20} + {spell_modifier} = {hit_total} vs AC {enemy_ac} -> MISS."
                
                self._append_combat_log(combat, action_msg, "player_action")
                
            elif action_type == "HEAL":
                from backend.engine.skill_check import roll_dice_detailed
                damage_type = action.get("damage_type", "FIXED").upper()
                damage_val_str = action.get("damage_value") or "10"
                
                heal_amount = 0
                rolls_str = ""
                if damage_type == "FIXED":
                    heal_amount = int(damage_val_str)
                    rolls_str = f"{heal_amount} (fixed)"
                else:
                    damage_info = roll_dice_detailed(damage_val_str)
                    heal_amount = damage_info["total"]
                    rolls_str = f"{damage_info['dice_str']} ({' + '.join(str(r) for r in damage_info['rolls'])}{' + ' + str(damage_info['bonus']) if damage_info['bonus'] > 0 else ''}) = {heal_amount}"
                
                self.avatar.hp = min(self.avatar.max_hp, self.avatar.hp + heal_amount)
                action_msg = f"{self.avatar.name} casts {action_name} (Mana: -{mana_cost})! Restores {rolls_str} HP."
                self._append_combat_log(combat, action_msg, "player_action")
                
            else:
                action_msg = f"{self.avatar.name} performs special action {action_name} (Mana: -{mana_cost}). Outcome: {outcome_desc}"
                self._append_combat_log(combat, action_msg, "player_action")
                
            if outcome_desc:
                await self._save_chat_message("system", f"Special action used: {action_name}. Outcome: {outcome_desc}")
            
            self._sync_combat_player_snapshot(combat)
        elif cmd in {"rest", "/rest", "wait", "/wait", "recover", "/recover", "skip", "/skip"}:
            self.avatar.stamina = min(self.avatar.max_stamina or 100, self.avatar.stamina + 40)
            # Mana does NOT recover in combat — only stamina restores on rest
            self._sync_combat_player_snapshot(combat)
            action_msg = f"{self.avatar.name} rests to recover stamina (+40 Stamina). Mana can only be restored outside of combat or by using a potion."
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
            msg = "Combat active. Valid actions: Attack, Run, Rest, /consume <item>, or /special <action_id>."
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
            xp_gained = self._award_combat_victory_xp(enemy_ent)
            combat["status_note"] = f"{enemy_ent.name} is defeated. (+{xp_gained} XP)"
            combat["loot_pending"] = True
            combat["loot_items"] = await self._normalize_loot_items(list(enemy.get("inventory") or enemy_ent.inventory or []))
            states = dict(self.state.entity_states or {})
            if enemy_id not in states:
                states[enemy_id] = {}
            states[enemy_id]["inventory"] = []
            if self._is_npc_killable(enemy_ent):
                # Mark NPC as permanently defeated so they cannot be re-engaged
                states[enemy_id]["is_defeated"] = True
                states[enemy_id]["is_attackable"] = False
            self.state.entity_states = states
            flag_modified(self.state, "entity_states")
            self._append_combat_log(combat, combat["status_note"], "outcome")
            
            msg = f"Defeated {enemy_ent.name}!"
            xp_msg = f"you gained {xp_gained} XP"
            await self._save_chat_message("system", msg)
            await self._save_chat_message("system", xp_msg)
            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"
            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': xp_msg})}\n\n"
            
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
            if gl.random.random() < 0.10: # 10% chance
                combat["active"] = False
                combat["outcome"] = "victory"
                xp_gained = self._award_combat_victory_xp(enemy_ent)
                combat["status_note"] = f"{enemy_ent.name} flees in panic! You won the battle. (+{xp_gained} XP)"
                # Mark NPC as permanently defeated (fled = no re-engagement)
                states = dict(self.state.entity_states or {})
                if enemy_id not in states:
                    states[enemy_id] = {}
                if self._is_npc_killable(enemy_ent):
                    states[enemy_id]["is_defeated"] = True
                    states[enemy_id]["is_attackable"] = False
                self.state.entity_states = states
                flag_modified(self.state, "entity_states")
                # Spawn any remaining NPC inventory items to the scene automatically
                flee_loot = await self._normalize_loot_items(list(enemy.get("inventory") or enemy_ent.inventory or []))
                for flee_item in flee_loot:
                    await self._spawn_scene_item(flee_item)
                self._append_combat_log(combat, combat["status_note"], "outcome")
                self._set_combat_state(combat)
                msg = f"Defeated {enemy_ent.name}!"
                xp_msg = f"you gained {xp_gained} XP"
                await self._save_chat_message("system", msg)
                await self._save_chat_message("system", xp_msg)
                yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"
                yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': xp_msg})}\n\n"
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

