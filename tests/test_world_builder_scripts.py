"""World-Builder proposals that attach scripts, trigger texts and guards, and its language rules."""

import re

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from backend.api.routes.adventures.editing.ai_fix_context import _summarize_world_for_fix
from backend.api.routes.adventures.editing.ai_fix_targets import _allowed_fields_for
from backend.api.routes.adventures.editing.common import _get_template_avatar
from backend.core.validators_prompts import FIX_PATCH_FIELD_RULES
from backend.core.world_builder_prompts import WORLD_BUILDER_INSTRUCTION_SYSTEM_PROMPT
from backend.main import app
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene
from tests.conftest import TestSessionLocal
from tests.test_ai_fix_endpoint import _auth_headers
from tests.test_world_builder_instruct import _patch_llm, _seed_user_with_adventure

_PATCH_TARGETS = ("scene", "object", "npc", "exit", "protagonist", "adventure", "sequence")


@pytest.fixture
async def client():
    app.dependency_overrides.clear()
    from backend.core.database import get_db
    from tests.conftest import override_get_db

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


def _script_proposal(target_type: str, target_id: str, field_updates: dict) -> dict:
    return {
        "title": "Scripted change",
        "summary": "Adds a script to the entity.",
        "patches": [
            {
                "target_type": target_type,
                "target_id": target_id,
                "description": "Attach the hook.",
                "field_updates": field_updates,
            }
        ],
    }


async def _apply(client, username: str, proposal: dict) -> tuple[str, dict]:
    tpl_id = await _seed_user_with_adventure(username)
    resp = await client.post(
        f"/api/adventures/{tpl_id}/editor/world-builder/apply",
        headers=_auth_headers(username),
        json={"proposal": proposal},
    )
    return tpl_id, {"status_code": resp.status_code, **resp.json()}


async def _entity(tpl_id: str, entity_id: str) -> WorldEntity:
    async with TestSessionLocal() as db:
        return (
            await db.execute(
                select(WorldEntity).where(
                    WorldEntity.template_id == tpl_id, WorldEntity.id == entity_id
                )
            )
        ).scalar_one()


@pytest.mark.parametrize("target_type", _PATCH_TARGETS)
def test_prompt_lists_every_allowlisted_field(target_type):
    # Arrange
    listed = set(re.findall(r"[a-z_]+", FIX_PATCH_FIELD_RULES))

    # Act
    missing = sorted(set(_allowed_fields_for(target_type)) - listed)

    # Assert
    assert missing == []


def test_prompt_asks_for_english_proposals_and_explains_scripts():
    # Arrange
    prompt = WORLD_BUILDER_INSTRUCTION_SYSTEM_PROMPT

    # Act / Assert
    assert "author's language" not in prompt
    assert "in English" in prompt
    assert "SCRIPTS AND GUARDS" in prompt
    assert "tw.vars: get(key, default), set(key, value)" in prompt


async def test_suggest_drops_a_proposal_with_invalid_script(client, setup_test_db, monkeypatch):
    # Arrange
    tpl_id = await _seed_user_with_adventure("wbs_user_1")
    broken = _script_proposal("object", "SAFE_01", {"on_pickup_script": "if True\n    pass"})
    valid = _script_proposal(
        "object", "SAFE_01", {"on_pickup_script": "tw.vars.set('safe_taken', True)"}
    )
    _patch_llm(monkeypatch, {"proposals": [broken, valid]}, {})

    # Act
    resp = await client.post(
        f"/api/adventures/{tpl_id}/editor/world-builder/suggest",
        headers=_auth_headers("wbs_user_1"),
        json={"instruction": "Remember when the safe is taken."},
    )

    # Assert
    payload = resp.json()
    assert len(payload["proposals"]) == 1
    patch = payload["proposals"][0]["patches"][0]
    assert patch["field_updates"] == {"on_pickup_script": "tw.vars.set('safe_taken', True)"}


async def test_suggest_drops_a_proposal_with_invalid_guard(client, setup_test_db, monkeypatch):
    # Arrange
    tpl_id = await _seed_user_with_adventure("wbs_user_2")
    proposal = _script_proposal("object", "SAFE_01", {"unlock_expression": "x = 1"})
    _patch_llm(monkeypatch, {"proposals": [proposal]}, {})

    # Act
    resp = await client.post(
        f"/api/adventures/{tpl_id}/editor/world-builder/suggest",
        headers=_auth_headers("wbs_user_2"),
        json={"instruction": "Guard the safe."},
    )

    # Assert
    payload = resp.json()
    assert payload["proposals"] == []
    assert "object.unlock_expression has invalid syntax" in payload["error"]


