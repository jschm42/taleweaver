import os
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy import select

from backend.api.routes.adventures.agent_logic import AgentDecision, AgentService
from backend.api.routes.adventures.sessions import start_session_for_template
from backend.core.config import settings
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.session_state import SessionState
from backend.models.user import User
from backend.models.world_entity import WorldEntity
from backend.utils.path_security import ensure_within_data_dir, safe_data_path

pytestmark = pytest.mark.asyncio


async def test_agent_toggle_commands(auth_client, setup_test_db):
    """Verifies /agent on and /agent off toggle the state correctly via process_turn."""
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user_res = await db.execute(select(User).limit(1))
        user = user_res.scalars().first()

        adv = AdventureTemplate(
            id="agent-toggle-test", owner_id=user.id, title="Agent Test", is_ready=True
        )
        db.add(adv)
        await db.commit()
        await db.refresh(user)
        await db.refresh(adv)

        result = await start_session_for_template("agent-toggle-test", db, user)
        game_id = result["game_id"]

        # Turn manager import
        from backend.api.routes.adventures.gameplay_logic import GameTurnManager

        manager = GameTurnManager(db, game_id, user)
        assert await manager.initialize()

        # Check default inactive
        agent_state = AgentService.get_agent_state(manager.state)
        assert agent_state.get("active") is False
        assert agent_state.get("monkey_mode") is False

        # Turn agent ON
        chunks = []
        async for chunk in manager.process_turn("/agent on"):
            chunks.append(chunk)

        # Re-fetch state using a fresh session to avoid stale transaction isolation
        async with TestSessionLocal() as verify_db:
            state_res = await verify_db.execute(
                select(SessionState).where(SessionState.session_id == game_id)
            )
            state = state_res.scalars().first()
            assert AgentService.get_agent_state(state).get("active") is True

        # Verify SSE output contains success message and sheet with agent_active = True
        full_sse = "".join(chunks)
        assert "Autonomous Agent Gameplay Mode enabled" in full_sse
        assert '"agent_active":true' in full_sse.replace(" ", "")
        assert '"agent_monkey_mode":false' in full_sse.replace(" ", "")

        # Turn agent OFF
        chunks = []
        async for chunk in manager.process_turn("/agent off"):
            chunks.append(chunk)

        async with TestSessionLocal() as verify_db:
            state_res = await verify_db.execute(
                select(SessionState).where(SessionState.session_id == game_id)
            )
            state = state_res.scalars().first()
            assert AgentService.get_agent_state(state).get("active") is False

        assert '"agent_active":false' in "".join(chunks).replace(" ", "")


async def test_agent_monkey_mode_toggle_commands(auth_client, setup_test_db):
    """Verifies /agent monkey on and /agent monkey off toggle monkey mode."""
    from backend.api.routes.adventures.gameplay_logic import GameTurnManager
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user_res = await db.execute(select(User).limit(1))
        user = user_res.scalars().first()

        adv = AdventureTemplate(
            id="agent-monkey-toggle-test",
            owner_id=user.id,
            title="Agent Monkey Test",
            is_ready=True,
        )
        db.add(adv)
        await db.commit()

        result = await start_session_for_template("agent-monkey-toggle-test", db, user)
        game_id = result["game_id"]

        manager = GameTurnManager(db, game_id, user)
        assert await manager.initialize()

        # Toggle monkey mode ON/OFF via slash command
        chunks = []
        async for chunk in manager.process_turn("/agent monkey on"):
            chunks.append(chunk)

        async with TestSessionLocal() as verify_db:
            state_res = await verify_db.execute(
                select(SessionState).where(SessionState.session_id == game_id)
            )
            state = state_res.scalars().first()
            assert AgentService.get_agent_state(state).get("monkey_mode") is True

        assert '"agent_monkey_mode":true' in "".join(chunks).replace(" ", "")
        assert "Monkey Mode enabled" in "".join(chunks)

        chunks = []
        async for chunk in manager.process_turn("/agent monkey off"):
            chunks.append(chunk)

        async with TestSessionLocal() as verify_db:
            state_res = await verify_db.execute(
                select(SessionState).where(SessionState.session_id == game_id)
            )
            state = state_res.scalars().first()
            assert AgentService.get_agent_state(state).get("monkey_mode") is False

        assert '"agent_monkey_mode":false' in "".join(chunks).replace(" ", "")
        assert "Monkey Mode disabled" in "".join(chunks)


