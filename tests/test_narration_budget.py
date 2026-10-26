"""Tests for the per-turn narration budget check (narrator prose vs. character dialogue)."""

from unittest.mock import patch

from backend.core.narration_budget import (
    budget_violations,
    log_narration_budget,
    measure_narration,
)

SCRIPT_TURN = (
    "The boss counts caps into Nate's palm.\n\n"
    'Caravan Boss: [warmly] "Not a cap short, soldier."\n\n'
    'Dispatch Clerk: [hesitant] "Is that a Pip-Boy? Which vault is it from?"\n\n'
    'Guard: "Here we go again."\n'
)

PROSE_TURN = (
    "The late sun leans across the yard. Dust hangs in the air. Hands pull packs off the brahmin.\n\n"
    "The air smells of warm hide and cooking fat drifting in from the market nearby.\n\n"
    "A guard flips through a delivery slip and frowns at a dented crate by the trough.\n\n"
    'Guard: "Two cases short."\n'
)


def test_measure_separates_beats_from_dialogue_lines():
    # Arrange / Act
    metrics = measure_narration(SCRIPT_TURN)

    # Assert
    assert metrics.narration_beats == 1
    assert metrics.dialogue_lines == 3
    assert metrics.longest_beat_sentences == 1
    assert metrics.narration_ratio < 0.34


def test_script_turn_fits_dialogue_budget():
    # Arrange
    metrics = measure_narration(SCRIPT_TURN)

    # Act
    violations = budget_violations(metrics, "dialogue")

    # Assert
    assert violations == []


def test_prose_heavy_turn_breaks_dialogue_budget():
    # Arrange
    metrics = measure_narration(PROSE_TURN)

    # Act
    violations = budget_violations(metrics, "dialogue")

    # Assert
    assert "narration_ratio" in violations
    assert "beat_length" in violations


def test_turn_without_dialogue_does_not_break_ratio():
    # Arrange
    metrics = measure_narration("The cellar is empty and silent.")

    # Act
    violations = budget_violations(metrics, "dialogue")

    # Assert
    assert "narration_ratio" not in violations


def test_narrator_label_is_reported_as_leak():
    # Arrange
    text = 'Narrator:\n\nThe caravan boss counts out caps.\n\nCaravan Boss: "There\'s your pay."\n'

    # Act
    metrics = measure_narration(text)

    # Assert
    assert metrics.leaked_narrator_labels == 1
    assert metrics.narration_beats == 1
    assert "narrator_label" in budget_violations(metrics, "balanced")


def test_log_narration_budget_emits_telemetry_event():
    # Arrange
    with patch("backend.core.narration_budget.log_structured_event") as log_event:
        # Act
        violations = log_narration_budget(SCRIPT_TURN, "unknown-style", game_id="g1")

    # Assert
    assert violations == []
    event_type = log_event.call_args.args[0]
    fields = log_event.call_args.kwargs
    assert event_type == "gm.turn.narration_budget"
    assert fields["narration_style"] == "dialogue"
    assert fields["dialogue_lines"] == 3
    assert fields["game_id"] == "g1"
