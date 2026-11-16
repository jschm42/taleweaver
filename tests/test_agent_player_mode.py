"""Play-agent as a regular player feature: XP-gated walkthrough, debug-only tools, full actions."""

from types import SimpleNamespace

import pytest
from sqlalchemy import select

from backend.api.routes.adventures.agent_access import (
    access_fields,
    is_blocked_command,
    uses_monkey_mode,
    uses_walkthrough,
)
from backend.api.routes.adventures.agent_actions import execute_agent_action
from backend.api.routes.adventures.agent_logic import AgentDecision, AgentService
from backend.api.routes.adventures.agent_party_view import format_companion, format_talents
from backend.api.routes.adventures.sessions import start_session_for_template
from backend.core.config import settings
from backend.engine.rules.walkthrough_unlocks import mark_revealed
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.session_state import SessionState
from backend.models.user import User

SPOILER = "Secret spoiler: push the blue brick on the wall."
SEQUENCES = [{"id": "SEQ_1", "order": 1, "title": "The Wall", "walkthrough": SPOILER}]


@pytest.fixture
def no_debug(monkeypatch):
    """Regular play: debug mode off for the server."""
    monkeypatch.setattr(settings, "TALEWEAVER_DEBUG_ENABLED", False)


def _fake_llm(monkeypatch, captured: dict[str, str]) -> None:
    class FakeLLM:
        async def aexecute_complex_task(self, **kwargs):
            captured["system_prompt"] = kwargs.get("system_prompt", "")
            return AgentDecision(
                thoughts="I should look closer.",
                action="/inspect wall",
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
        "backend.api.routes.adventures.agent_logic.GameMasterLLM", lambda *a, **k: FakeLLM()
    )


async def _start(db, template_id: str, username: str):
    user = User(username=username, hashed_password="hash", role="user")
    db.add(user)
    await db.flush()
    adv = AdventureTemplate(
        id=template_id, owner_id=user.id, title="Player Agent", is_ready=True, sequences=SEQUENCES
    )
    db.add(adv)
    await db.commit()
    result = await start_session_for_template(template_id, db, user)
    state_res = await db.execute(
        select(SessionState).where(SessionState.session_id == result["game_id"])
    )
    state = state_res.scalars().first()
    state.is_debug_enabled = False
    return user, adv, state


async def test_walkthrough_needs_xp_unlock_outside_debug(setup_test_db, monkeypatch, no_debug):
    from tests.conftest import TestSessionLocal

    captured: dict[str, str] = {}
    _fake_llm(monkeypatch, captured)

    async with TestSessionLocal() as db:
        user, adv, state = await _start(db, "agent-player-wt", "agent_player_wt")
        avatar = await db.get(Avatar, state.avatar_id)
        AgentService.set_walkthrough_allowed(state, True)
        await db.commit()

        # Act 1: chapter still sealed
        await AgentService.get_decision(
            db, state.session_id, user, state, avatar, adv, SimpleNamespace()
        )
        sealed_prompt = captured["system_prompt"]
        sealed_fields = access_fields(adv, state)

        # Act 2: the player unlocked the chapter with XP
        mark_revealed(state, "SEQ_1")
        await AgentService.get_decision(
            db, state.session_id, user, state, avatar, adv, SimpleNamespace()
        )
        unlocked_prompt = captured["system_prompt"]

    # Assert
    assert SPOILER not in sealed_prompt
    assert "WALKTHROUGH ACCESS: DISABLED" in sealed_prompt
    assert sealed_fields == {"agent_walkthrough_unlocked": False, "agent_debug_tools": False}
    assert SPOILER in unlocked_prompt


async def test_debug_session_always_gets_walkthrough(setup_test_db, no_debug):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        _, adv, state = await _start(db, "agent-player-dbg", "agent_player_dbg")
        state.is_debug_enabled = True
        agent_state = {"allow_walkthrough": True, "monkey_mode": True}

        assert uses_walkthrough(adv, state, agent_state) is True
        assert uses_monkey_mode(state, agent_state) is True
        assert uses_walkthrough(adv, state, {"allow_walkthrough": False}) is False


