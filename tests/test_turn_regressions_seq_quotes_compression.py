"""Regressions: sequence flags survive the turn, streamed quotes stay intact, compression batches."""

from types import SimpleNamespace

from backend.api.routes.adventures.entity_state_merge import merge_entity_states
from backend.api.routes.adventures.history_compression_window import messages_to_compress
from backend.core.llm_router import GameMasterLLM


def _turns(count: int) -> list[SimpleNamespace]:
    messages = []
    for n in range(1, count + 1):
        messages.append(SimpleNamespace(id=f"u{n}", role="user", content=f"Action {n}"))
        messages.append(SimpleNamespace(id=f"a{n}", role="assistant", content="Answer"))
    return messages


def test_merge_keeps_sequence_flag_written_during_the_turn() -> None:
    # Arrange: the applier copied the states, then sequence evaluation replaced __script_vars__
    base = {"__script_vars__": {"x": 1}, "NPC": {"hp": 5}}
    working = dict(base)
    working["NPC"] = {"hp": 3}
    current = dict(base)
    current["__script_vars__"] = {"x": 1, "__seq_completed_SEQ_HALL__": True}

    # Act
    merged = merge_entity_states(base, working, current)

    # Assert
    assert merged["__script_vars__"]["__seq_completed_SEQ_HALL__"] is True
    assert merged["NPC"] == {"hp": 3}


def test_merge_applies_keys_removed_from_the_working_copy() -> None:
    # Arrange
    base = {"GONE": {"a": 1}, "KEEP": {"b": 2}}
    working = {"KEEP": base["KEEP"]}

    # Act
    merged = merge_entity_states(base, working, dict(base))

    # Assert
    assert merged == {"KEEP": {"b": 2}}


def test_streamed_prefix_inside_a_quote_is_not_closed() -> None:
    # Arrange: the stream filter normalizes the first chunk before the quote is complete
    prefix = 'Vesper Glass: [gentle] "P'

    # Act
    normalized = GameMasterLLM.normalize_voice_tags(prefix)

    # Assert
    assert normalized == 'Vesper Glass: [gentle] "P'
    assert normalized + 'ip left."' == 'Vesper Glass: [gentle] "Pip left."'


def test_unquoted_dialogue_line_still_gets_quotes() -> None:
    # Act
    normalized = GameMasterLLM.normalize_voice_tags("Vesper Glass: [gentle] Pip left.")

    # Assert
    assert normalized == 'Vesper Glass: [gentle] "Pip left."'


def test_compression_waits_until_the_window_overflows() -> None:
    # Act
    selected = messages_to_compress(_turns(10), None, max_turns=10)

    # Assert
    assert selected == []


def test_compression_folds_half_the_window_at_once() -> None:
    # Act: 11 uncompressed turns with a window of 10 -> keep the newest 5
    selected = messages_to_compress(_turns(11), None, max_turns=10)

    # Assert
    assert [m.id for m in selected][-1] == "a6"
    assert len(selected) == 12


def test_compression_is_not_due_again_on_the_next_turn() -> None:
    # Arrange: turns 1-6 were compressed on the previous turn
    messages = _turns(12)

    # Act
    selected = messages_to_compress(messages, "a6", max_turns=10)

    # Assert
    assert selected == []


def test_dialog_choices_do_not_count_as_compression_turns() -> None:
    # Arrange: 10 typed turns, each followed by a dialog choice
    messages = []
    for n in range(1, 11):
        messages.append(SimpleNamespace(id=f"u{n}", role="user", content=f"Action {n}"))
        messages.append(SimpleNamespace(id=f"c{n}", role="user", content=f"[Choice] Option {n}"))
        messages.append(SimpleNamespace(id=f"a{n}", role="assistant", content="Answer"))

    # Act
    selected = messages_to_compress(messages, None, max_turns=10)

    # Assert
    assert selected == []
