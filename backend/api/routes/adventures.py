import logging
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from pydantic import BaseModel

from backend.core.database import get_db
from backend.models.user import User
from backend.models.adventure import Adventure
from backend.models.avatar import Avatar
from backend.models.character import Character
from backend.models.game_state import GameState
from backend.models.chat import ChatMessage
from backend.models.world_entity import WorldScene, WorldExit, WorldEntity
from backend.models.world_map import WorldMap
from backend.schemas.adventure import AdventureUpdate, AdventureDebugResponse
from backend.schemas.avatar import AvatarUpdate
from backend.schemas.game_state import GameStateUpdate
from backend.engine.world_generator import WorldGenerator
from backend.engine.command_parser import CommandParser
from backend.engine.rule_engine import RuleEngine, GameEvent, GameOverException
from backend.engine.map_engine import MapEngine
from backend.engine.media_engine import MediaEngine
from backend.engine.memory_manager import MemoryManager
from backend.engine.debug_engine import DebugEngine
from backend.core.llm_router import GameMasterLLM

router = APIRouter(prefix="/adventures", tags=["Adventures"])
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Request / Response Schemas
# ---------------------------------------------------------------------------

class CreateAdventurePayload(BaseModel):
    """Payload for creating a new adventure with its initial avatar."""
    id: str  # Added to support client-side UUID generation for polling
    title: str
    character_id: str
    image_url: Optional[str] = None
    context: Optional[str] = None
    strict_rules: bool = True
    generate_npc_images: bool = False
    generate_item_images: bool = False
    time_per_turn: int = 5
    game_over_rules: Optional[Dict[str, Any]] = None


class AdventureResponse(BaseModel):
    """Full adventure details returned to the client."""
    id: str
    title: str
    strict_rules: bool
    time_per_turn: int
    game_over_rules: Optional[Dict[str, Any]]
    context: Optional[str] = None

    class Config:
        from_attributes = True


class GameSessionResponse(BaseModel):
    """Summary of a game session (GameState + linked entities)."""
    game_id: str
    adventure_id: str
    avatar_id: str
    adventure_title: str
    image_url: Optional[str] = None
    scene_id: str
    in_game_time: int
    is_paused: bool

class ChatResponse(BaseModel):
    """Unified response for a game turn."""
    messages: List[Dict[str, str]] # [{'role': '...', 'content': '...'}]
    sheet: Dict[str, Any]
    mermaid: Optional[str] = None
    image_url: Optional[str] = None
    entities: List[Dict[str, Any]] = []
    game_over: bool = False
    game_over_reason: Optional[str] = None

class ChatRequest(BaseModel):
    content: str
    auto_visualize: bool = False


# ---------------------------------------------------------------------------
# Adventure CRUD
# ---------------------------------------------------------------------------

@router.post("", status_code=201)
async def create_adventure(
    payload: CreateAdventurePayload,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(User).limit(1))
    user = result.scalars().first()
    if not user:
        user = User(username="local_default_user")
        db.add(user)
        await db.flush()

    # Fetch character
    char_res = await db.execute(select(Character).where(Character.id == payload.character_id))
    character = char_res.scalars().first()
    if not character:
        raise HTTPException(status_code=404, detail="Character not found.")

    # Create placeholder adventure
    adv = Adventure(
        id=payload.id,
        title=payload.title,
        image_url=payload.image_url,
        context=payload.context,
        strict_rules=payload.strict_rules,
        time_per_turn=payload.time_per_turn,
        game_over_rules=payload.game_over_rules,
        is_ready=False,
        creation_status="Initializing Foundations..."
    )
    db.add(adv)
    await db.flush()

    avatar = Avatar(
        user_id=user.id,
        adventure_id=adv.id, # Link early for background tasks
        name=character.name,
        hp=200,
        stamina=200,
        mana=200,
        stats=character.stats,
        inventory=character.inventory,
        equipment=character.equipment,
        status_effects=character.status_effects,
    )
    db.add(avatar)
    await db.commit()

    # Dispatch generation
    background_tasks.add_task(run_background_generation, adv.id, user.id, payload.model_dump())
    
    return {"adventure_id": adv.id}

