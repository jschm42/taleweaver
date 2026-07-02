import pytest
from sqlalchemy import select
from unittest.mock import AsyncMock, MagicMock

from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.engine.rule_engine import GameEvent, InventoryItem
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.session_state import SessionState
from backend.models.user import User
from backend.models.world_entity import WorldEntity

pytestmark = pytest.mark.asyncio

async def _seed_game_context(db):
    """Seeds a minimal game context for turn testing."""
    user = User(username="player1", hashed_password="pw", role="user")
    adv = AdventureTemplate(
        id="adv-dynamic", 
        title="Dynamic Item Adventure", 
        owner_id="admin",
        time_per_turn=5,
        strict_rules=True
    )
    db.add_all([user, adv])
    await db.flush()
    
    avatar = Avatar(
        id="av-dynamic",
        template_id=adv.id,
        user_id=user.id,
        name="Dynamic Hero",
        role="Explorer",
        hp=50,
        max_hp=100,
        stats={"strength": 10, "dexterity": 10},
        inventory=[]
    )
    db.add(avatar)
    await db.flush()
    
    state = SessionState(
        session_id="session-dynamic",
        template_id=adv.id,
        avatar_id=avatar.id,
        user_id=user.id,
        current_scene_id="START",
        in_game_time=0
    )
    db.add(state)
    await db.commit()
    return user, adv, avatar, state

async def test_dynamic_item_generation_is_blocked(setup_test_db, monkeypatch):
    """Verifies that the GM/LLM is blocked from spawning new items that do not exist in the template."""
    from tests.conftest import TestSessionLocal
    
    async with TestSessionLocal() as db:
        user, adv, avatar, state = await _seed_game_context(db)
        
        # Mock LLM Pass 1 to return a spawned item (Magic Potion - not in DB)
        mock_llm_instance = MagicMock()
        mock_event = GameEvent(
            narrative_description="A mysterious potion appears on the altar.",
            hp_change=0,
            stamina_change=0,
            mana_change=0,
            new_status_effects=[],
            new_inventory_items=[],
            spawned_items=[
                InventoryItem(
                    id="DYNAMIC_POTION",
                    name="Magic Potion",
                    description="A potion created on-the-fly.",
                    item_type="CONSUMABLE",
                    hp_change=30,
                    spatial_position="on the altar"
                )
            ]
        )
        mock_llm_instance.aexecute_complex_task = AsyncMock(return_value=mock_event)
        
        # Mock Pass 2
        async def mock_stream(*args, **kwargs):
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="The potion glows."))])
        mock_llm_instance.stream_simple_task = AsyncMock(return_value=mock_stream())
        
        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.GameMasterLLM", lambda *args, **kwargs: mock_llm_instance)
        
        # Act
        manager = GameTurnManager(db, state.session_id, user)
        # We process the turn. The guardrail should intercept, log warning, filter out item, and yield a system message.
        chunks = []
        async for chunk in manager.process_turn("I search the altar"):
            chunks.append(chunk)
            
        # Assert: Check that WorldEntity was NOT created in DB
        res = await db.execute(select(WorldEntity).where(
            WorldEntity.session_id == state.session_id,
            WorldEntity.name == "Magic Potion"
        ))
        potion_ent = res.scalars().first()
        assert potion_ent is None

        # Check that the system message notified about the blocked item
        full_output = "".join(chunks)
        assert "Spontaneous item generation blocked" in full_output

async def test_debug_commands_toggle_rejected_and_drops(setup_test_db, monkeypatch):
    """Verifies that debug toggle for dynamic items is permanently disabled but drops work."""
    from tests.conftest import TestSessionLocal
    from backend.core.config import settings
    monkeypatch.setattr(settings, "TALEWEAVER_DEBUG_ENABLED", False)
    
    async with TestSessionLocal() as db:
        user, adv, avatar, state = await _seed_game_context(db)
        
        # Verify initial states
        assert not state.is_debug_enabled
        assert not state.allow_dynamic_items
        
        # 1. Test /debug on
        manager = GameTurnManager(db, state.session_id, user)
        async for _ in manager.process_turn("/debug on"):
            pass
        await db.refresh(state)
        assert state.is_debug_enabled
        
        # 2. Test /debug item dynamic on (should return error and keep allow_dynamic_items False)
        chunks = []
        async for chunk in manager.process_turn("/debug item dynamic on"):
            chunks.append(chunk)
        await db.refresh(state)
        assert not state.allow_dynamic_items
        assert "permanently disabled" in "".join(chunks)
        
        # 3. Test /debug npc drop_items
        # First, seed an NPC with inventory items in the current scene
        npc = WorldEntity(
            id="NPC_MARGE",
            session_id=state.session_id,
            entity_type="NPC",
            name="Marge",
            description="A friendly chef.",
            current_scene_id=state.current_scene_id,
            inventory=[
                {"id": "KITCHEN_KEY", "name": "Kitchen Key", "item_type": "KEY"}
            ]
        )
        db.add(npc)
        
        # Seed the kitchen key so it exists as a pre-defined item
        key = WorldEntity(
            id="KITCHEN_KEY",
            session_id=state.session_id,
            entity_type="OBJECT",
            name="Kitchen Key",
            description="Key to the kitchen.",
            current_scene_id="START",
            is_in_inventory=False,
            is_hidden=True
        )
        db.add(key)
        await db.commit()
        
        # Run /debug npc drop_items
        async for _ in manager.process_turn("/debug npc drop_items"):
            pass
            
        # Verify NPC inventory is cleared in DB
        await db.refresh(npc)
        assert npc.inventory == []
        
        # Verify item was spawned (visible) in the current scene
        res = await db.execute(select(WorldEntity).where(
            WorldEntity.session_id == state.session_id,
            WorldEntity.id == "KITCHEN_KEY"
        ))
        key_ent = res.scalars().first()
        assert key_ent is not None
        assert not key_ent.is_in_inventory
        assert key_ent.is_hidden is False
        assert key_ent.current_scene_id == state.current_scene_id

        # 4. Test /debug off
        async for _ in manager.process_turn("/debug off"):
            pass
        await db.refresh(state)
        assert not state.is_debug_enabled
