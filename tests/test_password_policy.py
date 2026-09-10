import pytest
from httpx import AsyncClient

from backend.core.auth import create_access_token, get_password_hash, validate_password_strength
from backend.core.config import settings
from backend.models.user import User
from tests.conftest import TestSessionLocal

def test_validate_password_strength_strict(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "STRICT_PASSWORD_POLICY", True)

    # Valid complex password (>= 10 chars, lower, upper, digit, special)
    validate_password_strength("Anno1503#!Test")

    # Too short
    with pytest.raises(ValueError, match="at least 10 characters"):
        validate_password_strength("Short1!")

    # Missing uppercase
    with pytest.raises(ValueError, match="at least one lowercase letter"):
        validate_password_strength("anno1503#!test")

    # Missing special char
    with pytest.raises(ValueError, match="at least one lowercase letter"):
        validate_password_strength("Anno15031234")


def test_validate_password_strength_relaxed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "STRICT_PASSWORD_POLICY", False)

    # Valid simple passwords
    validate_password_strength("1234")
    validate_password_strength("admin")
    validate_password_strength("admin123!")

    # Less than 4 characters still rejected
    with pytest.raises(ValueError, match="at least 4 characters"):
        validate_password_strength("abc")

    with pytest.raises(ValueError, match="must be a string"):
        validate_password_strength(1234)  # type: ignore


@pytest.mark.asyncio
async def test_update_credentials_with_relaxed_policy(
    monkeypatch: pytest.MonkeyPatch, client: AsyncClient
) -> None:
    monkeypatch.setattr(settings, "STRICT_PASSWORD_POLICY", False)

    async with TestSessionLocal() as session:
        user = User(
            username="dev_policy_user",
            hashed_password=get_password_hash("initial_pass"),
            role="user",
        )
        session.add(user)
        await session.commit()

    headers = {"Authorization": f"Bearer {create_access_token({'sub': 'dev_policy_user'})}"}
    payload = {
        "current_password": "initial_pass",
        "password": "simpledevpass",
    }
    response = await client.put("/api/users/me/credentials", headers=headers, json=payload)
    assert response.status_code == 200
    assert response.json()["user"]["username"] == "dev_policy_user"
