"""After a dialog choice the scene goes on by itself: /continue_story runs the waiting callback."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select

from backend.api.routes.adventures.dialog_service import DialogChoiceResolver
from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.engine.scripting.dialog import pending_dialog
from backend.engine.scripting.gm_directions import pending_after_narration
from backend.models.chat import ChatMessage
from tests.conftest import TestSessionLocal
from tests.test_game_loop import _seed_game_context

INIT_SCRIPT = """
def on_scream(answ):
    tw.story.narrate('Tina screams at the locked door.')
    tw.story.direct('The key rattles in the lock.', after='mom_bursts_out')

def mom_bursts_out():
    tw.story.narrate('The office door flies open.')
    tw.vars.set('mom_out', True)
"""


async def _manager(db) -> GameTurnManager:
    user, adv, _avatar, _state = await _seed_game_context(db)
    adv.original_manifest = {"init_script": INIT_SCRIPT}
    await db.commit()
    manager = GameTurnManager(db, "session-1", user)
    await manager.initialize()
    await manager._execute_inline_script(
        "tw.dialog.choose('Deal?', ['Scream'], on_choice='on_scream')", "on_interact", "TINA"
    )
    await db.commit()
    return manager


def _narration_llm(monkeypatch) -> MagicMock:
    llm = MagicMock()
    llm.aexecute_complex_task = AsyncMock(side_effect=AssertionError("no mechanics pass"))

    async def stream(*_args, **_kwargs):
        yield MagicMock(choices=[MagicMock(delta=MagicMock(content="The key keeps rattling."))])

    llm.stream_simple_task = AsyncMock(side_effect=stream)
    monkeypatch.setattr(
        "backend.api.routes.adventures.gameplay_logic.GameMasterLLM", lambda *a, **k: llm
    )
    return llm


async def _contents(db) -> list[str]:
    rows = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == "session-1")
        .order_by(ChatMessage.created_at, ChatMessage.id)
    )
    return [row.content for row in rows.scalars().all()]


@pytest.mark.asyncio
async def test_choice_with_a_waiting_callback_asks_the_client_to_continue(setup_test_db):
    async with TestSessionLocal() as db:
        # Arrange
        manager = await _manager(db)
        dialog_id = pending_dialog(manager.state.entity_states)["id"]

        # Act
        result = await DialogChoiceResolver(manager).resolve(dialog_id, 0, None)

        # Assert
        assert result["continue_story"] is True
        assert pending_after_narration(manager.state.entity_states)


@pytest.mark.asyncio
async def test_continue_story_narrates_without_mechanics_and_runs_the_callback(
    setup_test_db, monkeypatch
):
    _narration_llm(monkeypatch)
    async with TestSessionLocal() as db:
        # Arrange
        manager = await _manager(db)
        dialog_id = pending_dialog(manager.state.entity_states)["id"]
        await DialogChoiceResolver(manager).resolve(dialog_id, 0, None)

        # Act
        events = [e async for e in manager.process_turn("/continue_story")]
        contents = await _contents(db)

    # Assert: narration first, then the callback; the command itself is never shown
    assert contents.index("The key keeps rattling.") < contents.index("The office door flies open.")
    assert "/continue_story" not in contents
    assert manager.state.entity_states["__script_vars__"]["mom_out"] is True
    assert any(e.startswith("event: final") for e in events)


@pytest.mark.asyncio
async def test_continue_story_without_a_waiting_callback_does_nothing(setup_test_db, monkeypatch):
    llm = _narration_llm(monkeypatch)
    async with TestSessionLocal() as db:
        # Arrange
        user, _adv, _avatar, _state = await _seed_game_context(db)
        manager = GameTurnManager(db, "session-1", user)

        # Act
        events = [e async for e in manager.process_turn("/continue_story")]

    # Assert
    llm.stream_simple_task.assert_not_called()
    assert any(e.startswith("event: final") for e in events)
