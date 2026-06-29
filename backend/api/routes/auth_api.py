from typing import Optional, Union
from datetime import timedelta
import ipaddress
import time
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    get_current_user,
    get_password_hash,
    validate_password_strength,
)
from backend.core.database import get_db
from backend.core.config import settings
from backend.models.user import User

router = APIRouter()

# Simple in-memory rate limiting for auth
_login_attempts = defaultdict(list)
LOGIN_RATE_LIMIT = 5 # attempts
LOGIN_WINDOW = 60 # seconds

# Simple in-memory rate limiting for setup-root bootstrap
_setup_root_attempts = defaultdict(list)
SETUP_ROOT_RATE_LIMIT = 3  # attempts
SETUP_ROOT_WINDOW = 3600  # seconds (1 hour)

# IPs allowed to invoke the unauthenticated /setup-root bootstrap endpoint.
_SETUP_ROOT_ALLOWED_IPS = {"127.0.0.1", "::1", "::ffff:127.0.0.1", "localhost"}


def _client_ip_in_setup_allowlist(request: Request) -> bool:
    """Return True if the request originates from a loopback address.

    The setup-root bootstrap endpoint is only reachable from the local host
    unless the operator explicitly opts-in via ``ALLOW_REMOTE_SETUP=true``.
    """
    if settings.ALLOW_REMOTE_SETUP:
        return True
    client_host = request.client.host if request.client else ""
    if not client_host:
        return False
    try:
        ip = ipaddress.ip_address(client_host)
        return ip.is_loopback
    except ValueError:
        return client_host in _SETUP_ROOT_ALLOWED_IPS


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
    has_imported_defaults: bool = False
    adventure_count: Optional[int] = 0
    total_xp: Optional[int] = 0

class SetupRootRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=10, max_length=256)


class BootstrapStatusResponse(BaseModel):
    has_admin: bool
    has_users: bool
    app_version: str

@router.post("/auth/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    import logging
    logger = logging.getLogger(__name__)
    
    # Simple Rate Limiting
    now = time.time()
    client_id = form_data.username 
    _login_attempts[client_id] = [t for t in _login_attempts[client_id] if now - t < LOGIN_WINDOW]
    if len(_login_attempts[client_id]) >= LOGIN_RATE_LIMIT:
        logger.warning(f"Rate limit exceeded for user: {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later."
        )
    _login_attempts[client_id].append(now)

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
async def read_users_me(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    import os

    from backend.engine.adventure_importer import AdventureTemplateImporter
    from backend.models.game_session import GameSession
    from backend.models.avatar import Avatar
    from sqlalchemy import func
    
    # 1. Trigger background import of defaults if never done
    if not current_user.has_imported_defaults:
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"First login for user '{current_user.username}'. Importing default adventures...")
        
        defaults_dir = os.path.join("adventures", "default")
        try:
            await AdventureTemplateImporter.import_from_directory(db, defaults_dir, owner_id=current_user.id, delete_after=False)
            current_user.has_imported_defaults = True
            await db.commit()
        except Exception as e:
            logger.error(f"Failed to auto-import defaults for {current_user.username}: {e}")

    # Count unique adventures played by this user
    result = await db.execute(
        select(GameSession.template_id)
        .where(GameSession.user_id == current_user.id)
        .distinct()
    )
    adventure_count = len(result.scalars().all())

    # Calculate total XP across all user's avatars
    xp_res = await db.execute(
        select(func.sum(Avatar.exp)).where(Avatar.user_id == current_user.id)
    )
    total_xp = xp_res.scalar() or 0

    # Query game sessions to get the XP for completed/game-over games
    sessions_query = await db.execute(
        select(GameSession.id, Avatar.exp)
        .join(Avatar, GameSession.avatar_id == Avatar.id)
        .where(GameSession.user_id == current_user.id)
    )
    session_xp_map = {row[0]: row[1] for row in sessions_query.all()}

    # Enrich game log with XP
    enriched_game_log = []
    for entry in (current_user.game_log or []):
        s_id = entry.get("session_id")
        xp_val = session_xp_map.get(s_id, 0)
        enriched_game_log.append({
            **entry,
            "xp": xp_val
        })

    # Auto-heal legacy malformed media URL values like /data/data/users/...
    profile_image_url = current_user.profile_image_url
    if profile_image_url:
        normalized_profile_image_url = profile_image_url.replace("\\", "/")
        while normalized_profile_image_url.startswith("/data/data/"):
            normalized_profile_image_url = normalized_profile_image_url.replace("/data/data/", "/data/", 1)
        if normalized_profile_image_url != profile_image_url:
            current_user.profile_image_url = normalized_profile_image_url
            await db.commit()
            profile_image_url = normalized_profile_image_url
    
    # We convert the ORM object to a dict and add the extra field
    user_data = {
        "id": current_user.id,
        "username": current_user.username,
        "role": current_user.role,
        "profile_image_url": profile_image_url,
        "bio": current_user.bio,
        "default_language": current_user.default_language,
        "earned_awards": current_user.earned_awards or [],
        "is_admin": current_user.role == "admin",
        "adventure_count": adventure_count,
        "total_xp": total_xp,
        "game_log": enriched_game_log,
        "has_imported_defaults": current_user.has_imported_defaults
    }
    return user_data

@router.post("/auth/setup-root")
async def setup_root_admin(
    http_request: Request,
    request: SetupRootRequest,
    db: AsyncSession = Depends(get_db),
):
    """Bootstrap the first root admin.

    This endpoint is **only** reachable from loopback addresses unless the
    operator has explicitly set ``ALLOW_REMOTE_SETUP=true`` in the environment.
    It also enforces strict rate limiting and password-strength requirements.
    """
    client_ip = http_request.client.host if http_request.client else "unknown"
    now = time.time()
    attempts = [t for t in _setup_root_attempts[client_ip] if now - t < SETUP_ROOT_WINDOW]
    _setup_root_attempts[client_ip] = attempts
    if len(attempts) >= SETUP_ROOT_RATE_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many setup attempts from this IP. Try again later.",
        )

    if not _client_ip_in_setup_allowlist(http_request):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Setup is only allowed from the local host. Set ALLOW_REMOTE_SETUP=true to override.",
        )

    # Check if any ADMIN exists
    result = await db.execute(select(User).filter(User.role == "admin").limit(1))
    if result.scalars().first() is not None:
        raise HTTPException(status_code=400, detail="A root administrator already exists.")

    try:
        validate_password_strength(request.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    _setup_root_attempts[client_ip].append(now)

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
        app_version=settings.APP_VERSION,
    )
