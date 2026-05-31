# pyright: reportUnusedParameter=false, reportUnusedVariable=false, reportUnreachable=false
# pylint: disable=unused-argument,unused-variable,using-constant-test
# ruff: noqa: ARG001,F841,PLR0133

from unittest.mock import AsyncMock, MagicMock
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.engine.rule_engine import AdventureGeneratorToolIntent, ExitUpdate, GameEvent, InventoryItem, WorldEntityUpdate
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.chat import ChatMessage
from backend.models.session_state import SessionState
from backend.models.user import User
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene

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


async def test_off_scene_inspect_target_is_blocked_before_llm(setup_test_db, monkeypatch):
    """Inspecting an object from another scene must be rejected before the GM LLM is called."""
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, adv, _avatar, state = await _seed_game_context(db)
        user.earned_awards = []
        adv.awards = [{"key": "health-inspector", "title": "Health Inspector", "tier": "bronze"}]

        db.add(WorldScene(
            id="NEXT",
            session_id="session-1",
            label="Back Alley",
            description="A cramped alley behind the diner.",
        ))
        db.add(WorldEntity(
            id="TRASHCAN",
            session_id="session-1",
            entity_type="OBJECT",
            name="trashcan",
            description="A rusty trashcan in the next scene.",
            current_scene_id="NEXT",
            is_hidden=False,
            is_in_inventory=False,
        ))
        await db.commit()

        mock_llm_instance = MagicMock()
        mock_llm_instance.aexecute_simple_task = AsyncMock(return_value='{"action":"inspect","target":"trashcan"}')
        mock_llm_instance.aexecute_complex_task = AsyncMock(
            return_value=GameEvent(
                narrative_description="Should never run.",
                earned_award_keys=["health-inspector"],
            )
        )

        async def mock_stream(*args, **kwargs):
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="Should never stream."))])

        mock_llm_instance.stream_simple_task = AsyncMock(return_value=mock_stream())
        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.GameMasterLLM", lambda *args, **kwargs: mock_llm_instance)

        manager = GameTurnManager(db, "session-1", user)
        chunks = []
        async for chunk in manager.process_turn("untersuche trashcan"):
            chunks.append(chunk)

        await db.refresh(state)
        await db.refresh(user)

        all_output = "".join(chunks).lower()
        assert "cannot inspect or search" in all_output
        assert "award achievement" not in all_output
        assert state.in_game_time == 0
        assert user.earned_awards == []
        assert mock_llm_instance.aexecute_simple_task.await_count == 1
        assert mock_llm_instance.aexecute_complex_task.await_count == 0
        assert mock_llm_instance.stream_simple_task.await_count == 0


async def test_off_scene_name_mention_without_inspect_intent_is_not_blocked(setup_test_db, monkeypatch):
    """Mentioning an off-scene object in unrelated text should not be blocked by the inspect/search guard."""
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, adv, _avatar, state = await _seed_game_context(db)
        user.earned_awards = []
        adv.awards = [{"key": "health-inspector", "title": "Health Inspector", "tier": "bronze"}]

        db.add(WorldScene(
            id="NEXT",
            session_id="session-1",
            label="Back Alley",
            description="A cramped alley behind the diner.",
        ))
        db.add(WorldEntity(
            id="TRASHCAN",
            session_id="session-1",
            entity_type="OBJECT",
            name="trashcan",
            description="A rusty trashcan in the next scene.",
            current_scene_id="NEXT",
            is_hidden=False,
            is_in_inventory=False,
        ))
        await db.commit()

        mock_llm_instance = MagicMock()
        mock_llm_instance.aexecute_simple_task = AsyncMock(return_value='{"action":"other","target":null}')
        mock_llm_instance.aexecute_complex_task = AsyncMock(
            return_value=GameEvent(
                narrative_description="No direct interaction.",
                earned_award_keys=[],
            )
        )

        async def mock_stream(*args, **kwargs):
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="You pause and think."))])

        mock_llm_instance.stream_simple_task = AsyncMock(return_value=mock_stream())
        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.GameMasterLLM", lambda *args, **kwargs: mock_llm_instance)

        manager = GameTurnManager(db, "session-1", user)
        chunks = []
        async for chunk in manager.process_turn("Ich denke gerade an die trashcan, aber mache nichts."):
            chunks.append(chunk)

        await db.refresh(state)

        all_output = "".join(chunks).lower()
        assert "cannot inspect or search" not in all_output
        assert state.in_game_time == 5
        assert mock_llm_instance.aexecute_simple_task.await_count == 1
        assert mock_llm_instance.aexecute_complex_task.await_count == 1
        assert mock_llm_instance.stream_simple_task.await_count == 1

async def test_game_loop_session_overrides_template(setup_test_db, monkeypatch):
    """Verifies that the GameMaster receives plot/rules from SessionState, not AdventureTemplate."""
    from backend.engine.memory_manager import MemoryManager
    from tests.conftest import TestSessionLocal
    
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
        
        # Seed WorldExit to allow adjacent transition to CELLAR
        db.add(WorldExit(
            session_id="session-1",
            template_id=adv.id,
            from_scene_id="START",
            to_scene_id="CELLAR",
            label="Stairs down",
            is_locked=False,
        ))
        await db.commit()
        
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


async def test_chat_progression_does_not_move_on_hypothetical_text(setup_test_db, monkeypatch):
    """Chat progression must ignore hypothetical movement phrasing for scene transitions."""
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, adv, avatar, state = await _seed_game_context(db)
        adv.strict_rules = False
        adv.is_adventure_generator = False

        db.add_all(
            [
                WorldScene(id="START", label="Start", description="Start room", session_id="session-1", template_id=adv.id),
                WorldScene(id="CELLAR", label="Cellar", description="Cellar room", session_id="session-1", template_id=adv.id),
                WorldExit(
                    id="EXIT_START_CELLAR",
                    from_scene_id="START",
                    to_scene_id="CELLAR",
                    label="Stairs down",
                    is_locked=False,
                    session_id="session-1",
                    template_id=adv.id,
                ),
            ]
        )
        await db.commit()

        mock_llm_instance = MagicMock()

        async def _mock_progression_or_narration(*_args, **kwargs):
            if kwargs.get("response_model") is AdventureGeneratorToolIntent:
                return AdventureGeneratorToolIntent(new_scene_id="CELLAR", exit_label="Stairs down")
            return AdventureGeneratorToolIntent()

        mock_llm_instance.aexecute_complex_task = AsyncMock(side_effect=_mock_progression_or_narration)

        async def mock_stream(*args, **kwargs):
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="You stay where you are."))])

        mock_llm_instance.stream_simple_task = AsyncMock(return_value=mock_stream())

        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.GameMasterLLM", lambda *args, **kwargs: mock_llm_instance)

        manager = GameTurnManager(db, "session-1", user)
        async for _ in manager.process_turn("Wenn ich in den Keller gehe, was passiert?"):
            pass

        await db.refresh(state)
        assert state.current_scene_id == "START"


async def test_chat_progression_does_not_move_on_non_movement_text_even_if_llm_flags_transition(setup_test_db, monkeypatch):
    """Scene transition must not happen on non-movement text, even when intent classifier returns true."""
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, adv, _avatar, state = await _seed_game_context(db)
        adv.strict_rules = False
        adv.is_adventure_generator = False

        db.add_all(
            [
                WorldScene(id="START", label="Parking Lot", description="Rainy asphalt", session_id="session-1", template_id=adv.id),
                WorldScene(id="DINER_ENTRANCE", label="Diner Entrance", description="A neon-lit doorway", session_id="session-1", template_id=adv.id),
                WorldExit(
                    id="EXIT_PARKING_DINER",
                    from_scene_id="START",
                    to_scene_id="DINER_ENTRANCE",
                    label="Glass doors",
                    is_locked=False,
                    session_id="session-1",
                    template_id=adv.id,
                ),
            ]
        )
        await db.commit()

        mock_llm_instance = MagicMock()

        async def _mock_progression(*_args, **kwargs):
            if kwargs.get("response_model") is AdventureGeneratorToolIntent:
                return AdventureGeneratorToolIntent(new_scene_id="DINER_ENTRANCE", exit_label="Glass doors")
            return AdventureGeneratorToolIntent()

        mock_llm_instance.aexecute_complex_task = AsyncMock(side_effect=_mock_progression)
        mock_llm_instance.aexecute_simple_task = AsyncMock(return_value='{"explicit_transition": true}')

        async def mock_stream(*args, **kwargs):
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="You stay on the parking lot, gathering your thoughts."))])

        mock_llm_instance.stream_simple_task = AsyncMock(return_value=mock_stream())

        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.GameMasterLLM", lambda *args, **kwargs: mock_llm_instance)

        manager = GameTurnManager(db, "session-1", user)
        chunks = []
        async for chunk in manager.process_turn("I steady my breath and look at the rain."):
            chunks.append(chunk)

        await db.refresh(state)
        output = "".join(chunks)

        assert state.current_scene_id == "START"
        assert "You have entered" not in output


async def test_rule_pass_payload_is_compact_and_scene_split(setup_test_db, monkeypatch):
    """Mechanics payload should be compact/filtered while narration keeps full scene detail."""
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, adv, avatar, state = await _seed_game_context(db)
        state.quests = [{"id": "quest-1", "status": "active", "goal": "Find the key"}]
        adv.awards = [
            {"key": "earned-award", "title": "Already won"},
            {"key": "fresh-award", "title": "Still available"},
        ]
        user.earned_awards = [{"key": "earned-award", "template_id": adv.id}]
        avatar.inventory = [{
            "id": "ITEM-1",
            "name": "Test Blade",
            "item_type": "WEAPON",
            "metadata_json": {"damage_dice": "1d8"},
            "extra_field": "drop-me",
            "hp_change": None,
        }]
        db.add(WorldScene(
            id="START",
            session_id="session-1",
            label="Start Chamber",
            description="A very long description. " * 40,
        ))
        await db.commit()

        captured: dict[str, str] = {}
        mock_llm_instance = MagicMock()

        async def _mock_mechanics(system_prompt, _user_prompt, **_kwargs):
            captured["mechanics_prompt"] = system_prompt
            return GameEvent(
                narrative_description="OK",
                hp_change=0,
                stamina_change=0,
                mana_change=0,
                new_status_effects=[],
                new_inventory_items=[]
            )

        async def _mock_stream_simple(system_prompt, _user_prompt, _model):
            captured["narration_prompt"] = system_prompt

            async def _stream():
                yield MagicMock(choices=[MagicMock(delta=MagicMock(content="Narrative"))])

            return _stream()

        mock_llm_instance.aexecute_complex_task = AsyncMock(side_effect=_mock_mechanics)
        mock_llm_instance.stream_simple_task = AsyncMock(side_effect=_mock_stream_simple)

        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.GameMasterLLM", lambda *args, **kwargs: mock_llm_instance)

        manager = GameTurnManager(db, "session-1", user)
        async for _ in manager.process_turn("Check state"):
            pass

        mechanics_prompt = captured.get("mechanics_prompt", "")
        narration_prompt = captured.get("narration_prompt", "")

        assert "SCENE SUMMARY:" in mechanics_prompt
        assert "DESCRIPTION:" not in mechanics_prompt
        assert "DESCRIPTION:" in narration_prompt
        assert "SCENE SUMMARY: A very long description." in mechanics_prompt
        assert "..." in mechanics_prompt

        assert 'UNRESOLVED QUESTS:\n[{"id":"quest-1"' in mechanics_prompt
        assert '"key":"fresh-award"' in mechanics_prompt
        assert '"key":"earned-award"' not in mechanics_prompt
        assert '"metadata_json"' not in mechanics_prompt
        assert '"extra_field"' not in mechanics_prompt


