import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from backend.models.session_state import SessionState
from backend.models.chat import ChatMessage
from backend.models.user import User
from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.api.routes.adventures.turn_helpers import TurnSessionStateHelper


def test_build_compressed_history_prompt_block_empty():
    manager = MagicMock()
    manager.state = SessionState()
    manager.state.compressed_history = None

    helper = TurnSessionStateHelper(
        manager,
        gm_notes_state_key="__gm_notes__",
        gm_notes_max_items=10,
        terminal_epilogue_state_key="__terminal_epilogue__",
    )
    block = helper.build_compressed_history_prompt_block()
    assert block == ""


def test_build_compressed_history_prompt_block_populated():
    manager = MagicMock()
    manager.state = SessionState()
    manager.state.compressed_history = {
        "summary": "The hero entered the ancient crypt and recovered the sunstone.",
        "last_compressed_msg_id": "msg-10",
    }

    helper = TurnSessionStateHelper(
        manager,
        gm_notes_state_key="__gm_notes__",
        gm_notes_max_items=10,
        terminal_epilogue_state_key="__terminal_epilogue__",
    )
    block = helper.build_compressed_history_prompt_block()
    assert "PRIOR STORY SUMMARY (COMPRESSED HISTORY):" in block
    assert "The hero entered the ancient crypt and recovered the sunstone." in block


@pytest.mark.asyncio
async def test_compress_history_if_needed_disabled():
    manager = MagicMock(spec=GameTurnManager)
    manager.state = SessionState()
    manager.state.enable_history_compression = False
    manager.state.max_memory_turns = 2

    events = []
    async for ev in GameTurnManager._compress_history_if_needed(manager):
        events.append(ev)

    assert len(events) == 0


@pytest.mark.asyncio
async def test_compress_history_if_needed_triggers_compression():
    manager = MagicMock(spec=GameTurnManager)
    manager.game_id = "test-game"
    manager.user = User(id="user-1", username="testuser")
    manager.user.llm_settings = {
        "compression_model": "test-compress-model",
        "compression_model_provider": "openai",
    }
    manager.adventure = MagicMock()
    manager.adventure.max_memory_turns = 2

    state = SessionState()
    state.session_id = "test-game"
    state.template_id = "adv-1"
    state.enable_history_compression = True
    state.max_memory_turns = 2
    state.compressed_history = None
    manager.state = state

    # Create 4 user turns + assistant responses (total 8 messages)
    msgs = [
        ChatMessage(id="m1", session_id="test-game", role="user", content="I enter the cave."),
        ChatMessage(id="m2", session_id="test-game", role="assistant", content="You see glowing mushrooms."),
        ChatMessage(id="m3", session_id="test-game", role="user", content="I pick a mushroom."),
        ChatMessage(id="m4", session_id="test-game", role="assistant", content="It smells sweet."),
        ChatMessage(id="m5", session_id="test-game", role="user", content="I go deeper."),
        ChatMessage(id="m6", session_id="test-game", role="assistant", content="A goblin appears!"),
        ChatMessage(id="m7", session_id="test-game", role="user", content="I greet the goblin."),
        ChatMessage(id="m8", session_id="test-game", role="assistant", content="The goblin grunts friendly."),
    ]

    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = msgs
    manager.db = MagicMock()
    manager.db.execute = AsyncMock(return_value=mock_res)
    manager.db.commit = AsyncMock()
    manager._save_chat_message = AsyncMock()

    mock_llm_instance = MagicMock()
    mock_llm_instance.aexecute_simple_task = AsyncMock(
        return_value="The hero entered a glowing cave and gathered sweet-smelling mushrooms."
    )

    with patch("backend.api.routes.adventures.gameplay_logic.GameMasterLLM", return_value=mock_llm_instance):
        events = []
        async for ev in GameTurnManager._compress_history_if_needed(manager):
            events.append(ev)

    assert len(events) == 1
    assert "event: system" in events[0]
    assert manager.state.compressed_history is not None
    assert manager.state.compressed_history["summary"] == "The hero entered a glowing cave and gathered sweet-smelling mushrooms."
    assert manager.state.compressed_history["last_compressed_msg_id"] == "m4"
    manager.db.commit.assert_awaited()


def test_normalize_llm_settings_compacting_defaults():
    from backend.api.routes.config_api import _normalize_llm_settings

    # Default fallback
    norm = _normalize_llm_settings({})
    assert norm["turns_before_compacting"] == 10
    assert norm["enable_history_compression"] is True

    # Custom valid values
    norm2 = _normalize_llm_settings({"turns_before_compacting": 25, "enable_history_compression": False})
    assert norm2["turns_before_compacting"] == 25
    assert norm2["enable_history_compression"] is False

    # Clamping out-of-range values
    norm3 = _normalize_llm_settings({"turns_before_compacting": 999, "enable_history_compression": True})
    assert norm3["turns_before_compacting"] == 100
    norm4 = _normalize_llm_settings({"turns_before_compacting": 0, "enable_history_compression": True})
    assert norm4["turns_before_compacting"] == 1

