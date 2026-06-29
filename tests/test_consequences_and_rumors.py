import pytest
from backend.engine.rule_engine import GameEvent, WorldMemoryUpdate
from backend.models.session_state import SessionState
from backend.models.avatar import Avatar
from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.api.routes.adventures.turn_helpers import TurnSessionStateHelper
from unittest.mock import MagicMock, AsyncMock

def test_pydantic_game_event_memories():
    """Verify that GameEvent correctly parses memories in Pydantic with scope and scene_id."""
    event_data = {
        "narrative_description": "Test description",
        "new_world_memories": [
            {
                "description": "Test local memory",
                "npc_id": "npc_1",
                "emotion": "negative",
                "scope": "local",
                "scene_id": "SCENE_A"
            },
            {
                "description": "Test global memory",
                "npc_id": None,
                "emotion": "positive",
                "scope": "global"
            }
        ]
    }
    
    event = GameEvent.model_validate(event_data)
    assert event.new_world_memories is not None
    assert len(event.new_world_memories) == 2
    assert event.new_world_memories[0].description == "Test local memory"
    assert event.new_world_memories[0].scope == "local"
    assert event.new_world_memories[0].scene_id == "SCENE_A"
    assert event.new_world_memories[1].scope == "global"

@pytest.mark.asyncio
async def test_apply_game_event_memories():
    """Verify that _apply_game_event correctly updates SessionState and generates system messages with scopes."""
    # Arrange
    manager = MagicMock(spec=GameTurnManager)
    manager.game_id = "test-game-id"
    state = SessionState()
    state.session_id = "test-game-id"
    state.entity_states = {}
    state.world_memories = []
    manager.state = state
    
    avatar = Avatar()
    avatar.hp = 100
    avatar.stamina = 100
    avatar.mana = 100
    avatar.inventory = []
    manager.avatar = avatar
    
    manager._collect_existing_item_ids = AsyncMock(return_value=set())
    manager._save_chat_message = AsyncMock()
    manager._enforce_container_unlock_guardrails = AsyncMock(return_value=[])
    manager._enforce_exit_unlock_guardrails = AsyncMock(return_value=[])
    manager._enforce_quest_and_award_guardrails = AsyncMock()
    manager._apply_adventure_generator_tools = AsyncMock()
    manager._queue_checkpoint = MagicMock()
    manager.db = MagicMock()
    manager.db.flush = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    manager.db.execute = AsyncMock(return_value=mock_result)
    
    event = GameEvent(
        narrative_description="Player insulted the wizard.",
        new_world_memories=[
            WorldMemoryUpdate(description="You insulted the wizard. He is furious.", npc_id="wizard_npc", emotion="negative", scope="local", scene_id="TOWER")
        ]
    )

    # Act
    system_messages = await GameTurnManager._apply_game_event(manager, event)

    # Assert
    assert any("You insulted the wizard" in msg for msg in system_messages)
    assert len(manager.state.world_memories) == 1
    assert manager.state.world_memories[0]["description"] == "You insulted the wizard. He is furious."
    assert manager.state.world_memories[0]["emotion"] == "negative"
    assert manager.state.world_memories[0]["scope"] == "local"
    assert manager.state.world_memories[0]["scene_id"] == "TOWER"

def test_prompt_builders():
    """Verify that prompt builder blocks format world memories correctly based on current scene."""
    # Arrange
    manager = MagicMock()
    state = MagicMock()
    state.world_memories = [
        {"id": "m1", "description": "Helped Bob", "emotion": "positive", "scope": "global"},
        {"id": "m2", "description": "Stole bread in the tavern", "emotion": "negative", "scope": "local", "scene_id": "TAVERN"},
        {"id": "m3", "description": "Found a map in the forest", "emotion": "neutral", "scope": "local", "scene_id": "FOREST"}
    ]
    manager.state = state
    helper = TurnSessionStateHelper(
        manager,
        gm_notes_state_key="notes_key",
        gm_notes_max_items=10,
        terminal_epilogue_state_key="epilogue_key"
    )

    # Act
    memories_tavern_prompt = helper.build_world_memories_prompt_block("TAVERN")
    memories_forest_prompt = helper.build_world_memories_prompt_block("FOREST")

    # Assert
    assert "WORLD MEMORIES" in memories_tavern_prompt
    assert "- Helped Bob (Emotion: positive)" in memories_tavern_prompt
    assert "- Stole bread in the tavern (Emotion: negative)" in memories_tavern_prompt
    assert "Found a map" not in memories_tavern_prompt

    assert "WORLD MEMORIES" in memories_forest_prompt
    assert "- Helped Bob (Emotion: positive)" in memories_forest_prompt
    assert "- Found a map in the forest (Emotion: neutral)" in memories_forest_prompt
    assert "Stole bread" not in memories_forest_prompt
