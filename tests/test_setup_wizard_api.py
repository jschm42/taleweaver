"""Setup wizard state endpoints: per-user, open to every user, merged partial updates."""

import pytest

from backend.core.auth import create_access_token, get_password_hash
from backend.models.user import User
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio

URL = "/api/settings/setup-wizard"


async def test_new_admin_starts_pending(auth_client):
    # Act
    response = await auth_client.get(URL)

    # Assert
    assert response.status_code == 200
    assert response.json() == {"state": "pending", "visuals_opt_out": False}


async def test_update_merges_fields(auth_client):
    # Arrange
    await auth_client.put(URL, json={"visuals_opt_out": True})

    # Act
    response = await auth_client.put(URL, json={"state": "dismissed"})

    # Assert
    assert response.status_code == 200
    assert response.json() == {"state": "dismissed", "visuals_opt_out": True}
    assert (await auth_client.get(URL)).json()["state"] == "dismissed"


async def test_rejects_unknown_state(auth_client):
    # Act
    response = await auth_client.put(URL, json={"state": "maybe"})

    # Assert
    assert response.status_code == 422


async def test_regular_user_has_own_state(client, auth_client):
    # Arrange
    async with TestSessionLocal() as session:
        session.add(User(username="player", hashed_password=get_password_hash("pw"), role="user"))
        await session.commit()
    player_headers = {"Authorization": f"Bearer {create_access_token({'sub': 'player'})}"}

    await auth_client.put(URL, json={"state": "dismissed"})

    # Act
    response = await client.put(URL, json={"state": "skipped"}, headers=player_headers)

    # Assert
    assert response.status_code == 200
    assert response.json()["state"] == "skipped"
    assert (await auth_client.get(URL)).json()["state"] == "dismissed"
