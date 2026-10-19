import ipaddress
import logging
import os
import time
from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.account_recovery import (
    consume_recovery_code,
    find_user_by_reset_token,
    set_new_password,
)
from backend.core.auth import (
    MIN_PASSWORD_LENGTH,
    aget_password_hash,
    averify_password,
    create_user_access_token,
    get_current_user,
    validate_password_strength,
)
from backend.core.config import settings
from backend.core.database import get_db
from backend.core.login_throttle import login_throttle, recovery_throttle
from backend.crud.crud_profile import build_user_profile_data
from backend.models.user import User

router = APIRouter()
logger = logging.getLogger(__name__)

# Simple in-memory rate limiting for setup-root bootstrap
_setup_root_attempts = defaultdict(list)
SETUP_ROOT_RATE_LIMIT = 3  # attempts
SETUP_ROOT_WINDOW = 3600  # seconds (1 hour)

# IPs allowed to invoke the unauthenticated /setup-root bootstrap endpoint.
_SETUP_ROOT_ALLOWED_IPS = {"127.0.0.1", "::1", "::ffff:127.0.0.1", "localhost"}


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


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


def _validate_new_password(password: str) -> None:
    try:
        validate_password_strength(password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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
    recovery_codes_remaining: int = 0


class SetupRootRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=10, max_length=256)


class PasswordPolicy(BaseModel):
    min_length: int
    requires_complexity: bool


class BootstrapStatusResponse(BaseModel):
    has_admin: bool
    has_users: bool
    app_version: str
    password_policy: PasswordPolicy


class RecoveryCodeResetRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    recovery_code: str = Field(min_length=1, max_length=64)
    new_password: str = Field(min_length=1, max_length=256)


class ResetTokenRequest(BaseModel):
    token: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=1, max_length=256)


def _password_policy() -> PasswordPolicy:
    strict = bool(getattr(settings, "STRICT_PASSWORD_POLICY", True))
    return PasswordPolicy(
        min_length=MIN_PASSWORD_LENGTH if strict else 4, requires_complexity=strict
    )


@router.post("/auth/token", response_model=Token)
async def login_for_access_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    client_ip = _client_ip(request)
    if login_throttle.is_blocked(client_ip, form_data.username):
        logger.warning("Login throttled for username %r from %s", form_data.username, client_ip)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later.",
        )

    result = await db.execute(select(User).filter(User.username == form_data.username))
    user = result.scalars().first()

    # Always run a hash verification so response time does not reveal unknown usernames.
    password_ok = await averify_password(form_data.password, user.hashed_password if user else None)
    if not user or not password_ok:
        login_throttle.record_failure(client_ip, form_data.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    login_throttle.reset(client_ip, form_data.username)
    return {"access_token": create_user_access_token(user), "token_type": "bearer"}


@router.post("/auth/recover", response_model=Token)
async def reset_password_with_recovery_code(
    payload: RecoveryCodeResetRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Set a new password using one of the user's one-time recovery codes."""
    client_ip = _client_ip(request)
    if recovery_throttle.is_blocked(client_ip, payload.username):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many recovery attempts. Please try again later.",
        )
    _validate_new_password(payload.new_password)

    result = await db.execute(select(User).filter(User.username == payload.username.strip()))
    user = result.scalars().first()
    if user is None or not consume_recovery_code(user, payload.recovery_code):
        recovery_throttle.record_failure(client_ip, payload.username)
        raise HTTPException(status_code=400, detail="Invalid username or recovery code.")

    await set_new_password(user, payload.new_password)
    await db.commit()
    recovery_throttle.reset(client_ip, payload.username)
    logger.info("Password reset via recovery code for user %s", user.id)
    return {"access_token": create_user_access_token(user), "token_type": "bearer"}


@router.post("/auth/reset-password", response_model=Token)
async def reset_password_with_token(
    payload: ResetTokenRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Set a new password using an admin-issued one-time reset link."""
    client_ip = _client_ip(request)
    if recovery_throttle.is_blocked(client_ip, "reset-token"):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many reset attempts. Please try again later.",
        )
    _validate_new_password(payload.new_password)

    user = await find_user_by_reset_token(db, payload.token)
    if user is None:
        recovery_throttle.record_failure(client_ip, "reset-token")
        raise HTTPException(status_code=400, detail="This reset link is invalid or has expired.")

    await set_new_password(user, payload.new_password)
    await db.commit()
    logger.info("Password reset via admin reset link for user %s", user.id)
    return {"access_token": create_user_access_token(user), "token_type": "bearer"}


@router.get("/auth/me", response_model=UserResponse)
async def read_users_me(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from backend.engine.adventure_importer import AdventureTemplateImporter

    # Import default adventures on first login.
    if not current_user.has_imported_defaults:
        logger.info(
            "First login for user '%s'. Importing default adventures...", current_user.username
        )
        defaults_dir = os.path.join("adventures", "default")
        try:
            await AdventureTemplateImporter.import_from_directory(
                db, defaults_dir, owner_id=current_user.id, delete_after=False
            )
            current_user.has_imported_defaults = True
            await db.commit()
        except Exception as e:
            logger.error("Failed to auto-import defaults for %s: %s", current_user.username, e)

    profile = await build_user_profile_data(db, current_user)
    # Persist the healed profile image URL so the fix is applied only once.
    if profile["profile_image_url"] != current_user.profile_image_url:
        current_user.profile_image_url = profile["profile_image_url"]
        await db.commit()
    return profile


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
    client_ip = _client_ip(http_request)
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

    _validate_new_password(request.password)
    _setup_root_attempts[client_ip].append(now)

    new_admin = User(
        username=request.username.strip(),
        hashed_password=await aget_password_hash(request.password),
        role="admin",
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
        password_policy=_password_policy(),
    )