async def run_background_generation(adventure_id: str, user_id: str, payload_dict: dict):
    """Background task for world gen, scene init, and auto-cleanup on failure."""
    from backend.core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        try:
            # Re-fetch user in this session
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalars().first()
            if not user: return

            llm_settings = user.llm_settings or {}
            complex_model = llm_settings.get("complex_model", "gpt-4o")
            preferred_provider = llm_settings.get("preferred_provider", "openai")
            
            # 1. World Gen
            await WorldGenerator.generate_world(
                db=db, 
                user=user, 
                adventure_id=adventure_id, 
                title=payload_dict['title'], 
                context=payload_dict.get('context') or "A standard fantasy world.",
                model=complex_model,
                provider=preferred_provider,
                generate_npc_images=payload_dict.get('generate_npc_images', False),
                generate_item_images=payload_dict.get('generate_item_images', False)
            )
            
            # 2. Initial GameState
            scenes_res = await db.execute(select(WorldScene).where(WorldScene.adventure_id == adventure_id))
            scenes = scenes_res.scalars().all()
            if not scenes: raise ValueError("Engine failed to sprout any locations.")
            
            # Get Avatar ID
            avatar_res = await db.execute(select(Avatar).where(Avatar.adventure_id == adventure_id))
            avatar = avatar_res.scalars().first()
            
            db.add(GameState(
                id=adventure_id,
                user_id=user_id,
                adventure_id=adventure_id,
                avatar_id=avatar.id if avatar else None,
                scene_id=scenes[0].id,
                in_game_time=0
            ))
            
            # 3. Mark Ready
            adv = await db.get(Adventure, adventure_id)
            if adv:
                adv.is_ready = True
                adv.creation_status = "Ready"
            
            await db.commit()
            
        except Exception as e:
            logger.error("Background Gen Failed for %s: %s", adventure_id, e)
            try:
                await db.rollback()
                # Auto-cleanup as per user preference
                await db.execute(delete(Avatar).where(Avatar.adventure_id == adventure_id))
                await db.execute(delete(Adventure).where(Adventure.id == adventure_id))
                await db.commit()
            except:
                pass

@router.get("/{game_id}/status")
async def get_adventure_status(game_id: str, db: AsyncSession = Depends(get_db)):
    adv = await db.get(Adventure, game_id)
    if not adv:
        raise HTTPException(status_code=404, detail="Adventure cleaned up due to failure")
    return {
        "is_ready": adv.is_ready,
        "status": adv.creation_status,
        "error": adv.creation_error
    }


@router.get("", response_model=List[GameSessionResponse])
async def list_adventures(db: AsyncSession = Depends(get_db)) -> list:
    """Returns all game sessions with their linked adventure and avatar IDs."""
    result = await db.execute(
        select(GameState, Adventure)
        .join(Adventure, GameState.adventure_id == Adventure.id)
    )
    rows = result.all()
    return [
        GameSessionResponse(
            game_id=s.id,
            adventure_id=s.adventure_id,
            avatar_id=s.avatar_id,
            adventure_title=a.title,
            image_url=a.image_url,
            scene_id=s.scene_id,
            in_game_time=s.in_game_time,
            is_paused=s.is_paused,
        )
        for s, a in rows
    ]


@router.get("/{adventure_id}", response_model=AdventureResponse)
async def get_adventure(adventure_id: str, db: AsyncSession = Depends(get_db)) -> Adventure:
    """Returns the details of a single adventure by its ID."""
    result = await db.execute(select(Adventure).where(Adventure.id == adventure_id))
    adv = result.scalars().first()
    if not adv:
        raise HTTPException(status_code=404, detail="Adventure not found.")
    return adv