async def test_adventure_generator_runs_mechanics_in_chat_mode(setup_test_db, monkeypatch):
    """Adventure-generator sessions must execute Pass 1 even when strict_rules is disabled."""
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, adv, _avatar, _state = await _seed_game_context(db)
        adv.strict_rules = False
        adv.rule_enforcement_mode = "chat"
        adv.is_adventure_generator = True
        await db.commit()

        mock_llm_instance = MagicMock()
        mock_llm_instance.aexecute_complex_task = AsyncMock(return_value=GameEvent(
            narrative_description="Preparing generation.",
            hp_change=0,
            stamina_change=0,
            mana_change=0,
            new_status_effects=[],
            new_inventory_items=[]
        ))

        async def mock_stream():
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="Ready."))])

        mock_llm_instance.stream_simple_task = AsyncMock(return_value=mock_stream())
        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.GameMasterLLM", lambda *args, **kwargs: mock_llm_instance)

        manager = GameTurnManager(db, "session-1", user)
        async for _ in manager.process_turn("generate now"):
            pass

        assert mock_llm_instance.aexecute_complex_task.await_count == 1


async def test_replace_entity_ids_with_names_rewrites_plain_tokens():
    text = "Du setzt das FREEZER_RELEASE_WHEEL in die Zugangsplatte ein."
    replaced = GameTurnManager._replace_entity_ids_with_names(
        text,
        {"FREEZER_RELEASE_WHEEL": "Freezer Release Wheel"},
    )
    assert "FREEZER_RELEASE_WHEEL" not in replaced
    assert "Freezer Release Wheel" in replaced


async def test_replace_entity_ids_with_names_keeps_debug_id_markers():
    text = "ID: FREEZER_RELEASE_WHEEL ist sichtbar geworden."
    replaced = GameTurnManager._replace_entity_ids_with_names(
        text,
        {"FREEZER_RELEASE_WHEEL": "Freezer Release Wheel"},
    )
    assert replaced == text


async def test_adventure_generator_chat_mode_uses_tool_intent_pass(setup_test_db, monkeypatch):
    """Adventure-generator in chat mode should process tool intents without strict GameEvent mechanics."""
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, adv, _avatar, state = await _seed_game_context(db)
        adv.strict_rules = False
        adv.rule_enforcement_mode = "chat"
        adv.is_adventure_generator = True
        db.add(ChatMessage(session_id=state.session_id, role="user", content="The adventure should be called Neon Citadel."))
        db.add(ChatMessage(session_id=state.session_id, role="assistant", content="Great, noted. We can set a cyberpunk tone and 6 scenes."))
        await db.commit()

        captured = {}
        mock_llm_instance = MagicMock()

        async def _mock_intent(system_prompt, _user_prompt, **_kwargs):
            captured["system_prompt"] = system_prompt
            return AdventureGeneratorToolIntent(
                request_available_tones=True,
                narrative_description="I can offer tones for your new world."
            )

        mock_llm_instance.aexecute_complex_task = AsyncMock(side_effect=_mock_intent)

        async def mock_stream():
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="Narrative fallback."))])

        mock_llm_instance.stream_simple_task = AsyncMock(return_value=mock_stream())

        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.GameMasterLLM", lambda *args, **kwargs: mock_llm_instance)
        monkeypatch.setattr(
            "backend.engine.adventure_generator_service.AdventureGeneratorService.get_available_tones",
            AsyncMock(return_value=["heroic", "horror"]),
        )

        manager = GameTurnManager(db, "session-1", user)
        chunks = []
        async for chunk in manager.process_turn("show tones"):
            chunks.append(chunk)

        assert mock_llm_instance.aexecute_complex_task.await_count == 1
        assert "RECENT CHAT CONTEXT" in captured.get("system_prompt", "")
        assert "The adventure should be called Neon Citadel." in captured.get("system_prompt", "")
        assert "cyberpunk tone and 6 scenes" in captured.get("system_prompt", "")
        assert any("Available Tones: heroic, horror" in c for c in chunks)

        res = await db.execute(select(ChatMessage).where(ChatMessage.session_id == state.session_id, ChatMessage.role == "system"))
        system_msgs = [m.content for m in res.scalars().all()]
        assert any("Available Tones: heroic, horror" in m for m in system_msgs)


async def test_adventure_generator_chat_mode_emits_fallback_narrative_when_empty(setup_test_db, monkeypatch):
    """If no instant/pass2 narrative is produced, chat mode should emit a deterministic fallback narrative."""
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, adv, _avatar, _state = await _seed_game_context(db)
        adv.strict_rules = False
        adv.rule_enforcement_mode = "chat"
        adv.is_adventure_generator = True
        await db.commit()

        mock_llm_instance = MagicMock()
        mock_llm_instance.aexecute_complex_task = AsyncMock(return_value=AdventureGeneratorToolIntent(
            request_available_tones=True,
            narrative_description="Requesting tones...",
        ))

        async def empty_stream():
            if False:
                yield None

        mock_llm_instance.stream_simple_task = AsyncMock(return_value=empty_stream())

        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.GameMasterLLM", lambda *args, **kwargs: mock_llm_instance)
        monkeypatch.setattr(
            "backend.engine.adventure_generator_service.AdventureGeneratorService.get_available_tones",
            AsyncMock(return_value=["heroic"]),
        )

        manager = GameTurnManager(db, "session-1", user)
        chunks = []
        async for chunk in manager.process_turn("show tones"):
            chunks.append(chunk)

        assert any("floating catalogs" in c for c in chunks)


async def test_adventure_generator_requires_image_confirmation_before_generation(setup_test_db, monkeypatch):
    """Image-enabled generation must wait for user confirmation and allow a no-image continuation."""
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, adv, _avatar, state = await _seed_game_context(db)
        adv.strict_rules = False
        adv.rule_enforcement_mode = "chat"
        adv.is_adventure_generator = True
        await db.commit()

        mock_llm_instance = MagicMock()
        mock_llm_instance.aexecute_complex_task = AsyncMock(return_value=AdventureGeneratorToolIntent(
            requested_adventure_generation={
                "title": "Neon Foundry",
                "prompt": "Build a neon city under a broken moon.",
                "min_scenes": 4,
                "max_scenes": 6,
                "generate_scene_images": True,
                "selected_image_styles": ["cinematic-realism"],
                "selected_tone": "mystery",
                "min_awards": 2,
                "max_awards": 4,
                "award_generation_enabled": True,
            }
        ))

        async def empty_stream():
            if False:
                yield None

        mock_llm_instance.stream_simple_task = AsyncMock(return_value=empty_stream())

        generate_adventure_mock = AsyncMock(return_value="adv-generated-2")

        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.GameMasterLLM", lambda *args, **kwargs: mock_llm_instance)
        monkeypatch.setattr(
            "backend.engine.adventure_generator_service.AdventureGeneratorService.generate_adventure",
            generate_adventure_mock,
        )

        manager = GameTurnManager(db, "session-1", user)
        turn1_chunks = []
        async for chunk in manager.process_turn("generate a world with fitting images"):
            turn1_chunks.append(chunk)

        await db.refresh(state)
        assert any("please confirm" in c.lower() for c in turn1_chunks)
        assert any("event: system\ndata:" in c for c in turn1_chunks)
        assert not any("event: system\\ndata:" in c for c in turn1_chunks)
        assert generate_adventure_mock.await_count == 0
        assert "__ag_image_confirmation__" in (state.exit_states or {})

        turn2_chunks = []
        async for chunk in manager.process_turn("yes without images"):
            turn2_chunks.append(chunk)

        await db.refresh(state)
        assert generate_adventure_mock.await_count == 1
        req_arg = generate_adventure_mock.await_args.args[2]
        assert req_arg.generate_scene_images is False
        assert "__ag_image_confirmation__" not in (state.exit_states or {})
        assert any("text-only world generation" in c for c in turn2_chunks)
        assert any("event: system\ndata:" in c for c in turn2_chunks)
        assert not any("event: system\\ndata:" in c for c in turn2_chunks)


async def test_adventure_generator_always_confirms_image_mode_before_generation(setup_test_db, monkeypatch):
    """Generator requests must always ask for explicit image-mode confirmation."""
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, adv, _avatar, state = await _seed_game_context(db)
        adv.strict_rules = False
        adv.rule_enforcement_mode = "chat"
        adv.is_adventure_generator = True
        await db.commit()

        mock_llm_instance = MagicMock()
        mock_llm_instance.aexecute_complex_task = AsyncMock(return_value=AdventureGeneratorToolIntent(
            requested_adventure_generation={
                "title": "Quiet Archive",
                "prompt": "Create a library world with hidden passages.",
                "min_scenes": 4,
                "max_scenes": 6,
                "generate_scene_images": False,
                "selected_image_styles": ["cinematic-realism"],
                "selected_tone": "mystery",
                "min_awards": 1,
                "max_awards": 3,
                "award_generation_enabled": True,
            }
        ))

        async def empty_stream():
            if False:
                yield None

        mock_llm_instance.stream_simple_task = AsyncMock(return_value=empty_stream())

        generate_adventure_mock = AsyncMock(return_value="adv-confirm-1")

        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.GameMasterLLM", lambda *args, **kwargs: mock_llm_instance)
        monkeypatch.setattr(
            "backend.engine.adventure_generator_service.AdventureGeneratorService.generate_adventure",
            generate_adventure_mock,
        )

        manager = GameTurnManager(db, "session-1", user)
        turn1_chunks = []
        async for chunk in manager.process_turn("generate archive world"):
            turn1_chunks.append(chunk)

        await db.refresh(state)
        assert any("please confirm image mode" in c.lower() for c in turn1_chunks)
        assert generate_adventure_mock.await_count == 0
        assert "__ag_image_confirmation__" in (state.exit_states or {})

        turn2_chunks = []
        async for chunk in manager.process_turn("yes with images"):
            turn2_chunks.append(chunk)

        assert generate_adventure_mock.await_count == 1
        req_arg = generate_adventure_mock.await_args.args[2]
        assert req_arg.generate_scene_images is True
        assert any("generation finished successfully" in c.lower() for c in turn2_chunks)


async def test_token_limit_error_is_user_safe_in_chat(setup_test_db, monkeypatch):
    """Token limit exceptions should be surfaced as a short user-safe message without technical details."""
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, _adv, _avatar, _state = await _seed_game_context(db)

        mock_llm_instance = MagicMock()
        mock_llm_instance.aexecute_complex_task = AsyncMock(side_effect=Exception("maximum context length exceeded"))
        mock_llm_instance.stream_simple_task = AsyncMock()
        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.GameMasterLLM", lambda *args, **kwargs: mock_llm_instance)

        manager = GameTurnManager(db, "session-1", user)
        chunks = []
        async for chunk in manager.process_turn("tell a very long story"):
            chunks.append(chunk)

        assert any("event: error" in c and "shorter context" in c for c in chunks)
        assert not any("maximum context length" in c.lower() for c in chunks)


async def test_rate_limit_error_is_user_safe_in_chat(setup_test_db, monkeypatch):
    """Rate-limit exceptions should be surfaced as a short user-safe message without raw provider details."""
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, _adv, _avatar, _state = await _seed_game_context(db)

        mock_llm_instance = MagicMock()
        mock_llm_instance.aexecute_complex_task = AsyncMock(side_effect=Exception("429 Too Many Requests: provider rate limit exceeded"))
        mock_llm_instance.stream_simple_task = AsyncMock()
        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.GameMasterLLM", lambda *args, **kwargs: mock_llm_instance)

        manager = GameTurnManager(db, "session-1", user)
        chunks = []
        async for chunk in manager.process_turn("respond please"):
            chunks.append(chunk)

        assert any("event: error" in c and "busy right now" in c.lower() for c in chunks)
        assert not any("429" in c or "rate limit exceeded" in c.lower() for c in chunks)


