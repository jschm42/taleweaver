import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from backend.core.config import settings
from backend.models.chat import ChatMessage
from backend.models.session_state import SessionState
from backend.models.game_session import GameSession
from backend.models.avatar import Avatar
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User
from tests.conftest import TestSessionLocal

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def client(auth_client: AsyncClient) -> AsyncClient:
    """Adventures endpoints require authentication."""
    return auth_client


async def test_delete_message_endpoints(client: AsyncClient, monkeypatch):
    """Verifies message deletion succeeds only in debug mode, and returns correct statuses."""
    # Fetch seed user
    async with TestSessionLocal() as session:
        user = (await session.execute(select(User).where(User.username == "test_user"))).scalar_one()
        user_id = user.id

        # Seed template
        adv = AdventureTemplate(
            id="adv-delete-msg",
            title="Message Delete Test Quest",
            owner_id=user_id,
            time_per_turn=5,
        )
        session.add(adv)
        await session.flush()

        # Seed avatar
        avatar = Avatar(
            id="av-delete-msg",
            template_id=adv.id,
            user_id=user_id,
            name="Hero",
        )
        session.add(avatar)
        await session.flush()

        # Seed GameSession
        game_session = GameSession(
            id="session-delete-msg",
            user_id=user_id,
            avatar_id=avatar.id,
            template_id=adv.id,
            status="active",
        )
        session.add(game_session)
        await session.flush()

        # Seed SessionState
        state = SessionState(
            session_id=game_session.id,
            template_id=adv.id,
            avatar_id=avatar.id,
            user_id=user_id,
            current_scene_id="START",
            in_game_time=0,
            is_debug_enabled=False,
        )
        session.add(state)

        # Seed chat messages
        msg1 = ChatMessage(session_id=game_session.id, role="user", content="msg 1 to be deleted")
        msg2 = ChatMessage(session_id=game_session.id, role="assistant", content="msg 2 to keep")
        session.add_all([msg1, msg2])
        await session.commit()

        game_id = game_session.id
        msg1_id = msg1.id
        msg2_id = msg2.id

    # Try deleting when NOT in debug mode (should fail with 403)
    monkeypatch.setattr(settings, "TALEWEAVER_DEBUG_ENABLED", False)

    resp = await client.delete(f"/api/adventures/sessions/{game_id}/messages/{msg1_id}")
    assert resp.status_code == 403

    # Enable debug mode on the state (in-game debug mode)
    async with TestSessionLocal() as session:
        state = (await session.execute(select(SessionState).where(SessionState.session_id == game_id))).scalar_one()
        state.is_debug_enabled = True
        await session.commit()

    # Try deleting again (should succeed with 200)
    resp = await client.delete(f"/api/adventures/sessions/{game_id}/messages/{msg1_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "deleted"
    assert resp.json()["message_id"] == msg1_id

    # Verify that the message is actually deleted from the database
    async with TestSessionLocal() as session:
        msg_in_db = (await session.execute(select(ChatMessage).where(ChatMessage.id == msg1_id))).scalar_one_or_none()
        assert msg_in_db is None

        msg2_in_db = (await session.execute(select(ChatMessage).where(ChatMessage.id == msg2_id))).scalar_one_or_none()
        assert msg2_in_db is not None

    # Try deleting a non-existent message ID (should return 404)
    resp = await client.delete(f"/api/adventures/sessions/{game_id}/messages/invalid-uuid-or-id")
    assert resp.status_code == 404