@router.patch("/{adventure_id}", response_model=AdventureResponse)
async def update_adventure(
    adventure_id: str,
    payload: AdventureUpdate,
    db: AsyncSession = Depends(get_db),
) -> Adventure:
    """
    Partially updates an adventure's configuration (title, rules, heartbeat settings).
    Only provided fields are updated.
    """
    result = await db.execute(select(Adventure).where(Adventure.id == adventure_id))
    adv = result.scalars().first()
    if not adv:
        raise HTTPException(status_code=404, detail="Adventure not found.")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(adv, field, value)

    await db.commit()
    await db.refresh(adv)
    logger.info("Updated adventure %s: %s", adventure_id, update_data)
    return adv


@router.delete("/{adventure_id}", status_code=204)
async def delete_adventure(adventure_id: str, db: AsyncSession = Depends(get_db)) -> None:
    """
    Deletes an adventure and its associated game state.
    Returns 204 No Content on success.
    """
    result = await db.execute(select(Adventure).where(Adventure.id == adventure_id))
    adv = result.scalars().first()
    if not adv:
        raise HTTPException(status_code=404, detail="Adventure not found.")

    # Remove linked game states first to avoid FK constraint violations
    gs_result = await db.execute(
        select(GameState).where(GameState.adventure_id == adventure_id)
    )
    for gs in gs_result.scalars().all():
        await db.delete(gs)

    await db.delete(adv)
    await db.commit()
    logger.info("Deleted adventure %s", adventure_id)


# ---------------------------------------------------------------------------
# Game-State sub-routes
# ---------------------------------------------------------------------------

@router.get("/{adventure_id}/state", response_model=GameSessionResponse)
async def get_game_state(adventure_id: str, db: AsyncSession = Depends(get_db)) -> GameSessionResponse:
    """Returns the current game state for a given adventure."""
    result = await db.execute(
        select(GameState).where(GameState.adventure_id == adventure_id)
    )
    state = result.scalars().first()
    if not state:
        raise HTTPException(status_code=404, detail="Game state not found.")
    return GameSessionResponse(
        game_id=state.id,
        adventure_id=state.adventure_id,
        avatar_id=state.avatar_id,
        scene_id=state.scene_id,
        in_game_time=state.in_game_time,
        is_paused=state.is_paused,
    )


