"""
Tests for the Avatars REST API (Package 4).

Covers: get avatar, get aggregated stats, patch avatar, remove status effect.
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def client(auth_client: AsyncClient) -> AsyncClient:
    """Avatar endpoints require authentication."""
    return auth_client


async def _create_adventure(client: AsyncClient) -> dict:
    resp = await client.post(
        "/api/adventures/",
        json={"title": "Test", "avatar_name": "Warrior"},
    )
    assert resp.status_code == 201
    return resp.json()


# ---------------------------------------------------------------------------
# GET /api/avatars/{avatar_id}
# ---------------------------------------------------------------------------

async def test_get_avatar_success(client: AsyncClient):
    """Fetching an avatar returns its character sheet."""
    ids = await _create_adventure(client)

    resp = await client.get(f"/api/avatars/{ids['avatar_id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Warrior"
    assert data["hp"] == 200
    assert data["stamina"] == 200
    assert data["mana"] == 200


async def test_get_avatar_not_found(client: AsyncClient):
    """Fetching a non-existent avatar returns 404."""
    resp = await client.get("/api/avatars/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/avatars/{avatar_id}/stats
# ---------------------------------------------------------------------------

async def test_get_avatar_stats(client: AsyncClient):
    """Stats endpoint returns hp, stamina, mana, and total_stats."""
    ids = await _create_adventure(client)

    resp = await client.get(f"/api/avatars/{ids['avatar_id']}/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["hp"] == 200
    assert "total_stats" in data
    assert "status_effects" in data


# ---------------------------------------------------------------------------
# PATCH /api/avatars/{avatar_id}
# ---------------------------------------------------------------------------

async def test_patch_avatar_hp(client: AsyncClient):
    """Patching HP updates only that field."""
    ids = await _create_adventure(client)

    resp = await client.patch(f"/api/avatars/{ids['avatar_id']}", json={"hp": 150})
    assert resp.status_code == 200
    assert resp.json()["hp"] == 150
    # Other fields unchanged
    assert resp.json()["stamina"] == 200


async def test_patch_avatar_status_effects(client: AsyncClient):
    """Patching status_effects replaces the list."""
    ids = await _create_adventure(client)

    resp = await client.patch(
        f"/api/avatars/{ids['avatar_id']}",
        json={"status_effects": ["Poisoned", "Blessed"]},
    )
    assert resp.status_code == 200
    assert set(resp.json()["status_effects"]) == {"Poisoned", "Blessed"}


async def test_patch_avatar_not_found(client: AsyncClient):
    """Patching a non-existent avatar returns 404."""
    resp = await client.patch(
        "/api/avatars/00000000-0000-0000-0000-000000000000",
        json={"hp": 100},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/avatars/{avatar_id}/status-effects/{effect_name}
# ---------------------------------------------------------------------------

async def test_remove_status_effect(client: AsyncClient):
    """Removing an existing status effect succeeds with 204."""
    ids = await _create_adventure(client)
    avatar_id = ids["avatar_id"]

    # First add a status effect
    await client.patch(f"/api/avatars/{avatar_id}", json={"status_effects": ["Poisoned"]})

    resp = await client.delete(f"/api/avatars/{avatar_id}/status-effects/Poisoned")
    assert resp.status_code == 204

    # Verify it's gone
    stats = (await client.get(f"/api/avatars/{avatar_id}/stats")).json()
    assert "Poisoned" not in stats["status_effects"]


async def test_remove_status_effect_not_found(client: AsyncClient):
    """Removing a non-existent status effect returns 404."""
    ids = await _create_adventure(client)

    resp = await client.delete(f"/api/avatars/{ids['avatar_id']}/status-effects/Burning")
    assert resp.status_code == 404




