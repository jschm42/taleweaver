"""Update badges and updates of installed adventures from the adventure library (browser)."""

from types import SimpleNamespace

import pytest
from sqlalchemy import select

from backend.engine.adventures import adventure_updates
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.game_session import GameSession
from backend.models.user import User
from backend.services.adventure_library import updates
from backend.services.adventure_library.catalog import LibraryService
from backend.services.adventure_library.models import AdventureLibrary, LibraryEntry

ORIGIN = "origin-dark-forest"


def _library(version: str) -> AdventureLibrary:
    entry = LibraryEntry(
        id=ORIGIN,
        slug="dark-forest",
        title="Dark Forest",
        version=version,
        files=["adventure.adv"],
    )
    return AdventureLibrary(schema=1, adventures=[entry])


def _no_local_update() -> dict:
    return {"has_update": False, "available_version": None}


@pytest.fixture
def no_local_files(monkeypatch):
    monkeypatch.setattr(updates, "scan_available_adventure_files", lambda force_refresh=False: [])
    monkeypatch.setattr(
        adventure_updates, "scan_available_adventure_files", lambda force_refresh=False: []
    )


async def _user_id(db_session) -> str:
    return await db_session.scalar(select(User.id).where(User.username == "test_user"))


# --- Status merge ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("installed", "library_version", "expected"),
    [("1.0.0", "1.2.0", True), ("1.2.0", "1.2.0", False), ("2.0.0", "1.2.0", False)],
)
def test_merge_marks_newer_library_version(installed, library_version, expected) -> None:
    # Arrange
    template = SimpleNamespace(origin_id=ORIGIN, version=installed)

    # Act
    status = updates.merge_library_update(_no_local_update(), template, _library(library_version))

    # Assert
    assert status["has_update"] is expected
    assert status["update_source"] == ("library" if expected else None)


def test_merge_keeps_newer_local_file_and_ignores_unknown_origin() -> None:
    # Arrange
    template = SimpleNamespace(origin_id=ORIGIN, version="1.0.0")
    local = {"has_update": True, "available_version": "3.0.0"}
    stranger = SimpleNamespace(origin_id="someone-else", version="1.0.0")

    # Act
    merged = updates.merge_library_update(local, template, _library("1.2.0"))
    unrelated = updates.merge_library_update(_no_local_update(), stranger, _library("9.0.0"))

    # Assert
    assert (merged["available_version"], merged["update_source"]) == ("3.0.0", "local")
    assert unrelated["has_update"] is False


# --- API --------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_template_list_shows_library_update_badge(
    auth_client, db_session, monkeypatch, no_local_files
):
    # Arrange
    db_session.add(
        AdventureTemplate(
            id="tpl-forest",
            title="Dark Forest",
            owner_id=await _user_id(db_session),
            origin_id=ORIGIN,
            version="1.0.0",
            is_ready=True,
        )
    )
    await db_session.commit()
    monkeypatch.setattr(LibraryService, "peek_library", lambda self: _library("1.2.0"))

    # Act
    response = await auth_client.get("/api/adventures/templates")

    # Assert
    assert response.status_code == 200
    row = next(t for t in response.json() if t["template_id"] == "tpl-forest")
    assert row["has_update"] is True
    assert row["available_version"] == "1.2.0"
    assert row["update_source"] == "library"


@pytest.mark.asyncio
async def test_update_endpoint_installs_library_version_and_relinks_sessions(
    auth_client, db_session, monkeypatch, no_local_files
):
    # Arrange
    user_id = await _user_id(db_session)
    avatar = Avatar(id="forest-avatar", user_id=user_id, name="Hero")
    old = AdventureTemplate(
        id="tpl-forest-old", title="Dark Forest", owner_id=user_id, origin_id=ORIGIN, version="1.0"
    )
    session = GameSession(
        id="forest-session", template_id=old.id, user_id=user_id, avatar_id=avatar.id
    )
    db_session.add_all([avatar, old, session])
    await db_session.commit()

    async def library(self, *, force_refresh=False):
        return _library("1.2.0")

    installed: list[str] = []

    async def fake_install(db, entry, *, owner_id):
        installed.append(entry.version)
        db.add(
            AdventureTemplate(
                id="tpl-forest-new",
                title=entry.title,
                owner_id=owner_id,
                origin_id=entry.id,
                version=entry.version,
            )
        )
        await db.commit()
        return "tpl-forest-new"

    monkeypatch.setattr(LibraryService, "get_library", library)
    monkeypatch.setattr(updates, "install_entry", fake_install)

    # Act
    response = await auth_client.post(f"/api/adventures/templates/{old.id}/update")

    # Assert
    assert response.status_code == 200, response.text
    assert response.json()["template_id"] == "tpl-forest-new"
    assert installed == ["1.2.0"]
    db_session.expire_all()
    ids = set(
        (
            await db_session.execute(
                select(AdventureTemplate.id).where(AdventureTemplate.owner_id == user_id)
            )
        ).scalars()
    )
    assert "tpl-forest-old" not in ids
    relinked = await db_session.get(GameSession, "forest-session")
    assert relinked.template_id == "tpl-forest-new"


@pytest.mark.asyncio
async def test_update_endpoint_reports_missing_update(
    auth_client, db_session, monkeypatch, no_local_files
):
    # Arrange
    db_session.add(
        AdventureTemplate(
            id="tpl-current",
            title="Dark Forest",
            owner_id=await _user_id(db_session),
            origin_id=ORIGIN,
            version="1.2.0",
        )
    )
    await db_session.commit()

    async def library(self, *, force_refresh=False):
        return _library("1.2.0")

    monkeypatch.setattr(LibraryService, "get_library", library)

    # Act
    response = await auth_client.post("/api/adventures/templates/tpl-current/update")

    # Assert
    assert response.status_code == 404