async def test_timeout_error_is_user_safe_in_chat(setup_test_db, monkeypatch):
    """Timeout exceptions should be surfaced as a short user-safe message."""
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, _adv, _avatar, _state = await _seed_game_context(db)

        mock_llm_instance = MagicMock()
        mock_llm_instance.aexecute_complex_task = AsyncMock(side_effect=Exception("Request timeout while calling provider"))
        mock_llm_instance.stream_simple_task = AsyncMock()
        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.GameMasterLLM", lambda *args, **kwargs: mock_llm_instance)

        manager = GameTurnManager(db, "session-1", user)
        chunks = []
        async for chunk in manager.process_turn("respond please"):
            chunks.append(chunk)

        assert any("event: error" in c and "took too long" in c.lower() for c in chunks)
        assert not any("request timeout" in c.lower() for c in chunks)


async def test_service_unavailable_error_is_user_safe_in_chat(setup_test_db, monkeypatch):
    """Service unavailable exceptions should be surfaced as a short user-safe message."""
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, _adv, _avatar, _state = await _seed_game_context(db)

        mock_llm_instance = MagicMock()
        mock_llm_instance.aexecute_complex_task = AsyncMock(side_effect=Exception("503 Service Unavailable"))
        mock_llm_instance.stream_simple_task = AsyncMock()
        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.GameMasterLLM", lambda *args, **kwargs: mock_llm_instance)

        manager = GameTurnManager(db, "session-1", user)
        chunks = []
        async for chunk in manager.process_turn("respond please"):
            chunks.append(chunk)

        assert any("event: error" in c and "temporarily unavailable" in c.lower() for c in chunks)
        assert not any("503" in c for c in chunks)


async def test_invalid_structured_llm_payload_is_user_safe_in_chat(setup_test_db, monkeypatch):
    """Structured output contract failures should be surfaced as a short user-safe message."""
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, _adv, _avatar, _state = await _seed_game_context(db)

        mock_llm_instance = MagicMock()
        mock_llm_instance.aexecute_complex_task = AsyncMock(
            side_effect=ValueError("No content returned from LLM for complex task.")
        )
        mock_llm_instance.stream_simple_task = AsyncMock()
        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.GameMasterLLM", lambda *args, **kwargs: mock_llm_instance)

        manager = GameTurnManager(db, "session-1", user)
        chunks = []
        async for chunk in manager.process_turn("respond please"):
            chunks.append(chunk)

        assert any("event: error" in c and "invalid response" in c.lower() for c in chunks)
        assert not any("unexpected issue" in c.lower() for c in chunks)


async def test_unknown_pass1_error_returns_generic_sse_error(setup_test_db, monkeypatch):
    """Unknown pass-1 exceptions should not crash the stream or leak internals."""
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, _adv, _avatar, _state = await _seed_game_context(db)

        mock_llm_instance = MagicMock()
        mock_llm_instance.aexecute_complex_task = AsyncMock(side_effect=RuntimeError("database socket exploded with trace details"))
        mock_llm_instance.stream_simple_task = AsyncMock()
        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.GameMasterLLM", lambda *args, **kwargs: mock_llm_instance)

        manager = GameTurnManager(db, "session-1", user)
        chunks = []
        async for chunk in manager.process_turn("respond please"):
            chunks.append(chunk)

        assert any("event: error" in c and "unexpected issue" in c.lower() for c in chunks)
        assert not any("socket exploded" in c.lower() or "trace details" in c.lower() for c in chunks)


async def test_unknown_chat_progression_error_returns_generic_sse_error(setup_test_db, monkeypatch):
    """Unknown pass-1 exceptions in chat-progression mode should not silently abort the SSE stream."""
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, adv, _avatar, _state = await _seed_game_context(db)
        adv.strict_rules = False
        adv.rule_enforcement_mode = "chat"
        adv.is_adventure_generator = False
        await db.commit()

        mock_llm_instance = MagicMock()
        mock_llm_instance.aexecute_complex_task = AsyncMock(side_effect=RuntimeError("chat progression blew up internally"))
        mock_llm_instance.stream_simple_task = AsyncMock()
        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.GameMasterLLM", lambda *args, **kwargs: mock_llm_instance)

        manager = GameTurnManager(db, "session-1", user)
        chunks = []
        async for chunk in manager.process_turn("respond please"):
            chunks.append(chunk)

        assert any("event: error" in c and "unexpected issue" in c.lower() for c in chunks)
        assert not any("blew up internally" in c.lower() for c in chunks)


async def test_adventure_generator_retry_uses_last_request(setup_test_db, monkeypatch):
    """A retry phrase should recover the last request and proceed after confirmation."""
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, adv, _avatar, state = await _seed_game_context(db)
        adv.strict_rules = False
        adv.rule_enforcement_mode = "chat"
        adv.is_adventure_generator = True
        state.exit_states = {
            "__ag_last_generation_request__": {
                "title": "Bundy Boulevard",
                "prompt": "A suburban sitcom house with absurd family conflicts.",
                "min_scenes": 5,
                "max_scenes": 8,
                "generate_scene_images": True,
                "selected_image_styles": ["cinematic-realism"],
                "selected_tone": "satirical",
                "min_awards": 2,
                "max_awards": 4,
                "award_generation_enabled": True,
            },
            "__ag_last_generation_error__": "token_limit",
        }
        await db.commit()

        mock_llm_instance = MagicMock()
        mock_llm_instance.aexecute_complex_task = AsyncMock(return_value=AdventureGeneratorToolIntent())

        async def empty_stream():
            if False:
                yield None

        mock_llm_instance.stream_simple_task = AsyncMock(return_value=empty_stream())

        generate_adventure_mock = AsyncMock(return_value="adv-retry-1")

        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.GameMasterLLM", lambda *args, **kwargs: mock_llm_instance)
        monkeypatch.setattr(
            "backend.engine.adventure_generator_service.AdventureGeneratorService.generate_adventure",
            generate_adventure_mock,
        )

        manager = GameTurnManager(db, "session-1", user)
        chunks = []
        async for chunk in manager.process_turn("bitte nochmal erstellen"):
            chunks.append(chunk)

        # Mandatory image-mode confirmation should be requested first.
        assert any("please confirm image mode" in c.lower() for c in chunks)
        assert generate_adventure_mock.await_count == 0

        confirm_chunks = []
        async for chunk in manager.process_turn("yes without images"):
            confirm_chunks.append(chunk)

        assert generate_adventure_mock.await_count == 1
        req_arg = generate_adventure_mock.await_args.args[2]
        assert req_arg.title == "Bundy Boulevard"
        assert req_arg.generate_scene_images is False
        assert any("Generation finished successfully" in c for c in confirm_chunks)


async def test_chat_mode_runs_progression_pass_and_keeps_progress_unchanged(setup_test_db, monkeypatch):
    """Normal chat mode should run a lightweight progression pass before narration."""
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, adv, _avatar, state = await _seed_game_context(db)
        adv.strict_rules = False
        adv.rule_enforcement_mode = "chat"
        adv.is_adventure_generator = False
        adv.awards = [{"key": "heroic-heart", "title": "Heroic Heart", "tier": "silver"}]
        state.quests = [{"id": "q-1", "title": "Open the Gate", "status": "open", "is_main": True}]
        user.earned_awards = []
        db.add(WorldScene(
            id="START",
            session_id="session-1",
            label="Gate Hall",
            description="A stone corridor leads to an ancient gate.",
        ))
        db.add(WorldEntity(
            id="GUARDIAN",
            session_id="session-1",
            entity_type="NPC",
            name="Gate Guardian",
            description="A vigilant armored watcher.",
            current_scene_id="START",
            is_hidden=False,
            is_in_inventory=False,
        ))
        await db.commit()

        mock_llm_instance = MagicMock()

        async def mock_progression(_system_prompt, _user_prompt, **_kwargs):
            return AdventureGeneratorToolIntent(
                completed_quest_ids=[],
                earned_award_keys=[],
                game_over=False,
                game_completed=False,
            )

        mock_llm_instance.aexecute_complex_task = AsyncMock(side_effect=mock_progression)

        async def mock_stream(*args, **kwargs):
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="A quiet wind passes through the gate."))])

        mock_llm_instance.stream_simple_task = AsyncMock(return_value=mock_stream())
        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.GameMasterLLM", lambda *args, **kwargs: mock_llm_instance)

        manager = GameTurnManager(db, "session-1", user)
        chunks = []
        async for chunk in manager.process_turn("I wait and listen"):
            chunks.append(chunk)

        await db.refresh(state)
        await db.refresh(user)

        assert mock_llm_instance.aexecute_complex_task.await_count == 1
        assert mock_llm_instance.stream_simple_task.await_count == 1
        assert any("quiet wind" in c for c in chunks)
        assert (state.quests or [])[0].get("status") == "open"
        assert user.earned_awards == []


async def test_chat_mode_progression_completes_quest_and_award(setup_test_db, monkeypatch):
    """Lightweight chat progression pass should update quests and awards."""
    import json
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, adv, _avatar, state = await _seed_game_context(db)
        adv.strict_rules = False
        adv.rule_enforcement_mode = "chat"
        adv.is_adventure_generator = False
        adv.awards = [{"key": "heroic-heart", "title": "Heroic Heart", "tier": "silver"}]
        state.quests = [{"id": "q-1", "title": "Open the Gate", "status": "open", "is_main": True}]
        user.earned_awards = []
        db.add(WorldScene(
            id="START",
            session_id="session-1",
            label="Gate Hall",
            description="A stone corridor leads to an ancient gate.",
        ))
        db.add(WorldEntity(
            id="GUARDIAN",
            session_id="session-1",
            entity_type="NPC",
            name="Gate Guardian",
            description="A vigilant armored watcher.",
            current_scene_id="START",
            is_hidden=False,
            is_in_inventory=False,
        ))
        await db.commit()

        mock_llm_instance = MagicMock()

        async def mock_progression(system_prompt, _user_prompt, **_kwargs):
            assert "OPEN QUESTS (REDUCED):" in system_prompt
            assert "AVAILABLE UNEARNED AWARDS (REDUCED):" in system_prompt
            assert '"id":"q-1"' in system_prompt
            assert '"key":"heroic-heart"' in system_prompt
            assert "SCENE NPCS" in system_prompt
            assert "Gate Guardian" in system_prompt
            assert "CHARACTER SHEET JSON" not in system_prompt
            assert "CURRENT LOCATION" not in system_prompt
            return AdventureGeneratorToolIntent(
                completed_quest_ids=["q-1"],
                earned_award_keys=["heroic-heart"],
                status_note="Quest and award granted.",
            )

        async def mock_stream(*args, **kwargs):
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="You feel a surge of accomplishment."))])

        mock_llm_instance.aexecute_complex_task = AsyncMock(side_effect=mock_progression)
        mock_llm_instance.stream_simple_task = AsyncMock(return_value=mock_stream())
        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.GameMasterLLM", lambda *args, **kwargs: mock_llm_instance)
        monkeypatch.setattr(
            "backend.api.routes.adventures.gameplay_logic.SessionCheckpointService.create_checkpoint",
            AsyncMock(return_value=SimpleNamespace(id=1, trigger_reason="AWARD_GRANTED", created_at=None)),
        )

        manager = GameTurnManager(db, "session-1", user)
        chunks = []
        async for chunk in manager.process_turn("I open the gate with confidence"):
            chunks.append(chunk)

        await db.refresh(state)
        await db.refresh(user)

        assert mock_llm_instance.aexecute_complex_task.await_count == 1
        assert mock_llm_instance.stream_simple_task.await_count == 1
        assert any("accomplishment" in c for c in chunks)
        assert any("Award Achievement: Heroic Heart" in c for c in chunks)
        assert (state.quests or [])[0].get("status") == "completed"
        earned = user.earned_awards or []
        assert any(
            ea.get("key") == "heroic-heart"
            and (ea.get("template_id") == adv.id or ea.get("adventure_id") == adv.id)
            for ea in earned
        )

        final_payload = None
        for chunk in chunks:
            if "event: final" not in chunk:
                continue
            data_line = next((line for line in chunk.split("\n") if line.startswith("data:")), None)
            if data_line:
                final_payload = json.loads(data_line[5:])
                break

        assert final_payload is not None
        awards = final_payload.get("awards") or []
        heroic_award = next((aw for aw in awards if aw.get("key") == "heroic-heart"), None)
        assert heroic_award is not None
        assert heroic_award.get("is_earned") is True


