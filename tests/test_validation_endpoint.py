"""Integration tests for the editor validation endpoint."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.auth import create_access_token
from backend.main import app
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User
from tests.conftest import TestSessionLocal


async def _seed_adventure(db: AsyncSession, *, owner: User) -> str:
    template = AdventureTemplate(
        id="tpl-val-1",
        owner_id=owner.id,
        title="Validation Test Adventure",
        version="1.0",
        rule_enforcement_mode="rpg",
        is_ready=True,
        creation_status="Ready",
        generate_scene_images=False,
        generate_npc_images=False,
        generate_item_images=False,
        teaser="t",
        rules="r" * 200,
        plot="p",
        intro_text="i",
        walkthrough="w" * 100,
        completed_condition="done",
        gameover_condition="lost",
        tts_director_notes="notes",
        quests=[],
    )
    db.add(template)
    await db.commit()
    return template.id


def _auth_headers(username: str) -> dict:
    token = create_access_token(data={"sub": username})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def client():
    app.dependency_overrides.clear()
    from backend.core.database import get_db
    from tests.conftest import override_get_db
    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


async def test_structural_only_runs_no_ai_call(client, setup_test_db, monkeypatch):
    """include_ai=False must skip the LLM call entirely."""
    user = User(
        username="val_user",
        hashed_password="x",
        role="admin",
        llm_settings={"complex_model_provider": "openai", "complex_model": "gpt-4o"},
    )
    async with TestSessionLocal() as db:
        db.add(user)
        await db.commit()
        tpl_id = await _seed_adventure(db, owner=user)

    ai_called = {"count": 0}

    class _FakeLLM:
        def __init__(self, *args, **kwargs):
            pass

        async def aexecute_complex_task(self, **kwargs):
            ai_called["count"] += 1
            return []

    from backend.api.routes.adventures import editor as editor_module
    monkeypatch.setattr(editor_module, "GameMasterLLM", _FakeLLM)

    resp = await client.post(
        f"/api/adventures/{tpl_id}/editor/validate",
        headers=_auth_headers("val_user"),
        json={"include_ai": False},
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert "structural_findings" in payload
    assert payload["ai_skipped_reason"] == "ai_not_requested"
    assert ai_called["count"] == 0


async def test_full_validation_runs_ai(client, setup_test_db, monkeypatch):
    """include_ai=True triggers the AI pass."""
    user = User(
        username="val_user_2",
        hashed_password="x",
        role="admin",
        llm_settings={"complex_model_provider": "openai", "complex_model": "gpt-4o"},
    )
    async with TestSessionLocal() as db:
        db.add(user)
        await db.commit()
        tpl_id = await _seed_adventure(db, owner=user)

    class _FakeFinding:
        def __init__(self, code, message, location=None, context=None):
            self.code = code
            self.message = message
            self.location = location
            self.context = context

    captured = {}

    class _FakeResponse:
        def __init__(self, findings):
            self.findings = findings

    class _FakeLLM:
        def __init__(self, *args, **kwargs):
            pass

        async def aexecute_complex_task(self, *, system_prompt, user_prompt, response_model, model, **kwargs):
            captured["system"] = system_prompt[:80]
            captured["user"] = user_prompt[:80]
            captured["model"] = model
            # Verify the response_model exposes model_json_schema (regression
            # for the "type object 'list' has no attribute 'model_json_schema'"
            # bug). The endpoint must now pass a single Pydantic model, not
            # List[Finding].
            schema = response_model.model_json_schema()
            assert "findings" in schema.get("properties", {}), (
                "AIValidationResponse must wrap findings under a top-level key"
            )
            return _FakeResponse(
                findings=[
                    _FakeFinding(
                        code="orphaned_container_code",
                        message="Container has code '42' but no hint in the world.",
                        location="object:safe_01",
                        context={"container_id": "safe_01", "code": "42"},
                    ),
                ]
            )

    from backend.api.routes.adventures import editor as editor_module
    monkeypatch.setattr(editor_module, "GameMasterLLM", _FakeLLM)

    resp = await client.post(
        f"/api/adventures/{tpl_id}/editor/validate",
        headers=_auth_headers("val_user_2"),
        json={"include_ai": True},
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert len(payload["ai_findings"]) == 1
    assert payload["ai_findings"][0]["code"] == "orphaned_container_code"
    assert payload["ai_findings"][0]["severity"] == "warn"
    assert payload["ai_skipped_reason"] is None
    assert "linter" in captured["system"]
    # Regression: model must be passed explicitly. Previously aexecute_complex_task
    # was invoked without ``model``, raising "missing 1 required positional argument".
    assert captured["model"] == "gpt-4o"


async def test_ai_validation_handles_empty_findings(client, setup_test_db, monkeypatch):
    """When the LLM reports no issues, ``findings`` must default to []."""
    user = User(
        username="val_user_empty",
        hashed_password="x",
        role="admin",
        llm_settings={"complex_model_provider": "deepseek", "complex_model": "deepseek-chat"},
    )
    async with TestSessionLocal() as db:
        db.add(user)
        await db.commit()
        tpl_id = await _seed_adventure(db, owner=user)

    class _FakeEmptyResponse:
        findings = []

    class _FakeLLM:
        def __init__(self, *args, **kwargs):
            pass

        async def aexecute_complex_task(self, **kwargs):
            return _FakeEmptyResponse()

    from backend.api.routes.adventures import editor as editor_module
    monkeypatch.setattr(editor_module, "GameMasterLLM", _FakeLLM)

    resp = await client.post(
        f"/api/adventures/{tpl_id}/editor/validate",
        headers=_auth_headers("val_user_empty"),
        json={"include_ai": True},
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["ai_findings"] == []
    assert payload["ai_skipped_reason"] is None


async def test_ai_skipped_when_scene_count_exceeds_limit(client, setup_test_db, monkeypatch):
    """include_ai=True on a large adventure returns scene_limit_exceeded."""
    user = User(
        username="val_user_3",
        hashed_password="x",
        role="admin",
    )
    async with TestSessionLocal() as db:
        db.add(user)
        await db.commit()
        tpl_id = await _seed_adventure(db, owner=user)

    # Override the limit for test speed. Any value < 0 guarantees the gate
    # fires regardless of the seed data.
    from backend.core import config as config_module
    monkeypatch.setattr(config_module.settings, "MAX_AI_VALIDATION_SCENES", -1)

    ai_called = {"count": 0}

    class _FakeLLM:
        def __init__(self, *args, **kwargs):
            pass

        async def aexecute_complex_task(self, **kwargs):
            ai_called["count"] += 1
            return []

    from backend.api.routes.adventures import editor as editor_module
    monkeypatch.setattr(editor_module, "GameMasterLLM", _FakeLLM)

    resp = await client.post(
        f"/api/adventures/{tpl_id}/editor/validate",
        headers=_auth_headers("val_user_3"),
        json={"include_ai": True},
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["ai_skipped_reason"] == "scene_limit_exceeded"
    assert payload["ai_findings"] == []
    assert ai_called["count"] == 0


async def test_ai_skipped_when_llm_call_fails(client, setup_test_db, monkeypatch):
    """When the LLM call raises, the response returns ai_error and no findings."""
    user = User(
        username="val_user_4",
        hashed_password="x",
        role="admin",
    )
    async with TestSessionLocal() as db:
        db.add(user)
        await db.commit()
        tpl_id = await _seed_adventure(db, owner=user)

    class _FakeLLM:
        def __init__(self, *args, **kwargs):
            pass

        async def aexecute_complex_task(self, **kwargs):
            raise RuntimeError("simulated upstream failure")

    from backend.api.routes.adventures import editor as editor_module
    monkeypatch.setattr(editor_module, "GameMasterLLM", _FakeLLM)

    resp = await client.post(
        f"/api/adventures/{tpl_id}/editor/validate",
        headers=_auth_headers("val_user_4"),
        json={"include_ai": True},
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["ai_skipped_reason"] == "ai_error"
    assert payload["ai_findings"] == []


async def test_unauthorized_for_non_owner(client, setup_test_db):
    owner = User(username="val_owner", hashed_password="x", role="admin")
    intruder = User(username="val_intruder", hashed_password="x", role="user")
    async with TestSessionLocal() as db:
        db.add(owner)
        db.add(intruder)
        await db.commit()
        tpl_id = await _seed_adventure(db, owner=owner)

    resp = await client.post(
        f"/api/adventures/{tpl_id}/editor/validate",
        headers=_auth_headers("val_intruder"),
        json={"include_ai": False},
    )
    assert resp.status_code == 404


async def test_unauthenticated_request_rejected(client, setup_test_db):
    owner = User(username="val_owner2", hashed_password="x", role="admin")
    async with TestSessionLocal() as db:
        db.add(owner)
        await db.commit()
        tpl_id = await _seed_adventure(db, owner=owner)

    resp = await client.post(
        f"/api/adventures/{tpl_id}/editor/validate",
        json={"include_ai": False},
    )
    assert resp.status_code == 401


async def test_structural_findings_includes_real_issues(client, setup_test_db, monkeypatch):
    """Endpoint emits an unreachable_scene finding when an extra scene is unreachable."""
    from backend.models.world_entity import WorldScene
    user = User(username="val_user_5", hashed_password="x", role="admin")
    async with TestSessionLocal() as db:
        db.add(user)
        await db.commit()
        tpl_id = await _seed_adventure(db, owner=user)
        # Seed two scenes: START (reachable) and ORPHAN (no incoming exit).
        db.add(WorldScene(id="START", template_id=tpl_id, label="Start", description="Start"))
        db.add(WorldScene(id="ORPHAN", template_id=tpl_id, label="Orphan", description="Orphan"))
        await db.commit()

    resp = await client.post(
        f"/api/adventures/{tpl_id}/editor/validate",
        headers=_auth_headers("val_user_5"),
        json={"include_ai": False},
    )
    assert resp.status_code == 200, resp.text
    findings = resp.json()["structural_findings"]
    codes = {f["code"] for f in findings}
    # ORPHAN has no incoming exit and is unreachable from START.
    assert "unreachable_scene" in codes
    assert any(
        f["code"] == "unreachable_scene" and f.get("location") == "scene:ORPHAN"
        for f in findings
    )


def test_summarize_for_ai_handles_datetime_objects():
    """Regression: payloads from SQLAlchemy ORM contain ``datetime``
    instances (created_at / updated_at) that previously broke
    ``json.dumps`` in the AI path.
    """
    import datetime as dt
    import json

    from backend.api.routes.adventures.editor import _summarize_for_ai

    payload = {
        "adventure": {
            "title": "Test",
            "created_at": dt.datetime(2026, 1, 1, 12, 0, 0),
            "updated_at": dt.datetime(2026, 1, 2, 9, 30, 0),
            "start_scene_id": "START",
        },
        "scenes": [
            {
                "id": "START",
                "label": "Start",
                "created_at": dt.datetime(2026, 1, 1, 12, 0, 0),
                "description": "x" * 3000,  # exceeds max_field_len
            }
        ],
        "exits": [],
        "npcs": [],
        "objects": [],
        "entities_all": [],
    }

    summary = _summarize_for_ai(payload)

    # Round-trips through json.dumps without raising.
    dumped = json.dumps(summary)
    reparsed = json.loads(dumped)

    assert reparsed["adventure"]["created_at"].startswith("2026-01-01T12:00:00")
    assert reparsed["adventure"]["updated_at"].startswith("2026-01-02T09:30:00")
    assert reparsed["scenes"][0]["created_at"].startswith("2026-01-01T12:00:00")
    # Long text was truncated.
    assert reparsed["scenes"][0]["description"].endswith("...")


def test_summarize_for_ai_handles_pydantic_payload_with_datetime():
    """Pydantic v2 dumps keep datetime fields; the helper must coerce them."""
    import datetime as dt
    import json

    from pydantic import BaseModel

    from backend.api.routes.adventures.editor import _summarize_for_ai

    class _Model(BaseModel):
        created_at: dt.datetime
        title: str

    payload = _Model(
        created_at=dt.datetime(2026, 6, 1, 8, 0, 0),
        title="Adventure",
    )

    summary = _summarize_for_ai(payload.model_dump())
    dumped = json.dumps(summary)
    reparsed = json.loads(dumped)

    assert reparsed["created_at"].startswith("2026-06-01T08:00:00")
    assert reparsed["title"] == "Adventure"