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


async def test_npc_inventory_sync_and_name_fallback_spawning(setup_test_db, monkeypatch):
    """Verifies NPC inventories are synced and fallback name-matching is used when spawning scene items."""
    from tests.conftest import TestSessionLocal
    from backend.engine.memory_manager import MemoryManager
    
    async with TestSessionLocal() as db:
        user, adv, avatar, state, npc = await _seed_npc_context(db)
        
        # 1. Give the NPC an item in the database
        npc.inventory = [{"id": "KITCHEN_KEY", "name": "Kitchen Key", "item_type": "KEY"}]
        await db.commit()
        
        # 2. Test MemoryManager formats NPC inventories into prompts
        scene_res = await db.execute(
            select(WorldScene).where(
                WorldScene.id == state.current_scene_id,
                WorldScene.session_id == "session-npc"
            )
        )
        current_scene = scene_res.scalars().first()

        ctx = MemoryManager._build_location_context(
            current_scene=current_scene,
            entities=[npc],
            exits=[]
        )
        assert "[Inventory: Kitchen Key (ID: KITCHEN_KEY)]" in ctx

        world_ctx = MemoryManager._build_world_npcs_context(other_npcs=[npc])
        assert "Inventory: Kitchen Key (ID: KITCHEN_KEY)" in world_ctx

        # 3. Instantiate GameTurnManager
        manager = GameTurnManager(db, "session-npc", user)
        await manager.initialize()

        # Verify reduced NPCs for fast pass contains inventory
        reduced_npcs = manager._build_chat_progression_npcs([npc])
        assert reduced_npcs[0]["inventory"] == [{"id": "KITCHEN_KEY", "name": "Kitchen Key", "item_type": "KEY"}]

        # Verify _build_chat_rule_pass_prompt appends allow_dynamic_items instructions
        adv.allow_dynamic_items = False
        await db.commit()
        prompt_disabled = manager._build_chat_rule_pass_prompt([], [], reduced_npcs, [], [])
        assert "DYNAMIC ITEMS IS DISABLED" in prompt_disabled
        assert "You must ONLY move/use pre-defined items" in prompt_disabled

        adv.allow_dynamic_items = True
        await db.commit()
        prompt_enabled = manager._build_chat_rule_pass_prompt([], [], reduced_npcs, [], [])
        assert "DYNAMIC ITEMS IS ENABLED" in prompt_enabled

        # 4. Test fallback name matching when spawning an item in _spawn_scene_item
        key_obj = WorldEntity(
            id="KITCHEN_KEY",
            session_id="session-npc",
            entity_type="OBJECT",
            name="Kitchen Key",
            description="Opens the kitchen door.",
            current_scene_id="KITCHEN",
            is_in_inventory=False,
            item_type="KEY"
        )
        db.add(key_obj)
        await db.commit()

        mock_llm_instance = MagicMock()
        from backend.engine.rule_engine import InventoryItem
        mock_event = GameEvent(
            narrative_description="The key is dropped.",
            spawned_items=[
                InventoryItem(id="", name="Kitchen Key")
            ],
            updated_entities=[
                WorldEntityUpdate(entity_id="MARGE", inventory=[])
            ]
        )
        mock_llm_instance.aexecute_complex_task = AsyncMock(return_value=mock_event)
        
        async def mock_stream(*args, **kwargs):
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="Marge drops the key."))])
        mock_llm_instance.stream_simple_task = AsyncMock(return_value=mock_stream())
        
        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.GameMasterLLM", lambda *args, **kwargs: mock_llm_instance)
        
        # Act
        async for _ in manager.process_turn("Marge drops the key"):
            pass

        # Assert
        await db.refresh(state)
        res = await db.execute(
            select(WorldEntity).where(
                WorldEntity.session_id == "session-npc",
                WorldEntity.name == "Kitchen Key"
            )
        )
        keys = res.scalars().all()
        assert len(keys) == 1
        assert keys[0].id == "KITCHEN_KEY"
        assert keys[0].current_scene_id == "KITCHEN"
        assert keys[0].is_in_inventory is False

        marge_state = (state.entity_states or {}).get("MARGE")
        assert marge_state is not None
        assert marge_state["inventory"] == []
