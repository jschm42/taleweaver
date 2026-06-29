"""
REST routes for Avatar (Character Sheet) management.

Provides endpoints to read and update an avatar's stats, inventory,
equipment, and status effects.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.engine.stat_aggregator import calculate_total_stats
from backend.models.avatar import Avatar
from backend.models.user import User
from backend.schemas.avatar import Avatar as AvatarSchema
from backend.schemas.avatar import AvatarUpdate

router = APIRouter(prefix="/avatars", tags=["Avatars"])
logger = logging.getLogger(__name__)


async def _get_owned_avatar_or_404(
    db: AsyncSession, avatar_id: str, user_id: str
) -> Avatar:
    """Fetch an avatar only if it belongs to the given user (or user is admin)."""
    result = await db.execute(
        select(Avatar).where(Avatar.id == avatar_id, Avatar.user_id == user_id)
    )
    avatar = result.scalars().first()
    if not avatar:
        raise HTTPException(status_code=404, detail="Avatar not found.")
    return avatar


@router.get("/{avatar_id}", response_model=AvatarSchema)
async def get_avatar(
    avatar_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Avatar:
    """Returns the full character sheet for a given avatar (owner only)."""
    query = select(Avatar).where(Avatar.id == avatar_id)
    if current_user.role != "admin":
        query = query.where(Avatar.user_id == current_user.id)
    result = await db.execute(query)
    avatar = result.scalars().first()
    if not avatar:
        raise HTTPException(status_code=404, detail="Avatar not found.")
    return avatar


@router.get("/{avatar_id}/stats")
async def get_avatar_stats(
    avatar_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Returns the dynamically aggregated stats for an avatar (owner only).

    Combines base stats, equipment modifiers, and active status-effect
    modifiers into a single O(1) stat snapshot.
    """
    query = select(Avatar).where(Avatar.id == avatar_id)
    if current_user.role != "admin":
        query = query.where(Avatar.user_id == current_user.id)
    result = await db.execute(query)
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
    current_user: User = Depends(get_current_user),
) -> Avatar:
    """
    Partially updates an avatar's fields (stats, HP, inventory, equipment, etc.).
    Only provided fields are written; omitted fields remain unchanged.
    Only the owner (or an admin) may modify an avatar.
    """
    query = select(Avatar).where(Avatar.id == avatar_id)
    if current_user.role != "admin":
        query = query.where(Avatar.user_id == current_user.id)
    result = await db.execute(query)
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
    current_user: User = Depends(get_current_user),
) -> None:
    """
    Removes a single named status effect from an avatar (owner only).
    Returns 404 if the avatar or the effect does not exist.
    """
    query = select(Avatar).where(Avatar.id == avatar_id)
    if current_user.role != "admin":
        query = query.where(Avatar.user_id == current_user.id)
    result = await db.execute(query)
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