async def test_agent_on_uses_monkey_mode_default_from_settings(auth_client, setup_test_db):
    """/agent on should initialize monkey mode from persisted llm settings."""
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user_res = await db.execute(select(User).limit(1))
        user = user_res.scalars().first()
        user.llm_settings = {
            "small_model": "gpt-4o-mini",
            "small_model_provider": "openai",
            "complex_model": "gpt-4o",
            "complex_model_provider": "openai",
            "generator_model": "gpt-4o",
            "generator_model_provider": "openai",
            "play_agent_model": "gpt-4o-mini",
            "play_agent_model_provider": "openai",
            "play_agent_monkey_mode": True,
            "preferred_provider": "openai",
            "ollama_url": "http://localhost:11434",
        }

        adv = AdventureTemplate(
            id="agent-monkey-default-test",
            owner_id=user.id,
            title="Agent Monkey Default Test",
            is_ready=True,
        )
        db.add(adv)
        await db.commit()
        await db.refresh(user)

        result = await start_session_for_template("agent-monkey-default-test", db, user)
        game_id = result["game_id"]

        from backend.api.routes.adventures.gameplay_logic import GameTurnManager

        manager = GameTurnManager(db, game_id, user)
        assert await manager.initialize()

        chunks = []
        async for chunk in manager.process_turn("/agent on"):
            chunks.append(chunk)

        async with TestSessionLocal() as verify_db:
            state_res = await verify_db.execute(
                select(SessionState).where(SessionState.session_id == game_id)
            )
            state = state_res.scalars().first()
            assert AgentService.get_agent_state(state).get("active") is True
            assert AgentService.get_agent_state(state).get("monkey_mode") is True

        assert "Monkey Mode is active by default from settings" in "".join(chunks)


async def test_agent_turn_endpoint_validation(auth_client, setup_test_db):
    """Verifies agent turn endpoint rejects request if agent mode is not active."""
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user_res = await db.execute(select(User).limit(1))
        user = user_res.scalars().first()

        adv = AdventureTemplate(
            id="agent-endpoint-test", owner_id=user.id, title="Agent Endpoint Test", is_ready=True
        )
        db.add(adv)
        await db.commit()

        result = await start_session_for_template("agent-endpoint-test", db, user)
        game_id = result["game_id"]

        # Call endpoint directly without enabling agent
        response = await auth_client.post(f"/api/adventures/{game_id}/agent/turn")
        assert response.status_code == 400
        assert "Agent is not enabled" in response.json()["detail"]


@patch("backend.api.routes.adventures.agent_logic.AgentService.get_decision")
async def test_agent_turn_execution_success(mock_get_decision, auth_client, setup_test_db):
    """Verifies that a successful decision runs the turn, reset failures, and streams thoughts/actions."""
    from tests.conftest import TestSessionLocal

    # Mock decision
    mock_get_decision.return_value = AgentDecision(
        thoughts="I should inspect the altar first.",
        action="inspect altar",
        is_stuck_or_bug=False,
        issue_description="",
    )

    async with TestSessionLocal() as db:
        user_res = await db.execute(select(User).limit(1))
        user = user_res.scalars().first()

        adv = AdventureTemplate(
            id="agent-run-test", owner_id=user.id, title="Agent Run Test", is_ready=True
        )
        db.add(adv)
        await db.commit()

        result = await start_session_for_template("agent-run-test", db, user)
        game_id = result["game_id"]

        # Enable agent
        state_res = await db.execute(select(SessionState).where(SessionState.session_id == game_id))
        state = state_res.scalars().first()
        AgentService.set_agent_active(state, True)
        await db.commit()
        await db.close()

        # Mock game loop execution so we don't trigger actual LLM logic for the room transition
        with patch(
            "backend.api.routes.adventures.gameplay_logic.GameTurnManager.process_turn"
        ) as mock_process:

            async def mock_generator(action):
                yield 'event: chunk\ndata: {"content": "You look at the stone altar."}\n\n'
                yield "event: final\ndata: {}\n\n"

            mock_process.return_value = mock_generator("inspect altar")

            response = await auth_client.post(f"/api/adventures/{game_id}/agent/turn")
            assert response.status_code == 200

            # Read SSE stream
            sse_content = response.text
            assert "event: thought" in sse_content
            assert "I should inspect the altar first" in sse_content
            assert "event: status" in sse_content
            assert "Agent decides: inspect altar" in sse_content
            assert "You look at the stone altar" in sse_content


