"""
Tests for adventure format versioning, legacy format detection, and disk update mechanism.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from backend.api.routes.adventures.logic import AdventureLogic
from backend.core.adventure_format import CURRENT_VERSION
from backend.engine.adventures.adventure_updates import (
    check_template_update,
    is_legacy_session,
    is_legacy_template,
    is_version_newer,
)
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.game_session import GameSession
from backend.models.session_state import SessionState
from backend.models.user import User


def test_adventure_format_current_version():
    """Adventure format current version must be 1.3.1 (CONSTRUCTABLE recipes)."""
    assert CURRENT_VERSION == "1.3.1"


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

    # 2. 1.3 predates CONSTRUCTABLE recipes (1.3.1): still playable, but deprecated
    pre_recipe_tpl = AdventureTemplate(
        id="pre-recipe-1",
        title="Pre-recipe Quest",
        version="1.3.0",
        original_manifest={"version": "1.3", "sequences": [{"id": "seq1", "name": "Act 1"}]},
        sequences=[{"id": "seq1", "name": "Act 1"}],
    )
    assert is_legacy_template(pre_recipe_tpl) is False
    status = check_template_update(pre_recipe_tpl, [])
    assert status["can_start"] is True
    assert status["is_deprecated"] is True

    # 3. Modern 1.3.1 template with sequences
    modern_tpl = AdventureTemplate(
        id="modern-1",
        title="New Quest",
        version="1.3.1",
        original_manifest={"version": "1.3.1", "sequences": [{"id": "seq1", "name": "Act 1"}]},
        sequences=[{"id": "seq1", "name": "Act 1"}],
    )
    assert is_legacy_template(modern_tpl) is False
    status = check_template_update(modern_tpl, [])
    assert status["is_legacy_format"] is False
    assert status["is_deprecated"] is False
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
        version="1.3.1",
        original_manifest={"version": "1.3.1", "sequences": [{"id": "s1"}]},
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
                "original_manifest": {"version": "1.3.1", "sequences": [{"id": "s1"}]},
            }
        },
    )
    assert is_legacy_session(state=modern_state) is False


def test_current_adventure_without_sequences_is_playable():
    """Removing every sequence must not force a migration: only the format version counts."""
    # Arrange
    no_sequences_tpl = AdventureTemplate(
        id="tpl-no-seq",
        title="Sandbox Lab",
        version="1.0.0",
        original_manifest={"format_version": CURRENT_VERSION, "sequences": []},
        sequences=[],
    )
    no_sequences_state = SessionState(
        id="state-no-seq",
        session_id="sess-no-seq",
        entity_states={
            AdventureLogic.SESSION_MANIFEST_SNAPSHOT_KEY: {
                "original_manifest": {"format_version": CURRENT_VERSION, "sequences": []},
            }
        },
    )

    # Act
    status = check_template_update(no_sequences_tpl, [])

    # Assert
    assert is_legacy_template(no_sequences_tpl) is False
    assert status["is_legacy_format"] is False
    assert status["can_start"] is True
    assert is_legacy_session(template=no_sequences_tpl, state=no_sequences_state) is False


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


@pytest.mark.asyncio
async def test_migrate_legacy_template(auth_client: AsyncClient, db_session):
    """Migrating a legacy adventure converts its walkthrough into Sequence 1 and updates format."""
    user = (
        (await db_session.execute(select(User).where(User.username == "test_user")))
        .scalars()
        .first()
    )

    legacy_tpl = AdventureTemplate(
        id="legacy-migrate-test",
        title="Forgotten Crypt",
        owner_id=user.id,
        version="1.0.0",
        plot="Explore the ancient crypt.",
        completed_condition="Chalice on altar.",
        original_manifest={
            "version": "1.0",
            "format_version": "1.0",
            "title": "Forgotten Crypt",
            "walkthrough": "Find the silver chalice and place it on the altar.",
            "scenes": [
                {"id": "CRYPT_ENTRANCE", "name": "Crypt Entrance", "description": "Dark entryway"}
            ],
            "npcs": [
                {
                    "id": "SKELETON_GUARD",
                    "name": "Skeleton Guard",
                    "description": "Bony guard",
                    "start_scene_id": "CRYPT_ENTRANCE",
                }
            ],
            "objects": [
                {
                    "id": "SILVER_CHALICE",
                    "name": "Silver Chalice",
                    "description": "Shiny chalice",
                    "start_scene_id": "CRYPT_ENTRANCE",
                }
            ],
            "sequences": [],
        },
        sequences=[],
        is_ready=True,
    )
    db_session.add(legacy_tpl)
    await db_session.commit()

    # Prior to migration, it is flagged as legacy
    check = check_template_update(legacy_tpl, [])
    assert check["is_legacy_format"] is True

    # Call migrate endpoint
    resp = await auth_client.post(f"/api/adventures/templates/{legacy_tpl.id}/migrate")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["is_legacy_format"] is False
    assert data["can_start"] is True

    # Refresh from DB
    await db_session.refresh(legacy_tpl)
    assert len(legacy_tpl.sequences) == 1
    assert legacy_tpl.sequences[0]["title"] == "Main Journey"
    assert (
        legacy_tpl.sequences[0]["walkthrough"]
        == "Find the silver chalice and place it on the altar."
    )
    assert legacy_tpl.sequences[0]["end_condition"] == "Chalice on altar."
    assert is_legacy_template(legacy_tpl) is False

    # Verify editor assets rehydrate scenes, npcs, and objects
    editor_resp = await auth_client.get(f"/api/adventures/{legacy_tpl.id}/editor/assets")
    assert editor_resp.status_code == 200
    editor_data = editor_resp.json()
    assert len(editor_data["scenes"]) >= 1
    assert any(s["id"] == "CRYPT_ENTRANCE" for s in editor_data["scenes"])
    assert len(editor_data["npcs"]) >= 1
    assert any(n["id"] == "SKELETON_GUARD" for n in editor_data["npcs"])
    assert len(editor_data["objects"]) >= 1
    assert any(o["id"] == "SILVER_CHALICE" for o in editor_data["objects"])


@pytest.mark.asyncio
async def test_update_replaces_template_when_file_title_differs(
    auth_client: AsyncClient, db_session, monkeypatch
):
    """An update matched by filename stem must replace the old template, not duplicate it."""
    from backend.engine.adventures import adventure_updates
    from backend.engine.adventures.adventure_importer import AdventureTemplateImporter

    # Arrange
    user = (
        (await db_session.execute(select(User).where(User.username == "test_user")))
        .scalars()
        .first()
    )
    old_tpl = AdventureTemplate(
        id="stem-update-old", title="Crazy Job Interview", owner_id=user.id, version="2.0.0"
    )
    avatar = Avatar(id="stem-update-avatar", user_id=user.id, name="Hero")
    session = GameSession(
        id="stem-update-session", template_id=old_tpl.id, user_id=user.id, avatar_id=avatar.id
    )
    db_session.add_all([avatar, old_tpl, session])
    await db_session.commit()

    new_title = "Crazy Job Interview (Copy)"
    monkeypatch.setattr(
        adventure_updates,
        "scan_available_adventure_files",
        lambda force_refresh=False: [
            {
                "file_path": "/fake/Crazy_Job_Interview.adz",
                "stem": "Crazy_Job_Interview",
                "title": new_title,
                "origin_id": None,
                "version": "3.0.0",
                "format_version": CURRENT_VERSION,
                "has_sequences": True,
            }
        ],
    )

    async def fake_import_file(db, file_path, owner_id=None, allow_session=True, overwrite=False):
        db.add(
            AdventureTemplate(
                id="stem-update-new", title=new_title, owner_id=owner_id, version="3.0.0"
            )
        )
        await db.commit()
        return True

    monkeypatch.setattr(AdventureTemplateImporter, "import_file", fake_import_file)

    # Act
    result = await adventure_updates.update_single_adventure(db_session, old_tpl.id, user.id)

    # Assert
    assert result["template_id"] == "stem-update-new"
    remaining = (
        (
            await db_session.execute(
                select(AdventureTemplate.id).where(AdventureTemplate.owner_id == user.id)
            )
        )
        .scalars()
        .all()
    )
    assert "stem-update-old" not in remaining
    assert "stem-update-new" in remaining
    relinked = await db_session.get(GameSession, "stem-update-session")
    await db_session.refresh(relinked)
    assert relinked.template_id == "stem-update-new"