@router.patch("/{adventure_id}/state")
async def update_game_state(
    adventure_id: str,
    payload: GameStateUpdate,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Updates scene_id or in_game_time for the active game state of an adventure."""
    result = await db.execute(
        select(GameState).where(GameState.adventure_id == adventure_id)
    )
    state = result.scalars().first()
    if not state:
        raise HTTPException(status_code=404, detail="Game state not found.")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(state, field, value)

    await db.commit()
    return {"status": "updated", "game_id": state.id}


@router.post("/{adventure_id}/pause")
async def pause_game(adventure_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    """Pauses the heartbeat processing for a game session."""
    result = await db.execute(
        select(GameState).where(GameState.adventure_id == adventure_id)
    )
    state = result.scalars().first()
    if not state:
        raise HTTPException(status_code=404, detail="Game state not found.")
    state.is_paused = True
    await db.commit()
    return {"status": "paused", "game_id": state.id}


@router.post("/{adventure_id}/resume")
async def resume_game(adventure_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    """Resumes heartbeat processing for a paused game session."""
    result = await db.execute(
        select(GameState).where(GameState.adventure_id == adventure_id)
    )
    state = result.scalars().first()
    if not state:
        raise HTTPException(status_code=404, detail="Game state not found.")
    state.is_paused = False
    await db.commit()
    return {"status": "resumed", "game_id": state.id}

@router.get("/{adventure_id}/debug", response_model=AdventureDebugResponse)
async def get_adventure_debug(adventure_id: str, db: AsyncSession = Depends(get_db)):
    """
    Returns full world state and configuration for a specific adventure.
    """
    adv_res = await db.execute(select(Adventure).where(Adventure.id == adventure_id))
    adventure = adv_res.scalars().first()
    if not adventure:
        raise HTTPException(status_code=404, detail="Adventure not found")
        
    scene_res = await db.execute(select(WorldScene).where(WorldScene.adventure_id == adventure_id))
    scenes = scene_res.scalars().all()
    
    exit_res = await db.execute(select(WorldExit).where(WorldExit.adventure_id == adventure_id))
    exits = exit_res.scalars().all()
    
    entity_res = await db.execute(select(WorldEntity).where(WorldEntity.adventure_id == adventure_id))
    entities = entity_res.scalars().all()
    
    # Return serializable dicts
    return AdventureDebugResponse(
        adventure={c.name: getattr(adventure, c.name) for c in adventure.__table__.columns},
        scenes=[{c.name: getattr(s, c.name) for c in s.__table__.columns} for s in scenes],
        npcs=[{c.name: getattr(ent, c.name) for c in ent.__table__.columns} for ent in entities if ent.entity_type == "NPC"],
        objects=[{c.name: getattr(ent, c.name) for c in ent.__table__.columns} for ent in entities if ent.entity_type == "OBJECT"],
        exits=[{c.name: getattr(ex, c.name) for c in ex.__table__.columns} for ex in exits]
    )

@router.post("/{adventure_id}/reset")
async def reset_adventure(adventure_id: str, db: AsyncSession = Depends(get_db)):
    """
    Resets the adventure's world state to its original pre-generated blueprint.
    """
    adv_res = await db.execute(select(Adventure).where(Adventure.id == adventure_id))
    adventure = adv_res.scalars().first()
    if not adventure or not adventure.original_manifest:
        raise HTTPException(status_code=400, detail="Adventure not found or has no original manifest to reset to.")
    
    # Clear current world state
    await db.execute(delete(WorldScene).where(WorldScene.adventure_id == adventure_id))
    await db.execute(delete(WorldExit).where(WorldExit.adventure_id == adventure_id))
    await db.execute(delete(WorldEntity).where(WorldEntity.adventure_id == adventure_id))
    await db.execute(delete(WorldMap).where(WorldMap.adventure_id == adventure_id))
    
    # Re-apply manifest
    await WorldGenerator.apply_manifest(db, adventure_id, adventure.original_manifest)
    
    await db.commit()
    return {"status": "reset", "message": "World restored to initial state."}

@router.get("/{adventure_id}/export/manifest")
async def export_adventure_manifest(adventure_id: str, db: AsyncSession = Depends(get_db)):
    """Exports only the original world blueprint."""
    adv_res = await db.execute(select(Adventure).where(Adventure.id == adventure_id))
    adventure = adv_res.scalars().first()
    if not adventure or not adventure.original_manifest:
        raise HTTPException(status_code=404, detail="Original manifest not found.")
    return adventure.original_manifest

@router.get("/{adventure_id}/export/session")
async def export_adventure_session(adventure_id: str, db: AsyncSession = Depends(get_db)):
    """Exports the COMPLETE current game state as a bundle."""
    adv_res = await db.execute(select(Adventure).where(Adventure.id == adventure_id))
    adventure = adv_res.scalars().first()
    if not adventure:
        raise HTTPException(status_code=404, detail="Adventure not found")
        
    scene_res = await db.execute(select(WorldScene).where(WorldScene.adventure_id == adventure_id))
    exit_res = await db.execute(select(WorldExit).where(WorldExit.adventure_id == adventure_id))
    entity_res = await db.execute(select(WorldEntity).where(WorldEntity.adventure_id == adventure_id))
    
    # Game State & Avatar
    state_res = await db.execute(select(GameState).where(GameState.adventure_id == adventure_id))
    state = state_res.scalars().first()
    avatar = None
    chat_logs = []
    
    if state:
        av_res = await db.execute(select(Avatar).where(Avatar.id == state.avatar_id))
        avatar = av_res.scalars().first()
        
        chat_res = await db.execute(select(ChatMessage).where(ChatMessage.game_state_id == state.id).order_by(ChatMessage.created_at))
        chat_logs = chat_res.scalars().all()

    return {
        "version": "1.0",
        "type": "SESSION_BUNDLE",
        "adventure": {c.name: getattr(adventure, c.name) for c in adventure.__table__.columns},
        "scenes": [{c.name: getattr(s, c.name) for c in s.__table__.columns} for s in scene_res.scalars().all()],
        "exits": [{c.name: getattr(e, c.name) for c in e.__table__.columns} for e in exit_res.scalars().all()],
        "entities": [{c.name: getattr(ent, c.name) for c in ent.__table__.columns} for ent in entity_res.scalars().all()],
        "game_state": {c.name: getattr(state, c.name) for c in state.__table__.columns} if state else None,
        "avatar": {c.name: getattr(avatar, c.name) for c in avatar.__table__.columns} if avatar else None,
        "chat_history": [{c.name: getattr(msg, c.name) for c in msg.__table__.columns} for msg in chat_logs]
    }

@router.post("/import")
async def import_adventure(payload: Dict[str, Any], db: AsyncSession = Depends(get_db)):
    """
    Imports an adventure from JSON.
    Supports either a Raw Manifest or a Full Session Bundle.
    """
    res = await db.execute(select(User).limit(1))
    user = res.scalars().first()
    if not user:
        user = User(username="default_player")
        db.add(user)
        await db.flush()

    # Determine if this is a Session Bundle or just a Manifest
    is_session = payload.get("type") == "SESSION_BUNDLE"
    
    if is_session:
        # --- Handle Session Bundle ---
        data = payload
        old_adv = data["adventure"]
        
        # 1. Recreate Adventure
        new_adv = Adventure(
            title=f"{old_adv['title']} (Imported)",
            context=old_adv.get("context"),
            image_url=old_adv.get("image_url"),
            strict_rules=old_adv.get("strict_rules", True),
            time_per_turn=old_adv.get("time_per_turn", 10),
            game_over_rules=old_adv.get("game_over_rules"),
            original_manifest=old_adv.get("original_manifest")
        )
        db.add(new_adv)
        await db.flush() # Get new_adv.id
        
        # 2. Recreate Scenes (ID Slug preservation is fine as they are scoped by adventure_id)
        for s in data["scenes"]:
            db.add(WorldScene(
                id=s["id"],
                adventure_id=new_adv.id,
                label=s["label"],
                description=s["description"]
            ))
            
        # 3. Recreate Entities
        for ent in data["entities"]:
            db.add(WorldEntity(
                id=ent["id"],
                adventure_id=new_adv.id,
                entity_type=ent["entity_type"],
                name=ent["name"],
                description=ent["description"],
                current_scene_id=ent["current_scene_id"],
                spatial_position=ent.get("spatial_position"),
                inventory=ent.get("inventory", []),
                stats=ent.get("stats", {})
            ))
            
        # 4. Recreate Exits
        for ex in data["exits"]:
            db.add(WorldExit(
                adventure_id=new_adv.id,
                from_scene_id=ex["from_scene_id"],
                to_scene_id=ex["to_scene_id"],
                label=ex["label"],
                is_locked=ex.get("is_locked", False),
                lock_description=ex.get("lock_description")
            ))
            
        # 5. Recreate Avatar & GameState
        old_state = data.get("game_state")
        old_avatar = data.get("avatar")
        
        if old_state and old_avatar:
            new_avatar = Avatar(
                user_id=user.id,
                name=old_avatar["name"],
                hp=old_avatar["hp"],
                stamina=old_avatar["stamina"],
                mana=old_avatar["mana"],
                stats=old_avatar["stats"],
                inventory=old_avatar["inventory"],
                equipment=old_avatar["equipment"],
                status_effects=old_avatar["status_effects"]
            )
            db.add(new_avatar)
            await db.flush()
            
            new_state = GameState(
                user_id=user.id,
                adventure_id=new_adv.id,
                avatar_id=new_avatar.id,
                scene_id=old_state["scene_id"],
                in_game_time=old_state.get("in_game_time", 0)
            )
            db.add(new_state)
            await db.flush()
            
            # 6. Recreate Chat History
            for msg in data.get("chat_history", []):
                db.add(ChatMessage(
                    game_state_id=new_state.id,
                    role=msg["role"],
                    content=msg["content"]
                ))
        
        await db.commit()
        return {"status": "imported", "adventure_id": new_adv.id, "type": "SESSION"}

    else:
        # --- Handle Pure Manifest Import ---
        # Assume payload IS the manifest
        # We need a title and context to create the shell first
        new_adv = Adventure(
            title="Imported Blueprint",
            context="Restored from blueprint.",
            original_manifest=payload
        )
        db.add(new_adv)
        await db.flush()
        
        await WorldGenerator.apply_manifest(db, new_adv.id, payload)
        await db.commit()
        return {"status": "imported", "adventure_id": new_adv.id, "type": "MANIFEST"}

def _build_sheet_snapshot(avatar: Avatar, state: GameState) -> dict:
    """Builds a serialisable character-sheet snapshot."""
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

@router.get("/{game_id}/chat", response_model=ChatResponse)
async def get_chat_history(game_id: str, db: AsyncSession = Depends(get_db)):
    """Retrieves full chat history and current session state."""
    state_res = await db.execute(select(GameState).where(GameState.id == game_id))
    state = state_res.scalars().first()
    if not state:
        raise HTTPException(status_code=404, detail="Session not found.")
        
    av_res = await db.execute(select(Avatar).where(Avatar.id == state.avatar_id))
    avatar = av_res.scalars().first()
    
    chat_res = await db.execute(select(ChatMessage).where(ChatMessage.game_state_id == game_id).order_by(ChatMessage.created_at.asc()))
    history = [{"role": m.role, "content": m.content} for m in chat_res.scalars().all()]
    
    map_res = await db.execute(select(WorldMap).where(WorldMap.adventure_id == state.adventure_id))
    world_map = map_res.scalars().first()
    mermaid_data = MapEngine.to_mermaid(world_map) if world_map else None
    
    ent_res = await db.execute(select(WorldEntity).where(WorldEntity.adventure_id == state.adventure_id, WorldEntity.current_scene_id == state.scene_id))
    entities = [{c.name: getattr(e, c.name) for c in e.__table__.columns} for e in ent_res.scalars().all()]
    
    return ChatResponse(
        messages=history,
        sheet=_build_sheet_snapshot(avatar, state),
        mermaid=mermaid_data,
        entities=entities
    )

@router.post("/{game_id}/chat", response_model=ChatResponse)
async def post_chat_message(
    game_id: str,
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Unified game turn endpoint. Processes user input (natural language or slash command),
    advances world state, and returns all updates.
    """
    user_msg = payload.content.strip()
    
    # 1. Load context
    state_res = await db.execute(select(GameState).where(GameState.id == game_id))
    state = state_res.scalars().first()
    if not state:
        raise HTTPException(status_code=404, detail="Game session not found.")

    if state.is_paused:
        return ChatResponse(
            messages=[{"role": "system", "content": "The game is currently paused."}],
            sheet=_build_sheet_snapshot(avatar, state) if 'avatar' in locals() else {}
        )

    av_res = await db.execute(select(Avatar).where(Avatar.id == state.avatar_id))
    avatar = av_res.scalars().first()
    
    u_res = await db.execute(select(User).where(User.id == state.user_id))
    user = u_res.scalars().first()

    adv_res = await db.execute(select(Adventure).where(Adventure.id == state.adventure_id))
    adventure = adv_res.scalars().first()

    response_messages = []
    mermaid_data = None
    image_url = None
    game_over = False
    game_over_reason = None

    # --- Fresh Entry / Re-orientation Check ---
    msg_count_res = await db.execute(select(ChatMessage).where(ChatMessage.game_state_id == game_id).limit(1))
    is_first_message = msg_count_res.scalars().first() is None
    
    # If it's a [LOOK AROUND] trigger or a completely new start
    actual_user_input = user_msg
    if not user_msg:
        user_msg = "[LOOK AROUND]"

    # --- Handle Debug Commands ---
    if user_msg.startswith("/debug"):
        cmd_args = user_msg[7:].strip()
        debug_info = await DebugEngine.handle_debug_command(db, state, cmd_args)
        return ChatResponse(
            messages=[{"role": "system", "content": debug_info}],
            sheet=_build_sheet_snapshot(avatar, state)
        )

    # --- Slash-command fast path ---
    if user_msg.startswith("/"):
        if user_msg.strip().lower() == "/map":
             map_res = await db.execute(select(WorldMap).where(WorldMap.adventure_id == state.adventure_id))
             world_map = map_res.scalars().first()
             mermaid_data = MapEngine.to_mermaid(world_map) if world_map else None
             return ChatResponse(messages=[], sheet=_build_sheet_snapshot(avatar, state), mermaid=mermaid_data)
        
        response = CommandParser.parse_command(avatar, user_msg)
        await db.commit()
        return ChatResponse(
            messages=[{"role": "system", "content": response}],
            sheet=_build_sheet_snapshot(avatar, state)
        )

    # --- Turn-based Logic: Advance Time & Status Effects ---
    state.in_game_time += adventure.time_per_turn
    tick_msgs = RuleEngine.apply_ticks(avatar)
    for tm in tick_msgs:
        response_messages.append({"role": "system", "content": tm})

    # Record User Message
    if actual_user_input:
        user_chat_rec = ChatMessage(game_state_id=game_id, role="user", content=actual_user_input)
        db.add(user_chat_rec)
        await db.flush()

    # --- History & Context ---
    hist_res = await db.execute(select(ChatMessage).where(ChatMessage.game_state_id == game_id).order_by(ChatMessage.created_at.asc()))
    history = [{"role": m.role, "content": m.content} for m in hist_res.scalars().all()]

    # Fetch pre-generated entities for context
    scene_res = await db.execute(select(WorldScene).where(WorldScene.id == state.scene_id, WorldScene.adventure_id == state.adventure_id))
    current_scene = scene_res.scalars().first()
    
    entity_res = await db.execute(select(WorldEntity).where(WorldEntity.current_scene_id == state.scene_id, WorldEntity.adventure_id == state.adventure_id))
    entities = entity_res.scalars().all()
    
    exit_res = await db.execute(select(WorldExit).where(WorldExit.from_scene_id == state.scene_id, WorldExit.adventure_id == state.adventure_id))
    exits = exit_res.scalars().all()

    context_messages = MemoryManager.build_context(
        avatar, adventure.context or "", history, 
        current_scene=current_scene, entities=entities, exits=exits, in_game_time=state.in_game_time
    )
    system_prompt = context_messages[0]["content"]

    # --- LLM Processing ---
    settings = user.llm_settings or {}
    small_model = settings.get("small_model", "openai/gpt-4o-mini")
    complex_model = settings.get("complex_model", "openai/gpt-4o-mini")
    provider = settings.get("preferred_provider", "openai")
    
    llm = GameMasterLLM(user, provider=provider)
    game_event = None
    response_text = ""

    try:
        if adventure.strict_rules:
            # --- PASS 1: Technical Reasoning (Small Model) ---
            # We ask the small model to decide the technical outcomes (GameEvent)
            # focusing on IDs, resources, and world state.
            mechanics_system_prompt = system_prompt + "\n\nCRITICAL: Focus on logical consistency and mechanics. Your 'narrative_description' will be used as a draft/log; keep it short."
            game_event = llm.execute_complex_task(
                system_prompt=mechanics_system_prompt,
                user_prompt=user_msg,
                response_model=GameEvent,
                model=small_model
            )

            # --- PASS 2: Atmospheric Narration (Complex Model) ---
            # We use the complex model to turn the technical outcome into premium prose.
            narration_system_prompt = system_prompt + f"\n\nTECHNICAL OUTCOME TO NARRATE: {game_event.model_dump_json(exclude={'narrative_description'})}\n"
            narration_system_prompt += "Write a highly atmospheric, rich narrative for this turn. Do not mention numbers or system IDs; describe the effects physically. 1-2 paragraphs max."
            
            response_text = llm.execute_simple_task(
                system_prompt=narration_system_prompt,
                user_prompt=user_msg,
                model=complex_model
            )
            
            # Apply mechanics to avatar, but use the complex narration for the final output
            try:
                # We ignore the small model's narrative draft and use the complex one
                RuleEngine.apply_event(avatar, game_event)
            except GameOverException as exc:
                game_over = True
                game_over_reason = str(exc)
                response_text = str(exc)
        else:
            # Free-form narrative always uses the high-quality complex model
            response_text = llm.execute_simple_task(system_prompt, user_msg, complex_model)

        # Record Assistant Message
        assistant_chat = ChatMessage(game_state_id=game_id, role="assistant", content=response_text)
        db.add(assistant_chat)
        response_messages.append({"role": "assistant", "content": response_text})

        # --- Update World State ---
        if adventure.strict_rules and game_event:
            if game_event.new_scene_id: state.scene_id = game_event.new_scene_id
            
            if game_event.moved_entities:
                for move in game_event.moved_entities:
                    ent_mv_res = await db.execute(select(WorldEntity).where(WorldEntity.id == move.entity_id, WorldEntity.adventure_id == state.adventure_id))
                    entity = ent_mv_res.scalars().first()
                    if entity:
                        if move.to_scene_id: entity.current_scene_id = move.to_scene_id
                        if move.to_spatial_position: entity.spatial_position = move.to_spatial_position

            if game_event.updated_exits:
                for upd in game_event.updated_exits:
                    ex_res = await db.execute(select(WorldExit).where(WorldExit.from_scene_id == upd.from_scene_id, WorldExit.to_scene_id == upd.to_scene_id, WorldExit.adventure_id == state.adventure_id))
                    world_exit = ex_res.scalars().first()
                    if world_exit: world_exit.is_locked = upd.is_locked

            if game_event.extra_time_minutes:
                state.in_game_time += game_event.extra_time_minutes
                response_messages.append({"role": "system", "content": f"Gamemaster added +{game_event.extra_time_minutes} minutes."})

        # --- Update Map & Register Discovery ---
        map_res = await db.execute(select(WorldMap).where(WorldMap.adventure_id == state.adventure_id))
        world_map = map_res.scalars().first()
        if not world_map:
            world_map = WorldMap(adventure_id=state.adventure_id)
            db.add(world_map)
        
        MapEngine.register_visit(world_map, state.scene_id, label=game_event.scene_label if game_event else None)
        room_exits_res = await db.execute(select(WorldExit).where(WorldExit.from_scene_id == state.scene_id, WorldExit.adventure_id == state.adventure_id))
        for ex in room_exits_res.scalars().all():
            MapEngine.register_exit(world_map, ex.from_scene_id, ex.to_scene_id, exit_label=ex.label, is_locked=ex.is_locked)
        
        mermaid_data = MapEngine.to_mermaid(world_map)
        
        # --- Media Generation ---
        if adventure.strict_rules and game_event and game_event.image_prompt and payload.auto_visualize:
            image_url = await MediaEngine.generate_scene_image(
                game_event.image_prompt, 
                adventure.id,  # ADDED adventure_id
                {"t2i_settings": user.t2i_settings}, 
                user.encrypted_api_keys
            )

        await db.commit()
        
        # Fetch current entities for the response
        curr_ent_res = await db.execute(select(WorldEntity).where(WorldEntity.adventure_id == state.adventure_id, WorldEntity.current_scene_id == state.scene_id))
        curr_entities = [{c.name: getattr(e, c.name) for c in e.__table__.columns} for e in curr_ent_res.scalars().all()]

        return ChatResponse(
            messages=response_messages,
            sheet=_build_sheet_snapshot(avatar, state),
            mermaid=mermaid_data,
            image_url=image_url,
            entities=curr_entities,
            game_over=game_over,
            game_over_reason=game_over_reason
        )

    except Exception as e:
        logger.exception("Chat processing error")
        return ChatResponse(
            messages=[{"role": "system", "content": "The Game Master is momentarily unavailable. Please try again."}],
            sheet=_build_sheet_snapshot(avatar, state) if 'avatar' in locals() else {}
        )
