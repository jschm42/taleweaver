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
from backend.engine.rule_engine import GameEvent, AdventureGeneratorToolIntent

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
                instant_narrative="I can offer tones for your new world."
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
            instant_narrative=None,
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


async def test_chat_mode_narration_only_skips_first_pass_and_keeps_progress_unchanged(setup_test_db, monkeypatch):
    """Normal chat mode should skip first-pass tool/mechanics extraction and only stream narration."""
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user, adv, _avatar, state = await _seed_game_context(db)
        adv.strict_rules = False
        adv.rule_enforcement_mode = "chat"
        adv.is_adventure_generator = False
        adv.awards = [{"key": "heroic-heart", "title": "Heroic Heart", "tier": "silver"}]
        state.quests = [{"id": "q-1", "title": "Open the Gate", "status": "open", "is_main": True}]
        user.earned_awards = []
        await db.commit()

        mock_llm_instance = MagicMock()
        mock_llm_instance.aexecute_complex_task = AsyncMock()

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

        assert mock_llm_instance.aexecute_complex_task.await_count == 0
        assert mock_llm_instance.stream_simple_task.await_count == 1
        assert any("quiet wind" in c for c in chunks)
        assert (state.quests or [])[0].get("status") == "open"
        assert user.earned_awards == []

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