async def test_deterministic_quest_completion_marks_inactive_quest_and_emits_system_message(setup_test_db, monkeypatch):
    """Unresolved quests must complete even when not currently active and emit system feedback."""
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, _adv, avatar, state = await _seed_game_context(db)
        state.quests = [
            {
                "id": "q-equip-head",
                "title": "Suit Up",
                "status": "inactive",
                "goal": "Equip a head item",
                "description": "Put any helmet in your head slot.",
                "is_main": False,
            }
        ]
        avatar.equipment = {"head": {"name": "Iron Helm"}}
        await db.commit()

        mock_llm_instance = MagicMock()
        mock_llm_instance.aexecute_complex_task = AsyncMock(
            return_value=GameEvent(
                narrative_description="You tighten the helmet strap.",
                hp_change=0,
                stamina_change=0,
                mana_change=0,
                new_status_effects=[],
                new_inventory_items=[],
                completed_quest_ids=[],
            )
        )

        async def mock_stream(*args, **kwargs):
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="You are ready for battle."))])

        mock_llm_instance.stream_simple_task = AsyncMock(return_value=mock_stream())
        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.GameMasterLLM", lambda *args, **kwargs: mock_llm_instance)

        manager = GameTurnManager(db, "session-1", user)
        async for _ in manager.process_turn("I put on my helmet"):
            pass

        await db.refresh(state)
        assert (state.quests or [])[0].get("status") == "completed"

        sys_msgs = (
            (
                await db.execute(
                    select(ChatMessage).where(
                        ChatMessage.session_id == "session-1",
                        ChatMessage.role == "system",
                    )
                )
            )
            .scalars()
            .all()
        )
        assert any((m.content or "").strip() == "Quest completed: Suit Up" for m in sys_msgs)


async def test_chat_mode_progression_persists_and_reuses_notes(setup_test_db, monkeypatch):
    """Chat progression notes should be persisted and included in subsequent prompts."""
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, adv, _avatar, state = await _seed_game_context(db)
        adv.strict_rules = False
        adv.rule_enforcement_mode = "chat"
        adv.is_adventure_generator = False
        await db.commit()

        mock_llm_instance = MagicMock()
        seen_progression_prompts = []

        async def mock_progression(system_prompt, _user_prompt, **_kwargs):
            seen_progression_prompts.append(system_prompt)
            if len(seen_progression_prompts) == 1:
                assert "SESSION NOTES (REDUCED):" in system_prompt
                assert "[]" in system_prompt
                return AdventureGeneratorToolIntent(
                    remember_notes=["Innkeeper owes the player a favor"],
                )

            assert "SESSION NOTES (REDUCED):" in system_prompt
            assert "Innkeeper owes the player a favor" in system_prompt
            return AdventureGeneratorToolIntent()

        async def mock_stream(*args, **kwargs):
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="Narration."))])

        mock_llm_instance.aexecute_complex_task = AsyncMock(side_effect=mock_progression)
        mock_llm_instance.stream_simple_task = AsyncMock(return_value=mock_stream())
        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.GameMasterLLM", lambda *args, **kwargs: mock_llm_instance)

        manager = GameTurnManager(db, "session-1", user)

        async for _ in manager.process_turn("I tell the innkeeper my plan"):
            pass

        await db.refresh(state)
        assert (state.exit_states or {}).get("__gm_notes__") == ["Innkeeper owes the player a favor"]

        async for _ in manager.process_turn("I return to the inn"):
            pass

        assert mock_llm_instance.aexecute_complex_task.await_count == 2
        assert len(seen_progression_prompts) == 2


async def test_rpg_strict_mode_persists_and_reuses_notes(setup_test_db, monkeypatch):
    """Strict RPG mode should persist notes from mechanics pass and reuse them next turn."""
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, adv, _avatar, state = await _seed_game_context(db)
        adv.strict_rules = True
        adv.rule_enforcement_mode = "strict"
        adv.is_adventure_generator = False
        await db.commit()

        mock_llm_instance = MagicMock()
        seen_mechanics_prompts = []

        async def mock_mechanics(system_prompt, _user_prompt, **_kwargs):
            seen_mechanics_prompts.append(system_prompt)
            if len(seen_mechanics_prompts) == 1:
                assert "SESSION NOTES:" in system_prompt
                assert "- none" in system_prompt
                return GameEvent(
                    narrative_description="Noted.",
                    hp_change=0,
                    stamina_change=0,
                    mana_change=0,
                    new_status_effects=[],
                    new_inventory_items=[],
                    remember_notes=["The sheriff distrusts the mayor"],
                )

            assert "SESSION NOTES:" in system_prompt
            assert "The sheriff distrusts the mayor" in system_prompt
            return GameEvent(
                narrative_description="Still noted.",
                hp_change=0,
                stamina_change=0,
                mana_change=0,
                new_status_effects=[],
                new_inventory_items=[],
            )

        async def mock_stream(*args, **kwargs):
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="Narration."))])

        mock_llm_instance.aexecute_complex_task = AsyncMock(side_effect=mock_mechanics)
        mock_llm_instance.stream_simple_task = AsyncMock(return_value=mock_stream())
        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.GameMasterLLM", lambda *args, **kwargs: mock_llm_instance)

        manager = GameTurnManager(db, "session-1", user)

        async for _ in manager.process_turn("I question the sheriff"):
            pass

        await db.refresh(state)
        assert (state.exit_states or {}).get("__gm_notes__") == ["The sheriff distrusts the mayor"]

        async for _ in manager.process_turn("I meet the mayor"):
            pass

        assert mock_llm_instance.aexecute_complex_task.await_count == 2
        assert len(seen_mechanics_prompts) == 2


async def test_story_mode_persists_and_reuses_notes(setup_test_db, monkeypatch):
    """Strict Story mode should persist and reuse notes via story mechanics pass."""
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, adv, _avatar, state = await _seed_game_context(db)
        adv.strict_rules = True
        adv.rule_enforcement_mode = "story"
        adv.is_adventure_generator = False
        await db.commit()

        mock_llm_instance = MagicMock()
        seen_mechanics_prompts = []

        async def mock_story_mechanics(system_prompt, _user_prompt, **_kwargs):
            seen_mechanics_prompts.append(system_prompt)
            assert "STORY MODE" in system_prompt
            if len(seen_mechanics_prompts) == 1:
                return GameEvent(
                    narrative_description="You remember a rumor.",
                    hp_change=0,
                    stamina_change=0,
                    mana_change=0,
                    new_status_effects=[],
                    new_inventory_items=[],
                    remember_notes=["Old clocktower bell rings at midnight"],
                )

            assert "Old clocktower bell rings at midnight" in system_prompt
            return GameEvent(
                narrative_description="The rumor returns to mind.",
                hp_change=0,
                stamina_change=0,
                mana_change=0,
                new_status_effects=[],
                new_inventory_items=[],
            )

        async def mock_stream(*args, **kwargs):
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="Narration."))])

        mock_llm_instance.aexecute_complex_task = AsyncMock(side_effect=mock_story_mechanics)
        mock_llm_instance.stream_simple_task = AsyncMock(return_value=mock_stream())
        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.GameMasterLLM", lambda *args, **kwargs: mock_llm_instance)

        manager = GameTurnManager(db, "session-1", user)

        async for _ in manager.process_turn("I listen to village rumors"):
            pass

        await db.refresh(state)
        assert (state.exit_states or {}).get("__gm_notes__") == ["Old clocktower bell rings at midnight"]

        async for _ in manager.process_turn("I wait at the square"):
            pass

        assert mock_llm_instance.aexecute_complex_task.await_count == 2
        assert len(seen_mechanics_prompts) == 2


async def test_notes_are_rotated_to_maximum_size(setup_test_db, monkeypatch):
    """Persisted notes should be capped to avoid unbounded prompt growth."""
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, adv, _avatar, state = await _seed_game_context(db)
        adv.strict_rules = False
        adv.rule_enforcement_mode = "chat"
        adv.is_adventure_generator = False
        await db.commit()

        mock_llm_instance = MagicMock()
        notes = [f"note-{i}" for i in range(25)]

        async def mock_progression(system_prompt, _user_prompt, **_kwargs):
            if "note-24" in system_prompt:
                return AdventureGeneratorToolIntent()
            return AdventureGeneratorToolIntent(remember_notes=notes)

        async def mock_stream(*args, **kwargs):
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="Narration."))])

        mock_llm_instance.aexecute_complex_task = AsyncMock(side_effect=mock_progression)
        mock_llm_instance.stream_simple_task = AsyncMock(return_value=mock_stream())
        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.GameMasterLLM", lambda *args, **kwargs: mock_llm_instance)

        manager = GameTurnManager(db, "session-1", user)

        async for _ in manager.process_turn("I list many facts"):
            pass

        await db.refresh(state)
        persisted = (state.exit_states or {}).get("__gm_notes__") or []
        assert len(persisted) == 20
        assert persisted[0] == "note-5"
        assert persisted[-1] == "note-24"

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


async def test_process_turn_rejects_input_when_terminal_lock_active(setup_test_db, monkeypatch):
    """Locked terminal sessions should return read-only feedback and skip LLM processing."""
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, _adv, _avatar, _state = await _seed_game_context(db)

        manager = GameTurnManager(db, "session-1", user)
        monkeypatch.setattr(manager, "_is_input_locked", lambda: True)

        llm_ctor = AsyncMock()
        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.GameMasterLLM", llm_ctor)

        chunks = []
        async for chunk in manager.process_turn("I attack"):
            chunks.append(chunk)

        response = "".join(chunks)
        assert "final ending" in response.lower()
        assert "event: final" in response
        assert llm_ctor.call_count == 0

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
    from backend.engine.rule_engine import GameOverException, RuleEngine
    with pytest.raises(GameOverException):
        RuleEngine.apply_event(avatar, event)
    assert avatar.hp == 0


async def test_game_event_schema_tool_results_is_strict_object():
    """The structured response schema for tool_results must disallow arbitrary keys."""
    schema = GameEvent.model_json_schema()
    tool_results_ref = schema["properties"]["tool_results"]["anyOf"][0]["$ref"]
    definition_key = tool_results_ref.split("/")[-1]
    tool_results_schema = schema["$defs"][definition_key]

    assert tool_results_schema["type"] == "object"
    assert tool_results_schema.get("additionalProperties") is False


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


async def test_combat_start_blocked_when_npc_damage_disabled(setup_test_db):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, adv, _avatar, state, _npc = await _seed_combat_npc(db)
        adv.can_damage_npcs = False
        await db.commit()

        manager = GameTurnManager(db, state.session_id, user)
        async for _ in manager.process_turn("/fight RAT_ENEMY"):
            pass

        await db.refresh(state)
        combat = (state.entity_states or {}).get("__combat__") or {}
        assert combat.get("active") is not True


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


async def test_non_killable_npc_not_marked_permanently_defeated(setup_test_db, monkeypatch):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, _adv, _avatar, state, npc = await _seed_combat_npc(db)
        npc.is_killable = False
        await db.commit()

        manager = GameTurnManager(db, state.session_id, user)

        async for _ in manager.process_turn("/fight RAT_ENEMY"):
            pass

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
        npc_state = ((state.entity_states or {}).get("RAT_ENEMY") or {})
        assert npc_state.get("is_defeated") is not True
        assert npc_state.get("is_attackable") is not False


