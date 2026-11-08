"""Self-registration and admin activation: pending accounts, uniqueness, last-admin guards."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from backend.core.auth import create_user_access_token, get_password_hash
from backend.core.login_throttle import login_throttle, register_throttle
from backend.models.user import User
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio

PASSWORD = "Str0ng_Passw0rd!"
REGISTER_URL = "/api/auth/register"


@pytest.fixture(autouse=True)
def _clear_throttles():
    login_throttle.clear()
    register_throttle.clear()
    yield
    login_throttle.clear()
    register_throttle.clear()


def _bearer(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_user_access_token(user)}"}


async def _register(client: AsyncClient, username: str, email: str):
    return await client.post(
        REGISTER_URL, json={"username": username, "email": email, "password": PASSWORD}
    )


async def _load_user(username: str) -> User:
    async with TestSessionLocal() as session:
        query = select(User).where(User.username == username)
        return (await session.execute(query)).scalars().one()


async def _create_user(username: str, role: str = "user", is_active: bool = True) -> User:
    async with TestSessionLocal() as session:
        user = User(
            username=username,
            hashed_password=get_password_hash(PASSWORD),
            role=role,
            is_active=is_active,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


async def test_register_creates_inactive_user(client: AsyncClient) -> None:
    # Act
    response = await _register(client, "newcomer", "newcomer@example.com")

    # Assert
    assert response.status_code == 201
    assert "pending administrator approval" in response.json()["message"]
    user = await _load_user("newcomer")
    assert user.is_active is False
    assert user.role == "user"
    assert user.email == "newcomer@example.com"
    assert user.hashed_password != PASSWORD


async def test_pending_user_cannot_log_in(client: AsyncClient) -> None:
    # Arrange
    await _register(client, "waiting", "waiting@example.com")

    # Act
    response = await client.post(
        "/api/auth/token", data={"username": "waiting", "password": PASSWORD}
    )

    # Assert
    assert response.status_code == 403
    assert response.json()["detail"] == "Account is pending administrator approval."


async def test_register_rejects_duplicates_ignoring_case(client: AsyncClient) -> None:
    # Arrange
    await _register(client, "Taken", "taken@example.com")

    # Act
    same_name = await _register(client, "taken", "other@example.com")
    same_email = await _register(client, "someone", "TAKEN@example.com")

    # Assert
    assert same_name.status_code == 400
    assert same_name.json()["detail"] == "Username already registered"
    assert same_email.status_code == 400
    assert same_email.json()["detail"] == "Email already registered"


async def test_register_validates_input(client: AsyncClient) -> None:
    # Act
    bad_email = await _register(client, "mailless", "not-an-email")
    weak_password = await client.post(
        REGISTER_URL, json={"username": "weakling", "email": "w@example.com", "password": "a"}
    )

    # Assert
    assert bad_email.status_code == 422
    assert weak_password.status_code == 400


async def test_register_is_rate_limited(client: AsyncClient) -> None:
    # Arrange
    for index in range(10):
        await _register(client, f"spam{index}", f"spam{index}@example.com")

    # Act
    response = await _register(client, "spam_final", "final@example.com")

    # Assert
    assert response.status_code == 429


async def test_admin_activates_pending_user(client: AsyncClient) -> None:
    # Arrange
    admin = await _create_user("root_admin", role="admin")
    pending = await _create_user("pending_user", is_active=False)

    # Act
    response = await client.post(f"/api/users/{pending.id}/activate", headers=_bearer(admin))
    login = await client.post(
        "/api/auth/token", data={"username": "pending_user", "password": PASSWORD}
    )

    # Assert
    assert response.status_code == 200
    assert response.json()["is_active"] is True
    assert login.status_code == 200


async def test_activate_requires_admin(client: AsyncClient) -> None:
    # Arrange
    player = await _create_user("plain_player")
    pending = await _create_user("pending_two", is_active=False)

    # Act
    response = await client.post(f"/api/users/{pending.id}/activate", headers=_bearer(player))

    # Assert
    assert response.status_code == 403


async def test_deactivated_user_token_is_rejected(client: AsyncClient) -> None:
    # Arrange
    admin = await _create_user("deact_admin", role="admin")
    player = await _create_user("deact_player")
    player_headers = _bearer(player)

    # Act
    update = await client.put(
        f"/api/users/{player.id}", json={"is_active": False}, headers=_bearer(admin)
    )
    probe = await client.get("/api/auth/me", headers=player_headers)

    # Assert
    assert update.status_code == 200
    assert update.json()["is_active"] is False
    assert probe.status_code == 401


async def test_last_active_admin_cannot_be_deactivated(client: AsyncClient) -> None:
    # Arrange
    admin = await _create_user("only_admin", role="admin")
    inactive_admin = await _create_user("idle_admin", role="admin", is_active=False)
    other = await _create_user("second_admin", role="admin")

    # Act
    own = await client.put(
        f"/api/users/{admin.id}", json={"is_active": False}, headers=_bearer(admin)
    )
    first = await client.put(
        f"/api/users/{other.id}", json={"is_active": False}, headers=_bearer(admin)
    )
    demote_last = await client.put(
        f"/api/users/{inactive_admin.id}", json={"role": "user"}, headers=_bearer(admin)
    )

    # Assert
    assert own.status_code == 400
    assert first.status_code == 200
    assert demote_last.status_code == 200


async def test_admin_sets_unique_email(client: AsyncClient) -> None:
    # Arrange
    admin = await _create_user("mail_admin", role="admin")
    created = await client.post(
        "/api/users",
        json={"username": "mail_user", "password": PASSWORD, "email": "Mail@example.com"},
        headers=_bearer(admin),
    )

    # Act
    duplicate = await client.put(
        f"/api/users/{admin.id}", json={"email": "mail@EXAMPLE.com"}, headers=_bearer(admin)
    )
    own_again = await client.put(
        f"/api/users/{created.json()['id']}",
        json={"email": "mail@example.com"},
        headers=_bearer(admin),
    )

    # Assert
    assert created.status_code == 200
    assert created.json()["email"] == "Mail@example.com"
    assert duplicate.status_code == 400
    assert duplicate.json()["detail"] == "Email already registered"
    assert own_again.status_code == 200


async def test_activated_user_starts_with_pending_onboarding_wizard(client: AsyncClient) -> None:
    # Arrange
    await _register(client, "wizard_user", "wizard@example.com")
    admin = await _create_user("wizard_admin", role="admin")
    early_login = await client.post(
        "/api/auth/token", data={"username": "wizard_user", "password": PASSWORD}
    )
    pending = await _load_user("wizard_user")

    # Act
    activate = await client.post(f"/api/users/{pending.id}/activate", headers=_bearer(admin))
    login = await client.post(
        "/api/auth/token", data={"username": "wizard_user", "password": PASSWORD}
    )
    player_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    state_before = await client.get("/api/settings/setup-wizard", headers=player_headers)
    finish = await client.put(
        "/api/settings/setup-wizard", json={"state": "completed"}, headers=player_headers
    )
    state_after = await client.get("/api/settings/setup-wizard", headers=player_headers)
    admin_state = await client.get("/api/settings/setup-wizard", headers=_bearer(admin))

    # Assert
    assert early_login.status_code == 403
    assert activate.status_code == 200
    assert login.status_code == 200
    assert state_before.json()["state"] == "pending"
    assert finish.status_code == 200
    assert state_after.json()["state"] == "completed"
    assert admin_state.json()["state"] == "pending"
