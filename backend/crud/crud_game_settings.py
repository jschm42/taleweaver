"""Copy the admin's global game settings to every player without losing player-owned keys."""

from typing import Any, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.tts_preferences import USER_SCOPED_GAME_SETTING_KEYS, with_user_scoped_settings
from backend.models.user import User


async def broadcast_game_settings(db: AsyncSession, shared: Optional[dict[str, Any]]) -> None:
    """Write ``shared`` into every user's game_settings, keeping their personal keys.

    Users without personal keys get one bulk update; only the rest are merged row by row.
    """
    rows = (await db.execute(select(User.id, User.game_settings))).all()
    personal_by_id = {
        user_id: settings
        for user_id, settings in rows
        if any(key in (settings or {}) for key in USER_SCOPED_GAME_SETTING_KEYS)
    }
    await db.execute(
        update(User)
        .where(User.id.not_in(list(personal_by_id)))
        .values(game_settings=with_user_scoped_settings(shared, None))
    )
    for user_id, personal in personal_by_id.items():
        await db.execute(
            update(User)
            .where(User.id == user_id)
            .values(game_settings=with_user_scoped_settings(shared, personal))
        )
