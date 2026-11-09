"""Finishing the last sequence ends the adventure only when it has no win guard of its own."""

from types import SimpleNamespace

from backend.api.routes.adventures.out_of_turn_progress import last_sequence_ends_adventure

SEQUENCES = [{"id": "SEQ_1", "order": 1}, {"id": "SEQ_2", "order": 2}]


def _state(completed: list[str], win_guard: str = "") -> SimpleNamespace:
    script_vars = {f"__seq_completed_{seq_id}__": True for seq_id in completed}
    return SimpleNamespace(
        active_sequence_id=None,
        completed_guard_expression=win_guard,
        entity_states={"__script_vars__": script_vars},
        custom_variables={},
    )


def _adventure(win_guard: str = "") -> SimpleNamespace:
    return SimpleNamespace(sequences=SEQUENCES, completed_guard_expression=win_guard)


def test_all_sequences_done_without_win_guard_ends_the_adventure() -> None:
    # Act
    ends = last_sequence_ends_adventure(_adventure(), _state(["SEQ_1", "SEQ_2"]))

    # Assert
    assert ends is True


def test_win_guard_on_the_adventure_keeps_the_game_running() -> None:
    # Arrange: the showdown decides the win, not the last chapter
    adventure = _adventure("tw.vars.get('grandma_showdown_won', False)")

    # Act
    ends = last_sequence_ends_adventure(adventure, _state(["SEQ_1", "SEQ_2"]))

    # Assert
    assert ends is False


def test_open_sequence_never_ends_the_adventure() -> None:
    # Act
    ends = last_sequence_ends_adventure(_adventure(), _state(["SEQ_1"]))

    # Assert
    assert ends is False
