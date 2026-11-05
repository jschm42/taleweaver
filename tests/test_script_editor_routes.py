"""Script editor read endpoints: list all scripts and load a single script."""

import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app
from backend.models.user import User
from tests.conftest import TestSessionLocal
from tests.test_ai_fix_endpoint import _auth_headers
from tests.test_world_builder_instruct import _seed_user_with_adventure


@pytest.fixture
async def client():
    app.dependency_overrides.clear()
    from backend.core.database import get_db
    from tests.conftest import override_get_db

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


async def _seed_plain_user(username: str) -> None:
    async with TestSessionLocal() as db:
        db.add(User(username=username, hashed_password="x", role="user"))
        await db.commit()


async def _save_script(client, tpl_id: str, username: str, script_id: str, code: str) -> None:
    resp = await client.post(
        f"/api/adventures/{tpl_id}/editor/script",
        headers=_auth_headers(username),
        json={"id": script_id, "name": script_id, "trigger": "on_turn_start", "code": code},
    )
    assert resp.status_code == 200, resp.text


async def test_list_scripts_returns_empty_list_for_new_adventure(client, setup_test_db):
    # Arrange
    tpl_id = await _seed_user_with_adventure("se_user_1")

    # Act
    resp = await client.get(
        f"/api/adventures/{tpl_id}/editor/scripts", headers=_auth_headers("se_user_1")
    )

    # Assert
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"status": "success", "scripts": []}


async def test_list_scripts_returns_saved_scripts_in_order(client, setup_test_db):
    # Arrange
    tpl_id = await _seed_user_with_adventure("se_user_2")
    await _save_script(client, tpl_id, "se_user_2", "first", "x = 1")
    await _save_script(client, tpl_id, "se_user_2", "second", "y = 2")

    # Act
    resp = await client.get(
        f"/api/adventures/{tpl_id}/editor/scripts", headers=_auth_headers("se_user_2")
    )

    # Assert
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["status"] == "success"
    assert [s["id"] for s in payload["scripts"]] == ["first", "second"]
    assert payload["scripts"][1]["code"] == "y = 2"


async def test_get_script_returns_the_saved_script(client, setup_test_db):
    # Arrange
    tpl_id = await _seed_user_with_adventure("se_user_3")
    await _save_script(client, tpl_id, "se_user_3", "door_logic", "tw.exits.unlock('DOOR')")

    # Act
    resp = await client.get(
        f"/api/adventures/{tpl_id}/editor/script/door_logic", headers=_auth_headers("se_user_3")
    )

    # Assert
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["status"] == "success"
    assert payload["script"]["id"] == "door_logic"
    assert payload["script"]["code"] == "tw.exits.unlock('DOOR')"
    assert payload["script"]["trigger"] == "on_turn_start"


async def test_get_script_returns_404_for_unknown_id(client, setup_test_db):
    # Arrange
    tpl_id = await _seed_user_with_adventure("se_user_4")

    # Act
    resp = await client.get(
        f"/api/adventures/{tpl_id}/editor/script/missing", headers=_auth_headers("se_user_4")
    )

    # Assert
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Script not found"


async def test_get_script_rejects_invalid_id(client, setup_test_db):
    # Arrange
    tpl_id = await _seed_user_with_adventure("se_user_5")

    # Act
    resp = await client.get(
        f"/api/adventures/{tpl_id}/editor/script/bad%20id", headers=_auth_headers("se_user_5")
    )

    # Assert
    assert resp.status_code == 400


async def test_scripts_are_hidden_from_other_users(client, setup_test_db):
    # Arrange
    tpl_id = await _seed_user_with_adventure("se_owner")
    await _save_script(client, tpl_id, "se_owner", "secret", "x = 1")
    await _seed_plain_user("se_intruder")

    # Act
    list_resp = await client.get(
        f"/api/adventures/{tpl_id}/editor/scripts", headers=_auth_headers("se_intruder")
    )
    get_resp = await client.get(
        f"/api/adventures/{tpl_id}/editor/script/secret", headers=_auth_headers("se_intruder")
    )

    # Assert
    assert list_resp.status_code == 404
    assert get_resp.status_code == 404


async def test_endpoints_require_authentication(client, setup_test_db):
    # Arrange
    tpl_id = await _seed_user_with_adventure("se_user_6")

    # Act
    list_resp = await client.get(f"/api/adventures/{tpl_id}/editor/scripts")
    get_resp = await client.get(f"/api/adventures/{tpl_id}/editor/script/any")

    # Assert
    assert list_resp.status_code == 401
    assert get_resp.status_code == 401
