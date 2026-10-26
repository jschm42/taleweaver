"""Tests for deterministic NPC voice casting."""

from backend.core.tts_voices import GOOGLE_TTS_VOICE_CATALOG
from backend.engine.voice_casting import (
    CastingCandidate,
    cast_voices,
    infer_voice_gender,
)

_GENDER_BY_VOICE = {entry["name"]: entry.get("gender") for entry in GOOGLE_TTS_VOICE_CATALOG}


def test_infer_gender_from_description_wording():
    # Arrange / Act / Assert
    assert infer_voice_gender("A broad woman with a ledger tucked under her arm.") == "female"
    assert infer_voice_gender("He leans on his counter and adjusts his glasses.") == "male"
    assert infer_voice_gender("A robot made of rusted scrap.") is None


def test_cast_voices_matches_gender_and_avoids_narrator():
    # Arrange
    candidates = [
        CastingCandidate("BOSS", "A broad woman; she counts caps."),
        CastingCandidate("CLERK", "He wears glasses and fusses over his papers."),
    ]

    # Act
    voices = cast_voices(candidates, reserved=["Puck"])

    # Assert
    assert _GENDER_BY_VOICE[voices["BOSS"]] == "female"
    assert _GENDER_BY_VOICE[voices["CLERK"]] == "male"
    assert "Puck" not in voices.values()


def test_cast_voices_keeps_existing_voice_and_never_duplicates():
    # Arrange
    candidates = [CastingCandidate("GUARD", "He grunts.", "Charon")] + [
        CastingCandidate(f"NPC_{i}", "He nods.") for i in range(10)
    ]

    # Act
    voices = cast_voices(candidates)

    # Assert
    assert voices["GUARD"] == "Charon"
    assert len(set(voices.values())) == len(candidates)


def test_cast_voices_is_deterministic_and_ignores_unknown_voices():
    # Arrange
    candidates = [CastingCandidate("WITCH", "She cackles.", "NotAVoice")]

    # Act
    first = cast_voices(candidates)
    second = cast_voices(candidates)

    # Assert
    assert first == second
    assert first["WITCH"] != "NotAVoice"
