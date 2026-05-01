import pytest
import json
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy import select

from backend.models.user import User
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.session_state import SessionState
from backend.models.chat import ChatMessage
from backend.models.world_entity import WorldEntity
from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.engine.rule_engine import GameEvent

pytestmark = pytest.mark.asyncio

async def _seed_game_context(db):
    """Seeds a minimal game context for turn testing."""
    user = User(username="player1", hashed_password="pw", role="user")
    adv = AdventureTemplate(
        id="adv-1", 
        title="Test Adventure", 
        owner_id="admin",
        time_per_turn=5,
        strict_rules=True
    )
    db.add_all([user, adv])
    await db.flush()
    
    avatar = Avatar(
        id="av-1",
        template_id=adv.id,
        user_id=user.id,
        name="Hero",
        role="Warrior",
        hp=100,
        stats={"strength": 10, "dexterity": 10}
    )
    db.add(avatar)
    await db.flush()
    
    state = SessionState(
        session_id="session-1",
        template_id=adv.id,
        avatar_id=avatar.id,
        user_id=user.id,
        current_scene_id="START",
        in_game_time=0
    )
    db.add(state)
    await db.commit()
    return user, adv, avatar, state

async def test_game_loop_standard_turn(setup_test_db, monkeypatch):
    """Verifies a standard turn with Pass 1 (Mechanics) and Pass 2 (Narration)."""
    from tests.conftest import TestSessionLocal
    
    async with TestSessionLocal() as db:
        user, adv, avatar, state = await _seed_game_context(db)
        
        # Mock LLM
        mock_llm_instance = MagicMock()
        
        # Pass 1: Returns a GameEvent with no changes
        mock_event = GameEvent(
            narrative_description="You walk into the room.",
            hp_change=0,
            stamina_change=0,
            mana_change=0,
            new_status_effects=[],
            new_inventory_items=[],
            scene_change=None,
            requested_skill_checks=[]
        )
        mock_llm_instance.aexecute_complex_task = AsyncMock(return_value=mock_event)
        
        # Pass 2: Returns narration stream
        async def mock_stream(*args, **kwargs):
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="The "))])
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="room "))])
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="is "))])
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="dark."))])
            
        mock_llm_instance.stream_simple_task = AsyncMock(return_value=mock_stream())
        
        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.GameMasterLLM", lambda *args, **kwargs: mock_llm_instance)
        
        # Act
        manager = GameTurnManager(db, "session-1", user)
        chunks = []
        async for chunk in manager.process_turn("I look around"):
            chunks.append(chunk)
            
        # Assert
        full_response = "".join(chunks)
        assert "The " in full_response
        assert "room " in full_response
        assert "is " in full_response
        assert "dark." in full_response
        
        # Check if state was updated (time)
        await db.refresh(state)
        assert state.in_game_time == 5
        
        # Check if chat message was recorded
        res = await db.execute(select(ChatMessage).where(ChatMessage.session_id == "session-1", ChatMessage.role == "user"))
        user_msg = res.scalars().first()
        assert user_msg.content == "I look around"

async def test_game_loop_session_overrides_template(setup_test_db, monkeypatch):
    """Verifies that the GameMaster receives plot/rules from SessionState, not AdventureTemplate."""
    from tests.conftest import TestSessionLocal
    from backend.engine.memory_manager import MemoryManager
    
    async with TestSessionLocal() as db:
        user, adv, avatar, state = await _seed_game_context(db)
        
        # Override session state narrative
        state.plot = "SESSION PLOT"
        state.rules = "SESSION RULES"
        await db.commit()
        
        # Mock MemoryManager.build_context to spy on arguments
        original_build = MemoryManager.build_context
        spy_context = {}
        
        def mock_build(*args, **kwargs):
            spy_context['plot'] = kwargs.get('plot')
            spy_context['rules'] = kwargs.get('rules')
            return original_build(*args, **kwargs)
            
        monkeypatch.setattr("backend.engine.memory_manager.MemoryManager.build_context", mock_build)
        
        # Mock LLM to avoid actual calls
        mock_llm_instance = MagicMock()
        mock_llm_instance.aexecute_complex_task = AsyncMock(return_value=GameEvent(
            narrative_description="OK",
            hp_change=0,
            stamina_change=0,
            mana_change=0,
            new_status_effects=[],
            new_inventory_items=[]
        ))
        
        async def mock_stream(*args, **kwargs):
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="Narrative"))])
        mock_llm_instance.stream_simple_task = AsyncMock(return_value=mock_stream())
        
        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.GameMasterLLM", lambda *args, **kwargs: mock_llm_instance)
        
        # Act
        manager = GameTurnManager(db, "session-1", user)
        async for _ in manager.process_turn("Hello"):
            pass
            
        # Assert
        assert spy_context['plot'] == "SESSION PLOT"
        assert spy_context['rules'] == "SESSION RULES"