async def test_monkey_mode_is_debug_only(auth_client, setup_test_db, no_debug):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user = (await db.execute(select(User).limit(1))).scalars().first()
        db.add(
            AdventureTemplate(
                id="agent-player-monkey", owner_id=user.id, title="Monkey", is_ready=True
            )
        )
        await db.commit()
        game_id = (await start_session_for_template("agent-player-monkey", db, user))["game_id"]

    url = f"/api/adventures/{game_id}/agent/settings"
    resp = await auth_client.patch(url, json={"active": True, "monkey_mode": True})

    assert resp.status_code == 200
    body = resp.json()
    assert body["agent_monkey_mode"] is False
    assert body["agent_debug_tools"] is False
    assert uses_monkey_mode(SimpleNamespace(is_debug_enabled=False), {"monkey_mode": True}) is False


async def test_agent_never_plays_player_controls():
    manager = SimpleNamespace()

    outcome = await execute_agent_action(manager, "/walkthrough reveal")

    assert outcome.turn_command is None
    assert "player's own control" in (outcome.message or "")
    assert is_blocked_command("/playagent off") is True
    assert is_blocked_command("/talent Mind Reading") is False


def test_talents_block_lists_unlocked_talents_with_usage():
    avatar = SimpleNamespace(
        mana=5,
        stamina=50,
        stats={
            "talents": [
                {"id": "MIND", "name": "Mind Reading", "cost": 10, "target_type": "NPC"},
                {"id": "SECRET", "name": "Hidden Gift", "cost": 1},
            ],
            "unlocked_talents": ["MIND"],
            "talent_uses": {},
        },
    )

    text = format_talents(avatar)

    assert "Mind Reading" in text
    assert "target: npc" in text
    assert "NOT USABLE NOW" in text  # 5 mana < 10
    assert "Hidden Gift" not in text
    assert "/talent <name> | <target>" in text


def test_companion_block_lists_whereabouts_items_and_commands():
    sheet = {
        "name": "Bran",
        "hp": 30,
        "max_hp": 40,
        "present": False,
        "following": False,
        "is_defeated": False,
        "inventory": [{"name": "Rope"}],
        "equipment": {"MainHand": {"name": "Axe"}, "Head": None},
        "abilities": [{"name": "Bash", "enabled": True}],
    }

    text = format_companion(sheet)

    assert "Bran is NOT here" in text
    assert "Rope" in text
    assert "MainHand: Axe" in text
    assert "Bash (on)" in text
    assert "/companion follow" in text
    assert format_companion(None) == ""


async def test_dialogue_level_and_wait_for_tts_defaults(auth_client, setup_test_db):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user = (await db.execute(select(User).limit(1))).scalars().first()
        db.add(
            AdventureTemplate(id="agent-player-dlg", owner_id=user.id, title="Dlg", is_ready=True)
        )
        await db.commit()
        game_id = (await start_session_for_template("agent-player-dlg", db, user))["game_id"]
    url = f"/api/adventures/{game_id}/agent/settings"

    # Act / Assert: defaults on start
    body = (await auth_client.patch(url, json={"active": True})).json()
    assert body["agent_wait_for_tts"] is True
    assert body["agent_dialogue_level"] == "normal"

    # The player's choices stick, also when the agent is started again
    await auth_client.patch(url, json={"wait_for_tts": False, "dialogue_level": "Full roleplay"})
    await auth_client.patch(url, json={"active": False})
    body = (await auth_client.patch(url, json={"active": True})).json()
    assert body["agent_wait_for_tts"] is False
    assert body["agent_dialogue_level"] == "roleplay"

    bad = await auth_client.patch(url, json={"dialogue_level": "shouting"})
    assert bad.status_code == 400
    assert "dialogue level" in bad.json()["detail"]


async def test_dialogue_level_reaches_prompt_and_command(setup_test_db, monkeypatch):
    from backend.api.routes.adventures.agent_commands import resolve_playagent_message
    from tests.conftest import TestSessionLocal

    captured: dict[str, str] = {}
    _fake_llm(monkeypatch, captured)

    async with TestSessionLocal() as db:
        user, adv, state = await _start(db, "agent-player-dlg-prompt", "agent_player_dlg")
        avatar = await db.get(Avatar, state.avatar_id)
        manager = SimpleNamespace(state=state, adventure=adv, user=user)

        msg, changed = resolve_playagent_message(manager, "dialogue taciturn")
        await AgentService.get_decision(
            db, state.session_id, user, state, avatar, adv, SimpleNamespace()
        )
        usage, usage_changed = resolve_playagent_message(manager, "dialogue loud")

    assert changed is True
    assert "Taciturn" in msg
    assert "TACITURN" in captured["system_prompt"]
    assert usage_changed is False
    assert "roleplay" in usage


