"""Seed the server-wide settings row (``ServerSettings``) in tests."""

from typing import Any

from backend.models.server_settings import SERVER_SETTINGS_ID, ServerSettings


async def seed_server_settings(session: Any, **fields: Any) -> ServerSettings:
    """Create or update the single settings row with ``fields``; the caller commits."""
    row = await session.get(ServerSettings, SERVER_SETTINGS_ID)
    if row is None:
        row = ServerSettings(id=SERVER_SETTINGS_ID)
        session.add(row)
    for field, value in fields.items():
        setattr(row, field, value)
    return row
