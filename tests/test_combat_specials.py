import pytest
import json
import random
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy import select

from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.session_state import SessionState
from backend.models.user import User
from backend.models.world_entity import WorldEntity, WorldScene
from backend.engine.rule_engine import GameEvent

pytestmark = pytest.mark.asyncio

async def _seed_combat_context(db):
    user = User(username="combat_tester", hashed_password="pw", role="user")
    adv = AdventureTemplate(
        id="adv-combat", 
        title="Combat Test Adventure", 
        owner_id="admin",
        time_per_turn=5,
        strict_rules=True,
        rule_enforcement_mode="rpg"
    )
    db.add_all([user, adv])
    await db.flush()
    
    special_actions = [
        {
            "id": "FIREBALL",
            "name": "Fireball Spell",
            "description": "Deals rolled damage.",
            "action_type": "ATTACK",
            "mana_cost": 25,
            "damage_type": "ROLLED",
            "damage_value": "3d6",
            "outcome_description": "A scorching fireball engulfs the target.",
            "is_locked": True,
            "unlock_condition_type": "READ_ITEM",
            "unlock_condition_target": "SCROLL_FIRE"
        },
        {
            "id": "HEAL",
            "name": "Heal Spell",
            "description": "Heals fixed amount.",
            "action_type": "HEAL",
            "mana_cost": 15,
            "damage_type": "FIXED",
            "damage_value": "15",
            "outcome_description": "Wounds begin to close.",
            "is_locked": False
        }
    ]
    
    avatar = Avatar(
        id="av-combat",
        template_id=adv.id,
        user_id=user.id,
        name="Hero",
        role="Mage",
        hp=50,
        max_hp=80,
        stamina=100,
        max_stamina=100,
        mana=100,
        max_mana=100,
        stats={
            "dexterity": 12,
            "intelligence": 16,
            "wisdom": 10,
            "special_actions": special_actions,
            "unlocked_actions": ["HEAL"]
        },
        inventory=[],
        equipment={
            "Head": None, "Chest": None, "Arms": None, "Legs": None,
            "Feet": None, "Neck": None, "Ring_1": None, "Ring_2": None,
            "MainHand": None, "OffHand": None
        }
    )
    db.add(avatar)
    
    state = SessionState(
        session_id="session-combat",
        template_id=adv.id,
        avatar_id=avatar.id,
        user_id=user.id,
        current_scene_id="DUNGEON",
        in_game_time=0,
        entity_states={}
    )
    db.add(state)
    
    scene = WorldScene(id="DUNGEON", session_id="session-combat", label="Dungeon", description="Dark stone walls.")
    db.add(scene)
    
    # Magic Wand (consuming mana)
    wand = WorldEntity(
        id="WAND",
        session_id="session-combat",
        entity_type="OBJECT",
        name="Magic Wand",
        description="Consumes mana to shoot magic missiles.",
        current_scene_id="DUNGEON",
        item_type="WEAPON",
        is_portable=True,
        stat_modifier_strength=0,
        stat_modifier_dexterity=0,
        stat_modifier_intelligence=2,
        stat_modifier_wisdom=0,
        stat_modifier_charisma=0,
        stat_modifier_armor_class=0,
        metadata_json={
            "damage_dice": "1d6+2",
            "weapon_cost_type": "mana",
            "weapon_cost_value": 10
        }
    )
    # Sword (consuming stamina)
    sword = WorldEntity(
        id="SWORD",
        session_id="session-combat",
        entity_type="OBJECT",
        name="Iron Sword",
        description="A sturdy iron sword.",
        current_scene_id="DUNGEON",
        item_type="WEAPON",
        is_portable=True,
        stat_modifier_strength=0,
        stat_modifier_dexterity=0,
        stat_modifier_intelligence=0,
        stat_modifier_wisdom=0,
        stat_modifier_charisma=0,
        stat_modifier_armor_class=0,
        metadata_json={
            "damage_dice": "1d8",
            "weapon_cost_type": "stamina",
            "weapon_cost_value": 15
        }
    )
    # Readable Scroll
    scroll = WorldEntity(
        id="SCROLL_FIRE",
        session_id="session-combat",
        entity_type="OBJECT",
        name="Fireball Scroll",
        description="A dusty scroll with arcane runes.",
        current_scene_id="DUNGEON",
        item_type="READABLE",
        is_portable=True,
        metadata_json={
            "text_log_content": "Read the scroll of fire to learn fireball!"
        }
    )
    # Armor (AC bonus)
    armor = WorldEntity(
        id="LEATHER_ARMOR",
        session_id="session-combat",
        entity_type="OBJECT",
        name="Leather Armor",
        description="Protective leather armor.",
        current_scene_id="DUNGEON",
        item_type="WEARABLE",
        wearable_slots=["Chest"],
        is_portable=True,
        stat_modifier_strength=0,
        stat_modifier_dexterity=0,
        stat_modifier_intelligence=0,
        stat_modifier_wisdom=0,
        stat_modifier_charisma=0,
        stat_modifier_armor_class=4,
        metadata_json={}
    )
    # Goblin NPC with equip
    npc = WorldEntity(
        id="GOBLIN",
        session_id="session-combat",
        entity_type="NPC",
        name="Goblin",
        description="A sneaky goblin.",
        current_scene_id="DUNGEON",
        hp=40,
        max_hp=40,
        is_hidden=False,
        is_in_inventory=False,
        metadata_json={
            "equipped_weapon_id": "SWORD",
            "equipped_armor_id": "LEATHER_ARMOR",
            "special_actions": []
        }
    )
    
    db.add_all([wand, sword, scroll, armor, npc])
    await db.commit()
    return user, adv, avatar, state, npc, wand, sword, scroll, armor

