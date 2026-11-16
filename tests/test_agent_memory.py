"""Tests for Play-Agent persistent memory (``agent_memory.py``)."""

from __future__ import annotations

from backend.api.routes.adventures.agent_memory import (
    MAX_AGENT_MEMORIES,
    apply_memory_updates,
    format_memories,
    read_memories,
)
from backend.models.session_state import SessionState


def _state(memories: list[str] | None = None) -> SessionState:
    agent = {"memories": list(memories)} if memories is not None else {}
    return SessionState(entity_states={"__agent__": agent})


def test_apply_memory_updates_adds_deduplicates_and_formats():
    # Arrange
    state = _state(["Door code is 4711"])

    # Act
    notes = apply_memory_updates(
        state,
        remember=["door code is 4711", "  Already read:   Lab Log  ", ""],
    )

    # Assert
    assert notes == ["Door code is 4711", "Already read: Lab Log"]
    assert read_memories(state.entity_states["__agent__"]) == notes
    assert "- Door code is 4711" in format_memories(state.entity_states["__agent__"])


def test_apply_memory_updates_forgets_matching_notes_and_caps_size():
    # Arrange
    initial = [f"Note {i}" for i in range(MAX_AGENT_MEMORIES)]
    state = _state(initial)

    # Act
    notes = apply_memory_updates(
        state,
        remember=["Fresh clue: 9912"],
        forget=["note 0", "note 1"],
    )

    # Assert
    assert "Note 0" not in notes
    assert "Note 1" not in notes
    assert notes[-1] == "Fresh clue: 9912"
    assert len(notes) <= MAX_AGENT_MEMORIES
