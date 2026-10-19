import asyncio
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.core.database import get_db
from backend.models.user import User

# PBKDF2-HMAC-SHA256 with explicit iteration count above OWASP 2023 guidance
# (PBKDF2-HMAC-SHA256: 600_000 iterations).
_PBKDF2_ITERATIONS = 600_000
pwd_context = CryptContext(
    schemes=["pbkdf2_sha256"],
    deprecated="auto",
    pbkdf2_sha256__rounds=_PBKDF2_ITERATIONS,
)

# Use a strong secret key from settings
SECRET_KEY = getattr(settings, "SECRET_KEY", None)
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY must be configured in settings.")
ALGORITHM = "HS256"
# Reduced from 7 days to 24 hours. A refresh-token flow can be layered on
# top of this in a follow-up; the access-token expiry alone is the primary
# blast-radius control.
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# Password strength requirements
MIN_PASSWORD_LENGTH = 10
_PASSWORD_STRENGTH_RE = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).+$")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")

# Verified against when the username does not exist, so the response time does
# not reveal which usernames are registered.
_DUMMY_PASSWORD_HASH = pwd_context.hash("taleweaver-dummy-password")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


async def averify_password(plain_password: str, hashed_password: Optional[str]) -> bool:
    """Verify off the event loop (600k PBKDF2 rounds take hundreds of milliseconds)."""
    target_hash = hashed_password or _DUMMY_PASSWORD_HASH
    is_valid = await asyncio.to_thread(pwd_context.verify, plain_password, target_hash)
    return is_valid and hashed_password is not None


async def aget_password_hash(password: str) -> str:
    return await asyncio.to_thread(pwd_context.hash, password)


def validate_password_strength(password: str) -> None:
    """Enforce length + complexity requirements.

    Raises ValueError when the password does not satisfy policy.
    """
    if not isinstance(password, str):
        raise ValueError("Password must be a string.")

    # Allow relaxed password policy for local development if explicitly configured
    if not getattr(settings, "STRICT_PASSWORD_POLICY", True):
        if len(password) < 4:
            raise ValueError("Password must be at least 4 characters long.")
        return

    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters long.")
    if not _PASSWORD_STRENGTH_RE.fullmatch(password):
        raise ValueError(
            "Password must contain at least one lowercase letter, one uppercase "
            "letter, one digit, and one special character."
        )


USERNAME_MIN_LENGTH = 3
USERNAME_MAX_LENGTH = 50
_USERNAME_RE = re.compile(r"^[\w][\w .\-]*$")


def validate_username(username: str) -> str:
    """Return the trimmed username or raise ValueError when it violates policy."""
    candidate = (username or "").strip()
    if not USERNAME_MIN_LENGTH <= len(candidate) <= USERNAME_MAX_LENGTH:
        raise ValueError(
            f"Username must be between {USERNAME_MIN_LENGTH} and {USERNAME_MAX_LENGTH} characters."
        )
    if not _USERNAME_RE.fullmatch(candidate):
        raise ValueError(
            "Username may only contain letters, digits, spaces, dots, dashes and underscores."
        )
    return candidate


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_user_access_token(user: User) -> str:
    """Issue a token bound to the user id and current token version.

    The ``uid`` claim stops a token from authenticating a different account that
    later takes over a renamed username; ``ver`` revokes tokens issued before
    the last password change or reset.
    """
    return create_access_token(
        data={"sub": user.username, "uid": user.id, "ver": user.token_version or 0},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def _token_matches_user(payload: dict, user: User) -> bool:
    token_uid = payload.get("uid")
    if token_uid is not None and token_uid != user.id:
        return False
    token_version = payload.get("ver")
    return token_version is None or token_version == (user.token_version or 0)


async def get_current_user(
    token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except jwt.PyJWTError as exc:
        raise credentials_exception from exc

    result = await db.execute(select(User).filter(User.username == username))
    user = result.scalars().first()
    if user is None or not _token_matches_user(payload, user):
        raise credentials_exception
    return user


async def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
    return current_user