async def test_instruction_via_settings_and_chat_command(auth_client, setup_test_db, monkeypatch):
    from backend.api.routes.adventures.agent_commands import console_args, resolve_playagent_message
    from tests.conftest import TestSessionLocal

    captured: dict[str, str] = {}
    _fake_llm(monkeypatch, captured)

    async with TestSessionLocal() as db:
        user, adv, state = await _start(db, "agent-player-instr", "agent_player_instr")
        avatar = await db.get(Avatar, state.avatar_id)
        manager = SimpleNamespace(state=state, adventure=adv, user=user)

        # Act: /instruct <text> in the chat
        msg, changed = resolve_playagent_message(
            manager, console_args("/instruct", "Ask the  innkeeper about the girl")
        )
        await AgentService.get_decision(
            db, state.session_id, user, state, avatar, adv, SimpleNamespace()
        )
        cleared, _ = resolve_playagent_message(manager, console_args("/INSTRUCT", "clear"))

    # Assert
    assert changed is True
    assert 'instruction: "Ask the innkeeper about the girl"' in msg
    assert "Start the Play-Agent" in msg  # the agent is not running yet
    assert '"Ask the innkeeper about the girl"' in captured["system_prompt"]
    assert "PLAYER'S INSTRUCTION (TOP PRIORITY)" in captured["system_prompt"]
    assert "cleared" in cleared
    assert AgentService.get_agent_state(state)["instruction"] == ""


async def test_instruction_settings_endpoint_sets_and_clears(auth_client, setup_test_db):
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user = (await db.execute(select(User).limit(1))).scalars().first()
        db.add(
            AdventureTemplate(id="agent-player-instr2", owner_id=user.id, title="I", is_ready=True)
        )
        await db.commit()
        game_id = (await start_session_for_template("agent-player-instr2", db, user))["game_id"]
    url = f"/api/adventures/{game_id}/agent/settings"

    set_body = (await auth_client.patch(url, json={"instruction": "  Open the chest "})).json()
    clear_body = (await auth_client.patch(url, json={"instruction": ""})).json()

    assert set_body["agent_instruction"] == "Open the chest"
    assert clear_body["agent_instruction"] == ""


async def test_agent_turn_clears_instruction_when_done(auth_client, setup_test_db):
    from unittest.mock import patch

    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as db:
        user = (await db.execute(select(User).limit(1))).scalars().first()
        db.add(
            AdventureTemplate(id="agent-player-instr3", owner_id=user.id, title="I", is_ready=True)
        )
        await db.commit()
        game_id = (await start_session_for_template("agent-player-instr3", db, user))["game_id"]
        state = (
            (await db.execute(select(SessionState).where(SessionState.session_id == game_id)))
            .scalars()
            .first()
        )
        AgentService.set_agent_active(state, True)
        AgentService.set_instruction(state, "Inspect the altar")
        await db.commit()

    decision = AgentDecision(
        thoughts="The altar, as asked.",
        action="inspect altar",
        is_stuck_or_bug=False,
        issue_description="",
        instruction_done=True,
    )

    async def fake_turn(_action):
        yield "event: final\ndata: {}\n\n"

    with (
        patch(
            "backend.api.routes.adventures.agent_logic.AgentService.get_decision",
            return_value=decision,
        ),
        patch(
            "backend.api.routes.adventures.gameplay_logic.GameTurnManager.process_turn",
            side_effect=fake_turn,
        ),
    ):
        response = await auth_client.post(f"/api/adventures/{game_id}/agent/turn")

    assert response.status_code == 200
    async with TestSessionLocal() as db:
        state = (
            (await db.execute(select(SessionState).where(SessionState.session_id == game_id)))
            .scalars()
            .first()
        )
        assert AgentService.get_agent_state(state)["instruction"] == ""
