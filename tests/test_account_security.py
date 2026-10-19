"""Account security: login throttling, token revocation, recovery codes, reset links, profile sessions."""

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from backend.core.auth import create_user_access_token, get_password_hash
from backend.core.login_throttle import login_throttle, recovery_throttle
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.game_session import GameSession
from backend.models.session_state import SessionState
from backend.models.user import User
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio

PASSWORD = "Old_Passw0rd!"
NEW_PASSWORD = "New_Passw0rd!"
AUTH_PROBE = "/api/users/me/sessions"


@pytest.fixture(autouse=True)
def _clear_throttles():
    login_throttle.clear()
    recovery_throttle.clear()
    yield
    login_throttle.clear()
    recovery_throttle.clear()


async def _create_user(username: str, role: str = "user", password: str = PASSWORD) -> User:
    async with TestSessionLocal() as session:
        user = User(username=username, hashed_password=get_password_hash(password), role=role)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


async def _load_user(username: str) -> User:
    async with TestSessionLocal() as session:
        return (
            (await session.execute(select(User).where(User.username == username))).scalars().one()
        )


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _login(client: AsyncClient, username: str, password: str):
    return await client.post("/api/auth/token", data={"username": username, "password": password})


async def test_login_throttles_only_failed_attempts(client: AsyncClient) -> None:
    # Arrange
    await _create_user("throttle_user")

    # Act
    successes = [await _login(client, "throttle_user", PASSWORD) for _ in range(6)]
    failures = [await _login(client, "throttle_user", "wrong") for _ in range(5)]
    blocked = await _login(client, "throttle_user", PASSWORD)

    # Assert
    assert all(r.status_code == 200 for r in successes)
    assert all(r.status_code == 401 for r in failures)
    assert blocked.status_code == 429


async def test_password_change_revokes_previous_tokens(client: AsyncClient) -> None:
    # Arrange
    user = await _create_user("revoke_user")
    old_token = create_user_access_token(user)

    # Act
    resp = await client.put(
        "/api/users/me/credentials",
        headers=_bearer(old_token),
        json={"current_password": PASSWORD, "password": NEW_PASSWORD},
    )

    # Assert
    assert resp.status_code == 200
    new_token = resp.json()["access_token"]
    assert (await client.get(AUTH_PROBE, headers=_bearer(old_token))).status_code == 401
    assert (await client.get(AUTH_PROBE, headers=_bearer(new_token))).status_code == 200


async def test_token_of_renamed_user_cannot_authenticate_new_owner_of_name(
    client: AsyncClient,
) -> None:
    # Arrange
    original = await _create_user("shared_name")
    stale_token = create_user_access_token(original)
    async with TestSessionLocal() as session:
        renamed = await session.get(User, original.id)
        renamed.username = "renamed_user"
        await session.commit()
    await _create_user("shared_name")

    # Act
    resp = await client.get(AUTH_PROBE, headers=_bearer(stale_token))

    # Assert
    assert resp.status_code == 401


async def test_recovery_code_resets_password_once(client: AsyncClient) -> None:
    # Arrange
    user = await _create_user("recover_user")
    codes_resp = await client.post(
        "/api/users/me/recovery-codes",
        headers=_bearer(create_user_access_token(user)),
        json={"current_password": PASSWORD},
    )
    code = codes_resp.json()["codes"][0]
    payload = {
        "username": "recover_user",
        "recovery_code": code.lower(),
        "new_password": NEW_PASSWORD,
    }

    # Act
    first = await client.post("/api/auth/recover", json=payload)
    reuse = await client.post("/api/auth/recover", json=payload)

    # Assert
    assert codes_resp.status_code == 200 and len(codes_resp.json()["codes"]) == 10
    assert first.status_code == 200
    assert reuse.status_code == 400
    assert (await _login(client, "recover_user", NEW_PASSWORD)).status_code == 200
    assert (await _load_user("recover_user")).recovery_codes_remaining == 9


