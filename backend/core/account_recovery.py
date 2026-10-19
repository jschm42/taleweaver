"""One-time recovery codes and admin-issued password reset tokens.

Both secrets are high-entropy random values, so a fast SHA-256 digest is a
sufficient at-rest protection (unlike user-chosen passwords). Plaintext values
are only ever returned once, at creation time.
"""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.auth import aget_password_hash
from backend.models.user import User

RECOVERY_CODE_COUNT = 10
RECOVERY_CODE_GROUP_LENGTH = 5
# Crockford-style alphabet without easily confused characters (0/O, 1/I/L).
_RECOVERY_ALPHABET = "23456789ABCDEFGHJKMNPQRSTVWXYZ"
RESET_TOKEN_TTL = timedelta(hours=24)


def _digest(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def normalize_recovery_code(code: str) -> str:
    """Accept codes regardless of case, spaces, or dashes."""
    return "".join(ch for ch in (code or "").upper() if ch.isalnum())


def _random_recovery_code() -> str:
    groups = [
        "".join(secrets.choice(_RECOVERY_ALPHABET) for _ in range(RECOVERY_CODE_GROUP_LENGTH))
        for _ in range(2)
    ]
    return "-".join(groups)


def issue_recovery_codes(user: User) -> list[str]:
    """Replace the user's recovery codes and return the new plaintext codes."""
    codes = [_random_recovery_code() for _ in range(RECOVERY_CODE_COUNT)]
    user.recovery_code_hashes = [_digest(normalize_recovery_code(code)) for code in codes]
    return codes


def consume_recovery_code(user: User, code: str) -> bool:
    """Remove the matching code from the user and report whether one matched."""
    candidate = _digest(normalize_recovery_code(code))
    remaining = list(user.recovery_code_hashes or [])
    match = next((h for h in remaining if hmac.compare_digest(h, candidate)), None)
    if match is None:
        return False
    remaining.remove(match)
    # Reassign so SQLAlchemy detects the JSON change.
    user.recovery_code_hashes = remaining
    return True


def issue_password_reset_token(user: User) -> str:
    token = secrets.token_urlsafe(32)
    user.password_reset_token_hash = _digest(token)
    user.password_reset_expires_at = datetime.now(timezone.utc) + RESET_TOKEN_TTL
    return token


async def find_user_by_reset_token(db: AsyncSession, token: str) -> Optional[User]:
    if not token:
        return None
    result = await db.execute(select(User).where(User.password_reset_token_hash == _digest(token)))
    user = result.scalars().first()
    if user is None or user.password_reset_expires_at is None:
        return None
    expires_at = user.password_reset_expires_at
    if expires_at.tzinfo is None:
        # SQLite drops tz info; values are always written in UTC.
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        return None
    return user


async def set_new_password(user: User, new_password: str) -> None:
    """Store a new password, revoke all existing tokens, and clear any reset link."""
    user.hashed_password = await aget_password_hash(new_password)
    user.token_version = (user.token_version or 0) + 1
    user.password_reset_token_hash = None
    user.password_reset_expires_at = None
