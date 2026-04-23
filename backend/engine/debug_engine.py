from copy import deepcopy
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.game_state import GameState
from backend.models.world_entity import WorldScene, WorldEntity, WorldExit
from backend.models.adventure import Adventure
from backend.models.user import User

class DebugEngine:
    @staticmethod
    async def handle_debug_command(
        db: AsyncSession,
        state: GameState,
        args: str,
        user: User | None = None,
        adventure: Adventure | None = None,
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
            res = await db.execute(select(WorldScene).where(WorldScene.id == scene_id, WorldScene.adventure_id == adv_id))
            scene = res.scalars().first()
            if not scene: return f"DEBUG ERROR: Scene '{scene_id}' not found in world manifest."
            
            return f"--- DEBUG: SCENE [{scene_id}] ---\nLabel: {scene.label}\nDescription: {scene.description}"

        elif sub == "items" or sub == "entities":
            res = await db.execute(select(WorldEntity).where(WorldEntity.current_scene_id == scene_id, WorldEntity.adventure_id == adv_id))
            entities = res.scalars().all()
            if not entities: return "--- DEBUG: No entities or objects found in this scene. ---"
            
            lines = [f"--- DEBUG: ENTITIES IN {scene_id} ---"]
            for e in entities:
                lines.append(f"- [{e.entity_type}] {e.name} (ID: {e.id}): {e.description[:50]}...")
            return "\n".join(lines)

        elif sub == "plot" or sub == "context":
            res = await db.execute(select(Adventure).where(Adventure.id == adv_id))
            adv = res.scalars().first()
            return f"--- DEBUG: PLOT CONTEXT ---\n{adv.context}"

        elif sub == "map":
            # Just some stats
            s_count = await db.execute(select(WorldScene).where(WorldScene.adventure_id == adv_id))
            e_count = await db.execute(select(WorldEntity).where(WorldEntity.adventure_id == adv_id))
            ex_count = await db.execute(select(WorldExit).where(WorldExit.adventure_id == adv_id))
            
            return (
                f"--- DEBUG: WORLD STATS ---\n"
                f"Adventure ID: {adv_id}\n"
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

        return "DEBUG USAGE: /debug [szene | items | plot | map | log on/off | award(s)]"