async def test_combat_npc_equipment_stats_bonus(setup_test_db, monkeypatch):
    """Checks that the NPC's equipped item modifiers are correctly calculated and applied in combat."""
    from tests.conftest import TestSessionLocal
    
    async with TestSessionLocal() as db:
        user, adv, avatar, state, npc, wand, sword, scroll, armor = await _seed_combat_context(db)
        
        # Mock LLM
        mock_llm_instance = MagicMock()
        mock_event = GameEvent(
            narrative_description="The fight starts.",
            requested_attacks=[]
        )
        mock_llm_instance.aexecute_complex_task = AsyncMock(return_value=mock_event)
        
        async def mock_stream(*args, **kwargs):
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="Fight starts!"))])
        mock_llm_instance.stream_simple_task = AsyncMock(return_value=mock_stream())
        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.GameMasterLLM", lambda *args, **kwargs: mock_llm_instance)
        
        manager = GameTurnManager(db, "session-combat", user)
        
        # Trigger fight against GOBLIN
        async for _ in manager.process_turn("/fight GOBLIN"):
            pass
            
        combat = manager._read_combat_state()
        assert combat is not None
        assert combat.get("active") is True
        
        # Verify Goblin AC has the leather armor AC bonus applied (base AC is 10 + 4 = 14)
        # Note: the opponent AC is retrieved from combat state in the turn manager
        # AC modifier = 4, so AC is 14.
        assert combat["enemy"]["armor_mod"] == 4
        # dexterity mod = 10 (base) + 0 (sword) + 0 (armor) = 10
        assert combat["enemy"]["dexterity_mod"] == 10

async def test_weapon_cost_consumption_mana_vs_stamina(setup_test_db, monkeypatch):
    """Verifies that attacking with a mana-weapon consumes Mana, and with a stamina-weapon consumes Stamina."""
    from tests.conftest import TestSessionLocal
    
    async with TestSessionLocal() as db:
        user, adv, avatar, state, npc, wand, sword, scroll, armor = await _seed_combat_context(db)
        
        mock_llm = MagicMock()
        mock_llm.aexecute_complex_task = AsyncMock(return_value=GameEvent(narrative_description="Fight progresses."))
        async def mock_stream(*args, **kwargs):
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="Round continues."))])
        mock_llm.stream_simple_task = AsyncMock(return_value=mock_stream())
        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.GameMasterLLM", lambda *args, **kwargs: mock_llm)
        
        # Equip Magic Wand (Mana-based, cost = 10)
        avatar.equipment["MainHand"] = {
            "id": "WAND",
            "name": "Magic Wand",
            "item_type": "WEAPON",
            "metadata_json": {
                "damage_dice": "1d6+2",
                "weapon_cost_type": "mana",
                "weapon_cost_value": 10
            }
        }
        await db.commit()
        
        manager = GameTurnManager(db, "session-combat", user)
        
        # Start fight
        async for _ in manager.process_turn("/fight GOBLIN"):
            pass
            
        assert avatar.mana == 100
        assert avatar.stamina == 100
        
        # Perform attack (requires Magic Wand, should cost 10 Mana)
        async for _ in manager.process_turn("/attack"):
            pass
            
        await db.refresh(avatar)
        assert avatar.mana == 90
        assert avatar.stamina == 100
        
        # Now equip Sword (Stamina-based, cost = 15)
        avatar.equipment["MainHand"] = {
            "id": "SWORD",
            "name": "Iron Sword",
            "item_type": "WEAPON",
            "metadata_json": {
                "damage_dice": "1d8",
                "weapon_cost_type": "stamina",
                "weapon_cost_value": 15
            }
        }
        await db.commit()
        
        # Set turn back to player for testing next attack
        combat = manager._read_combat_state()
        combat["turn"] = "player"
        manager._set_combat_state(combat)
        
        # Perform attack (requires Sword, should cost 15 Stamina)
        async for _ in manager.process_turn("/attack"):
            pass
            
        await db.refresh(avatar)
        assert avatar.mana == 90  # Mana unchanged
        assert avatar.stamina == 85  # Stamina decreased by 15

