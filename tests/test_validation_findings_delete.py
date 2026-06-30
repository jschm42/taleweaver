"""Tests for the validation-findings deletion endpoint.

Mirrors the frontend trash icon / Delete-all flow: per-finding delete must
mutate the latest persisted ValidationRun and recompute the *_count columns
so subsequent /validation/latest calls don't return the deleted entries.
"""

import json

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.auth import create_access_token
from backend.main import app
from backend.core.database import get_db
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User
from backend.models.validation_run import ValidationRun
from tests.conftest import TestSessionLocal


def _auth_headers(username: str) -> dict:
    token = create_access_token(data={"sub": username})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def client():
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


async def override_get_db():
    async with TestSessionLocal() as session:
        yield session


async def _seed_template_with_run(*, structural: list[dict], ai: list[dict]) -> tuple[str, str]:
    """Insert user + template + a ValidationRun with the given findings.

    Returns (user_id, tpl_id).
    """
    user = User(username="validation_findings_user", hashed_password="x", role="admin")
    async with TestSessionLocal() as db:
        db.add(user)
        await db.commit()
        user_id = user.id
        tpl_id = "tpl-validation-findings"
        tpl = AdventureTemplate(
            id=tpl_id,
            owner_id=user_id,
            title="Validation Findings Test",
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

        combined = structural + ai
        error_count = sum(1 for e in combined if e.get("severity") == "error")
        warning_count = sum(1 for e in combined if e.get("severity") == "warn")
        run = ValidationRun(
            template_id=tpl_id,
            user_id=user_id,
            structural_findings=json.loads(json.dumps(structural)),
            ai_findings=json.loads(json.dumps(ai)),
            structural_finding_count=len(structural),
            ai_finding_count=len(ai),
            error_count=error_count,
            warning_count=warning_count,
            ai_skipped_reason=None,
            run_at=__import__("datetime").datetime.utcnow(),
        )
        db.add(run)
        await db.commit()
    return user_id, tpl_id


async def test_delete_single_structural_finding(client, setup_test_db):
    """A single structural finding can be removed by (source, code, location)."""
    user_id, tpl_id = await _seed_template_with_run(
        structural=[
            {"severity": "warn", "code": "unreachable_scene", "message": "Scene ORPHAN is unreachable.", "location": "scene:ORPHAN"},
            {"severity": "error", "code": "dead_end", "message": "Scene X has no exit.", "location": "scene:START"},
        ],
        ai=[],
    )
    headers = _auth_headers("validation_findings_user")

    res = await client.post(
        f"/api/adventures/{tpl_id}/editor/validation/latest/findings/delete",
        headers=headers,
        json={
            "findings": [
                {"source": "structural", "code": "unreachable_scene", "location": "scene:ORPHAN"}
            ],
            "delete_all": False,
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["deleted"] == 1
    assert body["structural_remaining"] == 1
    assert body["validation_run"]["structural_finding_count"] == 1
    # The remaining entry is the dead_end one
    remaining = body["validation_run"]["structural_findings"]
    assert len(remaining) == 1
    assert remaining[0]["code"] == "dead_end"


async def test_delete_single_ai_finding(client, setup_test_db):
    """AI bucket is independent of structural bucket and uses the same matching rule."""
    user_id, tpl_id = await _seed_template_with_run(
        structural=[
            {"severity": "warn", "code": "unreachable_scene", "message": "Scene ORPHAN is unreachable.", "location": "scene:ORPHAN"},
        ],
        ai=[
            {"severity": "warn", "code": "narrative_contradiction", "message": "AI feels the stakes are too low.", "location": "scene:START"},
        ],
    )
    headers = _auth_headers("validation_findings_user")

    res = await client.post(
        f"/api/adventures/{tpl_id}/editor/validation/latest/findings/delete",
        headers=headers,
        json={
            "findings": [
                {"source": "ai", "code": "narrative_contradiction", "location": "scene:START"}
            ],
            "delete_all": False,
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["deleted"] == 1
    assert body["structural_remaining"] == 1
    assert body["ai_remaining"] == 0


async def test_delete_does_not_match_across_buckets(client, setup_test_db):
    """Same code+location in different buckets is matched only against the explicit source."""
    user_id, tpl_id = await _seed_template_with_run(
        structural=[
            {"severity": "warn", "code": "X", "message": "structural X", "location": "scene:START"},
        ],
        ai=[
            {"severity": "warn", "code": "X", "message": "ai X", "location": "scene:START"},
        ],
    )
    headers = _auth_headers("validation_findings_user")

    res = await client.post(
        f"/api/adventures/{tpl_id}/editor/validation/latest/findings/delete",
        headers=headers,
        json={
            "findings": [
                {"source": "structural", "code": "X", "location": "scene:START"}
            ],
            "delete_all": False,
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["deleted"] == 1
    # AI entry survives
    assert body["ai_remaining"] == 1
    assert body["structural_remaining"] == 0


async def test_delete_empty_location_matches_unscoped_findings(client, setup_test_db):
    """An entry with location=None (stored as None or empty) matches when location=''."""
    user_id, tpl_id = await _seed_template_with_run(
        structural=[
            {"severity": "warn", "code": "ADV_GLOBAL", "message": "global issue", "location": None},
        ],
        ai=[],
    )
    headers = _auth_headers("validation_findings_user")

    res = await client.post(
        f"/api/adventures/{tpl_id}/editor/validation/latest/findings/delete",
        headers=headers,
        json={
            "findings": [
                {"source": "structural", "code": "ADV_GLOBAL", "location": ""}
            ],
            "delete_all": False,
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["deleted"] == 1
    assert body["structural_remaining"] == 0


async def test_delete_all_wipes_both_buckets(client, setup_test_db):
    """delete_all=True must empty both structural and AI buckets in one round-trip."""
    user_id, tpl_id = await _seed_template_with_run(
        structural=[
            {"severity": "warn", "code": "X1", "message": "1", "location": "a"},
            {"severity": "error", "code": "X2", "message": "2", "location": "b"},
        ],
        ai=[
            {"severity": "warn", "code": "Y1", "message": "1", "location": "c"},
        ],
    )
    headers = _auth_headers("validation_findings_user")

    res = await client.post(
        f"/api/adventures/{tpl_id}/editor/validation/latest/findings/delete",
        headers=headers,
        json={"findings": [], "delete_all": True},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["deleted"] == 3
    assert body["structural_remaining"] == 0
    assert body["ai_remaining"] == 0
    assert body["validation_run"]["error_count"] == 0
    assert body["validation_run"]["warning_count"] == 0


async def test_delete_recomputes_count_columns(client, setup_test_db):
    """After deletion, structural_finding_count/error_count/warning_count must reflect the surviving entries."""
    user_id, tpl_id = await _seed_template_with_run(
        structural=[
            {"severity": "error", "code": "E1", "message": "e", "location": "a"},
            {"severity": "warn", "code": "W1", "message": "w", "location": "b"},
            {"severity": "warn", "code": "W2", "message": "w", "location": "c"},
        ],
        ai=[],
    )
    headers = _auth_headers("validation_findings_user")

    res = await client.post(
        f"/api/adventures/{tpl_id}/editor/validation/latest/findings/delete",
        headers=headers,
        json={
            "findings": [
                {"source": "structural", "code": "E1", "location": "a"},
                {"source": "structural", "code": "W1", "location": "b"},
            ],
            "delete_all": False,
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["validation_run"]["structural_finding_count"] == 1
    assert body["validation_run"]["error_count"] == 0
    assert body["validation_run"]["warning_count"] == 1


async def test_delete_nonexistent_signature_is_noop(client, setup_test_db):
    """Deleting a signature that doesn't exist simply deletes 0 and leaves the row untouched."""
    user_id, tpl_id = await _seed_template_with_run(
        structural=[
            {"severity": "warn", "code": "REAL", "message": "real", "location": "a"},
        ],
        ai=[],
    )
    headers = _auth_headers("validation_findings_user")

    res = await client.post(
        f"/api/adventures/{tpl_id}/editor/validation/latest/findings/delete",
        headers=headers,
        json={
            "findings": [
                {"source": "structural", "code": "GHOST", "location": "x"}
            ],
            "delete_all": False,
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["deleted"] == 0
    assert body["structural_remaining"] == 1


async def test_delete_then_latest_does_not_return_deleted(client, setup_test_db):
    """End-to-end: after deletion, GET /validation/latest must not echo the deleted entry."""
    user_id, tpl_id = await _seed_template_with_run(
        structural=[
            {"severity": "warn", "code": "DROPPED", "message": "drop me", "location": "scene:X"},
            {"severity": "warn", "code": "KEEPER", "message": "keep me", "location": "scene:Y"},
        ],
        ai=[],
    )
    headers = _auth_headers("validation_findings_user")

    del_res = await client.post(
        f"/api/adventures/{tpl_id}/editor/validation/latest/findings/delete",
        headers=headers,
        json={
            "findings": [
                {"source": "structural", "code": "DROPPED", "location": "scene:X"}
            ],
            "delete_all": False,
        },
    )
    assert del_res.status_code == 200, del_res.text

    latest_res = await client.get(
        f"/api/adventures/{tpl_id}/editor/validation/latest",
        headers=headers,
    )
    assert latest_res.status_code == 200, latest_res.text
    body = latest_res.json()
    assert body is not None
    codes = {entry["code"] for entry in body["structural_findings"]}
    assert "DROPPED" not in codes
    assert "KEEPER" in codes


async def test_delete_rejects_unknown_template(client, setup_test_db):
    """Belt-and-suspenders: ownership check triggers 404 before any DB write."""
    user = User(username="validation_findings_user", hashed_password="x", role="admin")
    async with TestSessionLocal() as db:
        db.add(user)
        await db.commit()
    headers = _auth_headers("validation_findings_user")
    res = await client.post(
        "/api/adventures/tpl-does-not-exist/editor/validation/latest/findings/delete",
        headers=headers,
        json={"findings": [], "delete_all": False},
    )
    assert res.status_code == 404, res.text


async def test_delete_with_no_persisted_run_is_clean_noop(client, setup_test_db):
    """If the user has never run validation, the endpoint must respond cleanly (not crash)."""
    user = User(username="orphan_user", hashed_password="x", role="admin")
    async with TestSessionLocal() as db:
        db.add(user)
        await db.commit()
        tpl_id = "tpl-no-validation-yet"
        tpl = AdventureTemplate(
            id=tpl_id,
            owner_id=user.id,
            title="No Validation",
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
        await db.commit()

    headers = _auth_headers("orphan_user")
    res = await client.post(
        f"/api/adventures/{tpl_id}/editor/validation/latest/findings/delete",
        headers=headers,
        json={"findings": [], "delete_all": True},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["deleted"] == 0
    assert body["validation_run"] is None
