"""Read model for the player profile: account data and aggregated stats.

The paged session history lives in ``crud_player_sessions``.
"""

from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.tts_preferences import resolve_tts_preferences
from backend.models.avatar import Avatar
from backend.models.game_session import GameSession
from backend.models.user import User


def normalize_public_data_url(url: Optional[str]) -> Optional[str]:
    """Heal legacy malformed media URLs such as /data/data/users/..."""
    if not url:
        return url
    normalized = url.replace("\\", "/")
    while normalized.startswith("/data/data/"):
        normalized = normalized.replace("/data/data/", "/data/", 1)
    return normalized


async def _session_xp_by_id(db: AsyncSession, user_id: str) -> dict[str, int]:
    rows = await db.execute(
        select(GameSession.id, Avatar.exp)
        .join(Avatar, GameSession.avatar_id == Avatar.id)
        .where(GameSession.user_id == user_id)
    )
    return {session_id: exp or 0 for session_id, exp in rows.all()}


async def build_user_profile_data(db: AsyncSession, user: User) -> dict[str, Any]:
    """Assemble the payload for UserResponse including aggregated stats."""
    adventure_count = (
        await db.execute(
            # Sessions of deleted templates (NULL template_id) still count individually.
            select(
                func.count(func.distinct(func.coalesce(GameSession.template_id, GameSession.id)))
            ).where(GameSession.user_id == user.id)
        )
    ).scalar() or 0
    total_xp = (
        await db.execute(select(func.sum(Avatar.exp)).where(Avatar.user_id == user.id))
    ).scalar() or 0
    session_xp = await _session_xp_by_id(db, user.id)

    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "profile_image_url": normalize_public_data_url(user.profile_image_url),
        "bio": user.bio,
        "default_language": user.default_language,
        "earned_awards": user.earned_awards or [],
        "is_admin": user.role == "admin",
        "adventure_count": adventure_count,
        "total_xp": total_xp,
        "game_log": [
            {**entry, "xp": session_xp.get(entry.get("session_id"), 0)}
            for entry in (user.game_log or [])
        ],
        "has_imported_defaults": user.has_imported_defaults,
        "recovery_codes_remaining": user.recovery_codes_remaining,
        "tts_preferences": resolve_tts_preferences(user.game_settings),
    }
