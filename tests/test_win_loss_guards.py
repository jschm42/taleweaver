"""Unit tests for Win and Loss Deterministic Guards (completed_guard_expression & gameover_guard_expression)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.api.routes.adventures.turn_guardrails import TurnGuardrailEnforcer
from backend.api.routes.adventures.turn_state_applier import TurnStateApplier
from backend.engine.rule_engine import GameEvent


def _setup_mock_manager():
    mock_manager = MagicMock()
    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = []
    mock_res.scalars.return_value.first.return_value = None
    mock_manager.db = MagicMock()
    mock_manager.db.execute = AsyncMock(return_value=mock_res)
    mock_manager.db.flush = AsyncMock()
    mock_manager.db.add = MagicMock()

    mock_manager.game_id = "test_game"
    mock_manager.user = MagicMock()
    mock_manager.user.earned_awards = []

    mock_manager.state = MagicMock()
    mock_manager.state.session_id = "test_game"
    mock_manager.state.template_id = "test_adv"
    mock_manager.state.active_sequence_id = "SEQ_FINAL"
    mock_manager.state.is_completed = False
    mock_manager.state.entity_states = {}
    mock_manager.state.current_scene_id = "START_ROOM"
    mock_manager.state.quests = []
    mock_manager.state.custom_variables = {}
    mock_manager.state.completed_guard_expression = ""
    mock_manager.state.gameover_guard_expression = ""
    mock_manager.state.completed_condition = "You found the grail"
    mock_manager.state.gameover_condition = "You were consumed by shadow"

    mock_manager.avatar = MagicMock()
    mock_manager.avatar.hp = 100
    mock_manager.avatar.stamina = 100
    mock_manager.avatar.mana = 100
    mock_manager.avatar.inventory = []

    mock_manager.adventure = MagicMock()
    mock_manager.adventure.id = "test_adv"
    mock_manager.adventure.title = "Test Adventure"
    mock_manager.adventure.sequences = [
        {
            "id": "SEQ_FINAL",
            "order": 1,
            "title": "Final Sequence",
            "end_condition": "Find grail",
        }
    ]
    mock_manager.adventure.awards = []
    mock_manager.adventure.completed_guard_expression = ""
    mock_manager.adventure.gameover_guard_expression = ""

    mock_manager._save_chat_message = AsyncMock()
    mock_manager._collect_existing_item_ids = AsyncMock(return_value=set())
    mock_manager._apply_adventure_generator_tools = AsyncMock()
    mock_manager._queue_checkpoint = MagicMock()
    mock_manager._execute_inline_script = AsyncMock(return_value=[])

    return mock_manager


@pytest.mark.asyncio
async def test_loss_guard_blocks_hallucinated_game_over():
    """Verify that if gameover_guard_expression is unmet and HP > 0, hallucinated game_over is blocked."""
    manager = _setup_mock_manager()
    manager.state.gameover_guard_expression = "tw.vars.get('sanity', 100) <= 0"
    manager.state.custom_variables = {"sanity": 50}
    manager.avatar.hp = 80

    enforcer = TurnGuardrailEnforcer(manager)
    event = GameEvent(
        narrative_description="You succumb to absolute madness.",
        game_over=True,
    )

    violations = await enforcer._enforce_win_and_loss_guardrails(event)

    assert len(violations) == 1
    assert event.game_over is False
    assert "Blocked game over" in violations[0]


@pytest.mark.asyncio
async def test_loss_guard_triggers_game_over_when_condition_met():
    """Verify that when gameover_guard_expression is met, game_over is deterministically triggered."""
    manager = _setup_mock_manager()
    manager.state.gameover_guard_expression = "tw.vars.get('sanity', 100) <= 0"
    manager.state.custom_variables = {"sanity": 0}
    manager.avatar.hp = 80

    enforcer = TurnGuardrailEnforcer(manager)
    event = GameEvent(
        narrative_description="You stare into the abyss.",
        game_over=False,
    )

    await enforcer._enforce_win_and_loss_guardrails(event)

    assert event.game_over is True
    assert "Defeat condition met" in (event.status_note or "")


@pytest.mark.asyncio
async def test_win_guard_blocks_hallucinated_victory():
    """Verify that if completed_guard_expression is unmet, hallucinated victory is blocked."""
    manager = _setup_mock_manager()
    manager.state.completed_guard_expression = "tw.vars.get('grail_cleansed') == True"
    manager.state.custom_variables = {"grail_cleansed": False}

    enforcer = TurnGuardrailEnforcer(manager)
    event = GameEvent(
        narrative_description="You claim victory prematurely.",
        game_completed=True,
    )

    violations = await enforcer._enforce_win_and_loss_guardrails(event)

    assert len(violations) == 1
    assert event.game_completed is False
    assert "Blocked game completion" in violations[0]


@pytest.mark.asyncio
async def test_win_guard_triggers_victory_when_condition_met():
    """Verify that when completed_guard_expression is met, game_completed is deterministically triggered."""
    manager = _setup_mock_manager()
    manager.state.completed_guard_expression = "tw.vars.get('grail_cleansed') == True"
    manager.state.custom_variables = {"grail_cleansed": True}

    enforcer = TurnGuardrailEnforcer(manager)
    event = GameEvent(
        narrative_description="You cleanse the holy relic in the sacred spring.",
        game_completed=False,
    )

    await enforcer._enforce_win_and_loss_guardrails(event)

    assert event.game_completed is True
    assert "Victory condition met" in (event.status_note or "")


@pytest.mark.asyncio
async def test_win_guard_prevents_premature_final_sequence_completion():
    """Verify that final sequence completion does not trigger victory if completed_guard_expression is unsatisfied."""
    manager = _setup_mock_manager()
    manager.state.completed_guard_expression = "tw.vars.get('boss_slain') == True"
    manager.state.custom_variables = {"boss_slain": False}
    manager.state.is_completed = True

    applier = TurnStateApplier(manager)
    event = GameEvent(
        narrative_description="You finish the sequence walkthrough.",
        sequence_completed=True,
    )

    await applier._apply_game_event(event)

    assert event.game_completed is False
