"""Tests for the ElevenLabs voice list and deterministic NPC voice casting."""

import json

from backend.engine.audio import elevenlabs_voices
from backend.engine.audio.elevenlabs_voices import (
    load_voice_catalog,
    resolve_voice_reference,
    storable_voice_or_none,
)
from backend.engine.audio.voice_casting import (
    CastingCandidate,
    VoiceSetup,
    cast_npc_voices,
    cast_voices,
    infer_voice_gender,
)


def _voice(voice_id: str, name: str, gender):
    return {
        "id": voice_id,
        "name": name,
        "gender": gender,
        "age": "",
        "accent": "",
        "description": "",
        "good_for": [],
    }


NARRATOR = "N" * 20
VOICES = [
    _voice(NARRATOR, "Narrator", "male"),
    _voice("F" * 20, "Fiona", "female"),
    _voice("G" * 20, "Grace", "female"),
    _voice("M" * 20, "Marcus", "male"),
    _voice("O" * 20, "Otto", "male"),
]
_GENDER_BY_ID = {v["id"]: v["gender"] for v in VOICES}


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
    cast = cast_voices(candidates, VOICES, reserved=[NARRATOR])

    # Assert
    assert _GENDER_BY_ID[cast["BOSS"]] == "female"
    assert _GENDER_BY_ID[cast["CLERK"]] == "male"
    assert NARRATOR not in cast.values()


def test_cast_voices_keeps_listed_voice_and_avoids_duplicates():
    # Arrange
    candidates = [
        CastingCandidate("GUARD", "He grunts.", "M" * 20),
        CastingCandidate("SMITH", "He hammers."),
    ]

    # Act
    cast = cast_voices(candidates, VOICES, reserved=[NARRATOR])

    # Assert
    assert cast["GUARD"] == "M" * 20
    assert cast["SMITH"] == "O" * 20


def test_removed_voice_falls_back_to_narrator_voice():
    # Arrange
    candidates = [CastingCandidate("WITCH", "She cackles.", "X" * 20)]

    # Act
    cast = cast_voices(candidates, VOICES)

    # Assert
    assert cast["WITCH"] is None


def test_cast_voices_is_deterministic():
    # Arrange
    candidates = [CastingCandidate("WITCH", "She cackles.")]

    # Act / Assert
    assert cast_voices(candidates, VOICES) == cast_voices(candidates, VOICES)


def test_gemini_has_no_npc_voices():
    # Arrange
    setup = VoiceSetup("google", "Puck", [])

    # Act
    cast = cast_npc_voices(setup, [CastingCandidate("GUARD", "He grunts.", "M" * 20)])

    # Assert
    assert cast == {"GUARD": None}


def test_resolve_voice_reference_accepts_id_or_name():
    # Arrange / Act / Assert
    assert resolve_voice_reference("fiona", VOICES) == "F" * 20
    assert resolve_voice_reference("G" * 20, VOICES) == "G" * 20
    assert resolve_voice_reference("Nobody", VOICES) is None


def test_bundled_voice_list_is_valid():
    # Arrange
    raw = json.loads(elevenlabs_voices.BUNDLED_VOICE_LIST.read_text(encoding="utf-8"))

    # Act
    voices = load_voice_catalog()

    # Assert
    assert voices
    assert len(voices) == len(raw["voices"])
    assert len({v["id"] for v in voices}) == len(voices)


def test_data_dir_voice_list_overrides_bundled_list(tmp_path, monkeypatch):
    # Arrange
    from backend.core.config import settings

    override = tmp_path / "voices" / "elevenlabs_voices.json"
    override.parent.mkdir()
    override.write_text(
        json.dumps({"voices": [{"id": "A" * 20, "name": "Only"}, {"id": "bad", "name": "X"}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))

    # Act
    voices = load_voice_catalog()

    # Assert
    assert [v["name"] for v in voices] == ["Only"]


def test_custom_voice_is_always_used_and_not_given_to_others():
    # Arrange
    custom = "C" * 20
    candidates = [
        CastingCandidate("HERO", "He waits.", f"custom:{custom}"),
        CastingCandidate("SMITH", "He hammers."),
    ]

    # Act
    cast = cast_voices(candidates, VOICES)

    # Assert
    assert cast["HERO"] == custom
    assert cast["SMITH"] != custom


def test_storable_voice_accepts_list_and_custom_ids_only():
    # Arrange / Act / Assert
    assert storable_voice_or_none("M" * 20) == "M" * 20
    assert storable_voice_or_none(f"custom:{'C' * 20}") == f"custom:{'C' * 20}"
    assert storable_voice_or_none("custom:short") is None
    assert storable_voice_or_none("Waitress Betty") is None
    assert storable_voice_or_none("") is None


async def test_voice_metadata_includes_protagonist(auth_client):
    # Arrange
    from backend.api.routes.adventures.logic import AdventureLogic
    from backend.engine.audio.voice_casting import PROTAGONIST_VOICE_KEY
    from tests.conftest import TestSessionLocal
    from tests.test_adventures_api import _create_adventure

    ids = await _create_adventure(auth_client, "Voice Quest")

    # Act
    async with TestSessionLocal() as db:
        metadata = await AdventureLogic.get_npc_metadata(db, None, ids["game_id"])

    # Assert
    protagonist = metadata[PROTAGONIST_VOICE_KEY]
    assert protagonist["entity_type"] == "PROTAGONIST"
    assert protagonist["name"]
