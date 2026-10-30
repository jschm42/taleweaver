"""World-Builder proposals that create new NPCs and objects (new_npc / new_object)."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from backend.api.routes.adventures.editing.ai_fix_sanitize import sanitize_proposals
from backend.main import app
from backend.models.world_entity import WorldEntity
from tests.conftest import TestSessionLocal
from tests.test_ai_fix_endpoint import _auth_headers
from tests.test_world_builder_instruct import _patch_llm, _seed_user_with_adventure


@pytest.fixture
async def client():
    app.dependency_overrides.clear()
    from backend.core.database import get_db
    from tests.conftest import override_get_db

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


def _create_npc_proposal(npc_id: str = "OLD_FISHERMAN", scene_id: str = "START") -> dict:
    return {
        "title": "Grumpy fisherman",
        "summary": "Adds a grumpy fisherman who sells bait.",
        "patches": [
            {
                "target_type": "new_npc",
                "target_id": npc_id,
                "description": "Create the fisherman.",
                "field_updates": {
                    "name": "Old Fisherman",
                    "description": "A weathered man mending nets.",
                    "current_scene_id": scene_id,
                    "character": "Grumpy, short answers",
                    "goal": "Sell his bait",
                },
            },
            {
                "target_type": "npc",
                "target_id": npc_id,
                "description": "Place him at the door.",
                "field_updates": {"spatial_position": "by the door"},
            },
        ],
    }


async def _suggest(client, monkeypatch, username: str, proposal: dict) -> dict:
    tpl_id = await _seed_user_with_adventure(username)
    _patch_llm(monkeypatch, {"proposals": [proposal]}, {})
    resp = await client.post(
        f"/api/adventures/{tpl_id}/editor/world-builder/suggest",
        headers=_auth_headers(username),
        json={"instruction": "Add a grumpy fisherman."},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def test_suggest_keeps_a_valid_creation(client, setup_test_db, monkeypatch):
    # Act
    payload = await _suggest(client, monkeypatch, "wbc_user_1", _create_npc_proposal())

    # Assert
    assert payload["error"] is None
    patches = payload["proposals"][0]["patches"]
    assert [p["target_type"] for p in patches] == ["new_npc", "npc"]


async def test_suggest_rejects_an_existing_id(client, setup_test_db, monkeypatch):
    # Act
    payload = await _suggest(
        client, monkeypatch, "wbc_user_2", _create_npc_proposal(npc_id="OLD_LIBRARIAN")
    )

    # Assert
    assert payload["proposals"] == []
    assert "already exists" in payload["error"]


async def test_suggest_rejects_an_unknown_scene(client, setup_test_db, monkeypatch):
    # Act
    payload = await _suggest(
        client, monkeypatch, "wbc_user_3", _create_npc_proposal(scene_id="NOWHERE")
    )

    # Assert
    assert payload["proposals"] == []
    assert "NOWHERE" in payload["error"]


async def test_apply_creates_the_npc_and_configures_it(client, setup_test_db):
    # Arrange
    tpl_id = await _seed_user_with_adventure("wbc_user_4")

    # Act
    resp = await client.post(
        f"/api/adventures/{tpl_id}/editor/world-builder/apply",
        headers=_auth_headers("wbc_user_4"),
        json={"proposal": _create_npc_proposal()},
    )

    # Assert
    assert resp.status_code == 200, resp.text
    assert resp.json()["applied_targets"] == ["new_npc:OLD_FISHERMAN", "npc:OLD_FISHERMAN"]
    async with TestSessionLocal() as db:
        npc = (
            await db.execute(
                select(WorldEntity).where(
                    WorldEntity.template_id == tpl_id, WorldEntity.id == "OLD_FISHERMAN"
                )
            )
        ).scalar_one()
    assert npc.entity_type == "NPC"
    assert npc.current_scene_id == "START"
    assert npc.character == "Grumpy, short answers"
    assert npc.spatial_position == "by the door"


def test_ai_fix_suggestions_never_create():
    # Arrange
    summary = {"scenes": [{"id": "START"}], "npcs": [], "objects": []}

    # Act
    result = sanitize_proposals([_create_npc_proposal()], summary)

    # Assert
    assert result.proposals == []
    assert "new_npc (creating entities)" in result.rejected


def test_switch_objects_cannot_be_created():
    # Arrange
    summary = {"scenes": [{"id": "START"}], "npcs": [], "objects": []}
    proposal = {
        "title": "Lever",
        "summary": "Adds a lever.",
        "patches": [
            {
                "target_type": "new_object",
                "target_id": "LEVER",
                "description": "Create a lever.",
                "field_updates": {
                    "name": "Lever",
                    "description": "A rusty lever.",
                    "current_scene_id": "START",
                    "item_type": "SWITCH",
                },
            }
        ],
    }

    # Act
    result = sanitize_proposals([proposal], summary, allow_create=True)

    # Assert
    assert result.proposals == []
    assert "new_object.item_type SWITCH cannot be created" in result.rejected


async def test_apply_creates_an_object_with_script_and_visibility(client, setup_test_db):
    # Arrange
    tpl_id = await _seed_user_with_adventure("wbc_user_5")
    proposal = {
        "title": "Hidden note",
        "summary": "Adds a hidden note that tells a secret when read.",
        "patches": [
            {
                "target_type": "new_object",
                "target_id": "TORN_NOTE",
                "description": "Create the note.",
                "field_updates": {
                    "name": "Torn Note",
                    "description": "A torn piece of paper.",
                    "current_scene_id": "START",
                    "item_type": "READABLE",
                },
            },
            {
                "target_type": "object",
                "target_id": "TORN_NOTE",
                "description": "Hide it and add a read text.",
                "field_updates": {"is_hidden": True, "on_read_text": "You feel watched."},
            },
        ],
    }

    # Act
    resp = await client.post(
        f"/api/adventures/{tpl_id}/editor/world-builder/apply",
        headers=_auth_headers("wbc_user_5"),
        json={"proposal": proposal},
    )

    # Assert
    assert resp.status_code == 200, resp.text
    async with TestSessionLocal() as db:
        note = (
            await db.execute(
                select(WorldEntity).where(
                    WorldEntity.template_id == tpl_id, WorldEntity.id == "TORN_NOTE"
                )
            )
        ).scalar_one()
    assert note.item_type == "READABLE"
    assert note.is_hidden is True
    assert note.metadata_json["on_read_text"] == "You feel watched."
