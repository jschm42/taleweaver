"""Tests for the anti-AI-tell prose rules of the narration prompt."""

from backend.core import prompts
from backend.core.narration_styles import narration_style_rules
from backend.core.narrator_voices import narrator_voice_rules
from backend.core.prose_craft import PROSE_CRAFT_RULES

EM_DASH = "—"


def test_prose_rules_forbid_dashes_and_contrast_cadence():
    # Arrange / Act
    rules = PROSE_CRAFT_RULES

    # Assert
    assert "dash punctuation" in rules
    assert "not X, but Y" in rules
    assert "every response language" in rules


def test_narration_prompt_parts_do_not_model_em_dashes():
    # Arrange: models mirror the punctuation of their instructions
    parts = [
        prompts.GM_NARRATION_MANDATORY_FORMATTING,
        prompts.GM_NARRATION_TURN_CONTRACT,
        prompts.GM_CHAT_NARRATION_SUFFIX,
        prompts.get_vocal_direction_prompt(),
        *(
            narration_style_rules(style)
            for style in ("terse", "dialogue", "balanced", "rich", "epic")
        ),
        narrator_voice_rules({"name": "Noir", "instruction": "Narrate dry."}),
    ]

    # Act
    offenders = [part[:60] for part in parts if EM_DASH in part]

    # Assert
    assert offenders == []