async def test_enemy_turn_no_damage_when_npc_damage_to_protagonist_disabled(setup_test_db, monkeypatch):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, adv, avatar, state, _npc = await _seed_combat_npc(db)
        adv.npcs_can_damage_protagonist = False
        avatar.hp = 100
        await db.commit()

        manager = GameTurnManager(db, state.session_id, user)

        # Ensure player starts combat and enemy turn resolves deterministically.
        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.random.randint", lambda *_args, **_kwargs: 20)
        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.random.random", lambda: 1.0)

        async for _ in manager.process_turn("/fight RAT_ENEMY"):
            pass
        async for _ in manager.process_turn("/rest"):
            pass

        await db.refresh(avatar)
        assert avatar.hp == 100


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


async def test_combat_loot_done_spawns_visible_scene_loot_with_stale_overrides(setup_test_db, monkeypatch):
    from backend.api.routes.adventures.logic import AdventureLogic
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, _adv, _avatar, state, _npc = await _seed_combat_npc(db)

        # Simulate a stale override that previously hid an item in inventory.
        overrides = dict(state.entity_states or {})
        overrides["RAT_TOOTH"] = {
            "is_in_inventory": True,
            "current_scene_id": "INVENTORY",
        }
        state.entity_states = overrides
        await db.commit()

        manager = GameTurnManager(db, state.session_id, user)
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
                "damage_total": 99,
                "damage_dice_total": 99,
                "damage_rolls": [99],
                "damage_bonus": 0,
                "damage_dice_str": "1d8",
            },
        )

        async for _ in manager.process_turn("/attack"):
            pass
        async for _ in manager.process_turn("/loot done"):
            pass

        await db.refresh(state)
        entity_res = await db.execute(
            select(WorldEntity).where(
                WorldEntity.session_id == state.session_id,
                WorldEntity.id == "RAT_TOOTH",
            )
        )
        scene_item = entity_res.scalars().first()
        assert scene_item is not None
        assert scene_item.current_scene_id == state.current_scene_id
        assert scene_item.is_in_inventory is False

        visible_entities = await AdventureLogic.build_session_entities(db, state)
        assert any(ent.get("id") == "RAT_TOOTH" for ent in visible_entities)


async def test_build_session_entities_hides_items_inside_container_inventory(setup_test_db):
    from backend.api.routes.adventures.logic import AdventureLogic
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        _user, _adv, _avatar, state = await _seed_game_context(db)

        db.add_all([
            WorldEntity(
                id="TRASH_CAN",
                session_id=state.session_id,
                entity_type="OBJECT",
                name="Overflowing Trash Can",
                description="A plastic bin full of greasy napkins.",
                current_scene_id=state.current_scene_id,
                item_type="CONTAINER",
                is_hidden=False,
                is_in_inventory=False,
                is_portable=False,
                inventory=["CRUMPLED_RECEIPT"],
            ),
            WorldEntity(
                id="CRUMPLED_RECEIPT",
                session_id=state.session_id,
                entity_type="OBJECT",
                name="Crumpled Receipt",
                description="A greasy piece of thermal paper.",
                current_scene_id=state.current_scene_id,
                image_url="/data/adventures/test/crumpled-receipt.png",
                item_type="READABLE",
                is_hidden=False,
                is_in_inventory=False,
                is_portable=True,
                inventory=[],
            ),
        ])
        await db.commit()

        visible_entities = await AdventureLogic.build_session_entities(db, state)
        visible_ids = {str(ent.get("id")) for ent in visible_entities}
        assert "TRASH_CAN" in visible_ids
        assert "CRUMPLED_RECEIPT" not in visible_ids

        trash_can = next(ent for ent in visible_entities if str(ent.get("id")) == "TRASH_CAN")
        inventory_entries = trash_can.get("inventory") or []
        assert len(inventory_entries) == 1
        nested_item = inventory_entries[0]
        assert nested_item.get("id") == "CRUMPLED_RECEIPT"
        assert nested_item.get("name") == "Crumpled Receipt"
        assert nested_item.get("image_url")


async def test_debug_win_fight_uses_loot_phase_mechanism(setup_test_db, monkeypatch):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, _adv, _avatar, state, _npc = await _seed_combat_npc(db)
        manager = GameTurnManager(db, state.session_id, user)

        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.random.randint", lambda *_args, **_kwargs: 20)

        async for _ in manager.process_turn("/fight RAT_ENEMY"):
            pass
        async for _ in manager.process_turn("/debug win_fight"):
            pass

        await db.refresh(state)
        combat = (state.entity_states or {}).get("__combat__")
        assert combat is not None
        assert combat.get("active") is False
        assert combat.get("outcome") == "victory"
        assert combat.get("loot_pending") is True
        assert any((item or {}).get("id") == "RAT_TOOTH" for item in (combat.get("loot_items") or []))


async def test_combat_loot_done_emits_dropped_items_system_message(setup_test_db, monkeypatch):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, _adv, _avatar, state, _npc = await _seed_combat_npc(db)
        manager = GameTurnManager(db, state.session_id, user)

        mock_llm_instance = MagicMock()

        async def mock_stream(*_args, **_kwargs):
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="The battlefield quiets."))])

        mock_llm_instance.stream_simple_task = AsyncMock(return_value=mock_stream())
        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.GameMasterLLM", lambda *args, **kwargs: mock_llm_instance)

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
                "damage_total": 99,
                "damage_dice_total": 99,
                "damage_rolls": [99],
                "damage_bonus": 0,
                "damage_dice_str": "1d8",
            },
        )

        async for _ in manager.process_turn("/attack"):
            pass

        chunks: list[str] = []
        async for chunk in manager.process_turn("/loot done"):
            chunks.append(chunk)

        system_chunks = [c for c in chunks if "event: system" in c]
        assert any("Loot dropped to the scene:" in c for c in system_chunks)
        assert any("- Rat Tooth" in c for c in system_chunks)


async def test_talk_command_is_unknown(setup_test_db):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, _adv, _avatar, state, npc = await _seed_combat_npc(db)

        manager = GameTurnManager(db, state.session_id, user)
        chunks: list[str] = []
        async for chunk in manager.process_turn("/talk Giant Rat"):
            chunks.append(chunk)

        system_chunks = [c for c in chunks if "event: system" in c]
        assert any("Unknown command: /talk" in c for c in system_chunks)


async def test_say_to_defeated_npc_is_allowed_as_direct_speech(setup_test_db, monkeypatch):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, _adv, _avatar, state, npc = await _seed_combat_npc(db)
        overrides = dict(state.entity_states or {})
        overrides[npc.id] = {"is_defeated": True, "hp": 0}
        state.entity_states = overrides
        await db.commit()

        captured_user_msgs: list[str] = []

        async def _fake_run_llm_cycle(self, user_msg: str, auto_visualize: bool, language=None):
            _ = auto_visualize
            _ = language
            captured_user_msgs.append(user_msg)
            yield "event: final\ndata: {}\n\n"

        monkeypatch.setattr(GameTurnManager, "_run_llm_cycle", _fake_run_llm_cycle)

        manager = GameTurnManager(db, state.session_id, user)
        async for _ in manager.process_turn("/say Hello, Giant Rat"):
            pass

        assert captured_user_msgs
        assert captured_user_msgs[0] == 'Say out loud: "Hello, Giant Rat"'


async def test_take_on_defeated_npc_is_rejected_except_inspect(setup_test_db):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, _adv, _avatar, state, npc = await _seed_combat_npc(db)
        overrides = dict(state.entity_states or {})
        overrides[npc.id] = {"is_defeated": True, "hp": 0}
        state.entity_states = overrides
        await db.commit()

        manager = GameTurnManager(db, state.session_id, user)
        chunks: list[str] = []
        async for chunk in manager.process_turn("/take Giant Rat"):
            chunks.append(chunk)

        system_chunks = [c for c in chunks if "event: system" in c]
        assert any("Only inspect is available" in c for c in system_chunks)


async def test_open_command_forwards_chat_mirroring_instruction(setup_test_db, monkeypatch):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, _adv, _avatar, state = await _seed_game_context(db)
        captured_user_msgs: list[str] = []

        async def _fake_run_llm_cycle(self, user_msg: str, auto_visualize: bool, language=None):
            _ = auto_visualize
            _ = language
            captured_user_msgs.append(user_msg)
            yield "event: final\ndata: {}\n\n"

        monkeypatch.setattr(GameTurnManager, "_run_llm_cycle", _fake_run_llm_cycle)

        manager = GameTurnManager(db, state.session_id, user)
        async for _ in manager.process_turn("/open Iron Chest"):
            pass

        assert captured_user_msgs
        assert "Open Iron Chest." in captured_user_msgs[0]
        assert "visible in chat history" in captured_user_msgs[0]


async def test_read_command_forwards_chat_mirroring_instruction(setup_test_db, monkeypatch):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, _adv, _avatar, state = await _seed_game_context(db)
        captured_user_msgs: list[str] = []

        async def _fake_run_llm_cycle(self, user_msg: str, auto_visualize: bool, language=None):
            _ = auto_visualize
            _ = language
            captured_user_msgs.append(user_msg)
            yield "event: final\ndata: {}\n\n"

        monkeypatch.setattr(GameTurnManager, "_run_llm_cycle", _fake_run_llm_cycle)

        manager = GameTurnManager(db, state.session_id, user)
        async for _ in manager.process_turn("/read Captain Log"):
            pass

        assert captured_user_msgs
        assert "Read Captain Log." in captured_user_msgs[0]
        assert "remains in chat history" in captured_user_msgs[0]


async def test_combat_auto_triggers_from_gm_requested_attacks(setup_test_db, monkeypatch):
    from backend.engine.rule_engine import AttackRequest
    from tests.conftest import TestSessionLocal

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


async def test_combat_enemy_without_dexterity_uses_baseline_hit_modifier(setup_test_db, monkeypatch):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, _adv, avatar, state, npc = await _seed_combat_npc(db)
        npc.stat_modifier_dexterity = None
        npc.stat_modifier_armor_class = 0
        await db.commit()

        manager = GameTurnManager(db, state.session_id, user)

        # Ensure player starts, then force player miss and enemy hit with deterministic rolls.
        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.random.randint", lambda *_args, **_kwargs: 20)
        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.random.random", lambda: 1.0)

        def fake_roll_attack(attacker, _hit_stat, target_ac, _damage_dice):
            is_enemy = getattr(attacker, "name", "") == "Giant Rat"
            if is_enemy:
                return {
                    "hit_roll": 18,
                    "hit_modifier": int(getattr(attacker, "dexterity", 0)),
                    "hit_total": 18 + int(getattr(attacker, "dexterity", 0)),
                    "target_ac": target_ac,
                    "is_hit": True,
                    "damage_total": 7,
                    "damage_dice_total": 7,
                    "damage_rolls": [7],
                    "damage_bonus": 0,
                    "damage_dice_str": "1d6",
                }
            return {
                "hit_roll": 2,
                "hit_modifier": 0,
                "hit_total": 2,
                "target_ac": target_ac,
                "is_hit": False,
                "damage_total": 0,
                "damage_dice_total": 0,
                "damage_rolls": [],
                "damage_bonus": 0,
                "damage_dice_str": "1d8",
            }

        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.roll_attack", fake_roll_attack)

        async for _ in manager.process_turn("/fight RAT_ENEMY"):
            pass
        async for _ in manager.process_turn("/attack"):
            pass

        await db.refresh(avatar)
        await db.refresh(state)
        combat = (state.entity_states or {}).get("__combat__") or {}
        enemy_logs = [entry for entry in (combat.get("log") or []) if entry.get("type") == "enemy_action"]
        assert enemy_logs
        assert " + 10 = " in enemy_logs[-1].get("text", "")
        assert avatar.hp == 93


