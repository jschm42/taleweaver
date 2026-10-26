"""Integration tests for the World-Builder instruction suggest / apply endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from backend.main import app
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User
from backend.models.world_entity import WorldEntity
from tests.conftest import TestSessionLocal
from tests.test_ai_fix_endpoint import _auth_headers, _seed_simple_adventure


@pytest.fixture
async def client():
    app.dependency_overrides.clear()
    from backend.core.database import get_db
    from tests.conftest import override_get_db

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


async def _seed_user_with_adventure(username: str) -> str:
    user = User(
        username=username,
        hashed_password="x",
        role="admin",
        llm_settings={"complex_model_provider": "openai", "complex_model": "gpt-4o"},
    )
    async with TestSessionLocal() as db:
        db.add(user)
        await db.commit()
        return await _seed_simple_adventure(db, owner=user)


def _patch_llm(monkeypatch, wrapper, captured: dict) -> None:
    class _FakeLLM:
        def __init__(self, *args, **kwargs):
            pass

        async def aexecute_complex_task(
            self, *, system_prompt, user_prompt, response_model, model, **kwargs
        ):
            captured["system_prompt"] = system_prompt
            captured["user_prompt"] = user_prompt
            captured["schema_keys"] = list(
                response_model.model_json_schema().get("properties", {}).keys()
            )
            if isinstance(wrapper, Exception):
                raise wrapper
            return response_model.model_validate(wrapper)

    from backend.api.routes.adventures.editing import ai_fix_llm

    monkeypatch.setattr(ai_fix_llm, "GameMasterLLM", _FakeLLM)


def _npc_proposal(title: str, description: str) -> dict:
    return {
        "title": title,
        "summary": "Rewrite the librarian's description.",
        "patches": [
            {
                "target_type": "npc",
                "target_id": "OLD_LIBRARIAN",
                "description": "Change the librarian's demeanour.",
                "field_updates": {"description": description},
            }
        ],
    }


async def test_suggest_returns_at_most_three_proposals(client, setup_test_db, monkeypatch):
    # Arrange
    tpl_id = await _seed_user_with_adventure("wb_user_1")
    captured: dict = {}
    wrapper = {"proposals": [_npc_proposal(f"Option {i}", f"Grumpy {i}.") for i in range(5)]}
    _patch_llm(monkeypatch, wrapper, captured)

    # Act
    resp = await client.post(
        f"/api/adventures/{tpl_id}/editor/world-builder/suggest",
        headers=_auth_headers("wb_user_1"),
        json={"instruction": "Make the librarian grumpier."},
    )

    # Assert
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["instruction"] == "Make the librarian grumpier."
    assert [p["title"] for p in payload["proposals"]] == ["Option 0", "Option 1", "Option 2"]
    assert payload["error"] is None
    assert "Make the librarian grumpier." in captured["user_prompt"]
    assert "OLD_LIBRARIAN" in captured["user_prompt"]
    assert "World-Builder" in captured["system_prompt"]
    assert {"proposals", "note"} <= set(captured["schema_keys"])


async def test_suggest_passes_through_note_when_declined(client, setup_test_db, monkeypatch):
    # Arrange
    tpl_id = await _seed_user_with_adventure("wb_user_2")
    wrapper = {"proposals": [], "note": "  Creating new scenes is not supported.  "}
    _patch_llm(monkeypatch, wrapper, {})

    # Act
    resp = await client.post(
        f"/api/adventures/{tpl_id}/editor/world-builder/suggest",
        headers=_auth_headers("wb_user_2"),
        json={"instruction": "Add a dragon lair scene."},
    )

    # Assert
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["proposals"] == []
    assert payload["note"] == "Creating new scenes is not supported."
    assert payload["error"] is None


async def test_suggest_drops_disallowed_fields_and_reports_error(
    client, setup_test_db, monkeypatch
):
    # Arrange
    tpl_id = await _seed_user_with_adventure("wb_user_3")
    proposal = _npc_proposal("Bad", "x")
    proposal["patches"][0]["field_updates"] = {"hitpoints_secret": 99}
    _patch_llm(monkeypatch, {"proposals": [proposal]}, {})

    # Act
    resp = await client.post(
        f"/api/adventures/{tpl_id}/editor/world-builder/suggest",
        headers=_auth_headers("wb_user_3"),
        json={"instruction": "Buff the librarian."},
    )

    # Assert
    payload = resp.json()
    assert payload["proposals"] == []
    assert "npc.hitpoints_secret" in payload["error"]


async def test_suggest_llm_failure_returns_200_with_error(client, setup_test_db, monkeypatch):
    # Arrange
    tpl_id = await _seed_user_with_adventure("wb_user_4")
    _patch_llm(monkeypatch, RuntimeError("boom"), {})

    # Act
    resp = await client.post(
        f"/api/adventures/{tpl_id}/editor/world-builder/suggest",
        headers=_auth_headers("wb_user_4"),
        json={"instruction": "Make the librarian grumpier."},
    )

    # Assert
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["proposals"] == []
    assert payload["error"]


async def test_suggest_rejects_blank_instruction(client, setup_test_db):
    # Arrange
    tpl_id = await _seed_user_with_adventure("wb_user_5")

    # Act
    resp = await client.post(
        f"/api/adventures/{tpl_id}/editor/world-builder/suggest",
        headers=_auth_headers("wb_user_5"),
        json={"instruction": ""},
    )

    # Assert
    assert resp.status_code == 422


async def test_suggest_forbidden_for_non_owner(client, setup_test_db, monkeypatch):
    # Arrange
    tpl_id = await _seed_user_with_adventure("wb_owner")
    async with TestSessionLocal() as db:
        db.add(User(username="wb_intruder", hashed_password="x", role="user"))
        await db.commit()
    _patch_llm(monkeypatch, {"proposals": []}, {})

    # Act
    resp = await client.post(
        f"/api/adventures/{tpl_id}/editor/world-builder/suggest",
        headers=_auth_headers("wb_intruder"),
        json={"instruction": "Make the librarian grumpier."},
    )

    # Assert
    assert resp.status_code in (403, 404)


async def test_apply_updates_entities(client, setup_test_db):
    # Arrange
    tpl_id = await _seed_user_with_adventure("wb_user_6")
    proposal = _npc_proposal("Grumpy", "A scowling, impatient keeper.")
    proposal["patches"].append(
        {
            "target_type": "adventure",
            "target_id": None,
            "description": "Mention the mood in the teaser.",
            "field_updates": {"teaser": "Beware the grumpy librarian."},
        }
    )

    # Act
    resp = await client.post(
        f"/api/adventures/{tpl_id}/editor/world-builder/apply",
        headers=_auth_headers("wb_user_6"),
        json={"proposal": proposal},
    )

    # Assert
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["status"] == "applied"
    assert payload["applied_targets"] == ["npc:OLD_LIBRARIAN", "adventure:"]
    async with TestSessionLocal() as db:
        npc = (
            await db.execute(
                select(WorldEntity).where(
                    WorldEntity.template_id == tpl_id, WorldEntity.id == "OLD_LIBRARIAN"
                )
            )
        ).scalar_one_or_none()
        tpl = await db.get(AdventureTemplate, tpl_id)
    assert npc is not None and npc.description == "A scowling, impatient keeper."
    assert tpl is not None and tpl.teaser == "Beware the grumpy librarian."


async def test_apply_without_patches_is_no_op(client, setup_test_db):
    # Arrange
    tpl_id = await _seed_user_with_adventure("wb_user_7")

    # Act
    resp = await client.post(
        f"/api/adventures/{tpl_id}/editor/world-builder/apply",
        headers=_auth_headers("wb_user_7"),
        json={"proposal": {"title": "Empty", "summary": "Nothing.", "patches": []}},
    )

    # Assert
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "no_op"