async def test_game_loop_skill_check_trigger(setup_test_db, monkeypatch):
    """Verifies that the game loop processes skill checks requested by the GM."""
    from tests.conftest import TestSessionLocal
    
    async with TestSessionLocal() as db:
        user, adv, avatar, state = await _seed_game_context(db)
        
        mock_llm_instance = MagicMock()
        
        # Pass 1: Requests a Strength check
        from backend.engine.rule_engine import SkillCheckRequest
        mock_event = GameEvent(
            narrative_description="The door is heavy.",
            hp_change=0,
            stamina_change=0,
            mana_change=0,
            new_status_effects=[],
            new_inventory_items=[],
            requested_skill_checks=[SkillCheckRequest(stat="strength", dc=12, reason="Opening the heavy door")]
        )
        mock_llm_instance.aexecute_complex_task = AsyncMock(return_value=mock_event)
        
        # Pass 2: Acknowledges the check
        async def mock_stream(*args, **kwargs):
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="You strain against the wood..."))])
            
        mock_llm_instance.stream_simple_task = AsyncMock(return_value=mock_stream())
        
        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.GameMasterLLM", lambda *args, **kwargs: mock_llm_instance)
        
        # Mock dice roll to ensure predictable outcome
        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.roll_skill_check", lambda *args, **kwargs: {"d20": 15, "modifier": 0, "total": 15, "success": True})
        
        # Act
        manager = GameTurnManager(db, "session-1", user)
        chunks = []
        async for chunk in manager.process_turn("I push the door"):
            chunks.append(chunk)
            
        # Assert
        # Verify skill check was yielded as a system message with dice roll details
        full_response = "".join(chunks)
        assert "event: system" in full_response
        assert "STRENGTH CHECK" in full_response
        assert "Opening the heavy door" in full_response
        assert "SUCCESS" in full_response

async def test_game_loop_scene_change(setup_test_db, monkeypatch):
    """Verifies that the GM can trigger a scene change that updates the session state."""
    from tests.conftest import TestSessionLocal
    
    async with TestSessionLocal() as db:
        user, adv, avatar, state = await _seed_game_context(db)
        
        mock_llm_instance = MagicMock()
        mock_event = GameEvent(
            narrative_description="You descend into the cellar.",
            hp_change=0,
            stamina_change=0,
            mana_change=0,
            new_status_effects=[],
            new_inventory_items=[],
            new_scene_id="CELLAR"
        )
        mock_llm_instance.aexecute_complex_task = AsyncMock(return_value=mock_event)
        
        async def mock_stream(*args, **kwargs):
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="The air is damp here."))])
        mock_llm_instance.stream_simple_task = AsyncMock(return_value=mock_stream())
        
        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.GameMasterLLM", lambda *args, **kwargs: mock_llm_instance)
        
        # Act
        manager = GameTurnManager(db, "session-1", user)
        async for _ in manager.process_turn("I go down"):
            pass
            
        # Assert
        await db.refresh(state)
        assert state.current_scene_id == "CELLAR"

async def test_game_loop_slash_command_inventory(setup_test_db, monkeypatch):
    """Verifies that slash commands (like /inventory) are handled directly without LLM calls."""
    from tests.conftest import TestSessionLocal
    
    async with TestSessionLocal() as db:
        user, adv, avatar, state = await _seed_game_context(db)
        avatar.inventory = [{"id": "DAGGER", "name": "Rusty Dagger"}]
        await db.commit()
        
        mock_llm_call = AsyncMock()
        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.GameMasterLLM", mock_llm_call)
        
        # Act
        manager = GameTurnManager(db, "session-1", user)
        chunks = []
        async for chunk in manager.process_turn("/inventory"):
            chunks.append(chunk)
            
        # Assert
        # Should NOT call LLM
        assert mock_llm_call.call_count == 0
        assert any("Rusty Dagger" in c for c in chunks)
        assert any("event: system" in c for c in chunks)

