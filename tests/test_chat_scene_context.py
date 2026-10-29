"""Chat messages are stamped with the scene/sequence they were written in (story paging)."""

import pytest

from backend.models.chat import ChatMessage
from backend.models.session_state import SessionState

pytestmark = pytest.mark.asyncio


async def _seed_state(db, session_id: str = "session-scene-ctx") -> SessionState:
    state = SessionState(
        session_id=session_id,
        template_id="adv-scene-ctx",
        avatar_id="av-scene-ctx",
        user_id="user-scene-ctx",
        current_scene_id="LOBBY",
        active_sequence_id="SEQ_1",
        in_game_time=0,
    )
    db.add(state)
    await db.flush()
    return state


async def test_new_chat_messages_get_current_scene_and_sequence(setup_test_db):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        # Arrange
        state = await _seed_state(db)

        # Act
        first = ChatMessage(session_id=state.session_id, role="user", content="Talk to Ava")
        db.add(first)
        await db.flush()
        state.current_scene_id = "BASEMENT"
        state.active_sequence_id = "SEQ_2"
        second = ChatMessage(
            session_id=state.session_id, role="assistant", content="Dark basement."
        )
        db.add(second)
        await db.flush()

        # Assert
        assert (first.scene_id, first.sequence_id) == ("LOBBY", "SEQ_1")
        assert (second.scene_id, second.sequence_id) == ("BASEMENT", "SEQ_2")
        assert second.to_client_dict() == {
            "id": second.id,
            "role": "assistant",
            "content": "Dark basement.",
            "scene_id": "BASEMENT",
            "sequence_id": "SEQ_2",
            "raw": False,
        }


async def test_explicit_scene_is_kept_and_unknown_session_stays_unstamped(setup_test_db):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        # Arrange
        state = await _seed_state(db)
        explicit = ChatMessage(
            session_id=state.session_id, role="system", content="Old event", scene_id="ARCHIVE"
        )
        orphan = ChatMessage(session_id="no-loaded-state", role="system", content="Orphan")

        # Act
        db.add_all([explicit, orphan])
        await db.flush()

        # Assert
        assert explicit.scene_id == "ARCHIVE"
        assert orphan.scene_id is None
        assert orphan.sequence_id is None
