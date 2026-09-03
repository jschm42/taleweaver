from __future__ import annotations

import asyncio
import copy
import json
import logging
import re
import uuid
import os
from copy import deepcopy
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from sqlalchemy import and_, or_, select
from sqlalchemy.orm.attributes import flag_modified

from backend.api.routes.adventures.logic import AdventureLogic
from backend.core import prompts
from backend.core.config import settings
from backend.engine.map_engine import MapEngine
from backend.engine.quest_manager import QuestManager
from backend.engine.rule_engine import (
    EntityMovement,
    GameEvent,
    GameOverException,
    RuleEngine,
    WorldEntityUpdate,
)
from backend.models.adventure_template import AdventureTemplate
from backend.models.chat import ChatMessage
from backend.models.user import User
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene
from backend.utils.path_security import ensure_within_data_dir as _ensure_within_data_dir
from backend.utils.path_security import sanitize_path_component as _sanitize_path_component

if TYPE_CHECKING:
    from backend.api.routes.adventures.gameplay_logic import GameTurnManager

logger = logging.getLogger(__name__)

CHECKPOINT_REASON_SCENE_CHANGE = "SCENE_CHANGE"
CHECKPOINT_REASON_QUEST_UPDATE = "QUEST_UPDATE"
CHECKPOINT_REASON_AWARD_GRANTED = "AWARD_GRANTED"


