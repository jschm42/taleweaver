from unittest.mock import AsyncMock, MagicMock
import pytest
from sqlalchemy import select
from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.engine.rule_engine import GameEvent, EntityMovement, WorldEntityUpdate
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.chat import ChatMessage
from backend.models.session_state import SessionState
from backend.models.user import User
from backend.models.world_entity import WorldEntity, WorldScene, WorldExit

pytestmark = pytest.mark.asyncio

async def _seed_npc_context(db):
    """Seeds a game context with an NPC for testing."""
    user = User(username="npc_tester", hashed_password="pw", role="user")
    adv = AdventureTemplate(
        id="adv-npc", 
        title="NPC Test Adventure", 
        owner_id="admin",
        time_per_turn=5,
        strict_rules=True
    )
    db.add_all([user, adv])
    await db.flush()
    
    avatar = Avatar(
        id="av-npc",
        template_id=adv.id,
        user_id=user.id,
        name="Hero",
        role="Warrior",
        hp=100,
        stamina=100,
        mana=100,
        stats={"dexterity": 10},
        inventory=[],
        equipment={}
    )
    db.add(avatar)
    
    state = SessionState(
        session_id="session-npc",
        template_id=adv.id,
        avatar_id=avatar.id,
        user_id=user.id,
        current_scene_id="KITCHEN",
        in_game_time=0,
        entity_states={}
    )
    db.add(state)
    
    scene1 = WorldScene(id="KITCHEN", session_id="session-npc", label="Kitchen", description="A warm kitchen.")
    scene2 = WorldScene(id="LIVING_ROOM", session_id="session-npc", label="Living Room", description="A cozy living room.")
    db.add_all([scene1, scene2])
    
    npc = WorldEntity(
        id="MARGE",
        session_id="session-npc",
        entity_type="NPC",
        name="Marge",
        description="A friendly NPC.",
        current_scene_id="KITCHEN",
        spatial_position="by the stove",
        hp=50,
        max_hp=50,
        is_hidden=False,
        is_in_inventory=False
    )
    db.add(npc)
    await db.commit()
    return user, adv, avatar, state, npc

async def test_npc_movement_persistence(setup_test_db, monkeypatch):
    """Verifies that NPC movement triggered by the GM is persisted in SessionState."""
    from tests.conftest import TestSessionLocal
    
    async with TestSessionLocal() as db:
        user, adv, avatar, state, npc = await _seed_npc_context(db)
        
        # Mock LLM
        mock_llm_instance = MagicMock()
        
        # Pass 1: GM moves Marge to the Living Room
        mock_event = GameEvent(
            narrative_description="Marge walks into the living room.",
            moved_entities=[
                EntityMovement(entity_id="MARGE", to_scene_id="LIVING_ROOM", to_spatial_position="on the sofa")
            ]
        )
        mock_llm_instance.aexecute_complex_task = AsyncMock(return_value=mock_event)
        
        # Pass 2: Narration
        async def mock_stream(*args, **kwargs):
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="Marge leaves the kitchen."))])
            
        mock_llm_instance.stream_simple_task = AsyncMock(return_value=mock_stream())
        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.GameMasterLLM", lambda *args, **kwargs: mock_llm_instance)
        
        # Act
        manager = GameTurnManager(db, "session-npc", user)
        async for _ in manager.process_turn("Follow Marge"):
            pass
            
        # Assert
        await db.refresh(state)
        marge_state = (state.entity_states or {}).get("MARGE")
        assert marge_state is not None
        assert marge_state["current_scene_id"] == "LIVING_ROOM"
        assert marge_state["spatial_position"] == "on the sofa"

async def test_npc_update_persistence(setup_test_db, monkeypatch):
    """Verifies that NPC attribute updates (name, description, etc.) are persisted."""
    from tests.conftest import TestSessionLocal
    
    async with TestSessionLocal() as db:
        user, adv, avatar, state, npc = await _seed_npc_context(db)
        
        mock_llm_instance = MagicMock()
        
        # Pass 1: GM updates Marge's name and adds a description
        mock_event = GameEvent(
            narrative_description="Marge looks different now.",
            updated_entities=[
                WorldEntityUpdate(entity_id="MARGE", name="Angry Marge", description="She looks very upset.")
            ]
        )
        mock_llm_instance.aexecute_complex_task = AsyncMock(return_value=mock_event)
        
        async def mock_stream(*args, **kwargs):
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="Marge's face reddens."))])
            
        mock_llm_instance.stream_simple_task = AsyncMock(return_value=mock_stream())
        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.GameMasterLLM", lambda *args, **kwargs: mock_llm_instance)
        
        # Act
        manager = GameTurnManager(db, "session-npc", user)
        async for _ in manager.process_turn("Talk to Marge"):
            pass
            
        # Assert
        await db.refresh(state)
        marge_state = (state.entity_states or {}).get("MARGE")
        assert marge_state is not None
        assert marge_state["name"] == "Angry Marge"
        assert marge_state["description"] == "She looks very upset."

async def test_talk_command_trigger(setup_test_db, monkeypatch):
    """Verifies that /talk command correctly triggers an interaction turn."""
    from tests.conftest import TestSessionLocal
    
    async with TestSessionLocal() as db:
        user, adv, avatar, state, npc = await _seed_npc_context(db)
        
        mock_llm_instance = MagicMock()
        
        # We want to check what user message was sent to Pass 1
        captured_user_msg = []
        async def spy_aexecute(prompt, user_msg, **kwargs):
            captured_user_msg.append(user_msg)
            return GameEvent(narrative_description="Conversation started.")
        
        mock_llm_instance.aexecute_complex_task = AsyncMock(side_effect=spy_aexecute)
        
        async def mock_stream(*args, **kwargs):
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="Marge says hi."))])
        mock_llm_instance.stream_simple_task = AsyncMock(return_value=mock_stream())
        
        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.GameMasterLLM", lambda *args, **kwargs: mock_llm_instance)
        
        # Act
        manager = GameTurnManager(db, "session-npc", user)
        async for _ in manager.process_turn("/talk Marge"):
            pass
            
        # Assert
        # /talk Marge should be transformed into "Talk to Marge"
        assert captured_user_msg[0] == "Talk to Marge"
        
        # Verify it was saved as a chat message
        res = await db.execute(select(ChatMessage).where(ChatMessage.session_id == "session-npc", ChatMessage.role == "user"))
        msgs = res.scalars().all()
        # The first message is the transformed /talk Marge
        assert msgs[0].content == "/talk Marge"