async def test_recovery_codes_require_current_password(client: AsyncClient) -> None:
    user = await _create_user("codes_pw_user")

    resp = await client.post(
        "/api/users/me/recovery-codes",
        headers=_bearer(create_user_access_token(user)),
        json={"current_password": "wrong"},
    )

    assert resp.status_code == 400


async def test_admin_reset_link_is_single_use_and_expires(client: AsyncClient) -> None:
    # Arrange
    admin = await _create_user("reset_admin", role="admin")
    await _create_user("reset_target")
    target = await _load_user("reset_target")
    link = await client.post(
        f"/api/users/{target.id}/password-reset-link",
        headers=_bearer(create_user_access_token(admin)),
    )
    token = link.json()["token"]

    # Act
    used = await client.post(
        "/api/auth/reset-password", json={"token": token, "new_password": NEW_PASSWORD}
    )
    reused = await client.post(
        "/api/auth/reset-password", json={"token": token, "new_password": NEW_PASSWORD}
    )

    # Assert
    assert link.status_code == 200
    assert used.status_code == 200
    assert reused.status_code == 400
    assert (await _login(client, "reset_target", NEW_PASSWORD)).status_code == 200


async def test_expired_reset_link_is_rejected(client: AsyncClient) -> None:
    # Arrange
    from backend.core.account_recovery import issue_password_reset_token

    await _create_user("expired_target")
    async with TestSessionLocal() as session:
        user = (
            (await session.execute(select(User).where(User.username == "expired_target")))
            .scalars()
            .one()
        )
        token = issue_password_reset_token(user)
        user.password_reset_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        await session.commit()

    # Act
    resp = await client.post(
        "/api/auth/reset-password", json={"token": token, "new_password": NEW_PASSWORD}
    )

    # Assert
    assert resp.status_code == 400


async def test_admin_cannot_demote_self_or_assign_unknown_role(client: AsyncClient) -> None:
    admin = await _create_user("solo_admin", role="admin")
    headers = _bearer(create_user_access_token(admin))

    demote = await client.put(f"/api/users/{admin.id}", headers=headers, json={"role": "user"})
    bogus = await client.put(f"/api/users/{admin.id}", headers=headers, json={"role": "superuser"})

    assert demote.status_code == 400
    assert bogus.status_code == 400


async def test_player_can_update_own_language_preference(client: AsyncClient) -> None:
    user = await _create_user("lang_user")

    resp = await client.put(
        "/api/users/me/preferences",
        headers=_bearer(create_user_access_token(user)),
        json={"default_language": "German"},
    )

    assert resp.status_code == 200
    assert resp.json()["default_language"] == "German"


async def test_session_overview_reports_sequence_progress_and_xp(client: AsyncClient) -> None:
    # Arrange
    user = await _create_user("history_user")
    async with TestSessionLocal() as session:
        template = AdventureTemplate(
            id="history-tpl",
            owner_id=user.id,
            title="The Long Road",
            language="en",
            is_ready=True,
            sequences=[
                {"id": "s1", "order": 1, "title": "Departure", "exp_reward": 50},
                {"id": "s2", "order": 2, "title": "Crossing", "exp_reward": 75},
                {"id": "s3", "order": 3, "title": "Arrival", "exp_reward": 100},
            ],
        )
        avatar = Avatar(id="history-avatar", user_id=user.id, name="Mira", exp=50)
        game = GameSession(
            id="history-game",
            user_id=user.id,
            avatar_id=avatar.id,
            template_id=template.id,
            status="game_over",
        )
        state = SessionState(session_id=game.id, template_id=template.id, active_sequence_id="s2")
        session.add_all([template, avatar, game, state])
        await session.commit()

    # Act
    resp = await client.get(AUTH_PROBE, headers=_bearer(create_user_access_token(user)))

    # Assert
    assert resp.status_code == 200
    [entry] = resp.json()
    assert entry["status"] == "game_over"
    assert entry["xp"] == 50
    assert entry["sequences_completed"] == 1
    assert entry["sequences_total"] == 3
    assert [s["completed"] for s in entry["sequences"]] == [True, False, False]
    assert not any(s["active"] for s in entry["sequences"])