class TurnStateApplier:
    """Applies game event outcomes to the database, session state, entities, inventory, and awards."""

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

    def _queue_checkpoint(self, *args, **kwargs):
        return self.manager._queue_checkpoint(*args, **kwargs)

    async def _save_chat_message(self, *args, **kwargs):
        return await self.manager._save_chat_message(*args, **kwargs)

    def _apply_gm_notes_update(self, *args, **kwargs):
        return self.manager._apply_gm_notes_update(*args, **kwargs)

    def _award_combat_victory_xp(self, *args, **kwargs):
        return self.manager._award_combat_victory_xp(*args, **kwargs)

    def _collect_existing_item_ids(self, *args, **kwargs):
        return self.manager._collect_existing_item_ids(*args, **kwargs)

    async def _spawn_scene_item(self, *args, **kwargs):
        return await self.manager._spawn_scene_item(*args, **kwargs)

    async def _apply_adventure_generator_tools(self, *args, **kwargs):
        return await self.manager._apply_adventure_generator_tools(*args, **kwargs)

    def _upsert_entity_update(self, event: GameEvent, entity_id: str, **fields: object) -> None:
        """Insert or merge a WorldEntityUpdate for ``entity_id`` into the event."""
        if not entity_id:
            return
        if event.updated_entities is None:
            event.updated_entities = []
        for up in event.updated_entities:
            if up.entity_id == entity_id:
                for key, value in fields.items():
                    setattr(up, key, value)
                return
        event.updated_entities.append(WorldEntityUpdate(entity_id=entity_id, **fields))  # type: ignore[arg-type]

    def _upsert_entity_movement(self, event: GameEvent, entity_id: str, to_scene_id: str) -> None:
        """Insert or merge an EntityMovement for ``entity_id`` into the event."""
        if not entity_id or not to_scene_id:
            return
        if event.moved_entities is None:
            event.moved_entities = []
        for move in event.moved_entities:
            if move.entity_id == entity_id:
                move.to_scene_id = to_scene_id
                return
        event.moved_entities.append(EntityMovement(entity_id=entity_id, to_scene_id=to_scene_id))


    async def _build_map_payload(self) -> dict:
        """Helper to build the augmented map payload for the frontend."""
        world_map = await AdventureLogic.get_or_create_map(self.db, self.state.template_id)
        if not world_map:
            return {"nodes": {}, "edges": [], "current_scene_id": None}

        map_dict = MapEngine.to_dict(world_map)
        map_dict["current_scene_id"] = MapEngine._safe_id(self.state.current_scene_id)
        # Heal stale image_url values (e.g. from deleted sessions) in the map nodes
        for node in map_dict.get("nodes", {}).values():
            if isinstance(node, dict) and node.get("image_url"):
                node["image_url"] = AdventureLogic.resolve_existing_data_asset_url(node["image_url"])
        
        # Augment with adjacent unvisited scenes
        # Fetch exits for this session or template
        exit_query = select(WorldExit).where(
            or_(
                WorldExit.session_id == self.state.session_id,
                WorldExit.template_id == self.state.template_id
            )
        )
        exits_res = await self.db.execute(exit_query)
        exits = list(exits_res.scalars().all())
        map_dict = MapEngine.augment_map_data(map_dict, exits, self.state.current_scene_id)

        return map_dict

    async def _build_awards_payload(self, adventure: AdventureTemplate | None) -> list[dict]:
        """Helper to build the awards payload with earned status."""
        if not self.user:
            return []
            
        awards_list = (adventure.awards if adventure else (AdventureLogic.extract_manifest_snapshot(self.state).get("adventure") or {}).get("awards")) or []
        
        return [
            {
                **aw,
                "is_earned": any(
                    ea.get("key") == aw.get("key")
                    and (
                        ea.get("template_id") == (adventure.id if adventure else self.state.template_id)
                        or ea.get("adventure_id") == (adventure.id if adventure else self.state.template_id)
                    )
                    for ea in (self.user.earned_awards or [])
                ),
            }
            for aw in awards_list
        ]

    async def _apply_game_event(self, event: GameEvent) -> list[str]:
        """Applies technical mutations from a GameEvent to the database and session state. Returns messages for the UI."""
        system_messages: list[str] = []
        existing_item_ids = await self._collect_existing_item_ids()

        def _is_consumable(item: Any) -> bool:
            return str(getattr(item, "item_type", "") or "").upper() == "CONSUMABLE"

        def _allocate_copied_item_id(source_id: str | None) -> str:
            base = re.sub(r"[^A-Za-z0-9_\-]", "_", source_id or "CONSUMABLE")[:40] or "CONSUMABLE"
            counter = 1
            candidate = f"{base}_COPY_{counter}"
            while candidate in existing_item_ids:
                counter += 1
                candidate = f"{base}_COPY_{counter}"
            return candidate
        
        # If we are removing items in this event, they don't count as "existing" for duplicate checks
        # if the LLM wants to replace them with an updated version using the same ID.
        if event.removed_inventory_item_ids:
            logger.info("[Turn %s] Removing from duplicate check: %s", self.game_id, event.removed_inventory_item_ids)
            existing_item_ids -= set(event.removed_inventory_item_ids)

        logger.info("[Turn %s] Existing inventory IDs after removals: %s", self.game_id, list(existing_item_ids))

        if event.new_inventory_items:
            filtered_inventory_items = []
            for item in event.new_inventory_items:
                match = (
                    next(
                        (
                            i
                            for i in (self.avatar.inventory or [])
                            if isinstance(i, dict) and i.get("id") == item.id
                        ),
                        None,
                    )
                    if item.id
                    else None
                )

                if item.id and item.id in existing_item_ids and _is_consumable(item):
                    if not item.image_url and isinstance(match, dict) and match.get("image_url"):
                        item.image_url = match.get("image_url")
                    source_id = item.id
                    item.id = _allocate_copied_item_id(source_id)
                    logger.info(
                        "[Turn %s] Cloning duplicate consumable %s as %s",
                        self.game_id,
                        source_id,
                        item.id,
                    )

                if not item.image_url:
                    try:
                        from backend.engine.media_engine import MediaEngine
                        from backend.core.config import settings
                        import os
                        import uuid
                        
                        item_type = item.item_type or "PICKABLE"
                        safe_id = re.sub(r"[^A-Za-z0-9_\-]", "_", item.id or f"LOOT_{uuid.uuid4().hex[:8]}")[:50]
                        safe_adventure_id = _sanitize_path_component(self.adventure.id) or "adventure"
                        target_dir = _ensure_within_data_dir(
                            os.path.join(settings.DATA_DIR, "adventures", "library", safe_adventure_id, "entities")
                        )
                        item.image_url = await MediaEngine.generate_placeholder(
                            adventure_id=self.adventure.id,
                            entity_id=safe_id,
                            target_dir=target_dir,
                            category=f"ITEM_{item_type.upper()}"
                        )
                    except Exception as e:
                        logger.error("Failed to generate new inventory item placeholder: %s", e)

                if item.id and item.id in existing_item_ids:
                    # Check if it's a true duplicate (same name)
                    if match:
                        if match.get("name") == item.name:
                            logger.info(
                                "[Turn %s] Skipping true duplicate inventory item id: %s",
                                self.game_id,
                                item.id,
                            )
                            continue
                        else:
                            logger.info(
                                "[Turn %s] Permitting implied update for item id %s (Name: %s -> %s)",
                                self.game_id,
                                item.id,
                                match.get("name"),
                                item.name
                            )
                    else:
                        logger.info(
                            "[Turn %s] Permitting pickup/implied update for item id %s (exists in session but not in inventory)",
                            self.game_id,
                            item.id,
                        )
                
                filtered_inventory_items.append(item)
                if item.id:
                    existing_item_ids.add(item.id)
            event.new_inventory_items = filtered_inventory_items

        if event.spawned_items:
            filtered_spawned_items = []
            for item in event.spawned_items:
                match = (
                    next(
                        (
                            i
                            for i in (self.avatar.inventory or [])
                            if isinstance(i, dict) and i.get("id") == item.id
                        ),
                        None,
                    )
                    if item.id
                    else None
                )
                # Allow if it's a replacement for an item being removed
                is_replacement = event.removed_inventory_item_ids and item.id in event.removed_inventory_item_ids
                if item.id and item.id in existing_item_ids and not is_replacement and _is_consumable(item):
                    if not item.image_url and isinstance(match, dict) and match.get("image_url"):
                        item.image_url = match.get("image_url")
                    source_id = item.id
                    item.id = _allocate_copied_item_id(source_id)
                    logger.info(
                        "[Turn %s] Cloning duplicate spawned consumable %s as %s",
                        self.game_id,
                        source_id,
                        item.id,
                    )

                if item.id and item.id in existing_item_ids and not is_replacement:
                     # Check if it's a true duplicate (same name)
                    if match and match.get("name") == item.name:
                        logger.info(
                            "[Turn %s] Skipping true duplicate spawned item id: %s",
                            self.game_id,
                            item.id,
                        )
                        continue
                
                filtered_spawned_items.append(item)
                if item.id:
                    existing_item_ids.add(item.id)
            event.spawned_items = filtered_spawned_items

        if event.new_status_effects:
            for effect in event.new_status_effects:
                msg = f"You are now: {effect}"
                await self._save_chat_message("system", msg)
                system_messages.append(msg)

        RuleEngine.apply_event(self.avatar, event)
        
        state_dirty = False
        if event.new_scene_id and event.new_scene_id != self.state.current_scene_id:
            # Enforce that the target scene is adjacent (connected by a WorldExit from the current scene)
            exit_res = await self.db.execute(
                select(WorldExit).where(
                    WorldExit.session_id == self.state.session_id,
                    or_(
                        and_(
                            WorldExit.from_scene_id == self.state.current_scene_id,
                            WorldExit.to_scene_id == event.new_scene_id
                        ),
                        and_(
                            WorldExit.from_scene_id == event.new_scene_id,
                            WorldExit.to_scene_id == self.state.current_scene_id,
                            WorldExit.exit_type == "bidirectional"
                        )
                    )
                )
            )
            valid_exit = exit_res.scalars().first()
            if not valid_exit:
                blocked_msg = f"Movement blocked: The destination '{event.new_scene_id}' is not adjacent to your current location."
                await self._save_chat_message("system", blocked_msg)
                system_messages.append(blocked_msg)

                logger.warning(
                    f"[Turn {self.game_id}] Blocked invalid/non-adjacent scene transition: "
                    f"{self.state.current_scene_id} -> {event.new_scene_id}"
                )
                event.new_scene_id = None
                event.scene_label = None
                event.exit_label = None
            else:
                old_scene_id = self.state.current_scene_id
                self.state.current_scene_id = event.new_scene_id
                state_dirty = True
                
                # Map Update
                try:
                    world_map = await AdventureLogic.get_or_create_map(self.db, self.state.template_id)
                    # 1. Register exit between scenes
                    MapEngine.register_exit(
                        world_map, 
                        old_scene_id, 
                        event.new_scene_id, 
                        exit_label=event.exit_label or "",
                        exit_type=valid_exit.exit_type if valid_exit else "one_way"
                    )
                    # 2. Register visit to the new scene
                    # Use session snapshot for scene data
                    scene_res = await self.db.execute(
                        select(WorldScene).where(
                            WorldScene.id == event.new_scene_id,
                            WorldScene.session_id == self.state.session_id,
                        )
                    )
                    new_scene_db = scene_res.scalars().first()
                    
                    # Add system message for scene change
                    scene_name = new_scene_db.label if new_scene_db else (event.scene_label or "a new location")
                    msg = f"You have entered: {scene_name}"
                    await self._save_chat_message("system", msg)
                    system_messages.append(msg)
                    self._queue_checkpoint(CHECKPOINT_REASON_SCENE_CHANGE, scene_label=scene_name)

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
                if eid not in states:
                    states[eid] = {}
                if move.to_scene_id: 
                    states[eid]["current_scene_id"] = move.to_scene_id
                    # If moving to a new scene, clear spatial position unless a new one is provided
                    if not move.to_spatial_position:
                        states[eid]["spatial_position"] = None
                    
                    # Emit system message for NPC movement
                    ent_name = eid
                    ent_res = await self.db.execute(
                        select(WorldEntity).where(
                            WorldEntity.id == eid,
                            WorldEntity.session_id == self.game_id
                        )
                    )
                    ent_obj = ent_res.scalars().first()
                    if ent_obj:
                        ent_name = ent_obj.name
                    scene_label = move.to_scene_id
                    scene_res = await self.db.execute(
                        select(WorldScene).where(
                            WorldScene.id == move.to_scene_id,
                            WorldScene.session_id == self.game_id
                        )
                    )
                    scene_obj = scene_res.scalars().first()
                    if scene_obj:
                        scene_label = scene_obj.label
                    msg = f"{ent_name} moved to {scene_label}."
                    await self._save_chat_message("system", msg)
                    system_messages.append(msg)
                    
                if move.to_spatial_position: 
                    states[eid]["spatial_position"] = move.to_spatial_position
                state_dirty = True

        if event.updated_entities:
            session_ents_res = await self.db.execute(
                select(WorldEntity).where(WorldEntity.session_id == self.game_id)
            )
            canonical_ents = session_ents_res.scalars().all()
            ent_lookup_by_id = {e.id.upper(): e.id for e in canonical_ents if e.id}
            ent_lookup_by_name = {(e.name or "").strip().lower(): e.id for e in canonical_ents if e.name}

            for update in event.updated_entities:
                raw_eid = str(update.entity_id or "").strip()
                canonical_id = (
                    ent_lookup_by_id.get(raw_eid.upper())
                    or ent_lookup_by_name.get(raw_eid.lower())
                    or raw_eid
                )
                eid = canonical_id
                ent_obj = None
                if eid not in states:
                    states[eid] = {}
                if update.name is not None:
                    states[eid]["name"] = update.name
                if update.description is not None:
                    states[eid]["description"] = update.description
                if update.spatial_position is not None:
                    states[eid]["spatial_position"] = update.spatial_position
                if update.is_hidden is not None:
                    states[eid]["is_hidden"] = update.is_hidden
                if update.hp is not None:
                    states[eid]["hp"] = update.hp
                if update.mana is not None:
                    states[eid]["mana"] = update.mana
                if update.stamina is not None:
                    states[eid]["stamina"] = update.stamina
                if update.is_attackable is not None:
                    states[eid]["is_attackable"] = update.is_attackable
                if update.is_killable is not None:
                    states[eid]["is_killable"] = update.is_killable
                if update.switch_state is not None:
                    states[eid]["switch_state"] = update.switch_state
                if update.is_defeated is not None:
                    was_defeated = self.state.entity_states.get(eid, {}).get("is_defeated", False)
                    if not was_defeated and update.is_defeated is True:
                        ent_res = await self.db.execute(
                            select(WorldEntity).where(
                                WorldEntity.id == eid,
                                WorldEntity.session_id == self.game_id,
                            )
                        )
                        ent_obj = ent_res.scalars().first()
                        if ent_obj and ent_obj.entity_type == "NPC":
                            xp_gained = self._award_combat_victory_xp(ent_obj)
                            msg = f"Defeated {ent_obj.name}!"
                            xp_msg = f"you gained {xp_gained} XP"
                            await self._save_chat_message("system", msg)
                            await self._save_chat_message("system", xp_msg)
                            system_messages.append(msg)
                            system_messages.append(xp_msg)
                    states[eid]["is_defeated"] = update.is_defeated
                if update.locked is not None:
                    was_locked = self.state.entity_states.get(eid, {}).get("locked")
                    if was_locked is None:
                        ent_res = await self.db.execute(
                            select(WorldEntity).where(
                                WorldEntity.id == eid,
                                WorldEntity.session_id == self.game_id,
                            )
                        )
                        ent_obj = ent_res.scalars().first()
                        if ent_obj:
                            metadata_json = dict(ent_obj.metadata_json or {})
                            was_locked = bool(
                                metadata_json.get("code_to_unlock")
                                or metadata_json.get("item_to_unlock")
                                or metadata_json.get("rule_to_unlock")
                            )
                    
                    if was_locked and update.locked is False:
                        if ent_obj is None:
                            ent_res = await self.db.execute(
                                select(WorldEntity).where(
                                    WorldEntity.id == eid,
                                    WorldEntity.session_id == self.game_id,
                                )
                            )
                            ent_obj = ent_res.scalars().first()
                        
                        if ent_obj and ent_obj.entity_type == "OBJECT" and str(ent_obj.item_type or "").upper() == "CONTAINER":
                            metadata_json = dict(ent_obj.metadata_json or {})
                            code_to_unlock = str(metadata_json.get("code_to_unlock") or "").strip()
                            if code_to_unlock:
                                xp_reward = metadata_json.get("exp_reward") or metadata_json.get("xp_reward") or 100
                                self.avatar.exp = (self.avatar.exp or 0) + xp_reward
                                msg = f"Unlocked {ent_obj.name} with the correct code!"
                                xp_msg = f"you gained {xp_reward} XP"
                                await self._save_chat_message("system", msg)
                                await self._save_chat_message("system", xp_msg)
                                system_messages.append(msg)
                                system_messages.append(xp_msg)
                            else:
                                msg = f"Container unlocked: {ent_obj.name}."
                                await self._save_chat_message("system", msg)
                                system_messages.append(msg)
                    states[eid]["locked"] = update.locked
                if update.inventory is not None: 
                    states[eid]["inventory"] = [i.model_dump(exclude_none=True) for i in update.inventory]
                state_dirty = True
        
        if event.deleted_entities:
            for eid in event.deleted_entities:
                if eid not in states:
                    states[eid] = {}
                states[eid]["is_hidden"] = True
                state_dirty = True
        
        if event.new_inventory_items:
            for item in event.new_inventory_items:
                if item.id:
                    if item.id not in states:
                        states[item.id] = {}
                    states[item.id]["is_in_inventory"] = True
                    state_dirty = True

        if event.spawned_items:
            for item in event.spawned_items:
                await self._spawn_scene_item(item.model_dump(exclude_none=True))
            state_dirty = True

        if event.remember_notes or event.forget_notes or event.clear_notes:
            self._apply_gm_notes_update(event.remember_notes, event.forget_notes, bool(event.clear_notes))

        # Quest Updates
        newly_completed_quests: list[dict] = []
        if event.completed_quest_ids:
            new_quests = deepcopy(self.state.quests or [])
            modified = False
            for qid in event.completed_quest_ids:
                for q in new_quests:
                    if q.get("id") == qid and q.get("status") != "completed":
                        q["status"] = "completed"
                        newly_completed_quests.append(q)
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

                aw = award_defs.get(key)
                if not aw:
                    logger.warning("[Turn %s] GM tried to grant non-existent award: %s", self.game_id, key)
                    continue

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
                award_title = aw.get("title") or key
                msg = f"Award Achievement: {award_title}"
                await self._save_chat_message("system", msg)
                system_messages.append(msg)
                modified = True

            if modified:
                self.user.earned_awards = user_awards
                flag_modified(self.user, "earned_awards")
                self._queue_checkpoint(CHECKPOINT_REASON_AWARD_GRANTED)

        # Deterministic Quest Sync (Post-LLM check)
        det_completed = QuestManager.evaluate_quests(self.avatar, self.state)
        if det_completed:
            new_quests = deepcopy(self.state.quests or [])
            modified = False
            for qid in det_completed:
                for q in new_quests:
                    if q.get("id") == qid and q.get("status") != "completed":
                        q["status"] = "completed"
                        if not any(nq.get("id") == qid for nq in newly_completed_quests):
                            newly_completed_quests.append(q)
                        logger.info("[Turn %s] Deterministic Quest Completion: %s", self.game_id, qid)
                        modified = True
            if modified:
                self.state.quests = new_quests
                state_dirty = True

        if newly_completed_quests:
            self._queue_checkpoint(CHECKPOINT_REASON_QUEST_UPDATE)
            # Emit one system entry per newly completed quest so players get explicit feedback.
            for q in newly_completed_quests:
                quest_title = q.get("title") or q.get("id")
                xp_reward = int(q.get("exp_reward") or 0)
                msg = f"Quest completed: {quest_title}"
                self.db.add(
                    ChatMessage(
                        session_id=self.state.session_id,
                        role="system",
                        content=msg,
                    )
                )
                system_messages.append(msg)
                
                if xp_reward > 0:
                    self.avatar.exp = (self.avatar.exp or 0) + xp_reward
                    xp_msg = f"you gained {xp_reward} XP"
                    self.db.add(
                        ChatMessage(
                            session_id=self.state.session_id,
                            role="system",
                            content=xp_msg,
                        )
                    )
                    system_messages.append(xp_msg)

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
                    # Update DB row and get exit_type
                    exit_res = await self.db.execute(
                        select(WorldExit).where(
                            WorldExit.session_id == self.state.session_id,
                            or_(
                                and_(
                                    WorldExit.from_scene_id == up_exit.from_scene_id,
                                    WorldExit.to_scene_id == up_exit.to_scene_id
                                ),
                                and_(
                                    WorldExit.from_scene_id == up_exit.to_scene_id,
                                    WorldExit.to_scene_id == up_exit.from_scene_id,
                                    WorldExit.exit_type == "bidirectional"
                                )
                            )
                        )
                    )
                    exit_db = exit_res.scalars().first()
                    exit_type = exit_db.exit_type if exit_db else "one_way"

                    MapEngine.register_exit(
                        world_map, 
                        up_exit.from_scene_id, 
                        up_exit.to_scene_id, 
                        is_locked=up_exit.is_locked,
                        exit_type=exit_type
                    )
                    if exit_db:
                        was_locked = bool(exit_db.is_locked)
                        exit_db.is_locked = up_exit.is_locked
                        if was_locked and up_exit.is_locked is False:
                            exit_name = str(exit_db.label or "").strip() or f"{up_exit.from_scene_id} -> {up_exit.to_scene_id}"
                            msg = f"Exit unlocked: {exit_name}."
                            await self._save_chat_message("system", msg)
                            system_messages.append(msg)
            except Exception as e:
                logger.error(f"Manual map exit update failed: {e}")

        # Auto-cleanup: remove items from NPC inventories if they are now in the scene or player inventory
        player_item_ids = {
            item.get("id")
            for item in (self.avatar.inventory or [])
            if isinstance(item, dict) and item.get("id")
        }
        obj_res = await self.db.execute(
            select(WorldEntity).where(
                WorldEntity.session_id == self.game_id,
                WorldEntity.entity_type == "OBJECT"
            )
        )
        all_objs = obj_res.scalars().all()
        spawned_or_player_ids = set(player_item_ids)
        for obj in all_objs:
            is_in_inv = states.get(obj.id, {}).get("is_in_inventory", obj.is_in_inventory)
            if not is_in_inv:
                # Only add objects that are in the scene (not in any inventory).
                # Objects with is_in_inventory=True may belong to NPC inventories and
                # must NOT be added here, otherwise the cleanup loop below would
                # incorrectly strip them from every NPC's inventory.
                spawned_or_player_ids.add(obj.id)

        npc_res = await self.db.execute(
            select(WorldEntity).where(
                WorldEntity.session_id == self.game_id,
                WorldEntity.entity_type == "NPC"
            )
        )
        all_npcs = npc_res.scalars().all()
        for npc in all_npcs:
            npc_inv = states.get(npc.id, {}).get("inventory", npc.inventory)
            if npc_inv and isinstance(npc_inv, list):
                cleaned_inv = []
                npc_inv_modified = False
                for item in npc_inv:
                    if isinstance(item, dict):
                        item_id = item.get("id")
                        if item_id and item_id in spawned_or_player_ids:
                            logger.info(
                                "[Turn %s] Removing item %s from NPC %s inventory during auto-sync cleanup.",
                                self.game_id,
                                item_id,
                                npc.id
                            )
                            npc_inv_modified = True
                            continue
                    cleaned_inv.append(item)
                
                if npc_inv_modified:
                    if npc.id not in states:
                        states[npc.id] = {}
                    states[npc.id]["inventory"] = cleaned_inv
                    state_dirty = True

        if event.new_world_memories:
            import uuid
            existing_memories = list(self.state.world_memories or [])
            for mem in event.new_world_memories:
                new_mem = {
                    "id": str(uuid.uuid4()),
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "description": mem.description,
                    "npc_id": mem.npc_id,
                    "emotion": mem.emotion,
                    "scope": mem.scope,
                    "scene_id": mem.scene_id or (self.state.current_scene_id if self.state else None)
                }
                existing_memories.append(new_mem)
                emotion_label = "positiv" if mem.emotion == "positive" else ("negativ" if mem.emotion == "negative" else "neutral")
                scope_label = "szenen-lokal" if mem.scope == "local" else "global"
                msg = f"Erinnerung gespeichert ({scope_label}, {emotion_label}): {mem.description}"
                await self._save_chat_message("system", msg)
                system_messages.append(msg)
            self.state.world_memories = existing_memories
            flag_modified(self.state, "world_memories")
            self._queue_checkpoint("world_memories_updated")

        # Time Management
        if event.start_datetime_override:
            self.state.start_datetime = event.start_datetime_override
            state_dirty = True

        if event.time_override_minutes is not None:
            self.state.in_game_time = max(0, int(event.time_override_minutes))
            state_dirty = True
        elif event.extra_time_minutes != 0:
            base_turn = int(self.adventure.time_per_turn if self.adventure.time_per_turn is not None else 5)
            max_turn = getattr(self.adventure, "max_time_per_turn", None)
            if max_turn is None and self.adventure.time_config:
                max_turn = self.adventure.time_config.get("max_time_per_turn")

            extra = int(event.extra_time_minutes)
            if max_turn is not None and max_turn > 0:
                total_turn_time = max(0, min(base_turn + extra, max_turn))
                delta_to_add = total_turn_time - base_turn
            else:
                total_turn_time = max(0, base_turn + extra)
                delta_to_add = total_turn_time - base_turn

            if delta_to_add != 0:
                self.state.in_game_time = max(0, self.state.in_game_time + delta_to_add)
                state_dirty = True

        if state_dirty:
            self.state.entity_states = states
            flag_modified(self.state, "entity_states")
            
        await self._apply_adventure_generator_tools(event)
        await self.db.flush()
        return system_messages

