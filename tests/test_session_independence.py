"""A session plays from its own adventure copy: template edits and deletion never affect it."""

from httpx import AsyncClient
from sqlalchemy import select

from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.api.routes.adventures.logic import AdventureLogic
from backend.api.routes.adventures.session_adventure import SESSION_MANIFEST_SNAPSHOT_KEY
from backend.models.adventure_template import AdventureTemplate
from backend.models.game_session import GameSession
from backend.models.session_state import SessionState
from backend.models.user import User
from tests.conftest import TestSessionLocal

LATER_INIT_SCRIPT = "def added_later(index):\n    pass\n"


async def _start_session(client: AsyncClient, title: str) -> dict:
    resp = await client.post("/api/adventures/", json={"title": title, "avatar_name": "Hero"})
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _session_user(db, game_id: str) -> User:
    game_session = await db.get(GameSession, game_id)
    return await db.get(User, game_session.user_id)


async def _edit_template(template_id: str) -> None:
    async with TestSessionLocal() as db:
        template = await db.get(AdventureTemplate, template_id)
        template.title = "Renamed Later"
        template.rules = "Rules changed later"
        template.awards = [{"key": "added-later", "title": "Added Later"}]
        template.original_manifest = {"init_script": LATER_INIT_SCRIPT, "scripts": []}
        await db.commit()


async def test_template_edits_do_not_reach_running_session(auth_client: AsyncClient):
    # Arrange
    ids = await _start_session(auth_client, "Independent Quest")
    await _edit_template(ids["adventure_id"])

    # Act
    async with TestSessionLocal() as db:
        manager = GameTurnManager(db, ids["game_id"], await _session_user(db, ids["game_id"]))
        initialized = await manager.initialize()

    # Assert
    assert initialized
    assert manager.adventure.title == "Independent Quest"
    assert manager.adventure.rules != "Rules changed later"
    assert not manager.adventure.awards
    assert "added_later" not in (manager.adventure.init_script or "")


async def test_session_keeps_playing_after_template_deletion(auth_client: AsyncClient):
    # Arrange
    ids = await _start_session(auth_client, "Orphaned Quest")
    async with TestSessionLocal() as db:
        await AdventureLogic.delete_adventure(db, ids["adventure_id"])

    # Act
    resp = await auth_client.get(f"/api/adventures/{ids['game_id']}/chat")
    async with TestSessionLocal() as db:
        manager = GameTurnManager(db, ids["game_id"], await _session_user(db, ids["game_id"]))
        initialized = await manager.initialize()

    # Assert
    assert resp.status_code == 200, resp.text
    assert resp.json()["sheet"]["adventure_title"] == "Orphaned Quest"
    assert initialized
    assert manager.adventure.title == "Orphaned Quest"


async def test_older_snapshot_is_completed_once_then_frozen(auth_client: AsyncClient):
    # Arrange: a session from before the snapshot held every template column.
    ids = await _start_session(auth_client, "Legacy Quest")
    async with TestSessionLocal() as db:
        state = (
            (
                await db.execute(
                    select(SessionState).where(SessionState.session_id == ids["game_id"])
                )
            )
            .scalars()
            .first()
        )
        entity_states = dict(state.entity_states)
        entity_states[SESSION_MANIFEST_SNAPSHOT_KEY] = {"adventure": {"title": "Legacy Quest"}}
        state.entity_states = entity_states
        await db.commit()

    # Act: the first load completes the snapshot, later template edits are ignored.
    async with TestSessionLocal() as db:
        manager = GameTurnManager(db, ids["game_id"], await _session_user(db, ids["game_id"]))
        await manager.initialize()
        await db.commit()
    await _edit_template(ids["adventure_id"])
    async with TestSessionLocal() as db:
        manager = GameTurnManager(db, ids["game_id"], await _session_user(db, ids["game_id"]))
        await manager.initialize()

    # Assert
    assert manager.adventure.title == "Legacy Quest"
    assert manager.adventure.rules != "Rules changed later"
    assert "added_later" not in (manager.adventure.init_script or "")
