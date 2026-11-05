"""Paged chat history for the endless story feed (GET /chat?message_limit, GET /chat/history)."""

from datetime import UTC, datetime, timedelta

import pytest

from backend.api.routes.adventures.chat_history import load_history_page
from backend.core.auth import create_access_token
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.chat import ChatMessage
from backend.models.user import User
from backend.models.world_entity import WorldScene
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio

BASE_TIME = datetime(2030, 1, 1, tzinfo=UTC)

# Three exchanges: user -> system -> assistant
ROLES = ["user", "system", "assistant"] * 3


async def _seed_messages(session_id: str, roles: list[str] = ROLES) -> list[str]:
    """Saves messages one second apart; returns their contents in chronological order."""
    contents = []
    async with TestSessionLocal() as db:
        for i, role in enumerate(roles):
            content = f"{role}-{i}"
            contents.append(content)
            db.add(
                ChatMessage(
                    session_id=session_id,
                    role=role,
                    content=content,
                    created_at=BASE_TIME + timedelta(seconds=i),
                )
            )
        await db.commit()
    return contents


async def test_newest_page_starts_at_a_player_action(setup_test_db):
    contents = await _seed_messages("s-1")

    async with TestSessionLocal() as db:
        page = await load_history_page(db, "s-1", limit=4)

    # The newest 4 are system-4, assistant-5, user-6 ... cut back to the exchange start.
    assert [m["content"] for m in page.messages] == contents[6:]
    assert page.has_more is True


async def test_older_pages_continue_without_gaps_or_overlap(setup_test_db):
    contents = await _seed_messages("s-1")
    loaded: list[str] = []

    async with TestSessionLocal() as db:
        page = await load_history_page(db, "s-1", limit=4)
        loaded = [m["content"] for m in page.messages]
        while page.has_more:
            page = await load_history_page(db, "s-1", limit=4, before_id=page.messages[0]["id"])
            loaded = [m["content"] for m in page.messages] + loaded

    assert loaded == contents


async def test_same_timestamp_is_ordered_by_id(setup_test_db):
    async with TestSessionLocal() as db:
        for content in ("first", "second", "third"):
            db.add(
                ChatMessage(session_id="s-1", role="system", content=content, created_at=BASE_TIME)
            )
            await db.flush()
        await db.commit()

        page = await load_history_page(db, "s-1", limit=2)
        older = await load_history_page(db, "s-1", limit=2, before_id=page.messages[0]["id"])

    assert [m["content"] for m in page.messages] == ["second", "third"]
    assert [m["content"] for m in older.messages] == ["first"]
    assert older.has_more is False


async def test_unknown_cursor_returns_empty_page(setup_test_db):
    await _seed_messages("s-1")

    async with TestSessionLocal() as db:
        page = await load_history_page(db, "s-1", limit=4, before_id="no-such-id")

    assert page.messages == []
    assert page.has_more is False


async def _start_session(client) -> tuple[str, dict]:
    async with TestSessionLocal() as db:
        user = User(username="paging_user", hashed_password="x", role="admin")
        db.add(user)
        await db.flush()
        template = AdventureTemplate(
            title="Paging",
            owner_id=user.id,
            version="2.0.0",
            is_ready=True,
            creation_status="Ready",
            original_manifest={"version": "2.0.0", "start_scene_id": "HALL"},
        )
        db.add(template)
        await db.flush()
        db.add(WorldScene(id="HALL", template_id=template.id, label="Hall", description="A hall."))
        db.add(Avatar(user_id=user.id, template_id=template.id, name="Hero", inventory=[]))
        await db.commit()
        template_id = template.id

    headers = {"Authorization": f"Bearer {create_access_token(data={'sub': 'paging_user'})}"}
    res = await client.post(f"/api/adventures/{template_id}/sessions/start", headers=headers)
    assert res.status_code == 201
    return res.json()["game_id"], headers


async def test_chat_endpoints_page_the_history(client, setup_test_db):
    game_id, headers = await _start_session(client)
    contents = await _seed_messages(game_id)

    res = await client.get(f"/api/adventures/{game_id}/chat?message_limit=4", headers=headers)
    assert res.status_code == 200
    snapshot = res.json()
    assert [m["content"] for m in snapshot["messages"]] == contents[6:]
    assert snapshot["has_more_messages"] is True

    oldest_id = snapshot["messages"][0]["id"]
    res = await client.get(
        f"/api/adventures/{game_id}/chat/history?before={oldest_id}&limit=3", headers=headers
    )
    assert res.status_code == 200
    older = res.json()
    assert [m["content"] for m in older["messages"]] == contents[3:6]
    assert older["has_more"] is True

    full = await client.get(f"/api/adventures/{game_id}/chat", headers=headers)
    assert full.json()["has_more_messages"] is False
    assert [m["content"] for m in full.json()["messages"]][-len(contents) :] == contents


async def test_history_endpoint_rejects_foreign_session(client, setup_test_db):
    game_id, _headers = await _start_session(client)
    async with TestSessionLocal() as db:
        db.add(User(username="intruder", hashed_password="x", role="user"))
        await db.commit()
    intruder = {"Authorization": f"Bearer {create_access_token(data={'sub': 'intruder'})}"}

    res = await client.get(f"/api/adventures/{game_id}/chat/history?before=x", headers=intruder)

    assert res.status_code == 404


async def test_sequence_titles_list_only_reached_chapters(setup_test_db):
    from types import SimpleNamespace

    from backend.api.routes.adventures.chat_history import visited_sequence_titles

    async with TestSessionLocal() as db:
        for seq_id in ("SEQ_1", "SEQ_2", None):
            db.add(ChatMessage(session_id="s-1", role="system", content="x", sequence_id=seq_id))
        await db.commit()
        adventure = SimpleNamespace(
            sequences=[
                {"id": "SEQ_1", "title": "Arrival"},
                {"id": "SEQ_2"},
                {"id": "SEQ_3", "title": "The Twist"},
            ]
        )

        titles = await visited_sequence_titles(db, "s-1", adventure)

    assert titles == {"SEQ_1": "Arrival", "SEQ_2": "SEQ_2"}
