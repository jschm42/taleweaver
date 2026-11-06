"""Server-wide settings live once in ``ServerSettings``; every user reads them at runtime."""

import pytest
from sqlalchemy import select

from backend.core.auth import create_access_token, get_current_user
from backend.core.global_settings import apply_global_settings, read_server_settings
from backend.models.server_settings import SERVER_SETTINGS_ID, ServerSettings
from backend.models.user import User
from tests.conftest import TestSessionLocal
from tests.server_settings_helpers import seed_server_settings

pytestmark = pytest.mark.asyncio

SERVER_LLM = {"small_model": "gpt-4o-mini", "small_model_provider": "openai"}
SERVER_KEYS = {"openai": "encrypted-server-key"}


def _headers(username: str) -> dict:
    return {"Authorization": f"Bearer {create_access_token(data={'sub': username})}"}


async def _seed(*users: User) -> None:
    async with TestSessionLocal() as db:
        await seed_server_settings(
            db,
            encrypted_api_keys=dict(SERVER_KEYS),
            llm_settings=dict(SERVER_LLM),
            game_settings={"clock_24h": True},
        )
        db.add_all(users)
        await db.commit()


async def _server_row() -> ServerSettings:
    async with TestSessionLocal() as db:
        return await db.get(ServerSettings, SERVER_SETTINGS_ID)


async def test_every_user_reads_the_server_settings(setup_test_db):
    await _seed(
        User(username="player", hashed_password="x", role="user"),
        User(username="admin", hashed_password="x", role="admin"),
    )

    async with TestSessionLocal() as db:
        player = await get_current_user(create_access_token({"sub": "player"}), db)
        admin = await get_current_user(create_access_token({"sub": "admin"}), db)

        assert player.encrypted_api_keys == SERVER_KEYS
        assert player.llm_settings == SERVER_LLM
        assert admin.llm_settings == SERVER_LLM


async def test_overlay_is_never_written_to_the_user(setup_test_db):
    await _seed(User(username="player", hashed_password="x", role="user"))

    async with TestSessionLocal() as db:
        player = await get_current_user(create_access_token({"sub": "player"}), db)
        player.llm_settings = {"small_model": "tampered"}
        player.bio = "changed"
        await db.commit()

    async with TestSessionLocal() as db:
        player = (await db.execute(select(User).where(User.username == "player"))).scalar_one()
        assert player.bio == "changed"
        assert player.llm_settings is None
        await apply_global_settings(db, player)
        assert player.llm_settings == SERVER_LLM


async def test_overlay_survives_refresh(setup_test_db):
    await _seed(User(username="player", hashed_password="x", role="user"))

    async with TestSessionLocal() as db:
        player = await get_current_user(create_access_token({"sub": "player"}), db)
        await db.refresh(player)

        assert player.llm_settings == SERVER_LLM


async def test_admin_writes_go_to_the_server_row(client, setup_test_db):
    await _seed(User(username="admin", hashed_password="x", role="admin"))

    res = await client.post(
        "/api/settings/game",
        json={"clock_24h": False, "date_format": "YYYY-MM-DD", "whisper_model": "tiny"},
        headers=_headers("admin"),
    )

    assert res.status_code == 200
    assert (await _server_row()).game_settings["date_format"] == "YYYY-MM-DD"


async def test_settings_survive_deleting_every_former_admin(client, setup_test_db):
    await _seed(
        User(username="first_admin", hashed_password="x", role="admin"),
        User(username="second_admin", hashed_password="x", role="admin"),
    )
    async with TestSessionLocal() as db:
        first = (await db.execute(select(User).where(User.username == "first_admin"))).scalar_one()
        first_id = first.id

    res = await client.delete(f"/api/users/{first_id}", headers=_headers("second_admin"))

    assert res.status_code == 200
    assert (await _server_row()).encrypted_api_keys == SERVER_KEYS


async def test_new_user_sees_settings_saved_before_it_existed(setup_test_db):
    await _seed()

    async with TestSessionLocal() as db:
        db.add(User(username="late", hashed_password="x", role="user"))
        await db.commit()
        late = await get_current_user(create_access_token({"sub": "late"}), db)

        assert late.encrypted_api_keys == SERVER_KEYS


async def test_player_preferences_store_only_personal_keys(client, setup_test_db):
    await _seed(User(username="player", hashed_password="x", role="user"))

    res = await client.put(
        "/api/users/me/preferences",
        json={"tts_preferences": {"npcs": False}},
        headers=_headers("player"),
    )

    assert res.status_code == 200
    async with TestSessionLocal() as db:
        player = (await db.execute(select(User).where(User.username == "player"))).scalar_one()
        assert set(player.game_settings) == {"tts_preferences"}


async def test_reading_without_a_row_returns_empty_settings(setup_test_db):
    async with TestSessionLocal() as db:
        server = await read_server_settings(db)

        assert server.llm_settings is None
        assert await db.get(ServerSettings, SERVER_SETTINGS_ID) is None
