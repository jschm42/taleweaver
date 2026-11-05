from unittest.mock import AsyncMock

import pytest

from backend.api.routes.adventures.sequence_progress import apply_sequence_changeset
from backend.engine.scripting.context import GameContext, ScriptChangeset
from backend.models.avatar import Avatar
from backend.models.session_state import SessionState


def test_sequences_proxy_inspection():
    """Verifies that active sequence and properties can be retrieved."""
    # Arrange
    sequences = [
        {"id": "SEQ_1", "title": "Chapter One", "order": 1},
        {"id": "SEQ_2", "title": "Chapter Two", "order": 2},
    ]
    ctx = GameContext(
        active_sequence_id="SEQ_1",
        sequences=sequences,
    )

    # Act & Assert
    assert ctx.sequences.get_active_id() == "SEQ_1"
    assert ctx.sequences.active_id == "SEQ_1"
    assert ctx.sequences.id == "SEQ_1"
    assert ctx.sequences.title == "Chapter One"
    assert ctx.sequences.get_active() == sequences[0]
    assert ctx.sequences.is_active("SEQ_1") is True
    assert ctx.sequences.is_active("seq_1") is True
    assert ctx.sequences.is_active("SEQ_2") is False

    # Alias tw.sequence
    assert ctx.sequence.id == "SEQ_1"
    assert ctx.sequence.is_active("SEQ_1") is True


def test_sequences_proxy_start_and_end():
    """Verifies starting and ending sequences mutate changeset and local proxy state."""
    # Arrange
    sequences = [
        {"id": "SEQ_1", "title": "Chapter One", "order": 1},
        {"id": "SEQ_2", "title": "Chapter Two", "order": 2},
    ]
    ctx = GameContext(
        active_sequence_id="SEQ_1",
        sequences=sequences,
    )

    # Act: Start sequence 2
    ctx.sequences.start("SEQ_2")

    # Assert
    assert ctx.changeset.sequence_start_id == "SEQ_2"
    assert ctx.sequences.get_active_id() == "SEQ_2"
    assert ctx.sequences.is_active("SEQ_2") is True

    # Act: End sequence with advance=False
    ctx.sequences.end(advance=False)

    # Assert
    assert ctx.changeset.sequence_completed is True
    assert ctx.changeset.sequence_advance is False
    assert ctx.sequences.get_active_id() is None


@pytest.mark.asyncio
async def test_apply_sequence_changeset_start():
    """Verifies apply_sequence_changeset activates a sequence and triggers start hooks."""
    # Arrange
    adventure = type(
        "Adv",
        (),
        {
            "sequences": [
                {
                    "id": "SEQ_INTRO",
                    "title": "The Awakening",
                    "order": 1,
                    "on_start_sequence_text": "A new chapter begins.",
                },
                {"id": "SEQ_VAULT", "title": "The Vault", "order": 2},
            ]
        },
    )()
    state = SessionState(
        session_id="test_sess", active_sequence_id="SEQ_INTRO", active_sequence_order=1
    )
    changeset = ScriptChangeset()
    changeset.sequence_start_id = "SEQ_VAULT"
    saved_messages = []

    async def mock_save(role, text):
        saved_messages.append((role, text))

    # Act
    messages = await apply_sequence_changeset(
        adventure, state, None, changeset, message_saver=mock_save
    )

    # Assert
    assert state.active_sequence_id == "SEQ_VAULT"
    assert state.active_sequence_order == 2
    assert "Sequence started: The Vault" in messages


@pytest.mark.asyncio
async def test_apply_sequence_changeset_end_and_advance():
    """Verifies ending a sequence awards XP, runs end/start hooks, and advances to next."""
    # Arrange
    adventure = type(
        "Adv",
        (),
        {
            "sequences": [
                {
                    "id": "SEQ_1",
                    "title": "First Chapter",
                    "order": 1,
                    "exp_reward": 50,
                    "on_end_sequence_text": "First chapter concluded.",
                },
                {
                    "id": "SEQ_2",
                    "title": "Second Chapter",
                    "order": 2,
                    "on_start_sequence_text": "Second chapter begins.",
                },
            ]
        },
    )()
    state = SessionState(
        session_id="test_sess", active_sequence_id="SEQ_1", active_sequence_order=1
    )
    avatar = Avatar(id="av_1", exp=10)
    changeset = ScriptChangeset()
    changeset.sequence_completed = True
    changeset.sequence_advance = True

    mock_executor = AsyncMock(return_value=[])
    mock_save = AsyncMock()

    # Act
    messages = await apply_sequence_changeset(
        adventure, state, avatar, changeset, script_executor=mock_executor, message_saver=mock_save
    )

    # Assert
    assert avatar.exp == 60
    assert state.active_sequence_id == "SEQ_2"
    assert state.active_sequence_order == 2
    assert any("Sequence completed: First Chapter (+50 XP)" in m for m in messages)
    assert any("New Sequence unlocked: Second Chapter" in m for m in messages)


@pytest.mark.asyncio
async def test_apply_sequence_changeset_end_without_advance():
    """Verifies ending sequence with advance=False clears active sequence."""
    # Arrange
    adventure = type(
        "Adv",
        (),
        {
            "sequences": [
                {"id": "SEQ_EVENT", "title": "Special Event", "order": 1, "exp_reward": 25},
            ]
        },
    )()
    state = SessionState(
        session_id="test_sess", active_sequence_id="SEQ_EVENT", active_sequence_order=1
    )
    avatar = Avatar(id="av_1", exp=0)
    changeset = ScriptChangeset()
    changeset.sequence_completed = True
    changeset.sequence_advance = False

    # Act
    messages = await apply_sequence_changeset(adventure, state, avatar, changeset)

    # Assert
    assert avatar.exp == 25
    assert state.active_sequence_id is None
    assert state.active_sequence_order == 0
    assert any("Sequence completed: Special Event (+25 XP)" in m for m in messages)
