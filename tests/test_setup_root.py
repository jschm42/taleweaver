"""Root admin bootstrap: password policy errors are reported, relaxed policy is honoured."""

import pytest

from backend.api.routes import auth_api
from backend.core.config import settings

pytestmark = pytest.mark.asyncio

URL = "/api/auth/setup-root"


@pytest.fixture(autouse=True)
def _allow_setup(monkeypatch):
    monkeypatch.setattr(settings, "ALLOW_REMOTE_SETUP", True)
    monkeypatch.setattr(settings, "STRICT_PASSWORD_POLICY", True)
    auth_api._setup_root_attempts.clear()


async def test_short_password_reports_policy(client):
    # Act
    response = await client.post(URL, json={"username": "admin", "password": "Ab1!xyzq"})

    # Assert
    assert response.status_code == 400
    assert "at least 10 characters" in response.json()["detail"]


async def test_strong_password_creates_admin(client):
    # Act
    response = await client.post(URL, json={"username": "admin", "password": "Str0ng!Passw0rd"})

    # Assert
    assert response.status_code == 200


async def test_relaxed_policy_accepts_short_password(client, monkeypatch):
    # Arrange
    monkeypatch.setattr(settings, "STRICT_PASSWORD_POLICY", False)

    # Act
    response = await client.post(URL, json={"username": "admin", "password": "admin123"})

    # Assert
    assert response.status_code == 200