async def test_combat_consume_parses_description_healing_effect(setup_test_db, monkeypatch):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, _adv, avatar, state, _npc = await _seed_combat_npc(db)
        avatar.hp = 40
        avatar.max_hp = 100
        avatar.inventory = [
            {
                "id": "HEALING_POTION_1",
                "name": "Heiltrank",
                "description": "Ein kleiner Kristallflakon mit roter Fluessigkeit. Stellt 50 HP wieder her.",
                "item_type": "CONSUMABLE",
            }
        ]
        await db.commit()

        manager = GameTurnManager(db, state.session_id, user)

        # Ensure player starts; enemy turn after consume should not alter HP in this test.
        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.random.randint", lambda *_args, **_kwargs: 20)
        monkeypatch.setattr(
            "backend.api.routes.adventures.gameplay_logic.roll_attack",
            lambda *_args, **_kwargs: {
                "hit_roll": 2,
                "hit_modifier": 0,
                "hit_total": 2,
                "target_ac": 18,
                "is_hit": False,
                "damage_total": 0,
                "damage_dice_total": 0,
                "damage_rolls": [],
                "damage_bonus": 0,
                "damage_dice_str": "1d6",
            },
        )
        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.random.random", lambda: 1.0)

        async for _ in manager.process_turn("/fight RAT_ENEMY"):
            pass
        async for _ in manager.process_turn("/consume Heiltrank"):
            pass

        await db.refresh(avatar)
        await db.refresh(state)

        assert avatar.hp == 90
        assert not any((item or {}).get("id") == "HEALING_POTION_1" for item in (avatar.inventory or []))
        combat = (state.entity_states or {}).get("__combat__") or {}
        assert (combat.get("player") or {}).get("hp") == 90


async def test_combat_consume_uses_explicit_resource_fields(setup_test_db, monkeypatch):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, _adv, avatar, state, _npc = await _seed_combat_npc(db)
        avatar.hp = 70
        avatar.max_hp = 120
        avatar.mana = 20
        avatar.max_mana = 100
        avatar.stamina = 15
        avatar.max_stamina = 80
        avatar.inventory = [
            {
                "id": "COMBAT_TONIC",
                "name": "Combat Tonic",
                "description": "Restores combat resources.",
                "item_type": "CONSUMABLE",
                "hp_change": 25,
                "mana_change": 30,
                "stamina_change": -5,
            }
        ]
        await db.commit()

        manager = GameTurnManager(db, state.session_id, user)

        # Keep the turn deterministic and avoid special-event side effects.
        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.random.randint", lambda *_args, **_kwargs: 20)
        monkeypatch.setattr(
            "backend.api.routes.adventures.gameplay_logic.roll_attack",
            lambda *_args, **_kwargs: {
                "hit_roll": 1,
                "hit_modifier": 0,
                "hit_total": 1,
                "target_ac": 18,
                "is_hit": False,
                "damage_total": 0,
                "damage_dice_total": 0,
                "damage_rolls": [],
                "damage_bonus": 0,
                "damage_dice_str": "1d6",
            },
        )
        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.random.random", lambda: 1.0)

        async for _ in manager.process_turn("/fight RAT_ENEMY"):
            pass
        async for _ in manager.process_turn("/consume Combat Tonic"):
            pass

        await db.refresh(avatar)
        await db.refresh(state)

        assert avatar.hp == 95
        assert avatar.mana == 50
        assert avatar.stamina == 10
        assert not any((item or {}).get("id") == "COMBAT_TONIC" for item in (avatar.inventory or []))

        combat = (state.entity_states or {}).get("__combat__") or {}
        assert (combat.get("player") or {}).get("hp") == 95


async def test_combat_exit_run_triggers_gm_narrative_pass(setup_test_db, monkeypatch):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, _adv, _avatar, state, _npc = await _seed_combat_npc(db)
        manager = GameTurnManager(db, state.session_id, user)

        mock_llm_instance = MagicMock()

        async def mock_stream(*_args, **_kwargs):
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="The dust settles as you retreat."))])

        mock_llm_instance.stream_simple_task = AsyncMock(return_value=mock_stream())
        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.GameMasterLLM", lambda *args, **kwargs: mock_llm_instance)

        # Start with deterministic player initiative.
        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.random.randint", lambda *_args, **_kwargs: 20)

        async for _ in manager.process_turn("/fight RAT_ENEMY"):
            pass

        # Deterministic successful escape.
        escape_rolls = iter([20, 1])
        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.random.randint", lambda *_args, **_kwargs: next(escape_rolls, 20))

        async for _ in manager.process_turn("/run"):
            pass

        res = await db.execute(select(ChatMessage).where(ChatMessage.session_id == state.session_id, ChatMessage.role == "assistant"))
        assistant_msgs = [m.content for m in res.scalars().all()]
        assert any("dust settles" in msg for msg in assistant_msgs)


async def test_combat_exit_loot_done_triggers_gm_narrative_pass(setup_test_db, monkeypatch):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, _adv, _avatar, state, _npc = await _seed_combat_npc(db)
        manager = GameTurnManager(db, state.session_id, user)

        mock_llm_instance = MagicMock()

        async def mock_stream(*_args, **_kwargs):
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="Silence returns after your victory."))])

        mock_llm_instance.stream_simple_task = AsyncMock(return_value=mock_stream())
        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.GameMasterLLM", lambda *args, **kwargs: mock_llm_instance)

        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.random.randint", lambda *_args, **_kwargs: 20)

        async for _ in manager.process_turn("/fight RAT_ENEMY"):
            pass

        # Force lethal player hit to enter loot phase.
        monkeypatch.setattr(
            "backend.api.routes.adventures.gameplay_logic.roll_attack",
            lambda *_args, **_kwargs: {
                "hit_roll": 20,
                "hit_modifier": 5,
                "hit_total": 25,
                "target_ac": 11,
                "is_hit": True,
                "damage_total": 99,
                "damage_dice_total": 99,
                "damage_rolls": [99],
                "damage_bonus": 0,
                "damage_dice_str": "1d8",
            },
        )

        async for _ in manager.process_turn("/attack"):
            pass
        async for _ in manager.process_turn("/loot done"):
            pass

        res = await db.execute(select(ChatMessage).where(ChatMessage.session_id == state.session_id, ChatMessage.role == "assistant"))
        assistant_msgs = [m.content for m in res.scalars().all()]
        assert any("Silence returns" in msg for msg in assistant_msgs)


async def test_combat_npc_stamina_logic_active(setup_test_db, monkeypatch):
    """Verifies that if the NPC has max_stamina > 0, stamina consumption and exhausted resting are enforced."""
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, _adv, avatar, state, npc = await _seed_combat_npc(db)
        npc.stamina = 20
        npc.max_stamina = 20
        await db.commit()

        manager = GameTurnManager(db, state.session_id, user)

        # Force player to act first, and player misses so fight continues
        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.random.randint", lambda *_args, **_kwargs: 20)
        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.random.random", lambda: 1.0)
        
        # Player and enemy attack miss
        monkeypatch.setattr(
            "backend.api.routes.adventures.gameplay_logic.roll_attack",
            lambda *_args, **_kwargs: {
                "hit_roll": 2,
                "hit_modifier": 0,
                "hit_total": 2,
                "target_ac": 18,
                "is_hit": False,
                "damage_total": 0,
                "damage_dice_total": 0,
                "damage_rolls": [],
                "damage_bonus": 0,
                "damage_dice_str": "1d6",
            },
        )

        # Start combat
        async for _ in manager.process_turn("/fight RAT_ENEMY"):
            pass

        # 1st Attack: Player attacks (and misses). Then Enemy attacks.
        # This enemy attack should consume 20 stamina, bringing enemy stamina down to 0.
        async for _ in manager.process_turn("/attack"):
            pass

        await db.refresh(state)
        combat = (state.entity_states or {}).get("__combat__") or {}
        assert combat.get("enemy", {}).get("stamina") == 0

        # 2nd Attack: Player attacks (and misses) again.
        # Now the enemy has 0 stamina (< 20 required). Enemy must rest to recover +40 stamina (capped at max 20).
        async for _ in manager.process_turn("/attack"):
            pass

        await db.refresh(state)
        combat = (state.entity_states or {}).get("__combat__") or {}
        assert combat.get("enemy", {}).get("stamina") == 20
        logs = combat.get("log") or []
        assert any("is exhausted and rests to recover stamina" in entry.get("text", "") for entry in logs)


async def test_combat_npc_stamina_logic_inactive(setup_test_db, monkeypatch):
    """Verifies that if the NPC has max_stamina == 0 or None, stamina logic is bypassed and they attack normally without depletion."""
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, _adv, avatar, state, npc = await _seed_combat_npc(db)
        npc.stamina = 0
        npc.max_stamina = 0
        await db.commit()

        manager = GameTurnManager(db, state.session_id, user)

        # Force player to act first, and player misses so fight continues
        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.random.randint", lambda *_args, **_kwargs: 20)
        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.random.random", lambda: 1.0)
        
        # Player and enemy attack miss
        monkeypatch.setattr(
            "backend.api.routes.adventures.gameplay_logic.roll_attack",
            lambda *_args, **_kwargs: {
                "hit_roll": 2,
                "hit_modifier": 0,
                "hit_total": 2,
                "target_ac": 18,
                "is_hit": False,
                "damage_total": 0,
                "damage_dice_total": 0,
                "damage_rolls": [],
                "damage_bonus": 0,
                "damage_dice_str": "1d6",
            },
        )

        # Start combat
        async for _ in manager.process_turn("/fight RAT_ENEMY"):
            pass

        # Player attacks. Then Enemy attacks.
        # Enemy has max_stamina = 0, so they attack without stamina check, remaining at 0 stamina.
        async for _ in manager.process_turn("/attack"):
            pass

        await db.refresh(state)
        combat = (state.entity_states or {}).get("__combat__") or {}
        assert combat.get("enemy", {}).get("stamina") == 0
        logs = combat.get("log") or []
        # Enemy should not rest/be exhausted
        assert not any("is exhausted and rests to recover stamina" in entry.get("text", "") for entry in logs)


async def test_wrong_container_access_code_is_rejected_server_side(setup_test_db):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, _adv, avatar, state = await _seed_game_context(db)
        locker = WorldEntity(
            id="LOCKER",
            session_id=state.session_id,
            entity_type="OBJECT",
            name="Maintenance Locker",
            description="A secure maintenance locker.",
            current_scene_id=state.current_scene_id,
            item_type="CONTAINER",
            unlock_rule=None,
            inventory=["MEDIKIT_01"],
            is_portable=False,
            is_hidden=False,
            is_in_inventory=False,
            metadata_json={"code_to_unlock": "7341", "item_to_unlock": "", "locked": True},
        )
        db.add(locker)
        await db.commit()

        manager = GameTurnManager(db, state.session_id, user)
        manager.state = state
        manager.avatar = avatar

        event = GameEvent(
            updated_entities=[WorldEntityUpdate(entity_id="LOCKER", locked=False)],
            completed_quest_ids=["LOCKER_ROOKIE"],
            new_inventory_items=[InventoryItem(id="MEDIKIT_01", name="Medikit", item_type="CONSUMABLE")],
        )

        messages = await manager._enforce_container_unlock_guardrails(event, "use code 1111 on maintenance locker")

        assert any("mocking click" in msg for msg in messages)
        assert event.completed_quest_ids == []
        assert event.new_inventory_items == []
        assert any(up.entity_id == "LOCKER" and up.locked is True for up in (event.updated_entities or []))


