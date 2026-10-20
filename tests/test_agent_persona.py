from types import SimpleNamespace

import pytest
from sqlalchemy import select

from backend.api.routes.adventures.agent_logic import AgentDecision, AgentService
from backend.api.routes.adventures.agent_persona import format_protagonist_profile
from backend.api.routes.adventures.sessions import start_session_for_template
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.session_state import SessionState
from backend.models.user import User


def test_format_protagonist_profile_includes_all_fields():
    # Arrange
    avatar = SimpleNamespace(
        description="A retired  smuggler\nfrom the harbor.",
        character="Gruff, sarcastic, secretly kind.",
        goal="Find her lost brother.",
    )

    # Act
    profile = format_protagonist_profile(avatar)

    # Assert
    assert "Biography: A retired smuggler from the harbor." in profile
    assert "Personality & Traits: Gruff, sarcastic, secretly kind." in profile
    assert "Personal Goal: Find her lost brother." in profile


def test_format_protagonist_profile_fallback_when_empty():
    # Arrange
    avatar = SimpleNamespace(description=None, character="", goal="  ")

    # Act
    profile = format_protagonist_profile(avatar)

    # Assert
    assert profile.startswith("No biography provided.")


@pytest.mark.asyncio
async def test_agent_prompt_contains_protagonist_bio(setup_test_db, monkeypatch):
    from tests.conftest import TestSessionLocal

    # Arrange
    captured: dict[str, str] = {}

    class FakeLLM:
        async def aexecute_complex_task(self, **kwargs):
            captured["system_prompt"] = kwargs.get("system_prompt", "")
            return AgentDecision(
                thoughts="In character.",
                action="/look",
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
        user = User(username="agent_persona_user", hashed_password="hash", role="admin")
        db.add(user)
        await db.flush()
        adv = AdventureTemplate(
            id="agent-persona-test", owner_id=user.id, title="Persona Test", is_ready=True
        )
        db.add(adv)
        await db.commit()

        result = await start_session_for_template("agent-persona-test", db, user)
        game_id = result["game_id"]
        state_res = await db.execute(select(SessionState).where(SessionState.session_id == game_id))
        state = state_res.scalars().first()
        avatar = await db.get(Avatar, state.avatar_id)
        avatar.description = "Former court alchemist exiled for heresy."
        avatar.character = "Curious and arrogant."
        avatar.goal = "Clear her name."
        await db.commit()

        # Act
        await AgentService.get_decision(db, game_id, user, state, avatar, adv, SimpleNamespace())

    # Assert
    prompt = captured.get("system_prompt", "")
    assert "--- PROTAGONIST PROFILE (WHO YOU ARE) ---" in prompt
    assert "Biography: Former court alchemist exiled for heresy." in prompt
    assert "Personality & Traits: Curious and arrogant." in prompt
    assert "Personal Goal: Clear her name." in prompt
    assert "--- ROLE-PLAY RULES ---" in prompt
