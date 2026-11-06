"""Pass 1 accepts notes that a model wrapped as objects instead of plain strings."""

from backend.engine.interaction.llm_intents import MechanicsIntent, to_game_event


def test_object_notes_are_reduced_to_their_text() -> None:
    # Arrange: shape returned by deepseek-v4.1-flash in a play-agent run
    payload = {
        "narrative_description": "You sit down.",
        "remember_notes": [{"type": "note", "content": "Alex entered SOCIAL_HALL."}, "Plain note"],
        "forget_notes": [{"text": "Old note"}],
    }

    # Act
    event = to_game_event(MechanicsIntent.model_validate(payload))

    # Assert
    assert event.remember_notes == ["Alex entered SOCIAL_HALL.", "Plain note"]
    assert event.forget_notes == ["Old note"]