@patch("backend.api.routes.adventures.agent_logic.AgentService.get_decision")
async def test_agent_turn_retry_and_deactivation_on_failure(
    mock_get_decision, auth_client, setup_test_db
):
    """Verifies three-attempt retry limit and logging issues to AGENTS.md."""
    from tests.conftest import TestSessionLocal

    mock_get_decision.return_value = AgentDecision(
        thoughts="The door is locked and the key is missing. Walkthrough says to use key, but it's not in my inventory.",
        action="unlock door",
        is_stuck_or_bug=True,
        issue_description="Walkthrough mismatch: missing required key.",
    )

    async with TestSessionLocal() as db:
        user_res = await db.execute(select(User).limit(1))
        user = user_res.scalars().first()

        adv = AdventureTemplate(
            id="agent-fail-test", owner_id=user.id, title="Agent Fail Test", is_ready=True
        )
        db.add(adv)
        await db.commit()

        result = await start_session_for_template("agent-fail-test", db, user)
        game_id = result["game_id"]

        # Enable agent
        state_res = await db.execute(select(SessionState).where(SessionState.session_id == game_id))
        state = state_res.scalars().first()
        AgentService.set_agent_active(state, True)
        await db.commit()
        await db.close()

        # Clean old issues log if exists
        session_dir = safe_data_path("adventures", "sessions", game_id)
        agents_md_path = ensure_within_data_dir(os.path.join(session_dir, "AGENTS.md"))
        if os.path.exists(agents_md_path):
            os.remove(agents_md_path)

        # Attempt 1
        resp1 = await auth_client.post(f"/api/adventures/{game_id}/agent/turn")
        print("RESP1 TEXT:", resp1.text)
        assert resp1.status_code == 200
        assert "(Attempt 1/3)" in resp1.text
        assert os.path.exists(agents_md_path)

        # Re-fetch and verify failure count using fresh verify DB session
        async with TestSessionLocal() as verify_db:
            state_res = await verify_db.execute(
                select(SessionState).where(SessionState.session_id == game_id)
            )
            state = state_res.scalars().first()
            print("VERIFY STATE AGENT STATE:", AgentService.get_agent_state(state))
            assert AgentService.get_agent_state(state).get("failure_count") == 1
            assert AgentService.get_agent_state(state).get("active") is True

        # Attempt 2
        resp2 = await auth_client.post(f"/api/adventures/{game_id}/agent/turn")
        assert "(Attempt 2/3)" in resp2.text

        # Attempt 3 - Should deactivate agent
        resp3 = await auth_client.post(f"/api/adventures/{game_id}/agent/turn")
        assert "(Attempt 3/3)" in resp3.text
        assert "Agent mode has been deactivated" in resp3.text

        async with TestSessionLocal() as verify_db:
            state_res = await verify_db.execute(
                select(SessionState).where(SessionState.session_id == game_id)
            )
            state = state_res.scalars().first()
            assert AgentService.get_agent_state(state).get("failure_count") == 3
            assert AgentService.get_agent_state(state).get("active") is False

        # Read AGENTS.md content to check format
        with open(agents_md_path, encoding="utf-8") as f:
            content = f.read()
            assert "# TaleWeaver Agent Issues Log" in content
            assert "Walkthrough mismatch: missing required key" in content


