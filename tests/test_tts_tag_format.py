"""Tests for the single audio-tag format ([lowercase tag]) sent to TTS providers."""

import pytest

from backend.engine.audio.tts_helpers import _convert_brackets_to_angles
from backend.engine.audio.tts_tag_format import (
    canonicalize_tags,
    prepare_elevenlabs_text,
    supports_audio_tags,
)

MIXED = '<breath> Steele looks. [Reluctantly] (sigh) She <break time="1s"/> nods (in a whisper).'


def test_canonicalize_unifies_angle_paren_and_square_tags():
    # Arrange / Act
    text = canonicalize_tags(MIXED)

    # Assert
    assert text == "[breath] Steele looks. [reluctantly] [sigh] She nods (in a whisper)."


def test_prose_in_parentheses_is_left_alone():
    # Arrange / Act / Assert
    assert (
        canonicalize_tags("He waits (as always) by the door.")
        == "He waits (as always) by the door."
    )


def test_elevenlabs_text_uses_elevenlabs_sound_names():
    # Arrange / Act
    text = prepare_elevenlabs_text(MIXED, "eleven_v4")

    # Assert
    assert text == "[exhales] Steele looks. [reluctantly] [sighs] She nods (in a whisper)."
    assert "<" not in text


@pytest.mark.parametrize("model", ["eleven_multilingual_v2", "eleven_flash_v2_5"])
def test_models_without_tag_support_get_no_tags(model):
    # Arrange / Act
    text = prepare_elevenlabs_text(MIXED, model)

    # Assert
    assert not supports_audio_tags(model)
    assert "[" not in text and "<" not in text


def test_disabled_tags_are_stripped_for_elevenlabs():
    # Arrange / Act / Assert
    assert prepare_elevenlabs_text("[sighs] Fine.", "eleven_v4", use_tags=False) == "Fine."


def test_gemini_gets_angle_brackets_from_canonical_tags():
    # Arrange / Act
    text = _convert_brackets_to_angles(canonicalize_tags("(sigh) Fine. <Laugh>"))

    # Assert
    assert text == "<sigh> Fine. <laugh>"
