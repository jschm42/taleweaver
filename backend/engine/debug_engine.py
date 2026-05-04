from typing import Optional, Any
from copy import deepcopy
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.game_session import GameSession
from backend.models.session_state import SessionState
from backend.models.world_entity import WorldScene, WorldEntity, WorldExit
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User
from backend.models.world_map import WorldMap
from backend.engine.map_engine import MapEngine

class DebugEngine:
    @staticmethod
    async def handle_debug_command(
        db: AsyncSession,
        state: SessionState,
        args: str,
        user: Optional[User] = None,
        adventure: Optional[AdventureTemplate] = None,
        avatar: Optional[Any] = None,
    ) -> str:
        """
        Processes /debug sub-commands and returns atmospheric yet technical info.

        Optional ``user`` and ``adventure`` objects are required for sub-commands
        that mutate persistent data (e.g. ``award``).
        """
        sub = args.split(" ")[0].lower() if args else ""
        adv_id = state.adventure_id
        scene_id = state.scene_id

        if sub == "szene":
            res = await db.execute(select(WorldScene).where(WorldScene.id == scene_id, WorldScene.session_id == state.session_id))
            scene = res.scalars().first()
            if not scene: return f"DEBUG ERROR: Scene '{scene_id}' not found in session manifest."
            
            return f"--- DEBUG: SCENE [{scene_id}] ---\nLabel: {scene.label}\nDescription: {scene.description}"

        elif sub == "entities":
            res = await db.execute(select(WorldEntity).where(WorldEntity.current_scene_id == scene_id, WorldEntity.session_id == state.session_id))
            entities = res.scalars().all()
            if not entities: return "--- DEBUG: No entities or objects found in this scene. ---"
            
            lines = [f"--- DEBUG: ENTITIES IN {scene_id} ---"]
            for e in entities:
                lines.append(f"- [{e.entity_type}] {e.name} (ID: {e.id}): {e.description[:50]}...")
            return "\n".join(lines)

        elif sub == "plot" or sub == "context":
            res = await db.execute(select(AdventureTemplate).where(AdventureTemplate.id == adv_id))
            adv = res.scalars().first()
            return f"--- DEBUG: PLOT CONTEXT ---\n{adv.original_prompt}"

        elif sub == "map":
            # Just some stats
            s_count = await db.execute(select(WorldScene).where(WorldScene.session_id == state.session_id))
            e_count = await db.execute(select(WorldEntity).where(WorldEntity.session_id == state.session_id))
            ex_count = await db.execute(select(WorldExit).where(WorldExit.session_id == state.session_id))
            
            return (
                f"--- DEBUG: WORLD STATS ---\n"
                f"AdventureTemplate ID: {adv_id}\n"
                f"Session ID: {state.session_id}\n"
                f"Total Scenes: {len(s_count.scalars().all())}\n"
                f"Total Entities: {len(e_count.scalars().all())}\n"
                f"Total Connections: {len(ex_count.scalars().all())}"
            )
            
        elif sub == "log":
            # Handle /debug log on/off
            parts = args.split(" ")
            if len(parts) >= 2:
                cmd = parts[1].lower()
                if cmd == "on":
                    state.is_debug_enabled = True
                    return "[DEBUG_LOG_ON] Technical logging enabled. You will now see GameEvent outcomes in chat."
                elif cmd == "off":
                    state.is_debug_enabled = False
                    return "[DEBUG_LOG_OFF] Technical logging disabled."

        elif sub in {"award", "awards"}:
            # Grant all awards of the current adventure to the player instantly.
            if adventure is None or user is None:
                return "DEBUG ERROR: Award command requires adventure and user context."

            all_awards = adventure.awards or []
            if not all_awards:
                return "DEBUG: This adventure has no awards defined."

            updated_awards = deepcopy(all_awards)
            granted: list[str] = []
            now = datetime.utcnow().isoformat()

            for award in updated_awards:
                if award.get("is_earned"):
                    continue  # already earned — skip

                award["is_earned"] = True
                a_key = award.get("key", "")
                granted.append(f"  [{award.get('tier', '?').upper()}] {award.get('title', a_key)}")

                # Persist to user profile (deduplicated)
                user_awards = list(user.earned_awards or [])
                title = award.get("title") or a_key or "Unknown Award"
                dedupe_key = a_key or title
                if not any(
                    (ea.get("key") or ea.get("title")) == dedupe_key
                    and ea.get("adventure_id") == adventure.id
                    for ea in user_awards
                ):
                    user_awards.append({
                        "key": dedupe_key,
                        "title": title,
                        "description": award.get("description"),
                        "tier": award.get("tier"),
                        "adventure_id": adventure.id,
                        "adventure_title": adventure.title,
                        "session_id": state.id,
                        "earned_at": now,
                    })
                    user.earned_awards = user_awards
                    flag_modified(user, "earned_awards")

            if not granted:
                return "DEBUG: All awards are already earned."

            adventure.awards = updated_awards
            flag_modified(adventure, "awards")

            lines = ["[DEBUG] All adventure awards granted:"] + granted
            return "\n".join(lines)

        elif sub == "game_won":
            # Mark all main quests as completed
            if state.quests:
                new_quests = deepcopy(state.quests)
                for q in new_quests:
                    if q.get("is_main"):
                        q["status"] = "completed"
                state.quests = new_quests
                flag_modified(state, "quests")
            return "[TRIGGER_GAME_COMPLETED] Debug: Manual victory trigger."

        elif sub == "quest_finished":
            if not state.quests:
                return "DEBUG: No quests found in session state."
            new_quests = deepcopy(state.quests)
            target = next((q for q in new_quests if q.get("status") == "open"), None)
            if target:
                target["status"] = "completed"
                state.quests = new_quests
                flag_modified(state, "quests")
                return f"DEBUG: Quest '{target.get('title') or target.get('id')}' marked as completed."
            return "DEBUG: No open quests found to finish."

        elif sub == "claim_awards":
            # Redirect to awards logic
            return await DebugEngine.handle_debug_command(db, state, "awards", user, adventure, avatar)

        elif sub == "delete_item":
            parts = args.split(" ")
            if len(parts) < 2: return "DEBUG ERROR: Usage: /debug delete_item [ITEM_KEY]"
            item_key = parts[1]
            if not avatar: return "DEBUG ERROR: Avatar context missing."
            
            inv = list(avatar.inventory or [])
            new_inv = [item for item in inv if item.get("id") != item_key and item.get("key") != item_key]
            if len(new_inv) == len(inv):
                return f"DEBUG: Item '{item_key}' not found in inventory."
            
            avatar.inventory = new_inv
            flag_modified(avatar, "inventory")
            return f"DEBUG: Item '{item_key}' removed from inventory."

            return f"DEBUG: Entity '{target.name}' (ID: {target.id}) HP set to 0."

        elif sub == "heal":
            parts = args.split(" ")
            if len(parts) < 2: return "DEBUG ERROR: Usage: /debug heal [NPC_NAME] [AMOUNT?]"
            
            # Find the NPC
            amount = None
            try:
                amount = int(parts[-1])
                npc_name = " ".join(parts[1:-1]).lower()
            except ValueError:
                npc_name = " ".join(parts[1:]).lower()
            
            # Search in session entities
            res = await db.execute(select(WorldEntity).where(WorldEntity.session_id == state.session_id))
            entities = res.scalars().all()
            target = next((e for e in entities if e.name.lower() == npc_name or e.id.lower() == npc_name), None)
            
            if not target:
                return f"DEBUG: NPC/Entity '{npc_name}' not found in this session."
            
            final_hp = amount if amount is not None else (target.hp or 50)
            
            # Update state
            overrides = dict(state.entity_states or {})
            if target.id not in overrides: overrides[target.id] = {}
            overrides[target.id]["hp"] = final_hp
            state.entity_states = overrides
            flag_modified(state, "entity_states")
            return f"DEBUG: Entity '{target.name}' (ID: {target.id}) restored to {final_hp} HP."

        elif sub == "open_exit":
            parts = args.split(" ")
            if len(parts) < 2: return "DEBUG ERROR: Usage: /debug open_exit [EXIT_ID]"
            exit_id = parts[1]
            
            overrides = dict(state.exit_states or {})
            if exit_id not in overrides: overrides[exit_id] = {}
            overrides[exit_id]["is_locked"] = False
            state.exit_states = overrides
            flag_modified(state, "exit_states")
            return f"DEBUG: Exit '{exit_id}' is now unlocked."

        elif sub == "walkthrough":
            if not state.walkthrough:
                return "DEBUG: No walkthrough available for this adventure."
            return f"[TRIGGER_WALKTHROUGH_REVEAL_FREE] --- DEBUG: WALKTHROUGH ---\n{state.walkthrough}"

        elif sub == "game_over":
            return "[TRIGGER_GAME_OVER] Debug: Manual game over trigger."

        elif sub == "engine":
            # Return engine diagnostics
            import platform
            import sys
            import os
            from backend.core.config import settings
            
            lines = [
                "--- DEBUG: ENGINE DIAGNOSTICS ---",
                f"TaleWeaver Version: {settings.APP_VERSION}",
                f"Platform: {platform.platform()}",
                f"Python Version: {sys.version.split(' ')[0]}",
                f"Server Time: {datetime.now().isoformat()}",
                f"Current Session ID: {state.session_id}",
                f"Debug Mode: {'ENABLED' if settings.TALEWEAVER_DEBUG_ENABLED else 'DISABLED'}",
                f"Data Dir: {settings.DATA_DIR}",
            ]
            return "\n".join(lines)

        elif sub == "exp":
            parts = args.split(" ")
            if len(parts) < 2: return "DEBUG ERROR: Usage: /debug exp [AMOUNT]"
            try:
                amount = int(parts[1])
            except ValueError:
                return "DEBUG ERROR: Amount must be an integer."
            
            if not avatar: return "DEBUG ERROR: Avatar context missing."
            avatar.exp = (avatar.exp or 0) + amount
            return f"DEBUG: Granted {amount} XP to {avatar.name}. New total: {avatar.exp}"

        elif sub == "scenes":
            res = await db.execute(select(WorldScene).where(WorldScene.session_id == state.session_id))
            scenes = res.scalars().all()
            if not scenes: return "DEBUG: No scenes found for this session."
            lines = ["--- DEBUG: ALL SCENES ---"]
            for s in scenes:
                lines.append(f"- {s.label} (ID: {s.id})")
            return "\n".join(lines)

        elif sub == "npcs":
            res = await db.execute(select(WorldEntity).where(WorldEntity.session_id == state.session_id, WorldEntity.entity_type == "NPC"))
            npcs = res.scalars().all()
            if not npcs: return "DEBUG: No NPCs found for this session."
            lines = ["--- DEBUG: ALL NPCs ---"]
            for n in npcs:
                lines.append(f"- {n.name} (ID: {n.id}) @ {n.current_scene_id}")
            return "\n".join(lines)

        elif sub == "items":
            res = await db.execute(select(WorldEntity).where(WorldEntity.session_id == state.session_id, WorldEntity.entity_type == "OBJECT"))
            items = res.scalars().all()
            if not items: return "DEBUG: No items found for this session."
            lines = ["--- DEBUG: ALL ITEMS ---"]
            for i in items:
                loc = "Inventory" if i.is_in_inventory else f"Scene: {i.current_scene_id}"
                lines.append(f"- {i.name} (ID: {i.id}) @ {loc}")
            return "\n".join(lines)

        elif sub == "exits":
            res = await db.execute(select(WorldExit).where(WorldExit.session_id == state.session_id))
            exits = res.scalars().all()
            if not exits: return "DEBUG: No exits found for this session."
            lines = ["--- DEBUG: ALL EXITS ---"]
            for e in exits:
                locked = "[LOCKED]" if e.is_locked else "[OPEN]"
                lines.append(f"- {e.label} (ID: {e.id if hasattr(e, 'id') else 'N/A'}): {e.from_scene_id} -> {e.to_scene_id} {locked}")
            return "\n".join(lines)

        elif sub == "reveal_map":
            # 1. Fetch all world data for this session (snapshots)
            scenes_res = await db.execute(select(WorldScene).where(WorldScene.session_id == state.session_id))
            exits_res = await db.execute(select(WorldExit).where(WorldExit.session_id == state.session_id))
            
            scenes = scenes_res.scalars().all()
            exits = exits_res.scalars().all()
            
            # 2. Get or create the map
            map_res = await db.execute(select(WorldMap).where(WorldMap.template_id == state.template_id))
            world_map = map_res.scalars().first()
            if not world_map:
                world_map = WorldMap(template_id=state.template_id)
                db.add(world_map)
                await db.flush()
            
            # 3. Register everything
            for s in scenes:
                MapEngine.register_visit(world_map, s.id, label=s.label, description=s.description, image_url=s.image_url)
            
            # 4. Restore the actual current position
            # register_visit overwrites current_scene_id with the last one in the loop.
            # We must set it back to the safe version of our actual current scene_id.
            world_map.current_scene_id = MapEngine._safe_id(state.scene_id)
            
            for e in exits:
                MapEngine.register_exit(world_map, e.from_scene_id, e.to_scene_id, exit_label=e.label, is_locked=e.is_locked)
            
            return "DEBUG: World Map fully revealed and synchronized."

        elif sub == "gen_item":
            parts = args.split(" ", 1)
            if len(parts) < 2: return "DEBUG ERROR: Usage: /debug gen_item [PROMPT]"
            return f"[TRIGGER_GEN_ITEM] {parts[1]}"

        return "DEBUG USAGE: /debug [szene | heal | scenes | npcs | items | exits | plot | context | map | reveal_map | log on/off | walkthrough | engine | award(s) | game_won | game_over | quest_finished | claim_awards | delete_item X | kill NPC | open_exit ID | gen_item PROMPT]"
