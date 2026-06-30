"""Tests for the persistent ValidationRun storage and /validation/latest endpoint."""

from typing import List

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.auth import create_access_token
from backend.main import app
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User
from backend.models.validation_run import ValidationRun
from backend.models.world_entity import WorldScene
from tests.conftest import TestSessionLocal


def _auth_headers(username: str) -> dict:
    token = create_access_token(data={"sub": username})
    return {"Authorization": f"Bearer {token}"}


async def _seed_validation_adventure(db: AsyncSession, *, owner: User) -> str:
    tpl = AdventureTemplate(
        id="tpl-persist-1",
        owner_id=owner.id,
        title="Persist Test",
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
    db.add(WorldScene(id="START", template_id=tpl.id, label="Start", description="start"))
    db.add(WorldScene(id="ORPHAN", template_id=tpl.id, label="Orphan", description="orphan"))
    await db.commit()
    return tpl.id


@pytest.fixture
async def client():
    app.dependency_overrides.clear()
    from backend.core.database import get_db
    from tests.conftest import override_get_db
    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


async def test_validation_run_is_persisted_after_run(client, setup_test_db):
    """POST /editor/validate must write one ValidationRun row per call."""
    user = User(
        username="persist_user_1",
        hashed_password="x",
        role="admin",
    )
    async with TestSessionLocal() as db:
        db.add(user)
        await db.commit()
        tpl_id = await _seed_validation_adventure(db, owner=user)

    resp = await client.post(
        f"/api/adventures/{tpl_id}/editor/validate",
        headers=_auth_headers("persist_user_1"),
        json={"include_ai": False},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ai_skipped_reason"] == "ai_not_requested"

    async with TestSessionLocal() as db:
        res = await db.execute(
            select(ValidationRun).where(ValidationRun.template_id == tpl_id)
        )
        runs: List[ValidationRun] = list(res.scalars().all())
        assert len(runs) == 1
        run = runs[0]
        assert run.user_id == user.id
        assert run.include_ai is False
        assert run.ai_skipped_reason == "ai_not_requested"
        assert run.structural_finding_count == len(run.structural_findings)
        assert run.ai_finding_count == len(run.ai_findings)
        assert run.error_count + run.warning_count == (
            run.structural_finding_count + run.ai_finding_count
        )
        assert run.run_at is not None


async def test_latest_validation_returns_null_when_no_run(client, setup_test_db):
    user = User(username="persist_user_2", hashed_password="x", role="admin")
    async with TestSessionLocal() as db:
        db.add(user)
        await db.commit()
        tpl_id = await _seed_validation_adventure(db, owner=user)

    resp = await client.get(
        f"/api/adventures/{tpl_id}/editor/validation/latest",
        headers=_auth_headers("persist_user_2"),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() is None


async def test_latest_validation_returns_last_run_per_user(client, setup_test_db):
    """Two runs → /latest returns the most recent one."""
    user = User(username="persist_user_3", hashed_password="x", role="admin")
    async with TestSessionLocal() as db:
        db.add(user)
        await db.commit()
        tpl_id = await _seed_validation_adventure(db, owner=user)

    for _ in range(2):
        post = await client.post(
            f"/api/adventures/{tpl_id}/editor/validate",
            headers=_auth_headers("persist_user_3"),
            json={"include_ai": False},
        )
        assert post.status_code == 200, post.text

    get = await client.get(
        f"/api/adventures/{tpl_id}/editor/validation/latest",
        headers=_auth_headers("persist_user_3"),
    )
    assert get.status_code == 200, get.text
    payload = get.json()
    assert payload is not None
    assert payload["run_at"]
    assert payload["ai_skipped_reason"] == "ai_not_requested"

    async with TestSessionLocal() as db:
        res = await db.execute(
            select(ValidationRun).where(ValidationRun.template_id == tpl_id)
        )
        assert len(list(res.scalars().all())) == 2


async def test_validation_runs_are_scoped_per_user(client, setup_test_db):
    """User A's findings must never be returned to user B."""
    owner = User(username="persist_owner", hashed_password="x", role="admin")
    owner.id = "owner-uuid"
    other = User(username="persist_other", hashed_password="x", role="user")
    async with TestSessionLocal() as db:
        db.add(owner)
        db.add(other)
        await db.commit()
        tpl_id = await _seed_validation_adventure(db, owner=owner)

    post = await client.post(
        f"/api/adventures/{tpl_id}/editor/validate",
        headers=_auth_headers("persist_owner"),
        json={"include_ai": False},
    )
    assert post.status_code == 200, post.text

    other_get = await client.get(
        f"/api/adventures/{tpl_id}/editor/validation/latest",
        headers=_auth_headers("persist_other"),
    )
    assert other_get.status_code == 404

    owner_get = await client.get(
        f"/api/adventures/{tpl_id}/editor/validation/latest",
        headers=_auth_headers("persist_owner"),
    )
    assert owner_get.status_code == 200, owner_get.text
    assert owner_get.json() is not None


async def test_validation_template_delete_cascades_to_runs(client, setup_test_db):
    """The FK from validation_runs.template_id -> adventure_templates.id must use ON DELETE CASCADE."""
    from sqlalchemy import ForeignKey, inspect as _inspect

    fk_columns = list(
        ValidationRun.__table__.c.template_id.foreign_keys
    )
    assert fk_columns, "ValidationRun.template_id must be a FK"
    fk: ForeignKey = fk_columns[0]
    assert fk.ondelete == "CASCADE", (
        "ValidationRun.template_id FK must declare ondelete='CASCADE' so deleting "
        "an adventure removes its validation history."
    )

    user_fks = list(ValidationRun.__table__.c.user_id.foreign_keys)
    assert user_fks, "ValidationRun.user_id must be a FK"
    assert user_fks[0].ondelete == "CASCADE"


async def test_validation_persists_ai_when_requested(client, setup_test_db, monkeypatch):
    """include_ai=True persists AI findings alongside structural ones."""

    user = User(
        username="persist_user_5",
        hashed_password="x",
        role="admin",
        llm_settings={"complex_model_provider": "openai", "complex_model": "gpt-4o"},
    )
    async with TestSessionLocal() as db:
        db.add(user)
        await db.commit()
        tpl_id = await _seed_validation_adventure(db, owner=user)

    class _Finding:
        def __init__(self, code, message):
            self.code = code
            self.message = message
            self.location = None
            self.context = None

    class _Resp:
        findings = [
            _Finding("orphaned_container_code", "Container orphan.")
        ]

    class _FakeLLM:
        def __init__(self, *args, **kwargs):
            pass

        async def aexecute_complex_task(self, **kwargs):
            return _Resp()

    from backend.api.routes.adventures import editor as editor_module
    monkeypatch.setattr(editor_module, "GameMasterLLM", _FakeLLM)

    post = await client.post(
        f"/api/adventures/{tpl_id}/editor/validate",
        headers=_auth_headers("persist_user_5"),
        json={"include_ai": True},
    )
    assert post.status_code == 200, post.text
    payload = post.json()
    assert len(payload["ai_findings"]) == 1

    get = await client.get(
        f"/api/adventures/{tpl_id}/editor/validation/latest",
        headers=_auth_headers("persist_user_5"),
    )
    assert get.status_code == 200, get.text
    latest = get.json()
    assert latest is not None
    assert len(latest["ai_findings"]) == 1
    assert latest["ai_findings"][0]["code"] == "orphaned_container_code"
    assert latest["ai_finding_count"] == 1
