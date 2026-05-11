import logging
from datetime import datetime
from typing import Any, Optional, Union

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.engine.map_engine import MapEngine
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.game_session import GameSession
from backend.models.session_state import SessionState
from backend.models.world_entity import WorldEntity, WorldScene
from backend.models.world_map import WorldMap

logger = logging.getLogger(__name__)

class AdventureLogic:
    """Class grouping core business logic and helper functions for Adventure management."""

    @staticmethod
    async def get_or_create_map(db: AsyncSession, template_id: str, session_id: Optional[str] = None) -> WorldMap:
        """Fetch or lazily create a WorldMap row for the given adventure session."""
        query = select(WorldMap).where(WorldMap.template_id == template_id)
        if session_id:
            query = query.where(WorldMap.session_id == session_id)
        else:
            query = query.where(WorldMap.session_id == None)

        result = await db.execute(query)
        world_map = result.scalars().first()
        
        if not world_map:
            world_map = WorldMap(template_id=template_id, session_id=session_id)
            db.add(world_map)
            await db.flush()
        return world_map

    @staticmethod
    def calculate_quest_progress(quests: list[dict[str, Optional[Any]]]) -> int:
        if not quests:
            return 0
        total = len(quests)
        if total == 0:
            return 0
        completed = len([q for q in quests if q.get("status") == "completed"])
        return int((completed / total) * 100)

    @staticmethod
    def extract_asset_snapshot(state: SessionState) -> dict[str, Any]:
        raw = state.entity_states or {}
        if not isinstance(raw, dict):
            return {}
        snap = raw.get("__asset_snapshot__")
        return snap if isinstance(snap, dict) else {}

    @staticmethod
    def get_combat_snapshot(state: SessionState) -> dict[str, Optional[Any]]:
        raw = state.entity_states or {}
        if not isinstance(raw, dict):
            return None
        combat = raw.get("__combat__")
        if not isinstance(combat, dict):
            return None
        return combat

    @staticmethod
    def resolve_session_asset(state: SessionState, key: str, fallback: Optional[str] = None) -> Optional[str]:
        snapshot = AdventureLogic.extract_asset_snapshot(state)
        value = snapshot.get(key)
        return value if isinstance(value, str) and value else fallback

    @staticmethod
    def resolve_start_datetime(manifest: dict[str, Optional[Any]], state: Optional[SessionState] = None) -> Optional[str]:
        """Returns a usable ISO datetime string. Prioritizes session-specific state over manifest."""
        if state and state.start_datetime:
            return state.start_datetime
        
        # If relative time system is used, we don't necessarily need a start_datetime, 
        # but for backward compatibility and internal logic, we might still want a base.
        # However, if it's explicitly relative, we might return None or a dummy.
        
        target_manifest = manifest
        if not target_manifest:
            return None
            
        start_datetime = target_manifest.get("start_datetime")
        if isinstance(start_datetime, str) and start_datetime.strip():
            return start_datetime
        start_date = manifest.get("start_date")
        start_time = manifest.get("start_time")
        if not (isinstance(start_date, str) and start_date.strip() and isinstance(start_time, str) and start_time.strip()):
            # Check for year override in time_config
            time_config = target_manifest.get("time_config") or {}
            year_override = time_config.get("start_year_override")
            if year_override:
                # If we have a year override but no full date, we can construct a default date with that year
                try:
                    dt = datetime(year=int(year_override), month=1, day=1, hour=8, minute=0)
                    return dt.isoformat()
                except:
                    pass
            return None
        try:
            dt = datetime.fromisoformat(f"{start_date.strip()}T{start_time.strip()}")
            return dt.isoformat()
        except ValueError:
            return None

    @staticmethod
    async def resolve_session_state(db: AsyncSession, session_or_template_id: str, user_id: Optional[str] = None) -> Optional[SessionState]:
        """Resolve a session state by session id first, then by template/adventure id."""
        from sqlalchemy.orm import selectinload
        direct_res = await db.execute(
            select(SessionState)
            .options(selectinload(SessionState.session))
            .where(SessionState.session_id == session_or_template_id)
        )
        direct_state = direct_res.scalars().first()
        if direct_state:
            return direct_state

        session_candidate = None
        session_by_id_res = await db.execute(select(GameSession).where(GameSession.id == session_or_template_id))
        session_candidate = session_by_id_res.scalars().first()

        if not session_candidate:
            template_session_res = await db.execute(
                select(GameSession)
                .where(GameSession.template_id == session_or_template_id)
                .order_by(GameSession.updated_at.desc())
            )
            template_sessions = template_session_res.scalars().all()
            if user_id:
                session_candidate = next((s for s in template_sessions if s.user_id == user_id), None)
            else:
                session_candidate = template_sessions[0] if template_sessions else None

        if session_candidate:
            if user_id and session_candidate.user_id != user_id:
                return None
            existing_for_candidate_res = await db.execute(
                select(SessionState)
                .options(selectinload(SessionState.session))
                .where(SessionState.session_id == session_candidate.id)
            )
            existing_for_candidate = existing_for_candidate_res.scalars().first()
            if existing_for_candidate:
                return existing_for_candidate
            
            # Auto-healing logic
            scene_res = await db.execute(select(WorldScene.id).where(WorldScene.template_id == session_candidate.template_id).order_by(WorldScene.id.asc()).limit(1))
            first_scene_id = scene_res.scalar_one_or_none() or "START"
            
            adv_res = await db.execute(select(AdventureTemplate).where(AdventureTemplate.id == session_candidate.template_id))
            adventure = adv_res.scalars().first()

            healed_state = SessionState(
                session=session_candidate,
                user_id=session_candidate.user_id,
                template_id=session_candidate.template_id,
                avatar_id=session_candidate.avatar_id,
                current_scene_id=first_scene_id,
                in_game_time=0,
                quests=adventure.quests if adventure else [],
                plot=adventure.plot if adventure else None,
                rules=adventure.rules if adventure else None,
                walkthrough=adventure.walkthrough if adventure else None,
                completed_condition=adventure.completed_condition if adventure else None,
                gameover_condition=adventure.gameover_condition if adventure else None,
                tts_director_notes=adventure.tts_director_notes if adventure else None
            )
            db.add(healed_state)
            await db.commit()
            await db.refresh(healed_state, ["session"])
            return healed_state
        return None

    @staticmethod
    async def build_session_entities(db: AsyncSession, state: SessionState) -> list[dict[str, Any]]:
      """Fetches and processes entities for the current session, filtering for the current scene."""
      # Fetch all entities for this session to handle movement correctly
      ent_res = await db.execute(
          select(WorldEntity).where(
              WorldEntity.session_id == state.session_id
          )
      )
      base_entities = [{c.name: getattr(e, c.name) for c in e.__table__.columns} for e in ent_res.scalars().all()]
      
      session_overrides = state.entity_states or {}
      entities = []
      for ent in base_entities:
          eid = ent.get("id")
          
          # Apply session overrides (HP, position, scene_id, etc.)
          if eid in session_overrides:
              ent.update(session_overrides[eid])
          
          # Filter for the CURRENT scene
          if ent.get("current_scene_id") != state.current_scene_id:
              continue
          
          # Filter out hidden or inventory items
          if ent.get("is_hidden") or ent.get("is_in_inventory"):
              continue
              
          entities.append(ent)
      return entities

    @staticmethod
    async def build_sheet_snapshot(avatar: Avatar, state: SessionState, db: AsyncSession) -> dict:
        """Builds a serialisable character-sheet snapshot."""
        adv_res = await db.execute(select(AdventureTemplate).where(AdventureTemplate.id == state.template_id))
        adventure = adv_res.scalars().first()
        start_datetime = AdventureLogic.resolve_start_datetime(adventure.original_manifest if adventure else None, state=state)
        
        if not start_datetime and adventure and adventure.clock_enabled:
            start_datetime = "2026-04-17T08:00:00"

        snapshot = AdventureLogic.extract_asset_snapshot(state)
        has_asset_snapshot = "__asset_snapshot__" in (state.entity_states or {})
        snapshot_entity_images = snapshot.get("entity_images", {})

        res = await db.execute(select(WorldEntity.id, WorldEntity.image_url).where(WorldEntity.session_id == state.session_id, WorldEntity.image_url.is_not(None)))
        img_map = {row.id: row.image_url for row in res.all() if row.id}
        if has_asset_snapshot:
            img_map = {k: v for k, v in snapshot_entity_images.items() if isinstance(v, str) and v}
        else:
            img_map.update({k: v for k, v in snapshot_entity_images.items() if isinstance(v, str) and v})
        
        from backend.engine.item_logic import get_item_slot
        synced_inventory = []
        for item in (avatar.inventory or []):
            if not isinstance(item, dict):
                if isinstance(item, str):
                    item = {"name": item}
                else:
                    continue
            item_copy = dict(item)
            
            # On-the-fly slot fixup for old data
            if not item_copy.get("slot"):
                item_copy["slot"] = get_item_slot(item_copy.get("name", ""), item_copy.get("item_type", "PICKABLE"))
                
            item_id = item_copy.get("id")
            if item_id in img_map and not item_copy.get("image_url"):
                item_copy["image_url"] = img_map[item_id]
            synced_inventory.append(item_copy)
            
        synced_equipment = {}
        for slot, item in (avatar.equipment or {}).items():
            if item:
                if not isinstance(item, dict):
                    if isinstance(item, str):
                        item = {"name": item}
                    else:
                        synced_equipment[slot] = item
                        continue
                item_copy = dict(item)
                
                # On-the-fly slot fixup
                if not item_copy.get("slot"):
                    item_copy["slot"] = get_item_slot(item_copy.get("name", ""), item_copy.get("item_type", "PICKABLE"))
                
                item_id = item_copy.get("id")
                if item_id in img_map and not item_copy.get("image_url"):
                    item_copy["image_url"] = img_map[item_id]
                synced_equipment[slot] = item_copy
            else:
                synced_equipment[slot] = item
                
        scene_res = await db.execute(select(WorldScene).where(WorldScene.id == state.current_scene_id, WorldScene.session_id == state.session_id))
        current_scene = scene_res.scalars().first()
        
        # Fallback to template if session snapshot not found (e.g. legacy session)
        if not current_scene:
            scene_res = await db.execute(select(WorldScene).where(WorldScene.id == state.current_scene_id, WorldScene.template_id == state.template_id))
            current_scene = scene_res.scalars().first()
        
        from backend.engine.stat_aggregator import calculate_total_stats
        total_stats = calculate_total_stats(avatar)
        
        # Build base snapshot
        snapshot = {
            "name": avatar.name,
            "role": avatar.role,
            "description": avatar.description,
            "profile_image": AdventureLogic.resolve_session_asset(state, "protagonist", avatar.profile_image),
            "hp": avatar.hp, 
            "max_hp": avatar.max_hp,
            "stamina": avatar.stamina, 
            "max_stamina": avatar.max_stamina,
            "mana": avatar.mana,
            "max_mana": avatar.max_mana,
            # Core Stats (calculated totals)
            "strength": total_stats.get("strength", avatar.strength),
            "dexterity": total_stats.get("dexterity", avatar.dexterity),
            "intelligence": total_stats.get("intelligence", avatar.intelligence),
            "wisdom": total_stats.get("wisdom", avatar.wisdom),
            "charisma": total_stats.get("charisma", avatar.charisma),
            "armor_class": total_stats.get("armor_class", avatar.armor_class),
            "stats": total_stats, 
            "inventory": synced_inventory, 
            "equipment": synced_equipment,
            "status_effects": avatar.status_effects or [], 
            "in_game_time": state.in_game_time,
            "start_datetime": start_datetime,
            "current_scene": current_scene.label if current_scene else state.current_scene_id,
            "scene_id": state.current_scene_id,
            "adventure_title": adventure.title if adventure else "Unknown",
            "adventure_version": adventure.version if adventure else None,
            "template_id": state.template_id, 
            "exp": avatar.exp,
            "rule_enforcement_mode": adventure.rule_enforcement_mode if adventure else "rpg",
            "adventure_tone": adventure.selected_tone if adventure else None,
            "time_system": state.time_system or (adventure.time_system if adventure else "calendar"),
            "time_config": state.time_config or (adventure.time_config if adventure else None),
            "is_debug_enabled": bool(state.is_debug_enabled),
            "debug_mode": bool(settings.TALEWEAVER_DEBUG_ENABLED)
        }
        
        return snapshot

    @staticmethod
    async def get_all_scene_metadata(db: AsyncSession, template_id: str) -> dict:
        scene_res = await db.execute(select(WorldScene).where(WorldScene.template_id == template_id))
        metadata = {}
        for s in scene_res.scalars().all():
            metadata[MapEngine._safe_id(s.id)] = {
                "id": s.id,
                "label": s.label,
                "description": s.description,
                "image_url": s.image_url
            }
        return metadata

    @staticmethod
    async def delete_adventure(db: AsyncSession, template_id: str):
        """
        Deletes an adventure template and all associated records explicitly.
        Order is important to avoid FK violations.
        Also cleans up physical assets.
        """
        from sqlalchemy import delete

        from backend.engine.media_engine import MediaEngine
        from backend.models.avatar import Avatar
        from backend.models.game_session import GameSession
        from backend.models.session_state import SessionState
        from backend.models.world_entity import WorldEntity, WorldExit, WorldScene
        from backend.models.world_map import WorldMap

        # 1. Resolve and Delete Sessions & States
        # We find sessions first to delete their states
        session_query = select(GameSession.id).where(GameSession.template_id == template_id)
        session_ids = (await db.execute(session_query)).scalars().all()
        
        if session_ids:
            await db.execute(delete(SessionState).where(SessionState.session_id.in_(session_ids)))
            await db.execute(delete(GameSession).where(GameSession.id.in_(session_ids)))

        # 2. Delete Avatars (linked to template)
        await db.execute(delete(Avatar).where(Avatar.template_id == template_id))

        # 3. Delete World Content
        await db.execute(delete(WorldExit).where(WorldExit.template_id == template_id))
        await db.execute(delete(WorldEntity).where(WorldEntity.template_id == template_id))
        await db.execute(delete(WorldScene).where(WorldScene.template_id == template_id))
        await db.execute(delete(WorldMap).where(WorldMap.template_id == template_id))

        # 4. Finally delete the template itself
        await db.execute(delete(AdventureTemplate).where(AdventureTemplate.id == template_id))
        
        await db.commit()

        # 5. Cleanup Files
        await MediaEngine.cleanup_adventure_assets(template_id)

