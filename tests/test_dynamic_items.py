from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select

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
        stats={"strength": 10, "dexterity": 10}
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

async def test_spawned_items_logic(setup_test_db, monkeypatch):
    """Verifies that the GM can spawn new items into the scene."""
    from tests.conftest import TestSessionLocal
    
    async with TestSessionLocal() as db:
        user, adv, avatar, state = await _seed_game_context(db)
        
        # Mock LLM Pass 1 to return a spawned item
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
        async for _ in manager.process_turn("I search the altar"):
            pass
            
        # Assert: Check if WorldEntity was created
        res = await db.execute(select(WorldEntity).where(
            WorldEntity.session_id == state.session_id,
            WorldEntity.name == "Magic Potion"
        ))
        potion_ent = res.scalars().first()
        assert potion_ent is not None
        assert potion_ent.spatial_position == "on the altar"
        assert potion_ent.metadata_json.get("hp_change") == 30

async def test_on_the_fly_inventory_item_effects(setup_test_db, monkeypatch):
    """Verifies that on-the-fly inventory items have correct resource effects when consumed."""
    from tests.conftest import TestSessionLocal
    
    async with TestSessionLocal() as db:
        user, adv, avatar, state = await _seed_game_context(db)
        
        # Mock LLM Pass 1 to give item directly
        mock_llm_instance = MagicMock()
        mock_event = GameEvent(
            narrative_description="You find a health herb and eat it (or keep it).",
            hp_change=0,
            stamina_change=0,
            mana_change=0,
            new_status_effects=[],
            new_inventory_items=[
                InventoryItem(
                    name="Health Herb",
                    description="A fresh herb.",
                    item_type="CONSUMABLE",
                    hp_change=15
                )
            ]
        )
        mock_llm_instance.aexecute_complex_task = AsyncMock(return_value=mock_event)
        
        # Mock Pass 2
        async def mock_stream(*args, **kwargs):
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="You tuck it away."))])
        mock_llm_instance.stream_simple_task = AsyncMock(return_value=mock_stream())
        
        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.GameMasterLLM", lambda *args, **kwargs: mock_llm_instance)
        
        # Act 1: Get the item
        manager = GameTurnManager(db, state.session_id, user)
        async for _ in manager.process_turn("I look for herbs"):
            pass
            
        # Assert 1: Item in inventory
        await db.refresh(avatar)
        assert any(it.get("name") == "Health Herb" for it in avatar.inventory)
        
        # Act 2: Consume the item
        # We need to re-initialize manager or at least ensure db session is fresh
        async for _ in manager.process_turn("/consume Health Herb"):
            pass
            
        # Assert 2: HP increased
        await db.refresh(avatar)
        assert avatar.hp == 65 # 50 + 15
        assert not any(it.get("name") == "Health Herb" for it in avatar.inventory)


async def test_generated_item_ids_are_deduplicated_against_session(setup_test_db, monkeypatch):
    """GM-generated items with existing IDs in the session must be skipped."""
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, adv, avatar, state = await _seed_game_context(db)

        existing = WorldEntity(
            id="ANCIENT_KEY",
            session_id=state.session_id,
            template_id=None,
            entity_type="OBJECT",
            name="Ancient Key",
            description="An old key already present in this session.",
            current_scene_id=state.current_scene_id,
            is_in_inventory=False,
            is_hidden=False,
            is_portable=True,
        )
        db.add(existing)
        await db.commit()

        mock_llm_instance = MagicMock()
        mock_event = GameEvent(
            narrative_description="You try to craft another key and summon one in the room.",
            hp_change=0,
            stamina_change=0,
            mana_change=0,
            new_status_effects=[],
            new_inventory_items=[
                InventoryItem(
                    id="ANCIENT_KEY",
                    name="Duplicate Ancient Key",
                    description="Should be ignored due to duplicate id."
                )
            ],
            spawned_items=[
                InventoryItem(
                    id="ANCIENT_KEY",
                    name="Duplicate Ancient Key (Spawned)",
                    description="Should be ignored due to duplicate id.",
                    spatial_position="on the floor"
                )
            ]
        )
        mock_llm_instance.aexecute_complex_task = AsyncMock(return_value=mock_event)

        async def mock_stream(*args, **kwargs):
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="Nothing new materializes."))])

        mock_llm_instance.stream_simple_task = AsyncMock(return_value=mock_stream())

        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.GameMasterLLM", lambda *args, **kwargs: mock_llm_instance)

        manager = GameTurnManager(db, state.session_id, user)
        async for _ in manager.process_turn("I craft a new key"):
            pass

        await db.refresh(avatar)
        assert not any(it.get("id") == "ANCIENT_KEY" and it.get("name") == "Duplicate Ancient Key" for it in (avatar.inventory or []))

        res = await db.execute(select(WorldEntity).where(
            WorldEntity.session_id == state.session_id,
            WorldEntity.id == "ANCIENT_KEY"
        ))
        entities = res.scalars().all()
        assert len(entities) == 1
        assert entities[0].name == "Ancient Key"