async def test_apply_stores_object_hooks_and_guard(client, setup_test_db):
    # Arrange
    proposal = _script_proposal(
        "object",
        "SAFE_01",
        {
            "unlock_expression": "tw.vars.get('lever_pulled', False)",
            "on_unlock_failure_text": "The door will not budge.",
            "on_pickup_script": "tw.vars.set('safe_taken', True)",
            "on_interact_text": "The dial is cold.",
        },
    )

    # Act
    tpl_id, result = await _apply(client, "wbs_user_3", proposal)

    # Assert
    assert result["status_code"] == 200, result
    meta = (await _entity(tpl_id, "SAFE_01")).metadata_json
    assert meta["unlock_expression"] == "tw.vars.get('lever_pulled', False)"
    assert meta["on_unlock_failure_text"] == "The door will not budge."
    assert meta["on_pickup_script"] == "tw.vars.set('safe_taken', True)"
    assert meta["on_interact_text"] == "The dial is cold."


async def test_apply_stores_npc_hooks(client, setup_test_db):
    # Arrange
    proposal = _script_proposal(
        "npc", "OLD_LIBRARIAN", {"on_defeat_script": "tw.player.give_item('SAFE_01')"}
    )

    # Act
    tpl_id, result = await _apply(client, "wbs_user_4", proposal)

    # Assert
    assert result["status_code"] == 200, result
    meta = (await _entity(tpl_id, "OLD_LIBRARIAN")).metadata_json
    assert meta["on_defeat_script"] == "tw.player.give_item('SAFE_01')"


async def test_apply_stores_scene_and_exit_hooks(client, setup_test_db):
    # Arrange
    proposal = _script_proposal(
        "scene", "START", {"on_enter_scene_text": "Dust swirls around your feet."}
    )
    proposal["patches"].append(
        {
            "target_type": "exit",
            "target_id": "START->OBSERVATION_LOUNGE",
            "description": "Guard the door.",
            "field_updates": {
                "unlock_expression": "tw.vars.get('door_code_known', False)",
                "on_exit_used_script": "tw.vars.set('visited_lounge', True)",
            },
        }
    )

    # Act
    tpl_id, result = await _apply(client, "wbs_user_5", proposal)

    # Assert
    assert result["status_code"] == 200, result
    async with TestSessionLocal() as db:
        scene = (
            await db.execute(
                select(WorldScene).where(WorldScene.template_id == tpl_id, WorldScene.id == "START")
            )
        ).scalar_one()
        world_exit = (
            await db.execute(select(WorldExit).where(WorldExit.template_id == tpl_id))
        ).scalar_one()
    assert scene.on_enter_scene_text == "Dust swirls around your feet."
    assert world_exit.unlock_expression == "tw.vars.get('door_code_known', False)"
    assert world_exit.on_exit_used_script == "tw.vars.set('visited_lounge', True)"


async def test_apply_stores_protagonist_hooks_in_avatar_stats(client, setup_test_db):
    # Arrange
    tpl_id = await _seed_user_with_adventure("wbs_user_7")
    async with TestSessionLocal() as db:
        owner_id = (await db.get(AdventureTemplate, tpl_id)).owner_id
        db.add(Avatar(template_id=tpl_id, user_id=owner_id, name="Explorer", stats={"str": 12}))
        await db.commit()
    proposal = _script_proposal(
        "protagonist", None, {"on_hp_change_text": "Your wounds throb.", "hp": 30}
    )

    # Act
    resp = await client.post(
        f"/api/adventures/{tpl_id}/editor/world-builder/apply",
        headers=_auth_headers("wbs_user_7"),
        json={"proposal": proposal},
    )
    result = {"status_code": resp.status_code, **resp.json()}

    # Assert
    assert result["status_code"] == 200, result
    async with TestSessionLocal() as db:
        avatar = await _get_template_avatar(db, tpl_id)
    assert avatar is not None
    assert avatar.stats["on_hp_change_text"] == "Your wounds throb."
    assert avatar.hp == 30


async def test_apply_rejects_a_guard_with_invalid_syntax(client, setup_test_db):
    # Arrange
    proposal = _script_proposal("object", "SAFE_01", {"unlock_expression": "import os"})

    # Act
    _tpl_id, result = await _apply(client, "wbs_user_6", proposal)

    # Assert
    assert result["status_code"] == 400
    assert "unlock_expression" in result["detail"]


def test_world_summary_lists_existing_hooks():
    # Arrange
    payload = type(
        "Payload",
        (),
        {
            "adventure": {},
            "scenes": [],
            "exits": [],
            "npcs": [],
            "objects": [
                {
                    "id": "LEVER",
                    "name": "Lever",
                    "metadata_json": {"on_interact_script": "tw.vars.set('lever_pulled', True)"},
                }
            ],
        },
    )()

    # Act
    summary = _summarize_world_for_fix(payload)

    # Assert
    assert summary["objects"][0]["scripts"] == {
        "on_interact_script": "tw.vars.set('lever_pulled', True)"
    }
