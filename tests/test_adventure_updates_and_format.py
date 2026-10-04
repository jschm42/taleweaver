"""
Tests for adventure format versioning, legacy format detection, and disk update mechanism.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from backend.api.routes.adventures.logic import AdventureLogic
from backend.core.adventure_format import CURRENT_VERSION
from backend.engine.adventure_updates import (
    check_template_update,
    find_matching_file_for_template,
    is_legacy_session,
    is_legacy_template,
    is_version_newer,
    scan_available_adventure_files,
)
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.game_session import GameSession
from backend.models.session_state import SessionState
from backend.models.user import User

def test_adventure_format_current_version():
    """Adventure format current version must be 1.3."""
    assert CURRENT_VERSION == "1.3"


def test_is_version_newer_logic():
    """Verify semver and sequence comparison logic."""
    # Semver higher
    assert is_version_newer(file_version="1.3.0", db_version="1.2.0")
    assert not is_version_newer(file_version="1.1.0", db_version="1.2.0")

    # Sequence upgrade on same version
    assert is_version_newer(
        file_version="1.0.0",
        db_version="1.0.0",
        file_has_sequences=True,
        db_has_sequences=False,
    )
    assert not is_version_newer(
        file_version="1.0.0",
        db_version="1.0.0",
        file_has_sequences=False,
        db_has_sequences=True,
    )

    # Format version comparison
    assert is_version_newer(
        file_format_version="1.3",
        db_format_version="1.0",
    )


def test_legacy_format_detection():
    """Outdated format versions or missing sequences on imported ADVs are flagged as legacy."""
    # 1. Old format version in manifest
    legacy_tpl = AdventureTemplate(
        id="legacy-1",
        title="Old Quest",
        version="1.0.0",
        original_manifest={"version": "1.0", "sequences": []},
        sequences=[],
    )
    assert is_legacy_template(legacy_tpl) is True
    status = check_template_update(legacy_tpl, [])
    assert status["is_legacy_format"] is True
    assert status["can_start"] is False

    # 2. Modern 1.3 template with sequences
    modern_tpl = AdventureTemplate(
        id="modern-1",
        title="New Quest",
        version="1.3.0",
        original_manifest={"version": "1.3", "sequences": [{"id": "seq1", "name": "Act 1"}]},
        sequences=[{"id": "seq1", "name": "Act 1"}],
    )
    assert is_legacy_template(modern_tpl) is False
    status = check_template_update(modern_tpl, [])
    assert status["is_legacy_format"] is False
    assert status["can_start"] is True


@pytest.mark.asyncio
async def test_legacy_template_cannot_start_session(auth_client: AsyncClient, db_session):
    """Attempting to start a session on a legacy format template returns 400 Bad Request."""
    legacy_tpl = AdventureTemplate(
        id="legacy-tpl-start-test",
        title="Ancient Ruins",
        version="1.0.0",
        is_ready=True,
        original_manifest={"version": "1.0", "sequences": []},
        sequences=[],
    )
    db_session.add(legacy_tpl)
    await db_session.commit()

    resp = await auth_client.post(f"/api/adventures/{legacy_tpl.id}/sessions/start")
    assert resp.status_code == 400
    assert "outdated format" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_update_all_endpoint_exists_and_runs(auth_client: AsyncClient):
    """POST /api/adventures/templates/update-all executes cleanly."""
    resp = await auth_client.post("/api/adventures/templates/update-all")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("ok", "success")
    assert "updated_count" in data
    assert isinstance(data["updated_titles"], list)


@pytest.mark.asyncio
async def test_list_templates_returns_update_metadata(auth_client: AsyncClient, db_session):
    """GET /api/adventures/templates returns 200 and includes update/format metadata."""
    user_res = await db_session.execute(select(User).where(User.username == "test_user"))
    user = user_res.scalars().first()

    tpl = AdventureTemplate(
        id="test-list-tpl-metadata",
        title="Metadata Test Quest",
        version="1.0.0",
        is_ready=True,
        owner_id=user.id if user else None,
        original_manifest={"version": "1.0", "sequences": []},
        sequences=[],
    )
    db_session.add(tpl)
    await db_session.commit()

    resp = await auth_client.get("/api/adventures/templates")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    found = next((item for item in data if item["template_id"] == tpl.id), None)
    assert found is not None
    assert "has_update" in found
    assert "is_legacy_format" in found
    assert "can_start" in found
    assert found["is_legacy_format"] is True
    assert found["can_start"] is False


def test_is_legacy_session_logic():
    """Verify is_legacy_session logic for various session, state, and template configurations."""
    # 1. Session linked to legacy template
    legacy_tpl = AdventureTemplate(
        id="tpl-legacy-sess",
        title="Old Quest",
        version="1.0.0",
        original_manifest={"version": "1.0", "sequences": []},
        sequences=[],
    )
    assert is_legacy_session(template=legacy_tpl) is True

    # 2. Modern template with sequences
    modern_tpl = AdventureTemplate(
        id="tpl-modern-sess",
        title="Modern Quest",
        version="1.3.0",
        original_manifest={"version": "1.3", "sequences": [{"id": "s1"}]},
        sequences=[{"id": "s1"}],
    )
    assert is_legacy_session(template=modern_tpl) is False

    # 3. Session without template, but state contains legacy snapshot
    legacy_state = SessionState(
        id="state-leg-snap",
        session_id="sess-leg",
        entity_states={
            AdventureLogic.SESSION_MANIFEST_SNAPSHOT_KEY: {
                "original_manifest": {"version": "1.0", "sequences": []},
            }
        },
    )
    assert is_legacy_session(state=legacy_state) is True

    # 4. Session without template, but state contains modern snapshot
    modern_state = SessionState(
        id="state-mod-snap",
        session_id="sess-mod",
        entity_states={
            AdventureLogic.SESSION_MANIFEST_SNAPSHOT_KEY: {
                "original_manifest": {"version": "1.3", "sequences": [{"id": "s1"}]},
            }
        },
    )
    assert is_legacy_session(state=modern_state) is False


@pytest.mark.asyncio
async def test_sessions_and_chat_return_legacy_format(auth_client: AsyncClient, db_session):
    """GET /api/adventures/sessions and GET /api/adventures/{game_id}/chat return is_legacy_format."""
    user_res = await db_session.execute(select(User).where(User.username == "test_user"))
    user = user_res.scalars().first()

    avatar = Avatar(id="av-leg-test", user_id=user.id, name="Hero")
    db_session.add(avatar)

    legacy_tpl = AdventureTemplate(
        id="tpl-leg-for-session",
        title="Legacy Adventure",
        version="1.0.0",
        is_ready=True,
        owner_id=user.id,
        original_manifest={"version": "1.0", "sequences": []},
        sequences=[],
    )
    db_session.add(legacy_tpl)

    session = GameSession(
        id="sess-leg-test-1",
        user_id=user.id,
        avatar_id=avatar.id,
        template_id=legacy_tpl.id,
        adventure_title="Legacy Adventure",
        status="active",
    )
    db_session.add(session)

    state = SessionState(
        id="state-leg-test-1",
        session_id=session.id,
        user_id=user.id,
        template_id=legacy_tpl.id,
        avatar_id=avatar.id,
        current_scene_id="START",
        entity_states={
            AdventureLogic.SESSION_MANIFEST_SNAPSHOT_KEY: {
                "original_manifest": {"version": "1.0", "sequences": []},
            }
        },
    )
    db_session.add(state)
    await db_session.commit()

    # 1. Test GET /api/adventures/sessions
    resp = await auth_client.get("/api/adventures/sessions")
    assert resp.status_code == 200
    sessions_data = resp.json()
    found_sess = next((s for s in sessions_data if s["game_id"] == session.id), None)
    assert found_sess is not None
    assert "is_legacy_format" in found_sess
    assert found_sess["is_legacy_format"] is True

    # 2. Test GET /api/adventures/{game_id}/chat
    chat_resp = await auth_client.get(f"/api/adventures/{session.id}/chat")
    assert chat_resp.status_code == 200
    chat_data = chat_resp.json()
    assert "is_legacy_format" in chat_data
    assert chat_data["is_legacy_format"] is True


