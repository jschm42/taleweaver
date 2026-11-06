from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from backend.api.routes.adventures.sequence_progress import (
    apply_sequence_changeset,
    evaluate_sequence_progress,
)
from backend.engine.scripting.context import GameContext
from backend.models.avatar import Avatar
from backend.models.session_state import SessionState


def test_dynamic_progression_mode_does_not_auto_advance():
    """In dynamic mode, completing a sequence awards XP and clears active sequence without advancing."""
    # Arrange
    sequences = [
        {
            "id": "SEQ_ENTRY",
            "order": 1,
            "title": "Orientation",
            "required_scene_id": "ROOM_A",
            "exp_reward": 30,
        },
        {
            "id": "SEQ_WORKSHOP",
            "order": 2,
            "title": "Workshop",
            "required_scene_id": "ROOM_B",
            "exp_reward": 50,
        },
    ]
    adventure = SimpleNamespace(
        id="adv_test",
        sequences=sequences,
        sequence_progression_mode="dynamic",
    )
    state = SessionState(
        session_id="sess_1",
        active_sequence_id="SEQ_ENTRY",
        active_sequence_order=1,
        current_scene_id="ROOM_A",
        entity_states={},
    )
    avatar = Avatar(id="av_1", exp=0)

    # Act
    messages = evaluate_sequence_progress(adventure, state, avatar)

    # Assert: Sequence completed, XP awarded
    assert any("Sequence completed: Orientation (+30 XP)" in m for m in messages)
    assert avatar.exp == 30

    # In dynamic mode: active sequence is None, not advanced to SEQ_WORKSHOP!
    assert state.active_sequence_id is None
    assert not getattr(state, "is_completed", False)

    # Also marked as completed in script vars
    script_vars = state.entity_states.get("__script_vars__", {})
    assert script_vars.get("__seq_completed_SEQ_ENTRY__") is True


def test_dynamic_progression_activation_scene_auto_unlock():
    """Entering a scene matching activation_scene_id activates the sequence when none is active."""
    # Arrange
    sequences = [
        {
            "id": "SEQ_WORKSHOP",
            "order": 2,
            "title": "Workshop",
            "activation_scene_id": "ROOM_B",
            "required_scene_id": "ROOM_B",
            "guard_expression": "tw.vars.get('crafted', False) == True",
            "exp_reward": 50,
        },
    ]
    adventure = SimpleNamespace(
        id="adv_test",
        sequences=sequences,
        sequence_progression_mode="dynamic",
    )
    state = SessionState(
        session_id="sess_1",
        active_sequence_id=None,
        active_sequence_order=0,
        current_scene_id="ROOM_A",
        entity_states={},
    )
    avatar = Avatar(id="av_1", exp=0)

    # Act: Moving to ROOM_B
    messages = evaluate_sequence_progress(adventure, state, avatar, new_scene_id="ROOM_B")

    # Assert: Sequence activated
    assert any("New Sequence unlocked: Workshop" in m for m in messages)
    assert state.active_sequence_id == "SEQ_WORKSHOP"


def test_dynamic_progression_scripting_proxy():
    """SequencesProxy behaves appropriately in dynamic mode."""
    # Arrange
    sequences = [
        {"id": "SEQ_A", "title": "Section A", "order": 1},
        {"id": "SEQ_B", "title": "Section B", "order": 2},
    ]
    ctx = GameContext(
        active_sequence_id=None,
        sequences=sequences,
        sequence_progression_mode="dynamic",
    )

    # Assert: Does not force fallback to sequences[0] in dynamic mode
    assert ctx.sequences.progression_mode == "dynamic"
    assert ctx.sequences.get_active_id() is None

    # Act: Start sequence B explicitly
    ctx.sequences.start("SEQ_B")
    assert ctx.sequences.get_active_id() == "SEQ_B"
    assert ctx.sequences.is_active("SEQ_B") is True

    # Act: Complete current sequence in dynamic mode (default advance=False)
    ctx.sequences.complete()
    assert ctx.changeset.sequence_completed is True
    assert ctx.changeset.sequence_advance is False
    assert ctx.sequences.get_active_id() is None


@pytest.mark.asyncio
async def test_apply_sequence_changeset_dynamic_mode():
    """apply_sequence_changeset clears active sequence instead of advancing in dynamic mode."""
    # Arrange
    sequences = [
        {"id": "SEQ_1", "title": "First", "order": 1, "exp_reward": 20},
        {"id": "SEQ_2", "title": "Second", "order": 2, "exp_reward": 40},
    ]
    adventure = SimpleNamespace(
        id="adv_dyn",
        sequences=sequences,
        sequence_progression_mode="dynamic",
    )
    state = SessionState(
        session_id="sess_dyn",
        active_sequence_id="SEQ_1",
        active_sequence_order=1,
        entity_states={},
    )
    avatar = Avatar(id="av_dyn", exp=0)

    ctx = GameContext(
        active_sequence_id="SEQ_1",
        sequences=sequences,
        sequence_progression_mode="dynamic",
    )
    ctx.sequences.complete()

    # Act
    saver = AsyncMock()
    messages = await apply_sequence_changeset(
        adventure, state, avatar, ctx.changeset, message_saver=saver
    )

    # Assert
    assert any("Sequence completed: First (+20 XP)" in m for m in messages)
    assert state.active_sequence_id is None
    assert state.active_sequence_order == 0
    assert not getattr(state, "is_completed", False)


def test_linear_final_sequence_completion_does_not_win_adventure():
    """In linear mode, completing the final sequence clears active sequence without marking adventure completed."""
    # Arrange
    sequences = [
        {
            "id": "SEQ_FINAL",
            "title": "Final Sequence",
            "order": 1,
            "required_scene_id": "THRONE_ROOM",
            "exp_reward": 100,
        },
    ]
    adventure = SimpleNamespace(
        id="adv_linear",
        sequences=sequences,
        sequence_progression_mode="linear",
    )
    state = SessionState(
        session_id="sess_lin",
        active_sequence_id="SEQ_FINAL",
        active_sequence_order=1,
        current_scene_id="THRONE_ROOM",
        entity_states={},
    )
    avatar = Avatar(id="av_lin", exp=0)

    # Act
    messages = evaluate_sequence_progress(adventure, state, avatar)

    # Assert: Sequence completed & XP awarded
    assert any("Sequence completed: Final Sequence (+100 XP)" in m for m in messages)
    assert avatar.exp == 100

    # The adventure is NOT won automatically
    assert not getattr(state, "is_completed", False)
    assert state.active_sequence_id is None
    assert state.active_sequence_order == 0


def test_tw_game_game_won_alias():
    """tw.game.game_won sets game_completed on changeset."""
    ctx = GameContext()
    ctx.game.game_won("Glorious Victory!")

    assert ctx.changeset.game_completed is True
    assert ctx.changeset.status_note == "Glorious Victory!"
