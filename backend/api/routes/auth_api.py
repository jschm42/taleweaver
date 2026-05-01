from typing import List, Optional
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.core.database import get_db
from backend.core.auth import create_access_token, get_current_user, ACCESS_TOKEN_EXPIRE_MINUTES, get_password_hash
from backend.models.user import User
from pydantic import BaseModel

router = APIRouter()

class Token(BaseModel):
    access_token: str
    token_type: str

class UserResponse(BaseModel):
    id: str
    username: str
    role: str
    profile_image_url: Optional[str] = None
    bio: Optional[str] = None
    default_language: Optional[str] = None
    earned_awards: Optional[list] = None
    is_admin: bool = False
    game_log: Optional[list] = None

class SetupRootRequest(BaseModel):
    username: str
    password: str


class BootstrapStatusResponse(BaseModel):
    has_admin: bool
    has_users: bool

@router.post("/auth/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Login attempt for username: '{form_data.username}'")
    
    result = await db.execute(select(User).filter(User.username == form_data.username))
    user = result.scalars().first()
    
    from backend.core.auth import verify_password
    if not user or not verify_password(form_data.password, user.hashed_password):
        if user:
            logger.warning(f"Invalid password for user '{form_data.username}'")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/auth/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from backend.models.game_session import GameSession
    
    # Count unique adventures played by this user
    result = await db.execute(
        select(func.count(GameSession.template_id.distinct()))
        .where(GameSession.user_id == current_user.id)
    )
    adventure_count = result.scalar() or 0
    
    # We convert the ORM object to a dict and add the extra field
    user_data = {
        "id": current_user.id,
        "username": current_user.username,
        "role": current_user.role,
        "profile_image_url": current_user.profile_image_url,
        "bio": current_user.bio,
        "default_language": current_user.default_language,
        "earned_awards": current_user.earned_awards or [],
        "adventure_count": adventure_count,
        "game_log": current_user.game_log or []
    }
    return user_data

@router.post("/auth/setup-root")
async def setup_root_admin(request: SetupRootRequest, db: AsyncSession = Depends(get_db)):
    # Check if any ADMIN exists
    result = await db.execute(select(User).filter(User.role == "admin").limit(1))
    if result.scalars().first() is not None:
        raise HTTPException(status_code=400, detail="A root administrator already exists.")
    
    hashed_password = get_password_hash(request.password)
    new_admin = User(
        username=request.username,
        hashed_password=hashed_password,
        role="admin"
    )
    db.add(new_admin)
    await db.commit()
    await db.refresh(new_admin)
    return {"message": "Root admin created successfully"}


@router.get("/auth/bootstrap-status", response_model=BootstrapStatusResponse)
async def get_bootstrap_status(db: AsyncSession = Depends(get_db)):
    """Public bootstrap status used by frontend to choose setup vs login."""
    admin_result = await db.execute(select(User).filter(User.role == "admin").limit(1))
    user_result = await db.execute(select(User.id).limit(1))
    return BootstrapStatusResponse(
        has_admin=admin_result.scalars().first() is not None,
        has_users=user_result.first() is not None,
    )