async def test_quest_and_award_accessibility_guardrail(setup_test_db):
    from tests.conftest import TestSessionLocal
    from backend.models.world_entity import WorldEntity
    from backend.engine.rule_engine import GameEvent

    async with TestSessionLocal() as db:
        user, adv, avatar, state = await _seed_game_context(db)
        
        # Seed the slang dictionary item in another room (MEN_RESTROOM)
        dictionary = WorldEntity(
            id="DINER_SLANG_DICTIONARY",
            session_id=state.session_id,
            entity_type="OBJECT",
            name="Diner Slang Dictionary",
            description="A slang dictionary.",
            current_scene_id="MEN_RESTROOM",  # different scene!
            is_portable=True,
            is_hidden=False,
            is_in_inventory=False,
        )
        db.add(dictionary)
        
        # Seed quest and award in state/adventure
        state.quests = [
            {
                "id": "TRANSLATE_SLANG",
                "title": "Slang 101",
                "description": "Betty left notes. Find a translation guide.",
                "goal": "Read DINER_SLANG_DICTIONARY.",
                "status": "open"
            }
        ]
        adv.awards = [
            {
                "key": "SLANG_MASTER",
                "title": "Slang Master",
                "description": "Found and studied the diner slang dictionary.",
                "tier": "bronze",
                "requirement": "Read DINER_SLANG_DICTIONARY.",
                "is_earned": False
            }
        ]
        await db.commit()

        manager = GameTurnManager(db, state.session_id, user)
        await manager.initialize()

        # Simulate LLM trying to complete the quest and grant the award
        # while the player is in START (not MEN_RESTROOM) and does not have the item.
        event = GameEvent(
            completed_quest_ids=["TRANSLATE_SLANG"],
            earned_award_keys=["SLANG_MASTER"],
        )

        await manager._enforce_quest_and_award_guardrails(event)

        # Assert that both are blocked (removed from the event)
        assert event.completed_quest_ids == []
        assert event.earned_award_keys == []

        # Now make the dictionary accessible (move it to START, the current scene)
        dictionary.current_scene_id = state.current_scene_id
        await db.commit()

        event2 = GameEvent(
            completed_quest_ids=["TRANSLATE_SLANG"],
            earned_award_keys=["SLANG_MASTER"],
        )
        await manager._enforce_quest_and_award_guardrails(event2)

        # Assert that both are allowed now
        assert event2.completed_quest_ids == ["TRANSLATE_SLANG"]
        assert event2.earned_award_keys == ["SLANG_MASTER"]


async def test_quest_completion_accumulates_xp(setup_test_db, monkeypatch):
    """Verifies that completing a quest adds its exp_reward to the avatar's exp total."""
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, adv, avatar, state = await _seed_game_context(db)
        adv.strict_rules = False
        adv.rule_enforcement_mode = "chat"
        adv.is_adventure_generator = False
        
        # Seed quest with 250 XP reward
        state.quests = [{"id": "q-xp-test", "title": "XP Quest", "status": "open", "is_main": True, "exp_reward": 250}]
        avatar.exp = 50
        await db.commit()

        mock_llm_instance = MagicMock()
        async def mock_progression(*args, **kwargs):
            return AdventureGeneratorToolIntent(
                completed_quest_ids=["q-xp-test"],
            )

        async def mock_stream(*args, **kwargs):
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="Quest complete!"))])

        mock_llm_instance.aexecute_complex_task = AsyncMock(side_effect=mock_progression)
        mock_llm_instance.stream_simple_task = AsyncMock(return_value=mock_stream())
        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.GameMasterLLM", lambda *args, **kwargs: mock_llm_instance)

        manager = GameTurnManager(db, "session-1", user)
        async for _ in manager.process_turn("I complete the quest"):
            pass

        await db.refresh(avatar)
        await db.refresh(state)

        # 50 + 250 = 300 XP
        assert avatar.exp == 300
        assert (state.quests or [])[0].get("status") == "completed"

        # Check ChatMessage system entry
        sys_msgs = (
            await db.execute(
                select(ChatMessage).where(
                    ChatMessage.session_id == "session-1",
                    ChatMessage.role == "system",
                )
            )
        ).scalars().all()
        assert any("Quest completed: XP Quest" in m.content for m in sys_msgs)
        assert any("you gained 250 XP" in m.content for m in sys_msgs)


async def test_combat_defeat_adds_xp(setup_test_db, monkeypatch):
    """Verifies that combat victory adds XP and generates SSE/chat events."""
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, adv, avatar, state, npc = await _seed_combat_npc(db)
        npc.metadata_json = {"exp_reward": 75}
        avatar.exp = 10
        await db.commit()

        manager = GameTurnManager(db, state.session_id, user)
        
        # Start combat
        async for _ in manager.process_turn(f"/fight {npc.id}"):
            pass

        # Force roll_attack to hit with lethal damage
        monkeypatch.setattr(
            "backend.api.routes.adventures.gameplay_logic.roll_attack",
            lambda *_args, **_kwargs: {
                "hit_roll": 18,
                "hit_modifier": 2,
                "hit_total": 20,
                "target_ac": 10,
                "is_hit": True,
                "damage_total": 50,  # Lethal for 40 hp npc
                "damage_dice_total": 50,
                "damage_rolls": [50],
                "damage_bonus": 0,
                "damage_dice_str": "1d6",
            },
        )

        chunks = []
        async for chunk in manager.process_turn("/attack"):
            chunks.append(chunk)

        await db.refresh(avatar)
        # 10 + 75 = 85 XP
        assert avatar.exp == 85

        # Check ChatMessage
        sys_msgs = (
            await db.execute(
                select(ChatMessage).where(
                    ChatMessage.session_id == state.session_id,
                    ChatMessage.role == "system",
                )
            )
        ).scalars().all()
        assert any(f"Defeated {npc.name}" in m.content for m in sys_msgs)
        assert any("you gained 75 XP" in m.content for m in sys_msgs)


async def test_container_code_unlock_adds_xp(setup_test_db):
    """Verifies that unlocking a container via API or turn flow awards XP."""
    from tests.conftest import TestSessionLocal
    from fastapi import HTTPException
    from backend.api.routes.adventures.gameplay import unlock_container_with_code, ContainerUnlockCodeRequest

    async with TestSessionLocal() as db:
        user, adv, avatar, state = await _seed_game_context(db)
        avatar.exp = 100
        
        # Seed container requiring code
        chest = WorldEntity(
            id="CHEST_1",
            session_id=state.session_id,
            entity_type="OBJECT",
            name="Iron Chest",
            description="A heavy chest.",
            current_scene_id=state.current_scene_id,
            item_type="CONTAINER",
            is_portable=False,
            is_hidden=False,
            is_in_inventory=False,
            metadata_json={"code_to_unlock": "1234", "locked": True, "exp_reward": 80},
        )
        db.add(chest)
        await db.commit()

        # 1. Test API Unlock
        response = await unlock_container_with_code(
            game_id=state.session_id,
            entity_id="CHEST_1",
            payload=ContainerUnlockCodeRequest(code="1234"),
            db=db,
            current_user=user
        )
        assert response["locked"] is False

        await db.refresh(avatar)
        # 100 + 80 = 180 XP
        assert avatar.exp == 180

        # Check system message
        sys_msgs = (
            await db.execute(
                select(ChatMessage).where(
                    ChatMessage.session_id == state.session_id,
                    ChatMessage.role == "system",
                )
            )
        ).scalars().all()
        assert any("Unlocked Iron Chest with the correct code!" in m.content for m in sys_msgs)
        assert any("you gained 80 XP" in m.content for m in sys_msgs)

        with pytest.raises(HTTPException, match="mocking click") as exc_info:
            await unlock_container_with_code(
                game_id=state.session_id,
                entity_id="CHEST_1",
                payload=ContainerUnlockCodeRequest(code="9999"),
                db=db,
                current_user=user
            )
        assert exc_info.value.status_code == 403

        # Reset for turn-based testing
        avatar.exp = 100
        state.entity_states = {}
        await db.commit()

        # 2. Test Turn flow unlock transition
        manager = GameTurnManager(db, state.session_id, user)
        await manager.initialize()
        # Simulate LLM game event unlocking it
        event = GameEvent(
            updated_entities=[WorldEntityUpdate(entity_id="CHEST_1", locked=False)]
        )
        
        await manager._apply_game_event(event)
        await db.refresh(avatar)
        # 100 + 80 = 180 XP
        assert avatar.exp == 180
 
 
async def test_game_loop_adjacent_only_scene_transitions(setup_test_db, monkeypatch):
    """Verifies that scene transitions are allowed to adjacent scenes and blocked otherwise."""
    from tests.conftest import TestSessionLocal
    
    async with TestSessionLocal() as db:
        user, adv, avatar, state = await _seed_game_context(db)
        
        # Seed WorldExit: START -> CELLAR (adjacent)
        db.add(WorldExit(
            session_id="session-1",
            template_id=adv.id,
            from_scene_id="START",
            to_scene_id="CELLAR",
            label="cellar door",
            is_locked=False,
        ))
        await db.commit()
        
        manager = GameTurnManager(db, "session-1", user)
        await manager.initialize()
        
        # 1. Attempt valid adjacent transition
        event_valid = GameEvent(new_scene_id="CELLAR")
        await manager._apply_game_event(event_valid)
        await db.refresh(state)
        assert state.current_scene_id == "CELLAR"
        
        # 2. Attempt invalid non-adjacent transition (to VAULT)
        event_invalid = GameEvent(new_scene_id="VAULT")
        await manager._apply_game_event(event_invalid)
        await db.refresh(state)
        # Should stay in CELLAR
        assert state.current_scene_id == "CELLAR"
        
        # Check that transition fields in event_invalid were cleared
        assert event_invalid.new_scene_id is None
        
        # Check system message in DB
        res = await db.execute(
            select(ChatMessage).where(
                ChatMessage.session_id == "session-1",
                ChatMessage.role == "system",
            )
        )
        sys_msgs = [m.content for m in res.scalars().all()]
        assert any("Movement blocked: The destination 'VAULT' is not adjacent" in msg for msg in sys_msgs)


async def test_game_loop_lookaround_exits(setup_test_db, monkeypatch):
    """Verifies that lookaround adds compact exit instructions to the narration prompt."""
    import json
    from tests.conftest import TestSessionLocal
    
    async with TestSessionLocal() as db:
        user, adv, avatar, state = await _seed_game_context(db)
        
        # Seed exits from START:
        # 1. Locked exit
        db.add(WorldExit(
            session_id="session-1",
            template_id=adv.id,
            from_scene_id="START",
            to_scene_id="CELLAR",
            label="Iron Door",
            is_locked=True,
        ))
        # 2. Open exit
        db.add(WorldExit(
            session_id="session-1",
            template_id=adv.id,
            from_scene_id="START",
            to_scene_id="HALL",
            label="Wooden Door",
            is_locked=False,
        ))
        await db.commit()
        
        # Mock LLM
        mock_llm_instance = MagicMock()
        mock_event = GameEvent(
            narrative_description="You inspect the room.",
            hp_change=0,
            stamina_change=0,
            mana_change=0,
            new_status_effects=[],
            new_inventory_items=[],
            scene_change=None,
            requested_skill_checks=[]
        )
        mock_llm_instance.aexecute_complex_task = AsyncMock(return_value=mock_event)
        
        async def mock_stream(*args, **kwargs):
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="The room is dark."))])
            
        mock_llm_instance.stream_simple_task = AsyncMock(return_value=mock_stream())
        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.GameMasterLLM", lambda *args, **kwargs: mock_llm_instance)
        
        # Test 1: look around (natural language)
        manager = GameTurnManager(db, "session-1", user)
        chunks = []
        async for chunk in manager.process_turn("look around"):
            chunks.append(chunk)
            
        # Parse SSE events from chunk
        # Yield is in format: f"event: chunk\ndata: {json.dumps({'content': delta})}\n\n"
        full_text = ""
        for chunk in chunks:
            if "event: chunk" in chunk:
                # Extract content
                data_line = [line for line in chunk.split("\n") if line.startswith("data:")][0]
                content = json.loads(data_line[5:])["content"]
                full_text += content
                
        assert "The room is dark." in full_text
        assert "Exits:" not in full_text

        prompt_lookaround = mock_llm_instance.stream_simple_task.await_args_list[0].args[0]
        assert "EXIT DESCRIPTION TASK (MANDATORY)" in prompt_lookaround
        assert "CURRENT SCENE EXITS:" in prompt_lookaround
        assert "Keep it short (max 2 sentences)." in prompt_lookaround
        assert "Iron Door" in prompt_lookaround
        assert "Wooden Door" in prompt_lookaround
        assert '"is_locked":true' in prompt_lookaround

        # Test 2: language=de still gets the same exit-task prompt (language handled by runtime translation layer)
        chunks_de = []
        async for chunk in manager.process_turn("look around", language="de"):
            chunks_de.append(chunk)
            
        full_text_de = ""
        for chunk in chunks_de:
            if "event: chunk" in chunk:
                data_line = [line for line in chunk.split("\n") if line.startswith("data:")][0]
                content = json.loads(data_line[5:])["content"]
                full_text_de += content

        assert "Exits:" not in full_text_de

        prompt_lookaround_de = mock_llm_instance.stream_simple_task.await_args_list[1].args[0]
        assert "EXIT DESCRIPTION TASK (MANDATORY)" in prompt_lookaround_de
        assert "CURRENT SCENE EXITS:" in prompt_lookaround_de
        assert "Keep it short (max 2 sentences)." in prompt_lookaround_de
        assert "Iron Door" in prompt_lookaround_de
        assert "Wooden Door" in prompt_lookaround_de


