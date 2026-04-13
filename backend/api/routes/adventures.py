import logging
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException
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

router = APIRouter(prefix="/adventures", tags=["Adventures"])
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Request / Response Schemas
# ---------------------------------------------------------------------------

class CreateAdventurePayload(BaseModel):
    """Payload for creating a new adventure with its initial avatar."""
    title: str
    character_id: str
    image_url: Optional[str] = None
    context: Optional[str] = None
    strict_rules: bool = True
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


# ---------------------------------------------------------------------------
# Adventure CRUD
# ---------------------------------------------------------------------------

@router.post("", status_code=201)
async def create_adventure(
    payload: CreateAdventurePayload,
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

    adv = Adventure(
        title=payload.title,
        image_url=payload.image_url,
        context=payload.context,
        strict_rules=payload.strict_rules,
        time_per_turn=payload.time_per_turn,
        game_over_rules=payload.game_over_rules,
    )
    db.add(adv)
    await db.flush()

    avatar = Avatar(
        user_id=user.id,
        name=character.name,
        hp=200,
        stamina=200,
        mana=200,
        stats=character.stats,
        inventory=character.inventory,
        equipment=character.equipment,
        status_effects=character.status_effects,
    )
    # Add profile image if added to Avatar later, for now we skip adding the column to avoid migration issues.
    db.add(avatar)
    await db.flush()

    # --- Generate World ---
    llm_settings = user.llm_settings or {}
    complex_model = llm_settings.get("complex_model", "gpt-4o")
    
    await WorldGenerator.generate_world(
        db=db,
        user=user,
        adventure_id=adv.id,
        title=adv.title,
        context=adv.context or "A standard fantasy world.",
        model=complex_model
    )
    
    # Set initial scene to the first generated scene for this adventure
    scene_res = await db.execute(
        select(WorldScene).where(WorldScene.adventure_id == adv.id).limit(1)
    )
    first_scene = scene_res.scalars().first()
    start_scene_id = first_scene.id if first_scene else "START"

    game_state = GameState(
        user_id=user.id,
        adventure_id=adv.id,
        avatar_id=avatar.id,
        scene_id=start_scene_id,
        in_game_time=0,
    )
    db.add(game_state)
    await db.commit()

    logger.info("Created adventure '%s' (id=%s)", payload.title, adv.id)
    return {"game_id": game_state.id, "adventure_id": adv.id, "avatar_id": avatar.id}


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