async def test_agent_prompt_includes_scene_items_and_take_name_guidance(setup_test_db, monkeypatch):
    """Agent prompt should list visible scene items and explain /take uses item names (no ID required)."""
    from tests.conftest import TestSessionLocal

    captured: dict[str, str] = {}

    class FakeLLM:
        async def aexecute_complex_task(self, **kwargs):
            captured["system_prompt"] = kwargs.get("system_prompt", "")
            return AgentDecision(
                thoughts="I'll pick up the key.",
                action="/take Ancient Key",
                is_stuck_or_bug=False,
                issue_description="",
            )

    async def fake_build_context(self, user_msg: str, language=None):
        _ = user_msg
        _ = language
        return SimpleNamespace(
            mechanics_system_prompt="Mechanics context",
            small_model_provider="ollama",
            small_model="llama3.2",
        )

    monkeypatch.setattr(
        "backend.api.routes.adventures.agent_logic.TurnLlmContextBuilder.build_context",
        fake_build_context,
    )
    monkeypatch.setattr(
        "backend.api.routes.adventures.agent_logic.GameMasterLLM", lambda *args, **kwargs: FakeLLM()
    )

    async with TestSessionLocal() as db:
        user = User(username="agent_items_user", hashed_password="hash", role="admin")
        db.add(user)
        await db.flush()

        adv = AdventureTemplate(
            id="agent-items-test", owner_id=user.id, title="Agent Items Test", is_ready=True
        )
        db.add(adv)
        await db.commit()

        result = await start_session_for_template("agent-items-test", db, user)
        game_id = result["game_id"]

        state_res = await db.execute(select(SessionState).where(SessionState.session_id == game_id))
        state = state_res.scalars().first()
        assert state is not None

        db.add(
            WorldEntity(
                id="ANCIENT_KEY",
                session_id=game_id,
                template_id=None,
                entity_type="OBJECT",
                name="Ancient Key",
                description="A weathered bronze key.",
                current_scene_id=state.current_scene_id,
                is_hidden=False,
                is_in_inventory=False,
                is_portable=True,
            )
        )
        await db.commit()

        manager = SimpleNamespace()
        avatar = await db.get(Avatar, state.avatar_id)
        assert avatar is not None
        decision = await AgentService.get_decision(db, game_id, user, state, avatar, adv, manager)
        _ = decision

    prompt = captured.get("system_prompt", "")
    assert "CURRENT SCENE ITEMS (VISIBLE NOW)" in prompt
    assert "Ancient Key" in prompt
    assert "Use `/take <item name>`" in prompt
    assert "Do NOT require or invent item IDs" in prompt
    assert "`/open <target>`" in prompt
    assert "`/read <target>`" in prompt
    assert "`/talk` and `/chat` are removed" in prompt
    assert "ALWAYS use `/say`" in prompt
    assert "`/search` or `/search <target>`" in prompt
    assert "`/lookaround` or `/look`" in prompt
    assert "`/push <target>` or `/pull <target>`" in prompt
    assert "`/rest`" in prompt
    assert "MODAL CONTENT MIRRORING" in prompt


async def test_agent_prompt_switches_to_monkey_mode_objective(setup_test_db, monkeypatch):
    """Agent prompt should include monkey mode objective block when enabled in session state."""
    from tests.conftest import TestSessionLocal

    captured: dict[str, str] = {}

    class FakeLLM:
        async def aexecute_complex_task(self, **kwargs):
            captured["system_prompt"] = kwargs.get("system_prompt", "")
            return AgentDecision(
                thoughts="Let's test weird inputs.",
                action="/foobar ???",
                is_stuck_or_bug=False,
                issue_description="",
            )

    async def fake_build_context(self, user_msg: str, language=None):
        _ = user_msg
        _ = language
        return SimpleNamespace(
            mechanics_system_prompt="Mechanics context",
            small_model_provider="ollama",
            small_model="llama3.2",
        )

    monkeypatch.setattr(
        "backend.api.routes.adventures.agent_logic.TurnLlmContextBuilder.build_context",
        fake_build_context,
    )
    monkeypatch.setattr(
        "backend.api.routes.adventures.agent_logic.GameMasterLLM", lambda *args, **kwargs: FakeLLM()
    )

    async with TestSessionLocal() as db:
        user = User(username="agent_monkey_user", hashed_password="hash", role="admin")
        db.add(user)
        await db.flush()

        adv = AdventureTemplate(
            id="agent-monkey-test", owner_id=user.id, title="Agent Monkey Test", is_ready=True
        )
        db.add(adv)
        await db.commit()

        result = await start_session_for_template("agent-monkey-test", db, user)
        game_id = result["game_id"]

        state_res = await db.execute(select(SessionState).where(SessionState.session_id == game_id))
        state = state_res.scalars().first()
        assert state is not None

        AgentService.set_monkey_mode(state, True)
        await db.commit()

        manager = SimpleNamespace()
        avatar = await db.get(Avatar, state.avatar_id)
        assert avatar is not None
        decision = await AgentService.get_decision(db, game_id, user, state, avatar, adv, manager)
        _ = decision

    prompt = captured.get("system_prompt", "")
    assert "MONKEY MODE (ROBUSTNESS TEST) IS ACTIVE" in prompt
    assert "intentionally trying edge cases and bad inputs" in prompt


