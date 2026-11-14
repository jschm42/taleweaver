"""Account checks shared by self-registration and admin user management.

Usernames and e-mail addresses are unique case-insensitively, and administration must never
be locked out by demoting or deactivating the last active admin.
"""

from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.user import User


async def ensure_username_available(
    db: AsyncSession, username: str, exclude_user_id: Optional[str] = None
) -> None:
    """Raise 400 when another account already uses ``username`` (ignoring case)."""
    query = select(User.id).where(func.lower(User.username) == username.lower())
    if exclude_user_id:
        query = query.where(User.id != exclude_user_id)
    taken = await db.execute(query.limit(1))
    if taken.first() is not None:
        raise HTTPException(status_code=400, detail="Username already registered")


async def ensure_email_available(
    db: AsyncSession, email: str, exclude_user_id: Optional[str] = None
) -> None:
    """Raise 400 when another account already uses ``email`` (ignoring case)."""
    query = select(User.id).where(func.lower(User.email) == email.lower())
    if exclude_user_id:
        query = query.where(User.id != exclude_user_id)
    taken = await db.execute(query.limit(1))
    if taken.first() is not None:
        raise HTTPException(status_code=400, detail="Email already registered")


async def _other_active_admin_exists(db: AsyncSession, user: User) -> bool:
    other_admins = await db.execute(
        select(User.id)
        .where(User.role == "admin", User.is_active.is_(True), User.id != user.id)
        .limit(1)
    )
    return other_admins.first() is not None


async def ensure_admin_remains(db: AsyncSession, user: User, new_role: str, admin: User) -> None:
    """Block demotions that would lock everyone out of administration."""
    if user.role != "admin" or new_role == "admin":
        return
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="You cannot remove your own admin role.")
    if not await _other_active_admin_exists(db, user):
        raise HTTPException(status_code=400, detail="At least one administrator must remain.")


async def ensure_active_admin_remains(db: AsyncSession, user: User, admin: User) -> None:
    """Block deactivations that would lock everyone out of administration."""
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="You cannot deactivate your own account.")
    if user.role != "admin" or not user.is_active:
        return
    if not await _other_active_admin_exists(db, user):
        raise HTTPException(
            status_code=400, detail="At least one active administrator must remain."
        )
