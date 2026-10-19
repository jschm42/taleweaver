"""Self-service account endpoints: credentials, recovery codes, preferences, session history."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.auth_api import UserResponse
from backend.core.account_recovery import issue_recovery_codes, set_new_password
from backend.core.auth import (
    averify_password,
    create_user_access_token,
    get_current_user,
    validate_password_strength,
    validate_username,
)
from backend.core.database import get_db
from backend.crud.crud_profile import (
    PlayerSessionSummary,
    build_user_profile_data,
    list_player_sessions,
)
from backend.models.user import User

router = APIRouter(prefix="/users/me", tags=["Account"])
logger = logging.getLogger(__name__)

USER_DEP = Depends(get_current_user)
DB_DEP = Depends(get_db)


class UserCredentialsUpdateRequest(BaseModel):
    current_password: str
    username: Optional[str] = None
    password: Optional[str] = None


class UserCredentialsUpdateResponse(BaseModel):
    user: UserResponse
    access_token: Optional[str] = None
    token_type: Optional[str] = None


class CurrentPasswordRequest(BaseModel):
    current_password: str


class RecoveryCodesResponse(BaseModel):
    codes: list[str]


class PreferencesUpdateRequest(BaseModel):
    default_language: Optional[str] = Field(default=None, max_length=20)


async def _require_current_password(user: User, current_password: str) -> None:
    if not await averify_password(current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect current password.")


async def _apply_username_change(db: AsyncSession, user: User, requested: str) -> bool:
    """Validate and apply a new username. Returns True when it actually changed."""
    try:
        new_username = validate_username(requested)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if new_username == user.username:
        return False
    taken = await db.execute(select(User.id).where(User.username == new_username))
    if taken.first() is not None:
        raise HTTPException(status_code=400, detail="This username is already taken.")
    user.username = new_username
    return True


async def _apply_password_change(user: User, current_password: str, new_password: str) -> None:
    if new_password == current_password:
        raise HTTPException(
            status_code=400, detail="The new password must differ from the current one."
        )
    try:
        validate_password_strength(new_password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    # Revokes every other session; the caller receives a fresh token below.
    await set_new_password(user, new_password)


@router.put("/credentials", response_model=UserCredentialsUpdateResponse)
async def update_my_credentials(
    request: UserCredentialsUpdateRequest,
    current_user: User = USER_DEP,
    db: AsyncSession = DB_DEP,
):
    """
    Update the user's own username and/or password.
    Requires the current password to verify identity.
    """
    await _require_current_password(current_user, request.current_password)
    if request.username is None and request.password is None:
        raise HTTPException(
            status_code=400, detail="You must provide a new username or a new password."
        )

    changed = False
    if request.username is not None:
        changed = await _apply_username_change(db, current_user, request.username)
    if request.password is not None:
        await _apply_password_change(current_user, request.current_password, request.password)
        changed = True

    await db.commit()
    await db.refresh(current_user)

    access_token = create_user_access_token(current_user) if changed else None
    return UserCredentialsUpdateResponse(
        user=UserResponse(**await build_user_profile_data(db, current_user)),
        access_token=access_token,
        token_type="bearer" if access_token else None,
    )


@router.post("/recovery-codes", response_model=RecoveryCodesResponse)
async def regenerate_my_recovery_codes(
    request: CurrentPasswordRequest,
    current_user: User = USER_DEP,
    db: AsyncSession = DB_DEP,
):
    """Create a fresh set of one-time recovery codes (invalidates the previous set)."""
    await _require_current_password(current_user, request.current_password)
    codes = issue_recovery_codes(current_user)
    await db.commit()
    logger.info("Issued new recovery codes for user %s", current_user.id)
    return RecoveryCodesResponse(codes=codes)


@router.put("/preferences", response_model=UserResponse)
async def update_my_preferences(
    request: PreferencesUpdateRequest,
    current_user: User = USER_DEP,
    db: AsyncSession = DB_DEP,
):
    """Players may update their own preferences (the generic user update is admin-only)."""
    current_user.default_language = (request.default_language or "").strip() or None
    await db.commit()
    await db.refresh(current_user)
    return await build_user_profile_data(db, current_user)


@router.get("/sessions", response_model=list[PlayerSessionSummary])
async def list_my_sessions(current_user: User = USER_DEP, db: AsyncSession = DB_DEP):
    """Adventure history for the profile page: status, XP and sequence progress."""
    return await list_player_sessions(db, current_user)
