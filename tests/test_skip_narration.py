"""tw.story.skip_narration(): the next Pass 2 produces no narration (e.g. while audio plays)."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select

from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.engine.audio.audio_state import apply_audio_ops, read_audio_state
from backend.engine.rules.rule_engine import GameEvent
from backend.engine.scripting.context import GameContext
from backend.engine.scripting.narration_skip import (
    SKIP_NARRATION_KEY,
    store_skip_narration,
    take_skip_narration,
)
from backend.models.chat import ChatMessage
from backend.models.session_state import SessionState
from tests.conftest import TestSessionLocal
from tests.test_game_loop import _seed_game_context


def test_scripts_request_the_skip_and_it_is_taken_once():
    # Arrange
    ctx = GameContext()

    # Act
    ctx.skip_narration()
    states: dict = {}
    store_skip_narration(states, ctx.changeset.skip_narration)
    state = SessionState(entity_states=states)

    # Assert
    assert ctx.changeset.skip_narration and ctx.changeset.has_changes
    assert states[SKIP_NARRATION_KEY] is True
    assert take_skip_narration(state) is True
    assert take_skip_narration(state) is False


@pytest.mark.asyncio
async def test_turn_after_skip_request_has_no_narration(setup_test_db, monkeypatch):
    # Arrange
    llm = MagicMock()
    llm.aexecute_complex_task = AsyncMock(return_value=GameEvent(narrative_description="Bram."))

    async def stream(*_args, **_kwargs):
        yield MagicMock(choices=[MagicMock(delta=MagicMock(content="Bram grumbles at you."))])

    llm.stream_simple_task = AsyncMock(side_effect=stream)
    monkeypatch.setattr(
        "backend.api.routes.adventures.gameplay_logic.GameMasterLLM", lambda *a, **k: llm
    )

    async with TestSessionLocal() as db:
        user, _adv, _avatar, _state = await _seed_game_context(db)
        manager = GameTurnManager(db, "session-1", user)
        await manager.initialize()
        await manager._execute_inline_script(
            "tw.audio.play('x')\ntw.story.skip_narration()", "on_receive_item", "BRAM"
        )
        await db.commit()

        # Act
        skipped = "".join([event async for event in manager.process_turn("look at Bram")])
        narrated = "".join([event async for event in manager.process_turn("look again")])
        assistant = (
            (
                await db.execute(
                    select(ChatMessage.content).where(
                        ChatMessage.session_id == "session-1", ChatMessage.role == "assistant"
                    )
                )
            )
            .scalars()
            .all()
        )

    # Assert: only the second turn was narrated.
    assert "Bram grumbles at you." not in skipped
    assert "Bram grumbles at you." in narrated
    assert llm.stream_simple_task.await_count == 1
    assert list(assistant).count("Bram grumbles at you.") == 1
    assert SKIP_NARRATION_KEY not in (manager.state.entity_states or {})


def test_playback_volume_is_recorded_for_this_playback_only():
    # Arrange
    ctx = GameContext(audio_library=[{"id": "CRYPT_THEME"}])
    states: dict = {}

    # Act
    ctx.audio.play("CRYPT_THEME", volume=0.4)
    track_id = ctx.audio.generate("harp", name="harp", volume=1.7)
    apply_audio_ops(states, ctx.changeset.audio_ops)

    # Assert
    now = read_audio_state(states)["now"]
    assert now["id"] == track_id and now["volume"] == 1.0  # clamped to 0..1
    first = GameContext(audio_library=[{"id": "CRYPT_THEME"}])
    first.audio.play("CRYPT_THEME", volume=0.4)
    states2: dict = {}
    apply_audio_ops(states2, first.changeset.audio_ops)
    assert read_audio_state(states2)["now"] == {
        "library_id": "CRYPT_THEME",
        "loop": True,
        "fade": 2.0,
        "volume": 0.4,
    }