async def test_rule_engine_apply_ticks():
    """Verifies that status effect ticks correctly update avatar resources."""
    avatar = Avatar(hp=100, stamina=100, mana=100, status_effects=["Poisoned", "Resting"])
    
    from backend.engine.rule_engine import RuleEngine
    messages = RuleEngine.apply_ticks(avatar)
    
    assert avatar.hp == 95 # Poisoned: -5
    assert avatar.stamina == 103 # Resting: +3
    assert avatar.mana == 103
    assert any("Poisoned" in m for m in messages)

async def test_rule_engine_apply_event_game_over():
    """Verifies that the rule engine raises GameOverException when HP reaches 0."""
    avatar = Avatar(name="Hero", hp=10, stamina=10, mana=10)
    event = GameEvent(
        narrative_description="A fatal blow!",
        hp_change=-20,
        stamina_change=0,
        mana_change=0,
        new_status_effects=[],
        new_inventory_items=[]
    )
    
    from backend.engine.rule_engine import RuleEngine, GameOverException
    import pytest
    with pytest.raises(GameOverException):
        RuleEngine.apply_event(avatar, event)
    assert avatar.hp == 0


async def _seed_combat_npc(db) -> tuple[User, AdventureTemplate, Avatar, SessionState, WorldEntity]:
    user, adv, avatar, state = await _seed_game_context(db)
    adv.rule_enforcement_mode = "rpg"
    npc = WorldEntity(
        id="RAT_ENEMY",
        session_id=state.session_id,
        template_id=None,
        entity_type="NPC",
        name="Giant Rat",
        description="A vicious sewer rat.",
        current_scene_id=state.current_scene_id,
        hp=40,
        max_hp=40,
        stat_modifier_dexterity=2,
        stat_modifier_armor_class=1,
        inventory=[{"id": "RAT_TOOTH", "name": "Rat Tooth", "item_type": "PICKABLE"}],
        is_hidden=False,
        is_in_inventory=False,
        is_portable=False,
    )
    db.add(npc)
    await db.commit()
    return user, adv, avatar, state, npc


async def test_combat_start_creates_state(setup_test_db):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, _adv, _avatar, state, _npc = await _seed_combat_npc(db)
        manager = GameTurnManager(db, state.session_id, user)
        chunks = []
        async for chunk in manager.process_turn("/fight RAT_ENEMY"):
            chunks.append(chunk)

        await db.refresh(state)
        combat = (state.entity_states or {}).get("__combat__")
        assert combat is not None
        assert combat.get("active") is True
        assert combat.get("enemy", {}).get("id") == "RAT_ENEMY"
        assert any("event: final" in c for c in chunks)


async def test_combat_attack_defeat_enables_loot_phase(setup_test_db, monkeypatch):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, _adv, _avatar, state, _npc = await _seed_combat_npc(db)
        manager = GameTurnManager(db, state.session_id, user)

        # Start combat.
        async for _ in manager.process_turn("/fight RAT_ENEMY"):
            pass

        # Force lethal player hit.
        monkeypatch.setattr(
            "backend.api.routes.adventures.gameplay_logic.roll_attack",
            lambda *_args, **_kwargs: {
                "hit_roll": 19,
                "hit_modifier": 5,
                "hit_total": 24,
                "target_ac": 11,
                "is_hit": True,
                "damage_total": 60,
                "damage_dice_total": 60,
                "damage_rolls": [60],
                "damage_bonus": 0,
                "damage_dice_str": "1d8",
            },
        )

        async for _ in manager.process_turn("/attack"):
            pass

        await db.refresh(state)
        combat = (state.entity_states or {}).get("__combat__")
        assert combat is not None
        assert combat.get("active") is False
        assert combat.get("outcome") == "victory"
        assert combat.get("loot_pending") is True
        assert len(combat.get("loot_items") or []) == 1


