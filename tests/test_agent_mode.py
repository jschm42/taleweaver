import os
from types import SimpleNamespace
import json
import pytest
from unittest.mock import patch, AsyncMock
from sqlalchemy import select

from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.user import User
from backend.models.session_state import SessionState
from backend.models.world_entity import WorldEntity
from backend.api.routes.adventures.sessions import start_session_for_template
from backend.api.routes.adventures.agent_logic import AgentService, AgentDecision
from backend.core.config import settings
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
            state_res = await verify_db.execute(select(SessionState).where(SessionState.session_id == game_id))
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
            state_res = await verify_db.execute(select(SessionState).where(SessionState.session_id == game_id))
            state = state_res.scalars().first()
            assert AgentService.get_agent_state(state).get("active") is False
            
        assert '"agent_active":false' in "".join(chunks).replace(" ", "")

        # Toggle monkey mode ON/OFF via slash command
        chunks = []
        async for chunk in manager.process_turn("/agent monkey on"):
            chunks.append(chunk)

        async with TestSessionLocal() as verify_db:
            state_res = await verify_db.execute(select(SessionState).where(SessionState.session_id == game_id))
            state = state_res.scalars().first()
            assert AgentService.get_agent_state(state).get("monkey_mode") is True

        assert '"agent_monkey_mode":true' in "".join(chunks).replace(" ", "")
        assert "Monkey Mode enabled" in "".join(chunks)

        chunks = []
        async for chunk in manager.process_turn("/agent monkey off"):
            chunks.append(chunk)

        async with TestSessionLocal() as verify_db:
            state_res = await verify_db.execute(select(SessionState).where(SessionState.session_id == game_id))
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
            id="agent-monkey-default-test", owner_id=user.id, title="Agent Monkey Default Test", is_ready=True
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
            state_res = await verify_db.execute(select(SessionState).where(SessionState.session_id == game_id))
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
        issue_description=""
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
        with patch("backend.api.routes.adventures.gameplay_logic.GameTurnManager.process_turn") as mock_process:
            async def mock_generator(action):
                yield "event: chunk\ndata: {\"content\": \"You look at the stone altar.\"}\n\n"
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
async def test_agent_turn_retry_and_deactivation_on_failure(mock_get_decision, auth_client, setup_test_db):
    """Verifies three-attempt retry limit and logging issues to AGENTS.md."""
    from tests.conftest import TestSessionLocal

    mock_get_decision.return_value = AgentDecision(
        thoughts="The door is locked and the key is missing. Walkthrough says to use key, but it's not in my inventory.",
        action="unlock door",
        is_stuck_or_bug=True,
        issue_description="Walkthrough mismatch: missing required key."
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
            state_res = await verify_db.execute(select(SessionState).where(SessionState.session_id == game_id))
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
            state_res = await verify_db.execute(select(SessionState).where(SessionState.session_id == game_id))
            state = state_res.scalars().first()
            assert AgentService.get_agent_state(state).get("failure_count") == 3
            assert AgentService.get_agent_state(state).get("active") is False

        # Read AGENTS.md content to check format
        with open(agents_md_path, "r", encoding="utf-8") as f:
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

    monkeypatch.setattr("backend.api.routes.adventures.agent_logic.TurnLlmContextBuilder.build_context", fake_build_context)
    monkeypatch.setattr("backend.api.routes.adventures.agent_logic.GameMasterLLM", lambda *args, **kwargs: FakeLLM())

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

    monkeypatch.setattr("backend.api.routes.adventures.agent_logic.TurnLlmContextBuilder.build_context", fake_build_context)
    monkeypatch.setattr("backend.api.routes.adventures.agent_logic.GameMasterLLM", lambda *args, **kwargs: FakeLLM())

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