def test_log_issue_does_not_create_unknown_session_folder(tmp_path, monkeypatch):
    """Agent issue logging must not create arbitrary session folders for invalid IDs."""
    from backend.api.routes.adventures.agent_logic import AgentService

    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))

    unknown_session_id = "agent-items-test-spurious"
    target_session_dir = tmp_path / "adventures" / "sessions" / unknown_session_id
    assert not target_session_dir.exists()

    AgentService.log_issue(
        unknown_session_id,
        thoughts="test thoughts",
        action="/say Hello",
        issue_description="test issue",
        history_summary="history",
    )

    assert not target_session_dir.exists()


async def test_agent_walkthrough_and_step_toggle_commands(auth_client, setup_test_db):
    """Verifies /agent walkthrough on/off and /agent step on/off commands update state."""
    from backend.api.routes.adventures.gameplay_logic import GameTurnManager
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user_res = await db.execute(select(User).limit(1))
        user = user_res.scalars().first()

        adv = AdventureTemplate(
            id="agent-walkthrough-test", owner_id=user.id, title="Walkthrough Test", is_ready=True
        )
        db.add(adv)
        await db.commit()

        result = await start_session_for_template("agent-walkthrough-test", db, user)
        game_id = result["game_id"]

        manager = GameTurnManager(db, game_id, user)
        assert await manager.initialize()

        # Turn walkthrough OFF
        chunks = []
        async for chunk in manager.process_turn("/agent walkthrough off"):
            chunks.append(chunk)

        async with TestSessionLocal() as verify_db:
            state_res = await verify_db.execute(
                select(SessionState).where(SessionState.session_id == game_id)
            )
            state = state_res.scalars().first()
            assert AgentService.get_agent_state(state).get("allow_walkthrough") is False

        assert "Sequence Walkthrough guidance disabled" in "".join(chunks)

        # Turn walkthrough ON
        chunks = []
        async for chunk in manager.process_turn("/agent walkthrough on"):
            chunks.append(chunk)

        async with TestSessionLocal() as verify_db:
            state_res = await verify_db.execute(
                select(SessionState).where(SessionState.session_id == game_id)
            )
            state = state_res.scalars().first()
            assert AgentService.get_agent_state(state).get("allow_walkthrough") is True

        assert "Sequence Walkthrough guidance enabled" in "".join(chunks)

        # Turn step-by-step ON
        chunks = []
        async for chunk in manager.process_turn("/agent step on"):
            chunks.append(chunk)

        async with TestSessionLocal() as verify_db:
            state_res = await verify_db.execute(
                select(SessionState).where(SessionState.session_id == game_id)
            )
            state = state_res.scalars().first()
            assert AgentService.get_agent_state(state).get("step_by_step") is True

        assert "Step-by-Step mode enabled" in "".join(chunks)

        # Turn step-by-step OFF
        chunks = []
        async for chunk in manager.process_turn("/agent step off"):
            chunks.append(chunk)

        async with TestSessionLocal() as verify_db:
            state_res = await verify_db.execute(
                select(SessionState).where(SessionState.session_id == game_id)
            )
            state = state_res.scalars().first()
            assert AgentService.get_agent_state(state).get("step_by_step") is False

        assert "Step-by-Step mode disabled" in "".join(chunks)


async def test_agent_on_uses_walkthrough_and_step_defaults_from_settings(
    auth_client, setup_test_db
):
    """/agent on should initialize walkthrough and step_by_step from persisted settings."""
    from backend.api.routes.adventures.gameplay_logic import GameTurnManager
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user_res = await db.execute(select(User).limit(1))
        user = user_res.scalars().first()
        user.llm_settings = {
            "play_agent_allow_walkthrough": False,
            "play_agent_step_by_step": True,
        }

        adv = AdventureTemplate(
            id="agent-defaults-test", owner_id=user.id, title="Agent Defaults Test", is_ready=True
        )
        db.add(adv)
        await db.commit()

        result = await start_session_for_template("agent-defaults-test", db, user)
        game_id = result["game_id"]

        manager = GameTurnManager(db, game_id, user)
        assert await manager.initialize()

        chunks = []
        async for chunk in manager.process_turn("/agent on"):
            chunks.append(chunk)

        async with TestSessionLocal() as verify_db:
            state_res = await verify_db.execute(
                select(SessionState).where(SessionState.session_id == game_id)
            )
            state = state_res.scalars().first()
            agent_st = AgentService.get_agent_state(state)
            assert agent_st.get("active") is True
            assert agent_st.get("allow_walkthrough") is False
            assert agent_st.get("step_by_step") is True

        full_output = "".join(chunks)
        assert "Sequence Walkthrough guidance is disabled (normal player mode)" in full_output
        assert "Step-by-Step confirmation mode is enabled" in full_output