async def test_game_loop_scene_change_auto_appends_narrative_exits(setup_test_db, monkeypatch):
    """Verifies that scene transitions add compact exit instructions to narration prompt."""
    import json
    from types import SimpleNamespace
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, adv, avatar, state = await _seed_game_context(db)

        db.add(WorldExit(
            session_id="session-1",
            template_id=adv.id,
            from_scene_id="START",
            to_scene_id="HALL",
            label="Wooden Door",
            is_locked=False,
        ))
        db.add(WorldExit(
            session_id="session-1",
            template_id=adv.id,
            from_scene_id="HALL",
            to_scene_id="GARDEN",
            label="Garden Gate",
            is_locked=False,
        ))
        db.add(WorldScene(
            id="HALL",
            session_id="session-1",
            template_id=adv.id,
            label="Hall",
            description="A narrow hallway.",
        ))
        db.add(WorldScene(
            id="GARDEN",
            session_id="session-1",
            template_id=adv.id,
            label="Garden",
            description="A damp garden.",
        ))
        await db.commit()

        mock_llm_instance = MagicMock()
        mock_event = GameEvent(
            narrative_description="You step through the wooden door.",
            hp_change=0,
            stamina_change=0,
            mana_change=0,
            new_status_effects=[],
            new_inventory_items=[],
            scene_change=None,
            requested_skill_checks=[],
            new_scene_id="HALL",
            exit_label="Wooden Door",
        )
        mock_llm_instance.aexecute_complex_task = AsyncMock(return_value=mock_event)

        async def mock_stream(*args, **kwargs):
            yield MagicMock(choices=[MagicMock(delta=MagicMock(content="You step into the hall."))])

        mock_llm_instance.stream_simple_task = AsyncMock(return_value=mock_stream())
        monkeypatch.setattr("backend.api.routes.adventures.gameplay_logic.GameMasterLLM", lambda *args, **kwargs: mock_llm_instance)
        monkeypatch.setattr(
            "backend.api.routes.adventures.gameplay_logic.SessionCheckpointService.create_checkpoint",
            AsyncMock(return_value=SimpleNamespace(id=1, trigger_reason="SCENE_CHANGE", created_at=None)),
        )

        manager = GameTurnManager(db, "session-1", user)
        chunks = []
        async for chunk in manager.process_turn("go through the wooden door"):
            chunks.append(chunk)

        full_text = ""
        for chunk in chunks:
            if "event: chunk" in chunk:
                data_line = [line for line in chunk.split("\n") if line.startswith("data:")][0]
                content = json.loads(data_line[5:])["content"]
                full_text += content

        assert "You step into the hall." in full_text
        assert "Exits:" not in full_text

        prompt_scene_change = mock_llm_instance.stream_simple_task.await_args_list[0].args[0]
        assert "EXIT DESCRIPTION TASK (MANDATORY)" in prompt_scene_change
        assert "CURRENT SCENE EXITS:" in prompt_scene_change
        assert "Use exactly 1 sentence for the exit paragraph" in prompt_scene_change
        assert "do not use contrast/addition connectors" in prompt_scene_change
        assert "Garden Gate" in prompt_scene_change
        assert "Garden" in prompt_scene_change


async def test_exit_lock_guardrail_wrong_code(setup_test_db):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, _adv, avatar, state = await _seed_game_context(db)
        
        # Seed locked exit with code
        db.add(WorldExit(
            session_id=state.session_id,
            from_scene_id=state.current_scene_id,
            to_scene_id="CELLAR",
            label="Digital Security Door",
            is_locked=True,
            code_to_unlock="4711",
            item_to_unlock=None,
        ))
        await db.commit()

        manager = GameTurnManager(db, state.session_id, user)
        await manager.initialize()

        # Simulate LLM trying to transition to CELLAR
        event = GameEvent(
            new_scene_id="CELLAR",
            updated_exits=[ExitUpdate(from_scene_id=state.current_scene_id, to_scene_id="CELLAR", is_locked=False)],
            completed_quest_ids=["ENTER_CELLAR"],
        )

        reasons = await manager._enforce_exit_unlock_guardrails(event, "I try to use code 1234 on the digital security door")

        assert any("cold red blink" in r for r in reasons)
        assert event.new_scene_id is None
        assert event.completed_quest_ids == []
        assert any(up.to_scene_id == "CELLAR" and up.is_locked is True for up in event.updated_exits)


async def test_exit_lock_guardrail_correct_code(setup_test_db):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, _adv, avatar, state = await _seed_game_context(db)
        
        # Seed locked exit with code
        db.add(WorldExit(
            session_id=state.session_id,
            from_scene_id=state.current_scene_id,
            to_scene_id="CELLAR",
            label="Digital Security Door",
            is_locked=True,
            code_to_unlock="4711",
            item_to_unlock=None,
        ))
        await db.commit()

        manager = GameTurnManager(db, state.session_id, user)
        await manager.initialize()

        event = GameEvent(
            new_scene_id="CELLAR",
            completed_quest_ids=["ENTER_CELLAR"],
        )

        reasons = await manager._enforce_exit_unlock_guardrails(event, "I enter code 4711 on the digital security door")

        assert not reasons
        assert event.new_scene_id == "CELLAR"
        assert event.completed_quest_ids == ["ENTER_CELLAR"]
        assert any(up.to_scene_id == "CELLAR" and up.is_locked is False for up in event.updated_exits)


async def test_exit_lock_guardrail_missing_item(setup_test_db):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, _adv, avatar, state = await _seed_game_context(db)
        
        # Seed locked exit with item
        db.add(WorldExit(
            session_id=state.session_id,
            from_scene_id=state.current_scene_id,
            to_scene_id="CELLAR",
            label="Heavy Steel Gate",
            is_locked=True,
            code_to_unlock=None,
            item_to_unlock="CELLAR_KEY",
        ))
        await db.commit()

        manager = GameTurnManager(db, state.session_id, user)
        await manager.initialize()

        event = GameEvent(
            new_scene_id="CELLAR",
            updated_exits=[ExitUpdate(from_scene_id=state.current_scene_id, to_scene_id="CELLAR", is_locked=False)],
        )

        reasons = await manager._enforce_exit_unlock_guardrails(event, "I open the heavy steel gate")

        assert any("You need CELLAR_KEY" in r for r in reasons)
        assert event.new_scene_id is None
        assert any(up.to_scene_id == "CELLAR" and up.is_locked is True for up in event.updated_exits)


async def test_exit_lock_guardrail_correct_item(setup_test_db):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, _adv, avatar, state = await _seed_game_context(db)
        
        # Give item to player
        avatar.inventory = [{"id": "CELLAR_KEY", "name": "Cellar Key", "item_type": "KEY"}]
        
        # Seed locked exit with item
        db.add(WorldExit(
            session_id=state.session_id,
            from_scene_id=state.current_scene_id,
            to_scene_id="CELLAR",
            label="Heavy Steel Gate",
            is_locked=True,
            code_to_unlock=None,
            item_to_unlock="CELLAR_KEY",
        ))
        await db.commit()

        manager = GameTurnManager(db, state.session_id, user)
        await manager.initialize()

        event = GameEvent(
            new_scene_id="CELLAR",
        )

        reasons = await manager._enforce_exit_unlock_guardrails(event, "I unlock the heavy steel gate with my cellar key")

        assert not reasons
        assert event.new_scene_id == "CELLAR"
        assert any(up.to_scene_id == "CELLAR" and up.is_locked is False for up in event.updated_exits)


async def test_exit_rule_unlock_passes(setup_test_db):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, _adv, avatar, state = await _seed_game_context(db)
        
        # Seed locked exit with rule_to_unlock
        db.add(WorldExit(
            session_id=state.session_id,
            from_scene_id=state.current_scene_id,
            to_scene_id="CELLAR",
            label="Narrative Gate",
            is_locked=True,
            code_to_unlock=None,
            item_to_unlock=None,
            rule_to_unlock="Protagonist defeats NPC_2"
        ))
        await db.commit()

        manager = GameTurnManager(db, state.session_id, user)
        await manager.initialize()

        # CASE 1: Player tries to traverse, but GM does NOT unlock it (is_being_unlocked is False). It should fail!
        event_fail = GameEvent(
            new_scene_id="CELLAR",
        )
        reasons_fail = await manager._enforce_exit_unlock_guardrails(event_fail, "I try to walk through narrative gate")
        assert any("is locked" in r for r in reasons_fail)
        assert event_fail.new_scene_id is None

        # CASE 2: GM explicitly unlocks it (is_being_unlocked is True). It should succeed!
        event_ok = GameEvent(
            new_scene_id="CELLAR",
            updated_exits=[ExitUpdate(from_scene_id=state.current_scene_id, to_scene_id="CELLAR", is_locked=False)]
        )
        reasons_ok = await manager._enforce_exit_unlock_guardrails(event_ok, "I defeated the NPC, let me through")
        assert not reasons_ok
        assert event_ok.new_scene_id == "CELLAR"


async def test_container_rule_unlock_passes(setup_test_db):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, _adv, avatar, state = await _seed_game_context(db)
        
        # Seed locked container object with rule_to_unlock
        db.add(WorldEntity(
            id="MAGIC_CHEST",
            session_id=state.session_id,
            entity_type="OBJECT",
            name="Magic Chest",
            description="A glowing wooden chest",
            current_scene_id=state.current_scene_id,
            item_type="CONTAINER",
            metadata_json={
                "code_to_unlock": "",
                "item_to_unlock": "",
                "rule_to_unlock": "Protagonist overpersuades NPC_1",
                "locked": True,
            }
        ))
        await db.commit()

        manager = GameTurnManager(db, state.session_id, user)
        await manager.initialize()

        # Check that is_container_locked returns True initially
        chest_res = await db.execute(select(WorldEntity).where(WorldEntity.session_id == state.session_id, WorldEntity.id == "MAGIC_CHEST"))
        chest = chest_res.scalars().first()
        assert manager._is_container_locked(chest, None) is True

        # CASE 1: GM unlocks container (updated_entities has locked=False). It should succeed!
        event = GameEvent(
            updated_entities=[WorldEntityUpdate(entity_id="MAGIC_CHEST", locked=False)]
        )
        reasons = await manager._enforce_container_unlock_guardrails(event, "I persuaded the librarian to let me open the chest")
        assert not reasons


def test_mutual_exclusivity_normalization():
    from backend.engine.world_generator import _normalize_unlock_requirements

    # Priority 1: code wins over item and rule
    code, item, rule = _normalize_unlock_requirements("1234", "KEY_CARD", "narrative rule")
    assert code == "1234"
    assert item == ""
    assert rule == ""

    # Priority 2: item wins over rule
    code, item, rule = _normalize_unlock_requirements("", "KEY_CARD", "narrative rule")
    assert code == ""
    assert item == "KEY_CARD"
    assert rule == ""

    # Priority 3: rule is chosen if code and item are empty
    code, item, rule = _normalize_unlock_requirements("", "", "narrative rule")
    assert code == ""
    assert item == ""
    assert rule == "narrative rule"



