"""
WebSocket endpoint for real-time game communication.

Handles the main game loop: slash commands are routed directly to the
CommandParser (O(1) JSON mutations), while natural-language input is
forwarded to the GameMasterLLM. In strict_rules mode the LLM returns a
structured GameEvent that is validated and applied by the RuleEngine.
"""
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from backend.core.database import AsyncSessionLocal
from backend.models.adventure import Adventure
from backend.models.game_state import GameState
from backend.models.avatar import Avatar
from backend.models.chat import ChatMessage
from backend.models.user import User

from backend.engine.command_parser import CommandParser
from backend.engine.rule_engine import RuleEngine, GameEvent, GameOverException
from backend.engine.map_engine import MapEngine
from backend.engine.media_engine import MediaEngine
from backend.models.world_entity import WorldScene, WorldExit, WorldEntity
from backend.models.world_map import WorldMap
from backend.core.llm_router import GameMasterLLM
from backend.engine.memory_manager import MemoryManager
from backend.engine.debug_engine import DebugEngine

router = APIRouter(prefix="/ws", tags=["WebSocket"])
logger = logging.getLogger(__name__)

# Default LLM settings will be fetched from user profile


class ConnectionManager:
    """Manages active WebSocket connections keyed by game_id."""

    def __init__(self) -> None:
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, ws: WebSocket, game_id: str) -> None:
        await ws.accept()
        self.active_connections[game_id] = ws
        logger.info("WebSocket connected for game %s", game_id)

    def disconnect(self, game_id: str) -> None:
        if game_id in self.active_connections:
            del self.active_connections[game_id]
            logger.info("WebSocket disconnected for game %s", game_id)

    async def send_message(self, message: str, game_id: str, role: str = "assistant") -> None:
        """Sends a chat message payload to the client."""
        if game_id in self.active_connections:
            payload = json.dumps({"role": role, "content": message})
            await self.active_connections[game_id].send_text(payload)

    async def broadcast_sheet(self, game_id: str, sheet: dict) -> None:
        """Sends a full character-sheet snapshot to the client."""
        if game_id in self.active_connections:
            payload = json.dumps({"type": "sheet_update", "data": sheet})
            await self.active_connections[game_id].send_text(payload)

    async def send_game_over(self, game_id: str, reason: str) -> None:
        """Notifies the client that the game has ended."""
        if game_id in self.active_connections:
            payload = json.dumps({"type": "game_over", "reason": reason})
            await self.active_connections[game_id].send_text(payload)

    async def send_map_update(self, game_id: str, mermaid: str) -> None:
        """Pushes an updated Mermaid map diagram to the client."""
        if game_id in self.active_connections:
            payload = json.dumps({"type": "map_update", "mermaid": mermaid})
            await self.active_connections[game_id].send_text(payload)

    async def send_image_update(self, game_id: str, image_url: str) -> None:
        """Pushes a new scene image URL to the client."""
        if game_id in self.active_connections:
            payload = json.dumps({"type": "image_update", "url": image_url})
            await self.active_connections[game_id].send_text(payload)


manager = ConnectionManager()


def _build_sheet(avatar: Avatar, state: GameState) -> dict:
    """Builds a serialisable character-sheet snapshot from an Avatar ORM object."""
    return {
        "name": avatar.name,
        "hp": avatar.hp,
        "stamina": avatar.stamina,
        "mana": avatar.mana,
        "stats": avatar.stats,
        "inventory": avatar.inventory,
        "equipment": avatar.equipment,
        "status_effects": avatar.status_effects,
        "in_game_time": state.in_game_time,
    }


