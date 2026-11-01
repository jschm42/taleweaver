"""Quests and awards complete when a script (not the logic pass) changed the state.

Regression: an ``on_interact`` console script set ``teleport_attempt`` to 3 after the turn had
already evaluated quests, so the guarded side-quest stayed open.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.api.routes.adventures.out_of_turn_progress import apply_out_of_turn_progress
from backend.api.routes.adventures.quest_completion import (
    announce_completed_quests,
    mark_quests_completed,
)

GUARD = "tw.vars.get('teleport_attempt', 0) >= 3"


def _quest(quest_id: str, guard: str = GUARD, status: str = "open") -> dict:
    return {
        "id": quest_id,
        "title": quest_id.title(),
        "description": "Teleport Unit Seven.",
        "goal": "",
        "exp_reward": 100,
        "status": status,
        "guard_expression": guard,
    }


def _manager(teleport_attempt: int) -> MagicMock:
    manager = MagicMock()
    manager.game_id = "sess-1"
    manager.state_applier = None
    manager.db = MagicMock()
    manager.db.add = MagicMock()
    manager.state = SimpleNamespace(
        session_id="sess-1",
        session=SimpleNamespace(status="active"),
        entity_states={"__script_vars__": {"teleport_attempt": teleport_attempt}},
        custom_variables={},
        quests=[_quest("QUEST_BEAM_UNIT_SEVEN")],
        current_scene_id="TELEPORT_LAB",
        exit_states={},
        in_game_time=0,
        active_sequence_id=None,
        is_completed=False,
        completed_guard_expression="",
        gameover_guard_expression="",
    )
    manager.avatar = SimpleNamespace(name="Alex", hp=50, mana=10, stamina=10, inventory=[], exp=0)
    manager.adventure = SimpleNamespace(
        id="adv-1",
        title="Test-Lab",
        sequences=[],
        completed_guard_expression="",
        gameover_guard_expression="",
        awards=[
            {
                "key": "AWARD_TELEPORT_TECHNICIAN",
                "title": "Teleport Technician",
                "description": "Third time lucky.",
                "tier": "silver",
                "requirement": "",
                "guard_expression": GUARD,
            }
        ],
    )
    manager.user = MagicMock()
    manager.user.earned_awards = []
    manager._build_script_context = AsyncMock(return_value=None)
    manager._save_chat_message = AsyncMock()
    manager._queue_checkpoint = MagicMock()
    manager._finalize_session = AsyncMock()
    return manager


@pytest.mark.asyncio
async def test_recheck_completes_quest_and_grants_award_set_by_script():
    # Arrange
    manager = _manager(teleport_attempt=3)

    # Act
    messages, status = await apply_out_of_turn_progress(manager)

    # Assert
    assert status is None
    assert manager.state.quests[0]["status"] == "completed"
    assert manager.avatar.exp == 100
    assert "Side-quest completed: Quest_Beam_Unit_Seven (+100 XP)" in messages
    assert any("Teleport Technician" in str(m) for m in messages)
    assert {a["key"] for a in manager.user.earned_awards} == {"AWARD_TELEPORT_TECHNICIAN"}


@pytest.mark.asyncio
async def test_recheck_leaves_unmet_quest_open():
    # Arrange
    manager = _manager(teleport_attempt=2)

    # Act
    messages, status = await apply_out_of_turn_progress(manager)

    # Assert
    assert messages == []
    assert status is None
    assert manager.state.quests[0]["status"] == "open"
    assert manager.user.earned_awards == []


@pytest.mark.asyncio
async def test_recheck_does_not_repeat_completed_quest():
    # Arrange
    manager = _manager(teleport_attempt=3)
    manager.state.quests = [_quest("QUEST_BEAM_UNIT_SEVEN", status="completed")]
    manager.adventure.awards = []

    # Act
    messages, _status = await apply_out_of_turn_progress(manager)

    # Assert
    assert messages == []
    assert manager.avatar.exp == 0


def test_mark_and_announce_quests():
    # Arrange
    state = SimpleNamespace(session_id="s", quests=[_quest("A"), _quest("B", status="completed")])
    owner = SimpleNamespace(
        state=state,
        avatar=SimpleNamespace(exp=5),
        db=MagicMock(),
        _queue_checkpoint=MagicMock(),
    )

    # Act
    changed = mark_quests_completed(state, ["A", "B", "A", "UNKNOWN"])
    messages = announce_completed_quests(owner, changed)

    # Assert
    assert [q["id"] for q in changed] == ["A"]
    assert [q["status"] for q in state.quests] == ["completed", "completed"]
    assert messages == ["Side-quest completed: A (+100 XP)"]
    assert owner.avatar.exp == 105
    owner._queue_checkpoint.assert_called_once()
    owner.db.add.assert_called_once()