async def test_identical_consumable_is_cloned_with_visual(setup_test_db, monkeypatch):
    """Identical consumables should be cloned with a new id and keep the original visual."""
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, _adv, avatar, state = await _seed_game_context(db)
        avatar.inventory = [
            {
                "id": "HEALTH_POTION",
                "name": "Health Potion",
                "description": "A small healing potion.",
                "item_type": "CONSUMABLE",
                "hp_change": 25,
                "image_url": "generated/health-potion.webp",
            }
        ]
        await db.commit()

        mock_llm_instance = MagicMock()
        mock_event = GameEvent(
            narrative_description="You found another identical potion.",
            hp_change=0,
            stamina_change=0,
            mana_change=0,
            new_status_effects=[],
            new_inventory_items=[
                InventoryItem(
                    id="HEALTH_POTION",
                    name="Health Potion",
                    description="A small healing potion.",
                    item_type="CONSUMABLE",
                    hp_change=25,
                )
            ],
        )
        mock_llm_instance.aexecute_complex_task = AsyncMock(return_value=mock_event)

        async def mock_stream(*args, **kwargs):
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="You stash the second potion."))])

        mock_llm_instance.stream_simple_task = AsyncMock(return_value=mock_stream())

        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.GameMasterLLM", lambda *args, **kwargs: mock_llm_instance)

        manager = GameTurnManager(db, state.session_id, user)
        async for _ in manager.process_turn("I pick up another health potion"):
            pass

        await db.refresh(avatar)
        potions = [
            it for it in (avatar.inventory or [])
            if isinstance(it, dict) and it.get("name") == "Health Potion" and it.get("item_type") == "CONSUMABLE"
        ]
        assert len(potions) == 2

        potion_ids = {it.get("id") for it in potions}
        assert "HEALTH_POTION" in potion_ids
        assert any(str(pid).startswith("HEALTH_POTION_COPY_") for pid in potion_ids if pid)
        assert all(it.get("image_url") == "generated/health-potion.webp" for it in potions)


async def test_debug_commands_toggle_and_drops(setup_test_db, monkeypatch):
    """Verifies that debug commands toggle flags and cause NPCs to drop items."""
    from tests.conftest import TestSessionLocal
    from backend.core.config import settings
    monkeypatch.setattr(settings, "TALEWEAVER_DEBUG_ENABLED", False)
    
    async with TestSessionLocal() as db:
        user, adv, avatar, state = await _seed_game_context(db)
        
        # Verify initial states
        assert not state.is_debug_enabled
        assert state.allow_dynamic_items
        
        # 1. Test /debug on
        manager = GameTurnManager(db, state.session_id, user)
        async for _ in manager.process_turn("/debug on"):
            pass
        await db.refresh(state)
        assert state.is_debug_enabled
        
        # 2. Test /debug item dynamic off
        async for _ in manager.process_turn("/debug item dynamic off"):
            pass
        await db.refresh(state)
        assert not state.allow_dynamic_items
        
        # 3. Test /debug item dynamic on
        async for _ in manager.process_turn("/debug item dynamic on"):
            pass
        await db.refresh(state)
        assert state.allow_dynamic_items
        
        # 4. Test /debug npc drop_items
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
        await db.commit()
        
        # Run /debug npc drop_items
        async for _ in manager.process_turn("/debug npc drop_items"):
            pass
            
        # Verify NPC inventory is cleared in DB
        await db.refresh(npc)
        assert npc.inventory == []
        
        # Verify NPC inventory override is cleared in session state
        await db.refresh(state)
        assert state.entity_states.get("NPC_MARGE", {}).get("inventory") == []
        
        # Verify item was spawned in the current scene
        res = await db.execute(select(WorldEntity).where(
            WorldEntity.session_id == state.session_id,
            WorldEntity.id == "KITCHEN_KEY"
        ))
        key_ent = res.scalars().first()
        assert key_ent is not None
        assert not key_ent.is_in_inventory
        assert key_ent.current_scene_id == state.current_scene_id

        # 5. Test /debug off
        async for _ in manager.process_turn("/debug off"):
            pass
        await db.refresh(state)
        assert not state.is_debug_enabled

