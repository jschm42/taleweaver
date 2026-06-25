import pytest
from backend.engine.rule_engine import GameEvent, WorldMemoryUpdate, RumorUpdate
from backend.models.session_state import SessionState
from backend.models.avatar import Avatar
from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.api.routes.adventures.turn_helpers import TurnSessionStateHelper
from unittest.mock import MagicMock, AsyncMock

def test_pydantic_game_event_memories_and_rumors():
    """Verify that GameEvent correctly parses memories and rumors in Pydantic."""
    event_data = {
        "narrative_description": "Test description",
        "new_world_memories": [
            {
                "description": "Test memory 1",
                "npc_id": "npc_1",
                "emotion": "negative"
            }
        ],
        "new_rumors": [
            {
                "text": "Test rumor 1",
                "source_scene_id": "SCENE_A",
                "target_scene_ids": ["SCENE_B"]
            }
        ]
    }
    
    event = GameEvent.model_validate(event_data)
    assert event.new_world_memories is not None
    assert len(event.new_world_memories) == 1
    assert event.new_world_memories[0].description == "Test memory 1"
    assert event.new_world_memories[0].emotion == "negative"
    
    assert event.new_rumors is not None
    assert len(event.new_rumors) == 1
    assert event.new_rumors[0].text == "Test rumor 1"
    assert event.new_rumors[0].target_scene_ids == ["SCENE_B"]

@pytest.mark.asyncio
async def test_apply_game_event_memories_and_rumors():
    """Verify that _apply_game_event correctly updates SessionState and generates system messages."""
    # Arrange
    manager = MagicMock(spec=GameTurnManager)
    manager.game_id = "test-game-id"
    state = SessionState()
    state.session_id = "test-game-id"
    state.entity_states = {}
    state.world_memories = []
    state.world_rumors = []
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
            WorldMemoryUpdate(description="You insulted the wizard. He is furious.", npc_id="wizard_npc", emotion="negative")
        ],
        new_rumors=[
            RumorUpdate(text="A traveler insulted the powerful wizard!", source_scene_id="TOWER", target_scene_ids=["TAVERN"])
        ]
    )

    # Act
    system_messages = await GameTurnManager._apply_game_event(manager, event)

    # Assert
    assert any("You insulted the wizard" in msg for msg in system_messages)
    assert len(manager.state.world_memories) == 1
    assert manager.state.world_memories[0]["description"] == "You insulted the wizard. He is furious."
    assert manager.state.world_memories[0]["emotion"] == "negative"
    assert manager.state.world_memories[0]["npc_id"] == "wizard_npc"
    
    assert len(manager.state.world_rumors) == 1
    assert manager.state.world_rumors[0]["text"] == "A traveler insulted the powerful wizard!"
    assert manager.state.world_rumors[0]["source_scene_id"] == "TOWER"
    assert manager.state.world_rumors[0]["target_scene_ids"] == ["TAVERN"]

def test_prompt_builders():
    """Verify that prompt builder blocks format world memories and rumors correctly."""
    # Arrange
    manager = MagicMock()
    state = MagicMock()
    state.world_memories = [
        {"id": "m1", "description": "Helped Bob", "emotion": "positive"},
        {"id": "m2", "description": "Stole bread", "emotion": "negative"}
    ]
    state.world_rumors = [
        {"id": "r1", "text": "Bob is happy", "target_scene_ids": ["*"]},
        {"id": "r2", "text": "Someone stole bread", "target_scene_ids": ["TAVERN"]}
    ]
    manager.state = state
    helper = TurnSessionStateHelper(
        manager,
        gm_notes_state_key="notes_key",
        gm_notes_max_items=10,
        terminal_epilogue_state_key="epilogue_key"
    )

    # Act
    memories_prompt = helper.build_world_memories_prompt_block()
    rumors_tavern_prompt = helper.build_rumors_prompt_block("TAVERN")
    rumors_forest_prompt = helper.build_rumors_prompt_block("FOREST")

    # Assert
    assert "WORLD MEMORIES" in memories_prompt
    assert "- Helped Bob (Emotion: positive)" in memories_prompt
    assert "- Stole bread (Emotion: negative)" in memories_prompt

    assert "ACTIVE RUMORS" in rumors_tavern_prompt
    assert "- Bob is happy" in rumors_tavern_prompt
    assert "- Someone stole bread" in rumors_tavern_prompt

    assert "ACTIVE RUMORS" in rumors_forest_prompt
    assert "- Bob is happy" in rumors_forest_prompt
    assert "- Someone stole bread" not in rumors_forest_prompt
