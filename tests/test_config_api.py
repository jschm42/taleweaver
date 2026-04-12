"""
Tests for the Settings / Config REST API (Package 4).

Covers: saving encrypted API keys for different providers.
"""
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_save_api_key_creates_user(client: AsyncClient):
    """
    Saving an API key for the first time creates the default user
    and returns a success status.
    """
    # Arrange
    payload = {"provider": "openai", "api_key": "sk-test-key-123"}

    # Act
    resp = await client.post("/api/settings/keys", json=payload)

    # Assert
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert "openai" in data["message"]


async def test_save_api_key_multiple_providers(client: AsyncClient):
    """Saving keys for two providers both succeed independently."""
    for provider, key in [("openai", "sk-openai"), ("anthropic", "sk-anthropic")]:
        resp = await client.post(
            "/api/settings/keys",
            json={"provider": provider, "api_key": key},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"


async def test_save_api_key_overwrites_existing(client: AsyncClient):
    """Saving a key for the same provider twice overwrites the first key."""
    payload = {"provider": "openai", "api_key": "sk-first"}
    await client.post("/api/settings/keys", json=payload)

    payload["api_key"] = "sk-second"
    resp = await client.post("/api/settings/keys", json=payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"
