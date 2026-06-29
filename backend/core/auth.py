from datetime import datetime, timedelta, timezone
import re
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
_PASSWORD_STRENGTH_RE = re.compile(
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).+$"
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def validate_password_strength(password: str) -> None:
    """Enforce length + complexity requirements.

    Raises ValueError when the password does not satisfy policy.
    """
    if not isinstance(password, str):
        raise ValueError("Password must be a string.")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters long."
        )
    if not _PASSWORD_STRENGTH_RE.fullmatch(password):
        raise ValueError(
            "Password must contain at least one lowercase letter, one uppercase "
            "letter, one digit, and one special character."
        )

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)) -> User:
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
    except jwt.PyJWTError:
        raise credentials_exception

    result = await db.execute(select(User).filter(User.username == username))
    user = result.scalars().first()
    if user is None:
        raise credentials_exception
    return user

async def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user