@router.websocket("/adventure/{game_id}")
async def websocket_endpoint(websocket: WebSocket, game_id: str) -> None:
    """
    Main WebSocket game loop.

    Expected client message format:
        {"content": "<player input>"}

    Server sends one of:
        {"role": "assistant"|"system", "content": "..."}   — chat message
        {"type": "sheet_update", "data": {...}}             — character sheet
    """
    await manager.connect(websocket, game_id)

    async with AsyncSessionLocal() as db:
        # --- Pre-check for atmospheric entry ---
        state_res = await db.execute(select(GameState).where(GameState.id == game_id))
        state = state_res.scalars().first()
        if state:
            # Check if this is a fresh start (no messages yet) or a re-entry
            msg_res = await db.execute(select(ChatMessage).where(ChatMessage.game_state_id == game_id).limit(1))
            first_msg = msg_res.scalars().first()
            
            # Identify current location info
            scene_res = await db.execute(select(WorldScene).where(WorldScene.id == state.scene_id, WorldScene.adventure_id == state.adventure_id))
            current_scene = scene_res.scalars().first()
            
            if not first_msg:
                # NEW ADVENTURE: Generate Epic Prologue
                await manager.send_message("The mists of time part...", game_id, "system")
                # (Deferred till loop below for logic reuse if possible, or trigger here)
                # For cleaner logic, we'll mark a flag to trigger the LLM immediately in the first iteration
                # with a special 'look around' prompt.
                trigger_entry = True
            else:
                # RE-ENTRY: Generate Scene Re-orientation
                trigger_entry = True
        else:
            trigger_entry = False

    try:
        first_tick = trigger_entry
        while True:
            if first_tick:
                # Simulated user input to trigger atmospheric description
                user_msg = "[LOOK AROUND]" 
                first_tick = False
            else:
                data = await websocket.receive_text()
                try:
                    payload = json.loads(data)
                    user_msg = payload.get("content", "").strip()
                except json.JSONDecodeError:
                    await manager.send_message("Invalid message format.", game_id, "system")
                    continue

                if not user_msg:
                    continue

                # --- Intercept Debug Commands ---
                if user_msg.startswith("/debug"):
                    async with AsyncSessionLocal() as db:
                        state_res = await db.execute(select(GameState).where(GameState.id == game_id))
                        state = state_res.scalars().first()
                        if state:
                            cmd_args = user_msg[7:].strip()
                            debug_info = await DebugEngine.handle_debug_command(db, state, cmd_args)
                            await manager.send_message(debug_info, game_id, "system")
                            continue

            async with AsyncSessionLocal() as db:
                # --- Load game state ---
                state_res = await db.execute(select(GameState).where(GameState.id == game_id))
                state = state_res.scalars().first()
                if not state:
                    await manager.send_message("System Error: Game session not found.", game_id, "system")
                    continue

                if state.is_paused:
                    await manager.send_message("The game is currently paused.", game_id, "system")
                    continue

                av_res = await db.execute(select(Avatar).where(Avatar.id == state.avatar_id))
                avatar = av_res.scalars().first()

                u_res = await db.execute(select(User).where(User.id == state.user_id))
                user = u_res.scalars().first()

                adv_res = await db.execute(select(Adventure).where(Adventure.id == state.adventure_id))
                adventure = adv_res.scalars().first()

                # --- Slash-command fast path (no LLM call) ---
                if user_msg.startswith("/"):
                    # Special case: /map is handled here, not in CommandParser
                    if user_msg.strip().lower() == "/map":
                        adv_id = state.adventure_id
                        map_res = await db.execute(
                            select(WorldMap).where(WorldMap.adventure_id == adv_id)
                        )
                        world_map = map_res.scalars().first()
                        if world_map and world_map.nodes:
                            mermaid = MapEngine.to_mermaid(world_map)
                            await manager.send_map_update(game_id, mermaid)
                        else:
                            await manager.send_message("No map data yet. Explore the world first!", game_id, "system")
                        continue

                    response = CommandParser.parse_command(avatar, user_msg)
                    await db.commit()
                    await manager.send_message(response, game_id, "system")
                    await manager.broadcast_sheet(game_id, _build_sheet(avatar, state))
                    continue

                # --- Turn-based Logic: Advance Time & Status Effects ---
                # Advance baseline time
                state.in_game_time += adventure.time_per_turn
                
                # Apply status effect ticks
                tick_msgs = RuleEngine.apply_ticks(avatar)
                for tm in tick_msgs:
                    await manager.send_message(tm, game_id, "system")

                # --- Natural-language path ---
                user_chat = ChatMessage(game_state_id=game_id, role="user", content=user_msg)
                db.add(user_chat)
                await db.flush()

                hist_res = await db.execute(
                    select(ChatMessage)
                    .where(ChatMessage.game_state_id == game_id)
                    .order_by(ChatMessage.created_at.asc())
                )
                history = [
                    {"role": msg.role, "content": msg.content}
                    for msg in hist_res.scalars().all()
                ]

                try:
                    # Get user settings
                    settings = user.llm_settings or {
                        "small_model": "openai/gpt-4o-mini",
                        "complex_model": "openai/gpt-4o-mini",
                        "preferred_provider": "openai"
                    }
                    small_model = settings.get("small_model", "openai/gpt-4o-mini")
                    complex_model = settings.get("complex_model", "openai/gpt-4o-mini")
                    provider = settings.get("preferred_provider", "openai")

                    llm = GameMasterLLM(user, provider=provider)
                    world_setting = adventure.context if (adventure and adventure.context) else "A mysterious and dangerous world."
                    game_event = None
                    
                    # Fetch Pre-generated World Data for Context
                    adv_id = state.adventure_id
                    current_scene_id = state.scene_id
                    
                    scene_res = await db.execute(select(WorldScene).where(WorldScene.id == current_scene_id, WorldScene.adventure_id == adv_id))
                    current_scene = scene_res.scalars().first()
                    
                    entity_res = await db.execute(select(WorldEntity).where(WorldEntity.current_scene_id == current_scene_id, WorldEntity.adventure_id == adv_id))
                    entities = entity_res.scalars().all()
                    
                    exit_res = await db.execute(select(WorldExit).where(WorldExit.from_scene_id == current_scene_id, WorldExit.adventure_id == adv_id))
                    exits = exit_res.scalars().all()
                    
                    context_messages = MemoryManager.build_context(
                        avatar, world_setting, history, 
                        current_scene=current_scene, 
                        entities=entities, 
                        exits=exits,
                        in_game_time=state.in_game_time
                    )
                    system_prompt = context_messages[0]["content"]

                    if adventure and adventure.strict_rules:
                        # Structured output: LLM returns a validated GameEvent
                        game_event: GameEvent = llm.execute_complex_task(
                            system_prompt=system_prompt,
                            user_prompt=user_msg,
                            response_model=GameEvent,
                            model=complex_model,
                        )
                        try:
                            narrative = RuleEngine.apply_event(avatar, game_event)
                        except GameOverException as exc:
                            await db.commit()
                            await manager.send_message(str(exc), game_id, "system")
                            await manager.broadcast_sheet(game_id, _build_sheet(avatar, state))
                            await manager.send_game_over(game_id, str(exc))
                            continue

                        response_text = narrative
                    else:
                        # Free-form narrative response
                        response_text = llm.execute_simple_task(
                            system_prompt=system_prompt,
                            user_prompt=user_msg,
                            model=small_model,
                        )

                    gm_chat = ChatMessage(game_state_id=game_id, role="assistant", content=response_text)
                    db.add(gm_chat)

                    # ── Update World State ─────────────────────────────────────
                    if adventure.strict_rules:
                        if game_event.new_scene_id:
                            # Character movement
                            state.scene_id = game_event.new_scene_id
                        
                        if game_event.moved_entities:
                            # NPC/Object movement
                            for move in game_event.moved_entities:
                                ent_res = await db.execute(select(WorldEntity).where(WorldEntity.id == move.entity_id, WorldEntity.adventure_id == adv_id))
                                entity = ent_res.scalars().first()
                                if entity:
                                    if move.to_scene_id:
                                        entity.current_scene_id = move.to_scene_id
                                    if move.to_spatial_position:
                                        entity.spatial_position = move.to_spatial_position

                        if game_event.updated_exits:
                            # Locking/Unlocking exits
                            for upd in game_event.updated_exits:
                                ex_res = await db.execute(select(WorldExit).where(
                                    WorldExit.from_scene_id == upd.from_scene_id,
                                    WorldExit.to_scene_id == upd.to_scene_id,
                                    WorldExit.adventure_id == adv_id
                                ))
                                world_exit = ex_res.scalars().first()
                                if world_exit:
                                    world_exit.is_locked = upd.is_locked

                        if game_event.updated_entities:
                            # Modification of entity properties
                            for upd in game_event.updated_entities:
                                ent_res = await db.execute(select(WorldEntity).where(WorldEntity.id == upd.entity_id, WorldEntity.adventure_id == adv_id))
                                entity = ent_res.scalars().first()
                                if entity:
                                    if upd.name: entity.name = upd.name
                                    if upd.description: entity.description = upd.description
                                    if upd.spatial_position: entity.spatial_position = upd.spatial_position

                        if game_event.deleted_entities:
                            # Removal of entities
                            for ent_id in game_event.deleted_entities:
                                await db.execute(delete(WorldEntity).where(WorldEntity.id == ent_id, WorldEntity.adventure_id == adv_id))

                        # Apply GM extra time penalty/bonus
                        if game_event.extra_time_minutes:
                            state.in_game_time += game_event.extra_time_minutes
                            await manager.send_message(f"Gamemaster added +{game_event.extra_time_minutes} minutes to game time.", game_id, "system")

                    # ── Update world map ────────────────────────────────────
                    map_res = await db.execute(select(WorldMap).where(WorldMap.adventure_id == adv_id))
                    world_map = map_res.scalars().first()
                    if not world_map:
                        world_map = WorldMap(adventure_id=adv_id)
                        db.add(world_map)

                    # Update current scene visit
                    MapEngine.register_visit(world_map, state.scene_id, label=game_event.scene_label if game_event else None)
                    
                    # DISCOVERY: Show all exits from the current room on the map
                    room_exits_res = await db.execute(select(WorldExit).where(WorldExit.from_scene_id == state.scene_id, WorldExit.adventure_id == adv_id))
                    for ex in room_exits_res.scalars().all():
                        MapEngine.register_exit(world_map, ex.from_scene_id, ex.to_scene_id, exit_label=ex.label, is_locked=ex.is_locked)

                    await db.commit()

                    await manager.send_message(response_text, game_id, "assistant")
                    await manager.broadcast_sheet(game_id, _build_sheet(avatar, state))
                    
                    # Push content updates
                    await manager.send_map_update(game_id, MapEngine.to_mermaid(world_map))
                    
                    if adventure.strict_rules and game_event.image_prompt:
                        image_url = await MediaEngine.generate_scene_image(game_event.image_prompt, adv_id)
                        if image_url:
                            await manager.send_image_update(game_id, image_url)

                except Exception:
                    logger.exception("LLM processing error for game %s", game_id)
                    await manager.send_message("The Game Master is momentarily unavailable. Please try again.", game_id, "system")

    except WebSocketDisconnect:
        manager.disconnect(game_id)
