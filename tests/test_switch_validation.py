import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.auth import create_access_token
from backend.main import app
from backend.core.database import get_db
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User
from backend.models.world_entity import WorldEntity, WorldScene
from tests.conftest import TestSessionLocal


def _auth_headers(username: str) -> dict:
    token = create_access_token(data={"sub": username})
    return {"Authorization": f"Bearer {token}"}


async def _seed_template(username: str) -> tuple[str, str]:
    user = User(username=username, hashed_password="x", role="admin")
    async with TestSessionLocal() as db:
        db.add(user)
        await db.commit()
        user_id = user.id
        tpl_id = f"tpl-switch-val-{username}"
        tpl = AdventureTemplate(
            id=tpl_id,
            owner_id=user_id,
            title="Switch Validation Test",
            version="1.0",
            rule_enforcement_mode="rpg",
            is_ready=True,
            creation_status="Ready",
            generate_scene_images=False,
            generate_npc_images=False,
            generate_item_images=False,
            teaser="t",
            rules="r",
            plot="p",
            intro_text="i",
            walkthrough="w",
            completed_condition="done",
            gameover_condition="lost",
            tts_director_notes="notes",
            quests=[],
        )
        db.add(tpl)
        scene = WorldScene(id="SCENE_X", template_id=tpl_id, label="X", description="X")
        db.add(scene)
        await db.commit()
    return user_id, tpl_id


@pytest.mark.asyncio
async def test_create_switch_validation(client, setup_test_db):
    user_id, tpl_id = await _seed_template("switch_creator")
    headers = _auth_headers("switch_creator")

    # 1. Try to create switch with less than 2 states -> should fail
    res = await client.post(
        f"/api/adventures/{tpl_id}/editor/entity",
        headers=headers,
        json={
            "entity_id": "VAL_SWITCH",
            "scene_id": "SCENE_X",
            "entity_type": "OBJECT",
            "item_type": "SWITCH",
            "name": "Switch",
            "description": "A switch.",
            "metadata_json": {
                "switch": {
                    "states": ["ON"],
                    "initial_state": "ON"
                }
            }
        }
    )
    assert res.status_code == 400
    assert "at least 2 states" in res.text

    # 2. Try to create switch with empty initial state -> should fail
    res = await client.post(
        f"/api/adventures/{tpl_id}/editor/entity",
        headers=headers,
        json={
            "entity_id": "VAL_SWITCH",
            "scene_id": "SCENE_X",
            "entity_type": "OBJECT",
            "item_type": "SWITCH",
            "name": "Switch",
            "description": "A switch.",
            "metadata_json": {
                "switch": {
                    "states": ["ON", "OFF"],
                    "initial_state": ""
                }
            }
        }
    )
    assert res.status_code == 400
    assert "initial state must be defined" in res.text

    # 3. Try to create switch with initial state not in states list -> should fail
    res = await client.post(
        f"/api/adventures/{tpl_id}/editor/entity",
        headers=headers,
        json={
            "entity_id": "VAL_SWITCH",
            "scene_id": "SCENE_X",
            "entity_type": "OBJECT",
            "item_type": "SWITCH",
            "name": "Switch",
            "description": "A switch.",
            "metadata_json": {
                "switch": {
                    "states": ["ON", "OFF"],
                    "initial_state": "OTHER"
                }
            }
        }
    )
    assert res.status_code == 400
    assert "is not one of the switch states" in res.text

    # 4. Create a valid switch -> should succeed
    res = await client.post(
        f"/api/adventures/{tpl_id}/editor/entity",
        headers=headers,
        json={
            "entity_id": "VAL_SWITCH",
            "scene_id": "SCENE_X",
            "entity_type": "OBJECT",
            "item_type": "SWITCH",
            "name": "Switch",
            "description": "A switch.",
            "metadata_json": {
                "switch": {
                    "states": ["ON", "OFF"],
                    "initial_state": "OFF"
                }
            }
        }
    )
    assert res.status_code == 200, res.text
    assert res.json()["entity"]["metadata_json"]["switch"]["states"] == ["ON", "OFF"]
    assert res.json()["entity"]["metadata_json"]["switch"]["initial_state"] == "OFF"


@pytest.mark.asyncio
async def test_update_switch_validation(client, setup_test_db):
    user_id, tpl_id = await _seed_template("switch_updater")
    headers = _auth_headers("switch_updater")

    # Create a valid switch initially
    async with TestSessionLocal() as db:
        ent = WorldEntity(
            id="SWITCH_UPD",
            template_id=tpl_id,
            entity_type="OBJECT",
            item_type="SWITCH",
            name="Updater Switch",
            description="Desc",
            current_scene_id="SCENE_X",
            metadata_json={
                "switch": {
                    "states": ["UP", "DOWN"],
                    "initial_state": "UP"
                }
            }
        )
        db.add(ent)
        await db.commit()
        ent_pk = ent.pk

    # 1. Update states to < 2 -> should fail
    res = await client.patch(
        f"/api/adventures/{tpl_id}/editor/entity",
        headers=headers,
        json={
            "target_type": "object",
            "target_id": "SWITCH_UPD",
            "switch_states": ["UP"]
        }
    )
    assert res.status_code == 400
    assert "at least 2 states" in res.text

    # 2. Update initial state to not in list -> should fail
    res = await client.patch(
        f"/api/adventures/{tpl_id}/editor/entity",
        headers=headers,
        json={
            "target_type": "object",
            "target_id": "SWITCH_UPD",
            "switch_initial_state": "INVALID_STATE"
        }
    )
    assert res.status_code == 400
    assert "is not one of the switch states" in res.text

    # 3. Update switch successfully -> should succeed
    res = await client.patch(
        f"/api/adventures/{tpl_id}/editor/entity",
        headers=headers,
        json={
            "target_type": "object",
            "target_id": "SWITCH_UPD",
            "switch_states": ["LEFT", "RIGHT"],
            "switch_initial_state": "RIGHT"
        }
    )
    assert res.status_code == 200, res.text

    async with TestSessionLocal() as db:
        updated = await db.get(WorldEntity, ent_pk)
        assert updated is not None
        assert updated.metadata_json["switch"]["states"] == ["LEFT", "RIGHT"]
        assert updated.metadata_json["switch"]["initial_state"] == "RIGHT"