async def test_combat_loot_take_moves_item_to_inventory(setup_test_db, monkeypatch):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, _adv, avatar, state, _npc = await _seed_combat_npc(db)
        manager = GameTurnManager(db, state.session_id, user)

        # Deterministic initiative so the player can act first.
        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.random.randint", lambda *_args, **_kwargs: 20)

        async for _ in manager.process_turn("/fight RAT_ENEMY"):
            pass

        monkeypatch.setattr(
            "backend.api.routes.adventures.gameplay_logic.roll_attack",
            lambda *_args, **_kwargs: {
                "hit_roll": 20,
                "hit_modifier": 5,
                "hit_total": 25,
                "target_ac": 11,
                "is_hit": True,
                "damage_total": 60,
                "damage_dice_total": 60,
                "damage_rolls": [60],
                "damage_bonus": 0,
                "damage_dice_str": "1d8",
            },
        )

        async for _ in manager.process_turn("/attack"):
            pass
        async for _ in manager.process_turn("/loot take RAT_TOOTH"):
            pass

        await db.refresh(avatar)
        assert any((item or {}).get("id") == "RAT_TOOTH" for item in (avatar.inventory or []))


async def test_combat_auto_triggers_from_gm_requested_attacks(setup_test_db, monkeypatch):
    from tests.conftest import TestSessionLocal
    from backend.engine.rule_engine import AttackRequest

    async with TestSessionLocal() as db:
        user, _adv, _avatar, state, _npc = await _seed_combat_npc(db)

        mock_llm_instance = MagicMock()
        mock_event = GameEvent(
            narrative_description="The rat leaps forward.",
            hp_change=0,
            stamina_change=0,
            mana_change=0,
            new_status_effects=[],
            new_inventory_items=[],
            requested_attacks=[
                AttackRequest(
                    attacker_id="RAT_ENEMY",
                    target_id="PLAYER",
                    hit_stat="dexterity",
                    damage_dice="1d6",
                    reason="The rat lunges",
                )
            ],
        )
        mock_llm_instance.aexecute_complex_task = AsyncMock(return_value=mock_event)

        async def mock_stream(*_args, **_kwargs):
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="ignored"))])

        mock_llm_instance.stream_simple_task = AsyncMock(return_value=mock_stream())
        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.GameMasterLLM", lambda *args, **kwargs: mock_llm_instance)

        manager = GameTurnManager(db, state.session_id, user)
        async for _ in manager.process_turn("I approach the rat"):
            pass

        await db.refresh(state)
        combat = (state.entity_states or {}).get("__combat__")
        assert combat is not None
        assert combat.get("active") is True
        assert combat.get("enemy", {}).get("id") == "RAT_ENEMY"


async def test_combat_special_event_damage_updates_player_hp_snapshot(setup_test_db, monkeypatch):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, _adv, avatar, state, _npc = await _seed_combat_npc(db)
        manager = GameTurnManager(db, state.session_id, user)

        # Deterministic initiative so the player acts first.
        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.random.randint", lambda *_args, **_kwargs: 20)

        async for _ in manager.process_turn("/fight RAT_ENEMY"):
            pass

        # Player and enemy both miss; only the special-event damage should apply.
        monkeypatch.setattr(
            "backend.api.routes.adventures.gameplay_logic.roll_attack",
            lambda *_args, **_kwargs: {
                "hit_roll": 3,
                "hit_modifier": 0,
                "hit_total": 3,
                "target_ac": 11,
                "is_hit": False,
                "damage_total": 0,
                "damage_dice_total": 0,
                "damage_rolls": [],
                "damage_bonus": 0,
                "damage_dice_str": "1d6",
            },
        )

        # First random.random call enters special-event branch, second chooses damage event.
        rolls = iter([0.0, 0.0])
        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.random.random", lambda: next(rolls, 1.0))

        async for _ in manager.process_turn("/attack"):
            pass

        await db.refresh(avatar)
        await db.refresh(state)
        combat = (state.entity_states or {}).get("__combat__") or {}
        assert avatar.hp == 80
        assert (combat.get("player") or {}).get("hp") == 80
