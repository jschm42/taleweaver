"""
Tests for the Adventures REST API (Package 4).

Covers: create, list, get, update, delete, pause/resume, and game-state
sub-routes. All tests follow the Arrange-Act-Assert pattern.
"""
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

async def _create_adventure(client: AsyncClient, title: str = "Test Quest") -> dict:
    """Creates a minimal adventure and returns the response JSON."""
    resp = await client.post(
        "/api/adventures",
        json={"title": title, "avatar_name": "Hero"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# POST /api/adventures
# ---------------------------------------------------------------------------

async def test_create_adventure_returns_ids(client: AsyncClient):
    """Creating an adventure returns game_id, adventure_id, and avatar_id."""
    # Arrange & Act
    data = await _create_adventure(client)

    # Assert
    assert "game_id" in data
    assert "adventure_id" in data
    assert "avatar_id" in data


async def test_create_adventure_with_heartbeat(client: AsyncClient):
    """Heartbeat settings are persisted when creating an adventure."""
    # Arrange
    payload = {
        "title": "Timed Quest",
        "avatar_name": "Ranger",
        "heartbeat_enabled": True,
        "heartbeat_interval": 30,
    }

    # Act
    resp = await client.post("/api/adventures", json=payload)
    data = resp.json()

    # Assert
    assert resp.status_code == 201
    adv_resp = await client.get(f"/api/adventures/{data['adventure_id']}")
    adv = adv_resp.json()
    assert adv["heartbeat_enabled"] is True
    assert adv["heartbeat_interval"] == 30


# ---------------------------------------------------------------------------
# GET /api/adventures
# ---------------------------------------------------------------------------

async def test_list_adventures_empty(client: AsyncClient):
    """Listing adventures on a fresh DB returns an empty list."""
    resp = await client.get("/api/adventures")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_adventures_returns_created(client: AsyncClient):
    """After creating two adventures, both appear in the list."""
    await _create_adventure(client, "Quest A")
    await _create_adventure(client, "Quest B")

    resp = await client.get("/api/adventures")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


# ---------------------------------------------------------------------------
# GET /api/adventures/{adventure_id}
# ---------------------------------------------------------------------------

async def test_get_adventure_success(client: AsyncClient):
    """Fetching an existing adventure returns its details."""
    ids = await _create_adventure(client, "Dragon's Lair")

    resp = await client.get(f"/api/adventures/{ids['adventure_id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Dragon's Lair"
    assert "strict_rules" in data


async def test_get_adventure_not_found(client: AsyncClient):
    """Fetching a non-existent adventure returns 404."""
    resp = await client.get("/api/adventures/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /api/adventures/{adventure_id}
# ---------------------------------------------------------------------------

async def test_update_adventure_title(client: AsyncClient):
    """Patching the title of an adventure updates only that field."""
    ids = await _create_adventure(client, "Old Title")

    resp = await client.patch(
        f"/api/adventures/{ids['adventure_id']}",
        json={"title": "New Title"},
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "New Title"


async def test_update_adventure_strict_rules(client: AsyncClient):
    """Patching strict_rules toggles the flag correctly."""
    ids = await _create_adventure(client)

    resp = await client.patch(
        f"/api/adventures/{ids['adventure_id']}",
        json={"strict_rules": False},
    )
    assert resp.status_code == 200
    assert resp.json()["strict_rules"] is False


async def test_update_adventure_not_found(client: AsyncClient):
    """Patching a non-existent adventure returns 404."""
    resp = await client.patch(
        "/api/adventures/00000000-0000-0000-0000-000000000000",
        json={"title": "Ghost"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/adventures/{adventure_id}
# ---------------------------------------------------------------------------

async def test_delete_adventure(client: AsyncClient):
    """Deleting an adventure removes it; subsequent GET returns 404."""
    ids = await _create_adventure(client)
    adv_id = ids["adventure_id"]

    del_resp = await client.delete(f"/api/adventures/{adv_id}")
    assert del_resp.status_code == 204

    get_resp = await client.get(f"/api/adventures/{adv_id}")
    assert get_resp.status_code == 404


async def test_delete_adventure_not_found(client: AsyncClient):
    """Deleting a non-existent adventure returns 404."""
    resp = await client.delete("/api/adventures/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/adventures/{adventure_id}/state
# ---------------------------------------------------------------------------

async def test_get_game_state(client: AsyncClient):
    """The initial game state has scene_id='START' and in_game_time=0."""
    ids = await _create_adventure(client)

    resp = await client.get(f"/api/adventures/{ids['adventure_id']}/state")
    assert resp.status_code == 200
    data = resp.json()
    assert data["scene_id"] == "START"
    assert data["in_game_time"] == 0
    assert data["is_paused"] is False


# ---------------------------------------------------------------------------
# PATCH /api/adventures/{adventure_id}/state
# ---------------------------------------------------------------------------

async def test_update_game_state_scene(client: AsyncClient):
    """Patching the game state updates scene_id."""
    ids = await _create_adventure(client)

    resp = await client.patch(
        f"/api/adventures/{ids['adventure_id']}/state",
        json={"scene_id": "DUNGEON_ENTRANCE"},
    )
    assert resp.status_code == 200

    state_resp = await client.get(f"/api/adventures/{ids['adventure_id']}/state")
    assert state_resp.json()["scene_id"] == "DUNGEON_ENTRANCE"


# ---------------------------------------------------------------------------
# POST /api/adventures/{adventure_id}/pause & /resume
# ---------------------------------------------------------------------------

async def test_pause_and_resume_game(client: AsyncClient):
    """Pausing sets is_paused=True; resuming sets it back to False."""
    ids = await _create_adventure(client)
    adv_id = ids["adventure_id"]

    # Pause
    pause_resp = await client.post(f"/api/adventures/{adv_id}/pause")
    assert pause_resp.status_code == 200

    state = (await client.get(f"/api/adventures/{adv_id}/state")).json()
    assert state["is_paused"] is True

    # Resume
    resume_resp = await client.post(f"/api/adventures/{adv_id}/resume")
    assert resume_resp.status_code == 200

    state = (await client.get(f"/api/adventures/{adv_id}/state")).json()
    assert state["is_paused"] is False
