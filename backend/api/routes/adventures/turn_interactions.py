from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from typing import TYPE_CHECKING, Any, AsyncGenerator

from fastapi.encoders import jsonable_encoder
from sqlalchemy import and_, or_, select
from sqlalchemy.orm.attributes import flag_modified

from backend.api.routes.adventures.gameplay_logic import (
    WALKTHROUGH_HINT_COST,
    WALKTHROUGH_REVEAL_COST,
    _friendly_llm_error_message,
    _friendly_llm_unexpected_error_message,
)
from backend.api.routes.adventures.logic import AdventureLogic
from backend.core import prompts
from backend.core.config import settings
from backend.engine.command_parser import CommandParser
from backend.engine.debug_engine import DebugEngine
from backend.engine.rule_engine import GameEvent, WorldEntityUpdate
from backend.models.chat import ChatMessage
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene

if TYPE_CHECKING:
    from backend.api.routes.adventures.gameplay_logic import GameTurnManager

logger = logging.getLogger(__name__)


class TurnInteractionsManager:
    """Manages player interactions, slash commands, debug commands, switches, and containers."""

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
    def stop_requested(self):
        return self.manager.stop_requested

    @stop_requested.setter
    def stop_requested(self, val):
        self.manager.stop_requested = val

    def _queue_checkpoint(self, *args, **kwargs):
        return self.manager._queue_checkpoint(*args, **kwargs)

    async def _persist_pending_checkpoints(self, *args, **kwargs):
        return await self.manager._persist_pending_checkpoints(*args, **kwargs)

    def _append_combat_log(self, *args, **kwargs):
        return self.manager._append_combat_log(*args, **kwargs)

    def _award_combat_victory_xp(self, *args, **kwargs):
        return self.manager._award_combat_victory_xp(*args, **kwargs)

    def _build_map_payload(self, *args, **kwargs):
        return self.manager._build_map_payload(*args, **kwargs)

    def _build_prompt_suggestions_payload(self, *args, **kwargs):
        return self.manager._build_prompt_suggestions_payload(*args, **kwargs)

    def _build_terminal_flags_payload(self, *args, **kwargs):
        return self.manager._build_terminal_flags_payload(*args, **kwargs)

    async def _check_special_action_unlocks(self, *args, **kwargs):
        return await self.manager._check_special_action_unlocks(*args, **kwargs)

    def _consume_item_now(self, *args, **kwargs):
        return self.manager._consume_item_now(*args, **kwargs)

    def _emit_combat_final(self, *args, **kwargs):
        return self.manager._emit_combat_final(*args, **kwargs)

    async def _finalize_session(self, *args, **kwargs):
        return await self.manager._finalize_session(*args, **kwargs)

    async def _find_scene_npc_by_hint(self, *args, **kwargs):
        return await self.manager._find_scene_npc_by_hint(*args, **kwargs)

    def _is_container_item(self, *args, **kwargs):
        return self.manager._is_container_item(*args, **kwargs)

    def _is_container_locked(self, *args, **kwargs):
        return self.manager._is_container_locked(*args, **kwargs)

    def _is_npc_defeated(self, *args, **kwargs):
        return self.manager._is_npc_defeated(*args, **kwargs)

    def _normalize_loot_items(self, *args, **kwargs):
        return self.manager._normalize_loot_items(*args, **kwargs)

    def _read_combat_state(self, *args, **kwargs):
        return self.manager._read_combat_state(*args, **kwargs)

    def _run_llm_cycle(self, *args, **kwargs):
        return self.manager._run_llm_cycle(*args, **kwargs)

    async def _save_chat_message(self, *args, **kwargs):
        return await self.manager._save_chat_message(*args, **kwargs)

    def _set_combat_state(self, *args, **kwargs):
        return self.manager._set_combat_state(*args, **kwargs)

    async def _spawn_scene_item(self, *args, **kwargs):
        return await self.manager._spawn_scene_item(*args, **kwargs)

    async def _handle_traverse_exit(self, exit_ref: str, language: str | None = None) -> AsyncGenerator[str, None]:
        """Performs scene exit traversal and triggers an LLM narration pass for the new scene."""
        import json
        from sqlalchemy import or_, and_, func

        current_scene_id = str(self.state.current_scene_id or "").strip()
        world_exit = None

        # Support both a direct exit DB-ID and a 'FROM::TO' scene composite key
        # (map edges expose from/to but have no id field)
        if "::" in exit_ref:
            parts = exit_ref.split("::", 1)
            from_id, to_id = parts[0].strip(), parts[1].strip()
            exit_res = await self.db.execute(
                select(WorldExit).where(
                    or_(
                        WorldExit.session_id == self.state.session_id,
                        and_(
                            WorldExit.template_id == self.state.template_id,
                            WorldExit.session_id.is_(None),
                        ),
                    ),
                    or_(
                        and_(
                            func.lower(WorldExit.from_scene_id) == from_id.lower(),
                            func.lower(WorldExit.to_scene_id) == to_id.lower(),
                        ),
                        and_(
                            WorldExit.exit_type == "bidirectional",
                            func.lower(WorldExit.from_scene_id) == to_id.lower(),
                            func.lower(WorldExit.to_scene_id) == from_id.lower(),
                        ),
                    ),
                )
            )
            world_exit = exit_res.scalars().first()
        else:
            # Lookup by exit DB primary key (case-insensitive for UUIDs and custom string keys)
            clean_ref = exit_ref.strip()
            exit_res = await self.db.execute(
                select(WorldExit).where(
                    or_(
                        WorldExit.session_id == self.state.session_id,
                        and_(
                            WorldExit.template_id == self.state.template_id,
                            WorldExit.session_id.is_(None),
                        ),
                    ),
                    or_(
                        WorldExit.id == clean_ref,
                        func.lower(WorldExit.id) == clean_ref.lower(),
                    ),
                )
            )
            world_exit = exit_res.scalars().first()

        if not world_exit:
            err = f"Exit '{exit_ref}' not found."
            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': err})}\n\n"
            return

        if world_exit.is_locked:
            err = str(world_exit.lock_description or "The way is locked.")
            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': err})}\n\n"
            return

        if world_exit.from_scene_id.lower() == current_scene_id.lower():
            target_scene_id = world_exit.to_scene_id
        elif (
            str(world_exit.exit_type or "").lower() == "bidirectional"
            and world_exit.to_scene_id.lower() == current_scene_id.lower()
        ):
            target_scene_id = world_exit.from_scene_id
        else:
            err = "This exit does not connect to the current scene."
            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': err})}\n\n"
            return

        # Resolve target scene label
        scene_res = await self.db.execute(
            select(WorldScene).where(
                or_(
                    WorldScene.session_id == self.state.session_id,
                    and_(
                        WorldScene.template_id == self.state.template_id,
                        WorldScene.session_id.is_(None),
                    ),
                ),
                or_(
                    WorldScene.id == target_scene_id,
                    func.lower(WorldScene.id) == str(target_scene_id).lower(),
                ),
            )
        )
        scene = scene_res.scalars().first()
        if not scene:
            err = "The target scene is not available."
            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': err})}\n\n"
            return

        # Commit the scene change with canonical scene ID
        self.state.current_scene_id = scene.id
        await self.db.commit()

        # Signal frontend to clear old chat bubbles
        yield f"event: scene_transition\ndata: {json.dumps({'scene_id': scene.id, 'scene_label': scene.label})}\n\n"

        # Build a narration prompt for the new scene
        exit_label = world_exit.label or "the exit"
        scene_label = scene.label or target_scene_id
        narration_prompt = (
            f"[SCENE_TRANSITION] The player moves through {exit_label} and enters {scene_label}. "
            f"Describe the new location vividly: atmosphere, key details, and anything immediately notable. "
            f"Do not summarize previous events."
        )

        yield f"event: status\ndata: {json.dumps({'content': f'Entering {scene_label}...'})}\n\n"

        # Run full LLM cycle to narrate the new scene
        try:
            async for chunk in self._run_llm_cycle(narration_prompt, False, language=language):
                yield chunk
        except Exception as exc:
            user_safe_error = _friendly_llm_error_message(exc) or _friendly_llm_unexpected_error_message()
            yield f"event: error\ndata: {json.dumps({'detail': user_safe_error})}\n\n"

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
        elif debug_info.startswith("[TRIGGER_NPC_DROP_ITEMS]"):
            dropped_info = await self._debug_drop_npc_items()
            debug_info = f"DEBUG: {dropped_info}"

        
        # New: Combat Debug Commands
        elif cmd_args == "win_fight":
            combat = self._read_combat_state()
            if combat and combat.get("active"):
                combat["active"] = False
                combat["outcome"] = "victory"
                combat["enemy"]["hp"] = 0

                # Mirror normal victory behavior so debug wins can be used for loot testing.
                enemy_id = combat["enemy"]["id"]
                enemy_res = await self.db.execute(
                    select(WorldEntity).where(
                        WorldEntity.id == enemy_id,
                        WorldEntity.session_id == self.game_id,
                    )
                )
                enemy_ent = enemy_res.scalars().first()

                xp_gained = 0
                if enemy_ent:
                    xp_gained = self._award_combat_victory_xp(enemy_ent)
                combat["status_note"] = f"Combat won via debug command. (+{xp_gained} XP)"

                loot_items = await self._normalize_loot_items(
                    list(combat.get("enemy", {}).get("inventory") or (enemy_ent.inventory if enemy_ent else []) or [])
                )
                combat["loot_pending"] = bool(loot_items)
                combat["loot_items"] = loot_items

                states = dict(self.state.entity_states or {})
                if enemy_id not in states:
                    states[enemy_id] = {}
                states[enemy_id]["hp"] = 0
                states[enemy_id]["inventory"] = []
                enemy_is_killable = (states[enemy_id].get("is_killable") if "is_killable" in states[enemy_id] else enemy_ent.is_killable if enemy_ent else True)
                if enemy_is_killable:
                    states[enemy_id]["is_defeated"] = True
                    states[enemy_id]["is_attackable"] = False
                self.state.entity_states = states
                flag_modified(self.state, "entity_states")

                self._append_combat_log(combat, combat["status_note"], "outcome")
                if loot_items:
                    loot_msg = "Victory! Loot available. Use /loot take <item>, /loot leave <item>, /loot done"
                    self._append_combat_log(combat, loot_msg, "loot")
                self._set_combat_state(combat)
                debug_info = f"DEBUG: Combat forced to VICTORY (loot phase enabled). (+{xp_gained} XP)"
        
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

        if debug_info.startswith("[DEBUG_LOG_OFF]"):
            await self.db.commit()
            map_payload = await self._build_map_payload()
            final_data = jsonable_encoder({
                **map_payload,
                'sheet': await AdventureLogic.build_sheet_snapshot(self.avatar, self.state, self.db),
                'combat': AdventureLogic.get_combat_snapshot(self.state),
                'awards': self.adventure.awards if self.adventure else [],
                'game_over_reason': self.state.session.status_note if self.state.session else None,
                **self._build_prompt_suggestions_payload(),
                **self._build_terminal_flags_payload(),
                'status': 'success'
            })
            yield f"event: final\ndata: {json.dumps(final_data)}\n\n"
            return

        # Save the user's /debug command to DB so it can be deleted in debug mode.
        user_chat_msg = ChatMessage(session_id=self.state.session_id, role="user", content=user_msg)
        self.db.add(user_chat_msg)
        await self.db.flush()
        user_msg_id = str(user_chat_msg.id)

        # Send debug info as a system message so it appears in chat.
        # Include both IDs so the frontend can attach them for deletion.
        system_chat_msg = ChatMessage(session_id=self.state.session_id, role="system", content=debug_info)
        self.db.add(system_chat_msg)
        await self.db.flush()
        system_msg_id = str(system_chat_msg.id)

        await self.db.commit()
        yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': debug_info, 'is_debug': True, 'id': system_msg_id, 'user_msg_id': user_msg_id})}\n\n"

        final_data = jsonable_encoder({
            'sheet': await AdventureLogic.build_sheet_snapshot(self.avatar, self.state, self.db),
            'entities': await AdventureLogic.build_session_entities(self.db, self.state),
            'combat': AdventureLogic.get_combat_snapshot(self.state),
            **self._build_prompt_suggestions_payload(),
            **self._build_terminal_flags_payload(),
            'status': 'success',
        })
        yield f"event: final\ndata: {json.dumps(final_data)}\n\n"

    async def _handle_debug_gen_item(self, prompt: str) -> AsyncGenerator[str, None]:
        """Debug helper to force-generate an item based on a prompt."""
        instruction = f"DEBUG COMMAND: The user wants you to generate an item now. Instruction: {prompt}"
        # We temporarily set the prompt as if it was the user message
        async for chunk in self._run_llm_cycle(instruction, self.avatar):
            yield chunk

        map_payload = await self._build_map_payload()
        final_data = jsonable_encoder({
            **map_payload,
            'sheet': await AdventureLogic.build_sheet_snapshot(self.avatar, self.state, self.db),
            'combat': AdventureLogic.get_combat_snapshot(self.state),
            'awards': self.adventure.awards,
            'game_over_reason': self.state.session.status_note if self.state.session else None,
            **self._build_prompt_suggestions_payload(),
            **self._build_terminal_flags_payload(),
            'status': 'success'
        })
        yield f"event: final\ndata: {json.dumps(final_data)}\n\n"

    async def _debug_drop_npc_items(self) -> str:
        # Find all NPCs in the current scene
        res = await self.db.execute(
            select(WorldEntity).where(
                WorldEntity.session_id == self.game_id,
                WorldEntity.entity_type == "NPC",
                WorldEntity.current_scene_id == self.state.current_scene_id
            )
        )
        npcs = res.scalars().all()
        if not npcs:
            return "No NPCs found in the current scene."

        overrides = self.state.entity_states or {}
        dropped_items_summary = []

        for npc in npcs:
            # Determine NPC's current inventory
            npc_inv = overrides.get(npc.id, {}).get("inventory")
            if npc_inv is None:
                npc_inv = npc.inventory or []

            if not npc_inv:
                continue

            # Drop each item in scene
            for item in npc_inv:
                await self._spawn_scene_item(item)
                dropped_items_summary.append(f"{item.get('name') or 'Item'} (from {npc.name})")

            # Clear NPC's inventory in DB
            npc.inventory = []
            self.db.add(npc)

            # Clear NPC's inventory in session state overrides
            states = dict(self.state.entity_states or {})
            if npc.id not in states:
                states[npc.id] = {}
            states[npc.id]["inventory"] = []
            self.state.entity_states = states
            flag_modified(self.state, "entity_states")

        if not dropped_items_summary:
            return "No items to drop from NPCs in the current scene."

        return f"Dropped NPC items: {', '.join(dropped_items_summary)}"

    @staticmethod
    def _is_switch_entity(entity: WorldEntity | dict[str, Any] | None) -> bool:
        if not entity:
            return False
        if isinstance(entity, dict):
            item_type = str(entity.get("item_type") or "").upper()
            metadata_json = entity.get("metadata_json")
        else:
            item_type = str(getattr(entity, "item_type", "") or "").upper()
            metadata_json = getattr(entity, "metadata_json", None)

        if item_type == "SWITCH":
            return True
        return isinstance(metadata_json, dict) and isinstance(metadata_json.get("switch"), dict)

    @staticmethod
    def _switch_config(entity: WorldEntity) -> dict[str, Any]:
        metadata_json = dict(getattr(entity, "metadata_json", None) or {})
        config = metadata_json.get("switch")
        return config if isinstance(config, dict) else {}

    @staticmethod
    def _parse_switch_args(raw_args: str) -> tuple[str, str, str | None] | None:
        raw = (raw_args or "").strip()
        if not raw:
            return None

        quoted = re.match(r'^\s*"(?P<target>.+?)"\s+(?P<state>\S+)(?:\s+(?P<code>\S+))?\s*$', raw)
        if quoted:
            target = quoted.group("target").strip()
            state = quoted.group("state").strip().upper()
            code = quoted.group("code")
            return target, state, (code.strip() if code else None)

        parts = raw.split()
        if len(parts) < 2:
            return None

        target = parts[0].strip()
        state = parts[1].strip().upper()
        code = parts[2].strip() if len(parts) >= 3 else None
        return target, state, code

    async def _resolve_scene_switch(self, target_hint: str) -> WorldEntity | None:
        hint = (target_hint or "").strip().lower()
        if not hint:
            return None

        ent_res = await self.db.execute(
            select(WorldEntity).where(
                WorldEntity.session_id == self.game_id,
                WorldEntity.entity_type == "OBJECT",
            )
        )
        candidates = ent_res.scalars().all()
        states = self.state.entity_states or {}

        best: tuple[int, WorldEntity] | None = None
        for ent in candidates:
            if not self._is_switch_entity(ent):
                continue

            override = states.get(ent.id, {}) if isinstance(states, dict) else {}
            current_scene_id = override.get("current_scene_id", ent.current_scene_id)
            is_hidden = bool(override.get("is_hidden", ent.is_hidden))
            is_in_inventory = bool(override.get("is_in_inventory", ent.is_in_inventory))
            if current_scene_id != self.state.current_scene_id or is_hidden or is_in_inventory:
                continue

            id_token = str(ent.id or "").strip().lower()
            name_token = str(ent.name or "").strip().lower()
            token = ""
            if id_token and id_token == hint:
                token = id_token
            elif name_token and name_token == hint:
                token = name_token
            elif id_token and id_token in hint:
                token = id_token
            elif name_token and name_token in hint:
                token = name_token

            if not token:
                continue

            candidate = (len(token), ent)
            if best is None or candidate[0] > best[0]:
                best = candidate

        return best[1] if best else None

    def _switch_story_flags(self) -> dict[str, bool]:
        states = self.state.entity_states or {}
        raw = states.get("__switch_story_flags__")
        if not isinstance(raw, dict):
            return {}
        return {str(k): bool(v) for k, v in raw.items()}

    def _set_switch_story_flag(self, key: str) -> None:
        key_clean = str(key or "").strip()
        if not key_clean:
            return
        states = dict(self.state.entity_states or {})
        flags = states.get("__switch_story_flags__")
        if not isinstance(flags, dict):
            flags = {}
        flags[key_clean] = True
        states["__switch_story_flags__"] = flags
        self.state.entity_states = states
        flag_modified(self.state, "entity_states")

    def _avatar_inventory_ids(self) -> set[str]:
        ids: set[str] = set()
        for item in (self.avatar.inventory or []):
            if not isinstance(item, dict):
                continue
            raw_id = str(item.get("id") or "").strip().upper()
            if raw_id:
                ids.add(raw_id)
        return ids

    async def _apply_switch_outcomes(self, outcomes: list[Any], on_state: str) -> list[str]:
        messages: list[str] = []
        for outcome in outcomes:
            if not isinstance(outcome, dict):
                continue
            if str(outcome.get("on_state") or "").strip().upper() != on_state.upper():
                continue
            effects = outcome.get("effects")
            if not isinstance(effects, list):
                continue
            for effect in effects:
                if not isinstance(effect, dict):
                    continue
                effect_type = str(effect.get("type") or "").strip().lower()
                if effect_type == "story_flag":
                    key = str(effect.get("key") or "").strip()
                    if key:
                        self._set_switch_story_flag(key)
                        messages.append(f"Story flag set: {key}.")
                elif effect_type == "unlock_exit":
                    target_id = str(effect.get("target_id") or "").strip()
                    if not target_id:
                        continue
                    exit_res = await self.db.execute(
                        select(WorldExit).where(
                            WorldExit.session_id == self.state.session_id,
                            WorldExit.id == target_id,
                        )
                    )
                    ex = exit_res.scalars().first()
                    if ex and ex.is_locked:
                        ex.is_locked = False
                        messages.append(f"Exit unlocked: {ex.label or ex.id}.")
                elif effect_type == "unlock_container":
                    target_id = str(effect.get("target_id") or "").strip()
                    if not target_id:
                        continue
                    states = dict(self.state.entity_states or {})
                    entry = dict(states.get(target_id) or {})
                    entry["locked"] = False
                    states[target_id] = entry
                    self.state.entity_states = states
                    flag_modified(self.state, "entity_states")
                    messages.append(f"Container unlocked: {target_id}.")
        return messages

    async def _execute_switch_command(self, switch_args: str) -> str:
        parsed = self._parse_switch_args(switch_args)
        if not parsed:
            return "Usage: /switch <target> <state> [code] (quote target if it contains spaces)."

        target_hint, target_state, provided_code = parsed
        switch_entity = await self._resolve_scene_switch(target_hint)
        if not switch_entity:
            return f"No switch named '{target_hint}' was found in the current scene."

        config = self._switch_config(switch_entity)
        states = config.get("states")
        if not isinstance(states, list) or len(states) < 2:
            return f"{switch_entity.name} has no valid switch configuration."

        allowed_states = [str(state).strip().upper() for state in states if str(state).strip()]
        if target_state not in allowed_states:
            return f"Invalid state '{target_state}'. Allowed states: {', '.join(allowed_states)}."

        session_states = dict(self.state.entity_states or {})
        entry = dict(session_states.get(switch_entity.id) or {})
        configured_current = str(config.get("initial_state") or allowed_states[0]).strip().upper()
        current_state = str(entry.get("switch_state") or configured_current).strip().upper()
        if current_state == target_state:
            return f"{switch_entity.name} is already set to {target_state}."

        transitions = config.get("transitions")
        transition = None
        if isinstance(transitions, list):
            wildcard_candidate = None
            for candidate in transitions:
                if not isinstance(candidate, dict):
                    continue
                from_state = str(candidate.get("from") or "").strip().upper()
                to_state = str(candidate.get("to") or "").strip().upper()
                if not to_state or to_state != target_state:
                    continue
                if from_state:
                    if from_state == current_state:
                        transition = candidate
                        break
                elif wildcard_candidate is None:
                    wildcard_candidate = candidate
            if transition is None:
                transition = wildcard_candidate

        if transition is not None:
            gates = transition.get("gates") if isinstance(transition.get("gates"), dict) else {}
            required_item = str(gates.get("item") or "").strip().upper()
            required_code = str(gates.get("code") or "").strip()
            required_rule = str(gates.get("rule") or "").strip()
            fail_message = str(transition.get("fail_message") or "").strip()

            if required_item and required_item not in self._avatar_inventory_ids():
                return fail_message or f"{switch_entity.name} does not move."

            if required_code and str(provided_code or "").strip() != required_code:
                return fail_message or f"{switch_entity.name} does not move."

            if required_rule and not self._switch_story_flags().get(required_rule, False):
                return fail_message or f"{switch_entity.name} does not move."

        entry["switch_state"] = target_state
        session_states[switch_entity.id] = entry
        self.state.entity_states = session_states
        flag_modified(self.state, "entity_states")

        narration = config.get("narration") if isinstance(config.get("narration"), dict) else {}
        state_change_notes = narration.get("on_state_change") if isinstance(narration.get("on_state_change"), dict) else {}
        state_note = str(state_change_notes.get(target_state) or "").strip()

        outcome_notes = await self._apply_switch_outcomes(config.get("outcomes") if isinstance(config.get("outcomes"), list) else [], target_state)
        message = f"{switch_entity.name} set to {target_state}."
        if state_note:
            message = f"{message} {state_note}"
        if outcome_notes:
            message = f"{message} {' '.join(outcome_notes)}"
        return message

    async def _handle_slash(self, user_msg: str, response: str) -> AsyncGenerator[str, None]:
        # Handle /map specifically (doesn't use CommandParser)
        if user_msg.lower() == "/map":
            map_payload = await self._build_map_payload()
            final_data = jsonable_encoder({
                **map_payload,
                'sheet': await AdventureLogic.build_sheet_snapshot(self.avatar, self.state, self.db),
                **self._build_prompt_suggestions_payload(),
                **self._build_terminal_flags_payload(),
            })
            yield f"event: final\ndata: {json.dumps(final_data)}\n\n"
            return
            
        if response.startswith("[TRIGGER_TAKE_DIRECT]"):
            entity_id_or_name = response[21:].strip()
            take_npc = await self._find_scene_npc_by_hint(entity_id_or_name)
            if take_npc and self._is_npc_defeated(take_npc):
                msg = f"{take_npc.name} is defeated. Only inspect is available."
                yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"
                async for chunk in self._emit_combat_final(msg):
                    yield chunk
                return

            # Find portable OBJECT in current scene (snapshot), matching by name or ID (case-insensitive).
            ent_res = await self.db.execute(
                select(WorldEntity).where(
                    WorldEntity.session_id == self.game_id,
                    WorldEntity.current_scene_id == self.state.current_scene_id,
                    WorldEntity.entity_type == "OBJECT",
                    WorldEntity.is_hidden.is_(False),
                    WorldEntity.is_in_inventory.is_(False),
                )
            )
            candidates = ent_res.scalars().all()
            hint_lower = entity_id_or_name.lower()
            ent = None
            for candidate in candidates:
                if candidate.id and candidate.id.lower() == hint_lower:
                    ent = candidate
                    break
                if candidate.name and candidate.name.lower() == hint_lower:
                    ent = candidate
                    break
            if ent and ent.is_portable and str(ent.item_type or "").upper() != "SWITCH":
                # Move to inventory
                new_inv = list(self.avatar.inventory)
                item_dict = jsonable_encoder({c.name: getattr(ent, c.name) for c in ent.__table__.columns})
                new_inv.append(item_dict)
                self.avatar.inventory = new_inv
                
                # Update session state instead of global entity
                states = dict(self.state.entity_states or {})
                if ent.id not in states:
                    states[ent.id] = {}
                states[ent.id]["is_in_inventory"] = True
                self.state.entity_states = states
                flag_modified(self.state, "entity_states")
                response = f"Added {ent.name} to your inventory."
                await self._check_special_action_unlocks("FIND_ITEM", ent.id)
            else:
                response = "You cannot take that."
        
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

        if response.startswith("[TRIGGER_DROP]"):
            item_name = response[14:].strip()
            if not item_name:
                response = "Usage: /drop <item name>"
            else:
                # Find item in inventory
                item_idx = -1
                for idx, item in enumerate(self.avatar.inventory or []):
                    if isinstance(item, dict) and item.get("name", "").lower() == item_name.lower():
                        item_idx = idx
                        break
                
                if item_idx == -1:
                    response = f"You don't have '{item_name}' in your inventory."
                else:
                    new_inventory = list(self.avatar.inventory)
                    dropped_item = new_inventory.pop(item_idx)
                    self.avatar.inventory = new_inventory
                    
                    # Spawn in scene
                    await self._spawn_scene_item(dropped_item)
                    response = f"You dropped {dropped_item.get('name')}."

        if response.startswith("[TRIGGER_OPEN]"):
            container_hint = response.replace("[TRIGGER_OPEN]", "").strip()
            if not container_hint:
                response = "Usage: /open <container>"
            else:
                scene_container, inventory_container, _ = await self._resolve_container_target(container_hint)
                container_name = (scene_container.name if scene_container else inventory_container.get("name")) if (scene_container or inventory_container) else None
                if not container_name:
                    response = f"No container named '{container_hint}' was found."
                else:
                    is_locked = self._is_container_locked(scene_container, inventory_container)
                    if is_locked:
                        response = f"{container_name} is locked."
                    else:
                        container_inventory = await self._get_container_inventory(scene_container, inventory_container)
                        response = f"{container_name} contains {len(container_inventory)} item(s)."

        if response.startswith("[TRIGGER_SWITCH]"):
            switch_args = response.replace("[TRIGGER_SWITCH]", "").strip()
            response = await self._execute_switch_command(switch_args)

        if response.startswith("[TRIGGER_CONTAINER_TAKE_ALL]"):
            container_hint = response.replace("[TRIGGER_CONTAINER_TAKE_ALL]", "").strip()
            if not container_hint:
                response = "Usage: /container_take_all <container>"
            else:
                scene_container, inventory_container, inventory_idx = await self._resolve_container_target(container_hint)
                container_name = (scene_container.name if scene_container else inventory_container.get("name")) if (scene_container or inventory_container) else None
                if not container_name:
                    response = f"No container named '{container_hint}' was found."
                else:
                    is_locked = self._is_container_locked(scene_container, inventory_container)
                    if is_locked:
                        response = f"{container_name} is locked."
                    else:
                        raw_items = await self._get_container_inventory(scene_container, inventory_container)
                        normalized_items = await self._normalize_container_items(raw_items)
                        if not normalized_items:
                            response = f"{container_name} is empty."
                        else:
                            new_inventory = list(self.avatar.inventory or [])
                            for item in normalized_items:
                                new_inventory.append(item)
                                await self._move_container_item_to_inventory(item)
                            self.avatar.inventory = new_inventory
                            await self._clear_container_inventory(scene_container, inventory_container, inventory_idx)
                            response = f"You take all {len(normalized_items)} item(s) from {container_name}."

        if response.startswith("[TRIGGER_CONTAINER_DROP_SCENE]"):
            container_hint = response.replace("[TRIGGER_CONTAINER_DROP_SCENE]", "").strip()
            if not container_hint:
                response = "Usage: /container_drop_scene <container>"
            else:
                scene_container, inventory_container, inventory_idx = await self._resolve_container_target(container_hint)
                container_name = (scene_container.name if scene_container else inventory_container.get("name")) if (scene_container or inventory_container) else None
                if not container_name:
                    response = f"No container named '{container_hint}' was found."
                else:
                    is_locked = self._is_container_locked(scene_container, inventory_container)
                    if is_locked:
                        response = f"{container_name} is locked."
                    else:
                        raw_items = await self._get_container_inventory(scene_container, inventory_container)
                        normalized_items = await self._normalize_container_items(raw_items)
                        if not normalized_items:
                            response = f"{container_name} is empty."
                        else:
                            for item in normalized_items:
                                moved = await self._move_container_item_to_scene(item)
                                if not moved:
                                    await self._spawn_scene_item(item)
                            await self._clear_container_inventory(scene_container, inventory_container, inventory_idx)
                            response = f"You drop {len(normalized_items)} item(s) from {container_name} into the scene."

        if response.startswith("[TRIGGER_CONSUME]"):
            item_name = response.replace("[TRIGGER_CONSUME]", "").strip()
            action_msg = self._consume_item_now(item_name)
            await self._save_chat_message("system", action_msg)
            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': action_msg})}\n\n"
            response = action_msg # Allow it to fall through to persist and yield final state

        # PERSIST AND YIELD RESPONSE (For all commands including equip/unequip)
        if response and not response.startswith("[TRIGGER_"):
            await self._save_chat_message("system", response)
            yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': response})}\n\n"

        await self.db.commit()
        final_data = jsonable_encoder({
            'sheet': await AdventureLogic.build_sheet_snapshot(self.avatar, self.state, self.db),
            'entities': await AdventureLogic.build_session_entities(self.db, self.state),
            'combat': AdventureLogic.get_combat_snapshot(self.state),
            **self._build_prompt_suggestions_payload(),
            **self._build_terminal_flags_payload(),
        })
        yield f"event: final\ndata: {json.dumps(final_data)}\n\n"
        self.stop_requested = True # Stop after direct slash response


    async def _resolve_container_target(self, hint: str) -> tuple[WorldEntity | None, dict[str, Any] | None, int | None]:
        normalized_hint = (hint or "").strip().lower()
        if not normalized_hint:
            return None, None, None

        ent_res = await self.db.execute(
            select(WorldEntity).where(
                WorldEntity.session_id == self.game_id,
                WorldEntity.current_scene_id == self.state.current_scene_id,
                WorldEntity.entity_type == "OBJECT",
                or_(
                    WorldEntity.id == hint,
                    WorldEntity.name == hint,
                ),
            )
        )
        scene_ent = ent_res.scalars().first()
        if scene_ent and str(scene_ent.item_type or "").upper() == "CONTAINER":
            return scene_ent, None, None

        for idx, inv_item in enumerate(self.avatar.inventory or []):
            if not self._is_container_item(inv_item):
                continue
            item_id = str(inv_item.get("id") or "").strip().lower()
            item_name = str(inv_item.get("name") or "").strip().lower()
            if normalized_hint in {item_id, item_name}:
                return None, dict(inv_item), idx

        return None, None, None

    async def _get_container_inventory(self, scene_container: WorldEntity | None, inventory_container: dict[str, Any] | None) -> list[Any]:
        if scene_container:
            states = dict(self.state.entity_states or {})
            state_inv = (states.get(scene_container.id) or {}).get("inventory")
            if isinstance(state_inv, list):
                return list(state_inv)
            return list(scene_container.inventory or [])

        if inventory_container:
            return list(inventory_container.get("inventory") or [])

        return []

    async def _normalize_container_item_ref(self, item_ref: Any) -> dict[str, Any] | None:
        if isinstance(item_ref, dict):
            return dict(item_ref)

        if isinstance(item_ref, str) and item_ref.strip():
            item_id = item_ref.strip()
            ent_res = await self.db.execute(
                select(WorldEntity).where(
                    WorldEntity.session_id == self.game_id,
                    WorldEntity.id == item_id,
                )
            )
            ent = ent_res.scalars().first()
            if ent:
                item_data = jsonable_encoder({c.name: getattr(ent, c.name) for c in ent.__table__.columns})
                metadata = dict(ent.metadata_json or {})
                for key in [
                    "hp_change",
                    "mana_change",
                    "stamina_change",
                    "stat_modifier_strength",
                    "stat_modifier_dexterity",
                    "stat_modifier_intelligence",
                    "stat_modifier_wisdom",
                    "stat_modifier_charisma",
                    "stat_modifier_armor_class",
                ]:
                    if key not in item_data and key in metadata:
                        item_data[key] = metadata[key]
                return item_data

            return {"id": item_id, "name": item_id}

        return None

    async def _normalize_container_items(self, raw_items: list[Any]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for item in raw_items or []:
            normalized_item = await self._normalize_container_item_ref(item)
            if normalized_item:
                normalized.append(normalized_item)
        return normalized

    async def _move_container_item_to_inventory(self, item: dict[str, Any]) -> None:
        item_id = str(item.get("id") or "").strip()
        if not item_id:
            return

        ent_res = await self.db.execute(
            select(WorldEntity).where(
                WorldEntity.session_id == self.game_id,
                WorldEntity.id == item_id,
            )
        )
        ent = ent_res.scalars().first()
        if ent:
            ent.is_in_inventory = True
            ent.current_scene_id = "INVENTORY"
            ent.is_hidden = False

        states = dict(self.state.entity_states or {})
        if item_id not in states:
            states[item_id] = {}
        states[item_id]["is_in_inventory"] = True
        states[item_id]["current_scene_id"] = "INVENTORY"
        states[item_id]["is_hidden"] = False
        self.state.entity_states = states
        flag_modified(self.state, "entity_states")

    async def _move_container_item_to_scene(self, item: dict[str, Any]) -> bool:
        item_id = str(item.get("id") or "").strip()
        if not item_id:
            return False

        ent_res = await self.db.execute(
            select(WorldEntity).where(
                WorldEntity.session_id == self.game_id,
                WorldEntity.id == item_id,
            )
        )
        ent = ent_res.scalars().first()
        if not ent:
            return False

        ent.is_in_inventory = False
        ent.current_scene_id = self.state.current_scene_id
        ent.is_hidden = False

        states = dict(self.state.entity_states or {})
        if item_id not in states:
            states[item_id] = {}
        states[item_id]["is_in_inventory"] = False
        states[item_id]["current_scene_id"] = self.state.current_scene_id
        states[item_id]["is_hidden"] = False
        self.state.entity_states = states
        flag_modified(self.state, "entity_states")
        return True

    async def _clear_container_inventory(
        self,
        scene_container: WorldEntity | None,
        inventory_container: dict[str, Any] | None,
        inventory_idx: int | None,
    ) -> None:
        if scene_container:
            scene_container.inventory = []
            self.db.add(scene_container)

            states = dict(self.state.entity_states or {})
            if scene_container.id not in states:
                states[scene_container.id] = {}
            states[scene_container.id]["inventory"] = []
            self.state.entity_states = states
            flag_modified(self.state, "entity_states")

        if inventory_container is not None and inventory_idx is not None:
            updated_inventory = list(self.avatar.inventory or [])
            if 0 <= inventory_idx < len(updated_inventory) and isinstance(updated_inventory[inventory_idx], dict):
                updated_container = dict(updated_inventory[inventory_idx])
                updated_container["inventory"] = []
                updated_inventory[inventory_idx] = updated_container
                self.avatar.inventory = updated_inventory

