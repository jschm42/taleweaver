from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from backend.core.database import get_db
from backend.models.user import User
from backend.models.adventure import Adventure
from backend.models.avatar import Avatar
from backend.models.game_state import GameState

router = APIRouter(prefix="/adventures", tags=["Adventures"])

class CreateAdventurePayload(BaseModel):
    title: str
    avatar_name: str
    heartbeat_enabled: bool = False
    heartbeat_interval: int = 10

@router.post("")
async def create_adventure(payload: CreateAdventurePayload, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).limit(1))
    user = result.scalars().first()
    if not user:
        user = User(username="local_default_user")
        db.add(user)
        await db.flush()

    adv = Adventure(
        title=payload.title,
        strict_rules=True,
        heartbeat_enabled=payload.heartbeat_enabled,
        heartbeat_interval=payload.heartbeat_interval
    )
    db.add(adv)
    await db.flush()

    avatar = Avatar(
        user_id=user.id,
        name=payload.avatar_name,
        hp=200, stamina=200, mana=200
    )
    db.add(avatar)
    await db.flush()

    game_state = GameState(
        user_id=user.id,
        adventure_id=adv.id,
        avatar_id=avatar.id,
        scene_id="START",
        in_game_time=0
    )
    db.add(game_state)
    await db.commit()

    return {"game_id": game_state.id, "adventure_id": adv.id, "avatar_id": avatar.id}

@router.get("")
async def list_adventures(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(GameState))
    states = result.scalars().all()
    return [{"game_id": s.id, "adventure_id": s.adventure_id, "avatar_id": s.avatar_id} for s in states]