@patch("backend.api.routes.adventures.agent_logic.AgentService.get_decision")
async def test_agent_step_command_executes_single_decision(
    mock_get_decision, auth_client, setup_test_db
):
    """Verifies /agent step triggers a single turn decision when agent is active."""
    from backend.api.routes.adventures.gameplay_logic import GameTurnManager
    from tests.conftest import TestSessionLocal

    mock_get_decision.return_value = AgentDecision(
        thoughts="Step-by-step: looking around first.",
        action="/lookaround",
        is_stuck_or_bug=False,
        issue_description="",
    )

    async with TestSessionLocal() as db:
        user_res = await db.execute(select(User).limit(1))
        user = user_res.scalars().first()

        adv = AdventureTemplate(
            id="agent-step-exec-test", owner_id=user.id, title="Agent Step Exec Test", is_ready=True
        )
        db.add(adv)
        await db.commit()

        result = await start_session_for_template("agent-step-exec-test", db, user)
        game_id = result["game_id"]

        manager = GameTurnManager(db, game_id, user)
        assert await manager.initialize()

        # Without agent active, /agent step should reject
        inactive_chunks = []
        async for chunk in manager.process_turn("/agent step"):
            inactive_chunks.append(chunk)
        assert "Agent mode is not active" in "".join(inactive_chunks)

        # Enable agent
        AgentService.set_agent_active(manager.state, True)
        AgentService.set_step_by_step(manager.state, True)
        await db.commit()

        # Now /agent step should execute the decision
        with patch.object(manager, "process_turn", wraps=manager.process_turn):
            step_chunks = []
            async for chunk in manager.process_turn("/agent step"):
                step_chunks.append(chunk)

            full_step_output = "".join(step_chunks)
            assert "event: thought" in full_step_output
            assert "Step-by-step: looking around first" in full_step_output
            assert "event: player_action" in full_step_output


async def test_agent_prompt_walkthrough_disabled_vs_enabled(setup_test_db, monkeypatch):
    """Verifies system prompt changes when walkthrough is disabled vs enabled."""
    from tests.conftest import TestSessionLocal

    captured: dict[str, str] = {}

    class FakeLLM:
        async def aexecute_complex_task(self, **kwargs):
            captured["system_prompt"] = kwargs.get("system_prompt", "")
            return AgentDecision(
                thoughts="Exploring naturally.",
                action="/inspect bookshelf",
                is_stuck_or_bug=False,
                issue_description="",
            )

    async def fake_build_context(self, user_msg: str, language=None):
        return SimpleNamespace(
            mechanics_system_prompt="Mechanics context",
            small_model_provider="ollama",
            small_model="llama3.2",
            entities=[],
            exits=[],
        )

    monkeypatch.setattr(
        "backend.api.routes.adventures.agent_logic.TurnLlmContextBuilder.build_context",
        fake_build_context,
    )
    monkeypatch.setattr(
        "backend.api.routes.adventures.agent_logic.GameMasterLLM", lambda *args, **kwargs: FakeLLM()
    )

    async with TestSessionLocal() as db:
        user = User(username="agent_walkthrough_user", hashed_password="hash", role="admin")
        db.add(user)
        await db.flush()

        adv = AdventureTemplate(
            id="agent-wt-prompt-test",
            owner_id=user.id,
            title="Walkthrough Prompt Test",
            is_ready=True,
            walkthrough="Secret spoiler: push the blue brick on the wall.",
        )
        db.add(adv)
        await db.commit()

        result = await start_session_for_template("agent-wt-prompt-test", db, user)
        game_id = result["game_id"]

        state_res = await db.execute(select(SessionState).where(SessionState.session_id == game_id))
        state = state_res.scalars().first()
        avatar = await db.get(Avatar, state.avatar_id)

        # Test 1: Walkthrough DISABLED
        AgentService.set_walkthrough_allowed(state, False)
        await db.commit()

        manager = SimpleNamespace()
        await AgentService.get_decision(db, game_id, user, state, avatar, adv, manager)

        prompt_disabled = captured.get("system_prompt", "")
        assert "WALKTHROUGH ACCESS: DISABLED" in prompt_disabled
        assert "Secret spoiler: push the blue brick" not in prompt_disabled
        assert (
            "play through the adventure autonomously as a regular player without walkthrough assistance"
            in prompt_disabled
        )

        # Test 2: Walkthrough ENABLED
        AgentService.set_walkthrough_allowed(state, True)
        await db.commit()

        await AgentService.get_decision(db, game_id, user, state, avatar, adv, manager)

        prompt_enabled = captured.get("system_prompt", "")
        assert "Secret spoiler: push the blue brick" in prompt_enabled
        assert "following the current sequence walkthrough step-by-step" in prompt_enabled


