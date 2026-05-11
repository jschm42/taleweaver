"""
REST routes for Avatar (Character Sheet) management.

Provides endpoints to read and update an avatar's stats, inventory,
equipment, and status effects.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.engine.stat_aggregator import calculate_total_stats
from backend.models.avatar import Avatar
from backend.schemas.avatar import Avatar as AvatarSchema
from backend.schemas.avatar import AvatarUpdate

router = APIRouter(prefix="/avatars", tags=["Avatars"])
logger = logging.getLogger(__name__)


@router.get("/{avatar_id}", response_model=AvatarSchema)
async def get_avatar(avatar_id: str, db: AsyncSession = Depends(get_db)) -> Avatar:
    """Returns the full character sheet for a given avatar."""
    result = await db.execute(select(Avatar).where(Avatar.id == avatar_id))
    avatar = result.scalars().first()
    if not avatar:
        raise HTTPException(status_code=404, detail="Avatar not found.")
    return avatar


@router.get("/{avatar_id}/stats")
async def get_avatar_stats(avatar_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    """
    Returns the dynamically aggregated stats for an avatar.

    Combines base stats, equipment modifiers, and active status-effect
    modifiers into a single O(1) stat snapshot.
    """
    result = await db.execute(select(Avatar).where(Avatar.id == avatar_id))
    avatar = result.scalars().first()
    if not avatar:
        raise HTTPException(status_code=404, detail="Avatar not found.")

    total_stats = calculate_total_stats(avatar)
    return {
        "avatar_id": avatar_id,
        "hp": avatar.hp,
        "stamina": avatar.stamina,
        "mana": avatar.mana,
        "total_stats": total_stats,
        "status_effects": avatar.status_effects,
    }


@router.patch("/{avatar_id}", response_model=AvatarSchema)
async def update_avatar(
    avatar_id: str,
    payload: AvatarUpdate,
    db: AsyncSession = Depends(get_db),
) -> Avatar:
    """
    Partially updates an avatar's fields (stats, HP, inventory, equipment, etc.).
    Only provided fields are written; omitted fields remain unchanged.
    """
    result = await db.execute(select(Avatar).where(Avatar.id == avatar_id))
    avatar = result.scalars().first()
    if not avatar:
        raise HTTPException(status_code=404, detail="Avatar not found.")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(avatar, field, value)

    await db.commit()
    await db.refresh(avatar)
    logger.info("Updated avatar %s: %s", avatar_id, list(update_data.keys()))
    return avatar


@router.delete("/{avatar_id}/status-effects/{effect_name}", status_code=204)
async def remove_status_effect(
    avatar_id: str,
    effect_name: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Removes a single named status effect from an avatar.
    Returns 404 if the avatar or the effect does not exist.
    """
    result = await db.execute(select(Avatar).where(Avatar.id == avatar_id))
    avatar = result.scalars().first()
    if not avatar:
        raise HTTPException(status_code=404, detail="Avatar not found.")

    current_effects = list(avatar.status_effects or [])
    if effect_name not in current_effects:
        raise HTTPException(status_code=404, detail=f"Status effect '{effect_name}' not found.")

    current_effects.remove(effect_name)
    avatar.status_effects = current_effects
    await db.commit()
    logger.info("Removed status effect '%s' from avatar %s", effect_name, avatar_id)