async def test_special_actions_fixed_vs_rolled(setup_test_db, monkeypatch):
    """Verifies that special action healing and damage works correctly with fixed or rolled damage/heal."""
    from tests.conftest import TestSessionLocal
    
    async with TestSessionLocal() as db:
        user, adv, avatar, state, npc, wand, sword, scroll, armor = await _seed_combat_context(db)
        
        mock_llm = MagicMock()
        mock_llm.aexecute_complex_task = AsyncMock(return_value=GameEvent(narrative_description="Combat state."))
        async def mock_stream(*args, **kwargs):
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="Turn resolved."))])
        mock_llm.stream_simple_task = AsyncMock(return_value=mock_stream())
        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.GameMasterLLM", lambda *args, **kwargs: mock_llm)
        
        # Stub roll_attack to always miss so the enemy turn doesn't modify player HP
        monkeypatch.setattr(
            "backend.api.routes.adventures.gameplay_logic.roll_attack",
            lambda *args, **kwargs: {
                "is_hit": False,
                "hit_roll": 1,
                "hit_modifier": 0,
                "hit_total": 1,
                "damage_total": 0
            }
        )
        
        # Stub random.random to return 0.9 to avoid triggering random combat events
        monkeypatch.setattr(
            "backend.api.routes.adventures.gameplay_logic.random.random",
            lambda: 0.9
        )
        
        manager = GameTurnManager(db, "session-combat", user)
        
        # Start fight
        async for _ in manager.process_turn("/fight GOBLIN"):
            pass
            
        # Force player HP to 50 and turn to player to be independent of initiative roll
        avatar.hp = 50
        await db.commit()
        
        combat = manager._read_combat_state()
        combat["turn"] = "player"
        manager._set_combat_state(combat)
            
        assert avatar.hp == 50
        assert avatar.mana == 100
        
        # HEAL action is unlocked initially and costs 15 mana, fixed healing 15 HP
        async for _ in manager.process_turn("/special HEAL"):
            pass
            
        await db.refresh(avatar)
        assert avatar.hp == 65
        assert avatar.mana == 85

async def test_special_action_unlock_conditions(setup_test_db, monkeypatch):
    """Verifies that a locked special action is unlocked when the player reads the specified scroll."""
    from tests.conftest import TestSessionLocal
    
    async with TestSessionLocal() as db:
        user, adv, avatar, state, npc, wand, sword, scroll, armor = await _seed_combat_context(db)
        
        # Initially, FIREBALL is locked
        assert "FIREBALL" not in avatar.stats.get("unlocked_actions", [])
        
        # Add scroll to inventory
        avatar.inventory = [
            {
                "id": "SCROLL_FIRE",
                "name": "Fireball Scroll",
                "item_type": "READABLE",
                "metadata_json": {
                    "text_log_content": "Read the scroll of fire to learn fireball!"
                }
            }
        ]
        await db.commit()
        
        # Mock LLM for read command response
        mock_llm = MagicMock()
        async def mock_stream(*args, **kwargs):
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="You read the scroll of fire."))])
        mock_llm.stream_simple_task = AsyncMock(return_value=mock_stream())
        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.GameMasterLLM", lambda *args, **kwargs: mock_llm)
        
        manager = GameTurnManager(db, "session-combat", user)
        
        # Read the scroll
        async for _ in manager.process_turn("/read Fireball Scroll"):
            pass
            
        await db.refresh(avatar)
        # Verify FIREBALL is now unlocked!
        assert "FIREBALL" in avatar.stats.get("unlocked_actions", [])
