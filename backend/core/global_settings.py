"""Server-wide settings: stored once in ``ServerSettings``, managed by admins, read live.

API keys, model / image / TTS settings and the style and tone catalogs are not stored per
user. ``apply_global_settings`` copies them onto a loaded ``User`` as plain (non-column)
attributes, so every code path that reads ``user.llm_settings`` & co. sees the current server
values, and nothing can write them back into the users table.

Shared game settings and the narrator voice catalog are read from ``ServerSettings``
directly; ``User.game_settings`` holds only the player-owned keys.
"""

import copy
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.tts_preferences import with_user_scoped_settings
from backend.models.server_settings import SERVER_SETTINGS_ID, ServerSettings
from backend.models.user import User

# Anything carrying the settings fields: the server row, or a user with the overlay applied.
SettingsSource = ServerSettings | User

# Server settings laid over every loaded user.
USER_OVERLAY_FIELDS: tuple[str, ...] = (
    "encrypted_api_keys",
    "llm_settings",
    "t2i_settings",
    "tts_settings",
    "image_styles_catalog",
    "tone_catalog",
)


async def read_server_settings(db: AsyncSession) -> ServerSettings:
    """Return the settings row for reading; an unsaved empty row when none exists yet."""
    row = await db.get(ServerSettings, SERVER_SETTINGS_ID)
    return row if row is not None else ServerSettings(id=SERVER_SETTINGS_ID)


async def get_server_settings_for_update(db: AsyncSession) -> ServerSettings:
    """Return the settings row attached to the session, creating it on first write."""
    row = await db.get(ServerSettings, SERVER_SETTINGS_ID)
    if row is None:
        row = ServerSettings(id=SERVER_SETTINGS_ID)
        db.add(row)
    return row


async def apply_global_settings(db: AsyncSession, user: Optional[User]) -> Optional[User]:
    """Copy the server settings onto ``user`` (runtime attributes, never persisted)."""
    if user is None:
        return None
    server = await read_server_settings(db)
    for field in USER_OVERLAY_FIELDS:
        setattr(user, field, copy.deepcopy(getattr(server, field)))
    return user


def personal_game_settings(game_settings: Optional[dict[str, Any]]) -> dict[str, Any]:
    """Return only the player-owned keys of ``game_settings``."""
    return with_user_scoped_settings(None, game_settings)


def shared_game_settings(game_settings: Optional[dict[str, Any]]) -> dict[str, Any]:
    """Return ``game_settings`` without player-owned keys, for storing in ``ServerSettings``."""
    return with_user_scoped_settings(game_settings, None)
