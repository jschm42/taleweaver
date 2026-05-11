from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.models.character import Character
from backend.models.user import User
from backend.schemas.character import CharacterCreate, CharacterSchema, CharacterUpdate

router = APIRouter()

@router.get("/characters", response_model=list[CharacterSchema])
async def list_characters(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(Character).where(Character.user_id == current_user.id))
    return result.scalars().all()

@router.post("/characters", response_model=CharacterSchema)
async def create_character(
    payload: CharacterCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    char = Character(
        user_id=current_user.id,
        name=payload.name,
        profile_image=payload.profile_image,
        stats=payload.stats or {"strength": 10, "endurance": 10, "agility": 10, "intelligence": 10, "charisma": 10},
        inventory=payload.inventory or [],
        equipment=payload.equipment or {
            "Head": None, "Chest": None, "Arms": None, "Legs": None, "Hands": None, 
            "Feet": None, "Ring_1": None, "Ring_2": None, "Neck": None,
            "MainHand": None, "OffHand": None
        },
        status_effects=payload.status_effects or []
    )
    db.add(char)
    await db.commit()
    await db.refresh(char)
    return char

@router.put("/characters/{char_id}", response_model=CharacterSchema)
async def update_character(
    char_id: str,
    payload: CharacterUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(Character).where(Character.id == char_id, Character.user_id == current_user.id))
    char = result.scalars().first()
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")

    update_data = payload.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(char, key, value)
        
    await db.commit()
    await db.refresh(char)
    return char

@router.delete("/characters/{char_id}")
async def delete_character(
    char_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(Character).where(Character.id == char_id, Character.user_id == current_user.id))
    char = result.scalars().first()
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")
        
    await db.delete(char)
    await db.commit()
    return {"message": "Character deleted successfully"}

@router.get("/characters/{char_id}/export")
async def export_character(
    char_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(Character).where(Character.id == char_id, Character.user_id == current_user.id))
    char = result.scalars().first()
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")
        
    # Standard Pydantic export
    return CharacterSchema.from_orm(char)

@router.post("/characters/import", response_model=CharacterSchema)
async def import_character(
    payload: CharacterCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Re-use create logic but allow the payload to be the full source
    char = Character(
        user_id=current_user.id,
        name=payload.name,
        profile_image=payload.profile_image,
        stats=payload.stats or {"strength": 10, "endurance": 10, "agility": 10, "intelligence": 10, "charisma": 10},
        inventory=payload.inventory or [],
        equipment=payload.equipment or {},
        status_effects=payload.status_effects or []
    )
    db.add(char)
    await db.commit()
    await db.refresh(char)
    return char