async def test_playagent_console_commands_toggle(auth_client, setup_test_db):
    """Verifies /playagent in-game console commands: activation, direct preset, and shutdown."""
    from backend.api.routes.adventures.gameplay_logic import GameTurnManager
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user_res = await db.execute(select(User).limit(1))
        user = user_res.scalars().first()

        adv = AdventureTemplate(
            id="playagent-cmd-test", owner_id=user.id, title="Playagent Command Test", is_ready=True
        )
        db.add(adv)
        await db.commit()

        result = await start_session_for_template("playagent-cmd-test", db, user)
        game_id = result["game_id"]

        manager = GameTurnManager(db, game_id, user)
        assert await manager.initialize()

        # 1. /playagent (bare command enables agent mode)
        chunks = []
        async for chunk in manager.process_turn("/playagent"):
            chunks.append(chunk)
        full_sse = "".join(chunks)
        assert "Autonomous Agent Gameplay Mode enabled" in full_sse

        async with TestSessionLocal() as verify_db:
            st = (await verify_db.execute(select(SessionState).where(SessionState.session_id == game_id))).scalars().first()
            agent_st = AgentService.get_agent_state(st)
            assert agent_st.get("active") is True

        # 2. /playagent powerplayer (direct activation / personality switch)
        chunks = []
        async for chunk in manager.process_turn("/playagent powerplayer"):
            chunks.append(chunk)
        full_sse = "".join(chunks)
        assert "Autonomous Agent Gameplay Mode enabled" in full_sse
        assert "Powerplayer" in full_sse

        async with TestSessionLocal() as verify_db:
            st = (await verify_db.execute(select(SessionState).where(SessionState.session_id == game_id))).scalars().first()
            agent_st = AgentService.get_agent_state(st)
            assert agent_st.get("personality") == "powerplayer"

        # 3. /playagent off
        chunks = []
        async for chunk in manager.process_turn("/playagent off"):
            chunks.append(chunk)
        full_sse = "".join(chunks)
        assert "Autonomous Agent Gameplay Mode disabled" in full_sse

        async with TestSessionLocal() as verify_db:
            st = (await verify_db.execute(select(SessionState).where(SessionState.session_id == game_id))).scalars().first()
            agent_st = AgentService.get_agent_state(st)
            assert agent_st.get("active") is False


