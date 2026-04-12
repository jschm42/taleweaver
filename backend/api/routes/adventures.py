import logging
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from backend.core.database import get_db
from backend.models.user import User
from backend.models.adventure import Adventure
from backend.models.avatar import Avatar
from backend.models.game_state import GameState
from backend.schemas.adventure import AdventureUpdate
from backend.schemas.avatar import AvatarUpdate
from backend.schemas.game_state import GameStateUpdate

router = APIRouter(prefix="/adventures", tags=["Adventures"])
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Request / Response Schemas
# ---------------------------------------------------------------------------

class CreateAdventurePayload(BaseModel):
    """Payload for creating a new adventure with its initial avatar."""
    title: str
    avatar_name: str
    strict_rules: bool = True
    heartbeat_enabled: bool = False
    heartbeat_interval: int = 60
    game_over_rules: Optional[Dict[str, Any]] = None


class AdventureResponse(BaseModel):
    """Full adventure details returned to the client."""
    id: str
    title: str
    strict_rules: bool
    heartbeat_enabled: bool
    heartbeat_interval: int
    game_over_rules: Optional[Dict[str, Any]]

    class Config:
        from_attributes = True


class GameSessionResponse(BaseModel):
    """Summary of a game session (GameState + linked entities)."""
    game_id: str
    adventure_id: str
    avatar_id: str
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
    """
    Creates a new adventure, an avatar, and the initial game state.
    Returns the IDs of all three created entities.
    """
    result = await db.execute(select(User).limit(1))
    user = result.scalars().first()
    if not user:
        user = User(username="local_default_user")
        db.add(user)
        await db.flush()

    adv = Adventure(
        title=payload.title,
        strict_rules=payload.strict_rules,
        heartbeat_enabled=payload.heartbeat_enabled,
        heartbeat_interval=payload.heartbeat_interval,
        game_over_rules=payload.game_over_rules,
    )
    db.add(adv)
    await db.flush()

    avatar = Avatar(
        user_id=user.id,
        name=payload.avatar_name,
        hp=200,
        stamina=200,
        mana=200,
        stats={},
        inventory=[],
        equipment={},
        status_effects=[],
    )
    db.add(avatar)
    await db.flush()

    game_state = GameState(
        user_id=user.id,
        adventure_id=adv.id,
        avatar_id=avatar.id,
        scene_id="START",
        in_game_time=0,
    )
    db.add(game_state)
    await db.commit()

    logger.info("Created adventure '%s' (id=%s)", payload.title, adv.id)
    return {"game_id": game_state.id, "adventure_id": adv.id, "avatar_id": avatar.id}


@router.get("", response_model=List[GameSessionResponse])
async def list_adventures(db: AsyncSession = Depends(get_db)) -> list:
    """Returns all game sessions with their linked adventure and avatar IDs."""
    result = await db.execute(select(GameState))
    states = result.scalars().all()
    return [
        GameSessionResponse(
            game_id=s.id,
            adventure_id=s.adventure_id,
            avatar_id=s.avatar_id,
            scene_id=s.scene_id,
            in_game_time=s.in_game_time,
            is_paused=s.is_paused,
        )
        for s in states
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