async def test_playagent_console_commands_personality(auth_client, setup_test_db):
    """Verifies /playagent personality selection and custom instructions via console."""
    from backend.api.routes.adventures.gameplay_logic import GameTurnManager
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user_res = await db.execute(select(User).limit(1))
        user = user_res.scalars().first()

        adv = AdventureTemplate(
            id="playagent-personality-cmd-test", owner_id=user.id, title="Playagent Personality Cmd Test", is_ready=True
        )
        db.add(adv)
        await db.commit()

        result = await start_session_for_template("playagent-personality-cmd-test", db, user)
        game_id = result["game_id"]

        manager = GameTurnManager(db, game_id, user)
        assert await manager.initialize()

        # 1. /playagent personality buerokrat
        chunks = []
        async for chunk in manager.process_turn("/playagent personality buerokrat"):
            chunks.append(chunk)
        full_sse = "".join(chunks)
        assert "Play-Agent personality set to Bürokrat" in full_sse

        async with TestSessionLocal() as verify_db:
            st = (await verify_db.execute(select(SessionState).where(SessionState.session_id == game_id))).scalars().first()
            agent_st = AgentService.get_agent_state(st)
            assert agent_st.get("personality") == "buerokrat"

        # 2. /playagent personality custom Always talk in rhyme
        chunks = []
        async for chunk in manager.process_turn("/playagent personality custom Always talk in rhyme"):
            chunks.append(chunk)
        full_sse = "".join(chunks)
        assert "Play-Agent custom personality updated" in full_sse

        async with TestSessionLocal() as verify_db:
            st = (await verify_db.execute(select(SessionState).where(SessionState.session_id == game_id))).scalars().first()
            agent_st = AgentService.get_agent_state(st)
            assert agent_st.get("personality") == "custom"
            assert agent_st.get("custom_personality") == "Always talk in rhyme"


async def test_playagent_personalities_prompt_injection(setup_test_db, monkeypatch):
    """Verifies that each personality (Casual, Bürokrat, Powerplayer, Custom) is correctly injected into LLM prompt."""
    from tests.conftest import TestSessionLocal

    captured: dict[str, str] = {}

    class FakeLLM:
        async def aexecute_complex_task(self, **kwargs):
            captured["system_prompt"] = kwargs.get("system_prompt", "")
            return AgentDecision(
                thoughts="Testing personality.",
                action="/lookaround",
                is_stuck_or_bug=False,
                issue_description="",
            )

    async def fake_build_context(self, user_msg: str, language=None):
        return SimpleNamespace(
            mechanics_system_prompt="Mechanics context",
            small_model_provider="ollama",
            small_model="llama3.2",
            entities=[],
            exits=[],
        )

    monkeypatch.setattr(
        "backend.api.routes.adventures.agent_logic.TurnLlmContextBuilder.build_context",
        fake_build_context,
    )
    monkeypatch.setattr(
        "backend.api.routes.adventures.agent_logic.GameMasterLLM", lambda *args, **kwargs: FakeLLM()
    )

    async with TestSessionLocal() as db:
        user = User(username="agent_personality_user", hashed_password="hash", role="admin")
        db.add(user)
        await db.flush()

        adv = AdventureTemplate(
            id="agent-personality-test", owner_id=user.id, title="Personality Test", is_ready=True
        )
        db.add(adv)
        await db.commit()

        result = await start_session_for_template("agent-personality-test", db, user)
        game_id = result["game_id"]

        state_res = await db.execute(select(SessionState).where(SessionState.session_id == game_id))
        state = state_res.scalars().first()
        avatar = await db.get(Avatar, state.avatar_id)
        manager = SimpleNamespace()

        # Case 1: Casual
        AgentService.set_personality(state, "casual")
        await db.commit()
        await AgentService.get_decision(db, game_id, user, state, avatar, adv, manager)
        prompt = captured.get("system_prompt", "")
        assert "AGENT PERSONALITY: CASUAL" in prompt
        assert "Laid-back, curious, and easygoing" in prompt

        # Case 2: Bürokrat
        AgentService.set_personality(state, "buerokrat")
        await db.commit()
        await AgentService.get_decision(db, game_id, user, state, avatar, adv, manager)
        prompt = captured.get("system_prompt", "")
        assert "AGENT PERSONALITY: BÜROKRAT" in prompt
        assert "documentation, and proper protocol" in prompt

        # Case 3: Powerplayer
        AgentService.set_personality(state, "powerplayer")
        await db.commit()
        await AgentService.get_decision(db, game_id, user, state, avatar, adv, manager)
        prompt = captured.get("system_prompt", "")
        assert "AGENT PERSONALITY: POWERPLAYER" in prompt
        assert "Hyper-efficient min-maxer" in prompt

        # Case 4: Custom
        AgentService.set_personality(state, "custom", "Always speak like Sherlock Holmes.")
        await db.commit()
        await AgentService.get_decision(db, game_id, user, state, avatar, adv, manager)
        prompt = captured.get("system_prompt", "")
        assert "AGENT PERSONALITY: CUSTOM" in prompt
        assert "Always speak like Sherlock Holmes." in prompt
