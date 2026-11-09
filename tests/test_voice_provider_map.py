"""Tests for the per-provider voice mapping of the voice list (Google / OpenAI-compatible voices)."""

import json

import pytest
from httpx import AsyncClient

from backend.core.security import encryption_util
from backend.engine.audio.speaker_voice import NarratorVoices, resolve_speaker_voices
from backend.engine.audio.voice_casting import CastingCandidate, VoiceSetup, cast_npc_voices
from backend.engine.audio.voice_map_transfer import (
    export_csv,
    export_json,
    merge_import,
    parse_import,
)
from backend.engine.audio.voice_provider_map import (
    VoiceMapError,
    build_voice_map,
    clean_provider_voice,
    effective_voice_map,
    normalize_voice_map,
    provider_voice,
    supports_character_voices,
    voices_sounding_like,
)
from tests.conftest import TestSessionLocal
from tests.server_settings_helpers import seed_server_settings

ARIA = "9BWtsMINqrJLrRacOk9x"
ROGER = "CwhRBWXzGAHq8TQ4Fs17"


def _row(voice_id: str, name: str, google: str = "", compatible: str = "") -> dict:
    return {
        "id": voice_id,
        "name": name,
        "description": "",
        "elevenlabs": voice_id,
        "google": google,
        "custom_openai": compatible,
    }


async def _seed_tts(provider: str, voice_map: dict, **tts: object) -> None:
    tts_settings = {
        "enabled": True,
        "provider": provider,
        "selected_model": "gemini-3.8-flash-tts",
        "selected_voice": "Puck",
        "use_vocal_tags": True,
        "elevenlabs_voice_id": "",
        **tts,
    }
    async with TestSessionLocal() as session:
        await seed_server_settings(
            session,
            tts_settings=tts_settings,
            encrypted_api_keys={"google": encryption_util.encrypt_key("test-key")},
            voice_provider_map=voice_map,
        )
        await session.commit()


def _capture_speech(monkeypatch) -> dict:
    captured: dict = {}

    async def fake_generate_speech(**kwargs):
        captured.update(kwargs)
        return "/data/audio/test.wav"

    monkeypatch.setattr(
        "backend.api.routes.tts_api.TTSEngine.generate_speech", fake_generate_speech
    )
    return captured


def test_google_cells_must_name_a_google_voice():
    # Act / Assert
    assert clean_provider_voice("google", " kore ") == "Kore"
    assert clean_provider_voice("google", "") == ""
    with pytest.raises(VoiceMapError):
        clean_provider_voice("google", "NotAVoice")


def test_normalize_drops_invalid_ids_and_empty_cells():
    # Arrange
    raw = {ARIA: {"google": "Kore", "custom_openai": "", "other": "x"}, "bad": {"google": "Kore"}}

    # Act
    cleaned = normalize_voice_map(raw)

    # Assert
    assert cleaned == {ARIA: {"google": "Kore"}}


def test_provider_voice_falls_back_to_narrator_when_unmapped():
    # Arrange
    voice_map = {ARIA: {"google": "Kore"}}

    # Act / Assert
    assert provider_voice(voice_map, "google", ARIA) == "Kore"
    assert provider_voice(voice_map, "google", ROGER) is None
    assert provider_voice(voice_map, "custom_openai", ARIA) is None
    assert provider_voice(voice_map, "elevenlabs", ARIA) == ARIA
    assert supports_character_voices("google", voice_map) is True
    assert supports_character_voices("custom_openai", voice_map) is False


def test_suggestions_apply_until_a_mapping_is_saved():
    # Arrange
    voices = [
        {"id": ARIA, "name": "Aria", "google_voice": "pulcherrima", "openai_compatible_voice": ""}
    ]

    # Act / Assert
    assert effective_voice_map(None, voices) == {ARIA: {"google": "Pulcherrima"}}
    assert effective_voice_map({}, voices) == {}


def test_bundled_suggestions_are_valid_google_voices_and_avoid_the_default_narrator():
    # Arrange
    from backend.engine.audio.elevenlabs_voices import load_voice_catalog

    voices = load_voice_catalog()

    # Act
    suggested = effective_voice_map(None, voices)

    # Assert
    assert len(suggested) == len(voices)
    assert all(entry["google"] != "Puck" for entry in suggested.values())


def test_build_voice_map_reports_unknown_rows_and_rejects_invalid_cells():
    # Arrange
    rows = [_row(ARIA, "Aria", google="Kore"), _row("X" * 20, "Ghost", google="Puck")]

    # Act
    voice_map, unknown = build_voice_map(rows, {ARIA})

    # Assert
    assert voice_map == {ARIA: {"google": "Kore"}}
    assert unknown == ["X" * 20]
    with pytest.raises(VoiceMapError, match="Aria"):
        build_voice_map([_row(ARIA, "Aria", google="Nope")], {ARIA})


def test_speaker_voices_use_mapped_voice_or_narrator():
    # Arrange
    narrator = NarratorVoices("Puck", "N" * 20)
    voice_map = {ARIA: {"google": "Kore"}}

    # Act
    mapped = resolve_speaker_voices("google", narrator, voice_map, ARIA)
    unmapped = resolve_speaker_voices("google", narrator, voice_map, ROGER)

    # Assert
    assert mapped.voice == "Kore"
    assert unmapped.voice == "Puck"
    assert mapped.elevenlabs_voice_id == "N" * 20


def test_csv_round_trip_keeps_cells_and_names_with_commas():
    # Arrange
    table = [_row(ARIA, "Valf - Young, Playful", google="Kore", compatible="af_heart")]
    empty = [_row(ARIA, "Valf - Young, Playful")]

    # Act
    result = merge_import(empty, parse_import(export_csv(table), "csv"))

    # Assert
    assert result.matched == 1
    assert result.rows[0]["google"] == "Kore"
    assert result.rows[0]["custom_openai"] == "af_heart"


def test_import_matches_by_name_accepts_semicolons_and_lists_problems():
    # Arrange
    table = [_row(ARIA, "Aria"), _row(ROGER, "Roger", google="Charon")]
    content = (
        "name;elevenlabs_id;google_voice;openai_compatible_voice\n"
        "aria;;Kore;af_bella\nRoger;;Bogus;\nNobody;;Puck;\n"
    )

    # Act
    result = merge_import(table, parse_import(content, "csv"))

    # Assert
    assert result.rows[0]["google"] == "Kore"
    assert result.rows[0]["custom_openai"] == "af_bella"
    assert result.rows[1]["google"] == "Charon"
    assert result.unknown == ["Nobody"]
    assert len(result.errors) == 1


def test_json_round_trip():
    # Arrange
    table = [_row(ARIA, "Aria", compatible="nova")]

    # Act
    content = export_json(table)
    result = merge_import([_row(ARIA, "Aria")], parse_import(content, "json"))

    # Assert
    assert json.loads(content)["voices"][0]["openai_compatible_voice"] == "nova"
    assert result.rows[0]["custom_openai"] == "nova"


def test_casting_works_for_google_and_skips_voices_mapped_to_the_narrator():
    # Arrange
    voices = [
        {
            "id": ARIA,
            "name": "Aria",
            "gender": "female",
            "age": "",
            "accent": "",
            "description": "",
            "good_for": [],
        },
        {
            "id": "S" * 20,
            "name": "Sarah",
            "gender": "female",
            "age": "",
            "accent": "",
            "description": "",
            "good_for": [],
        },
    ]
    reserved = tuple(voices_sounding_like({ARIA: {"google": "Kore"}}, "google", "kore"))
    setup = VoiceSetup("google", "Kore", voices, reserved)

    # Act
    cast = cast_npc_voices(setup, [CastingCandidate("INNKEEPER", "She wipes the bar.")])

    # Assert
    assert reserved == (ARIA,)
    assert cast == {"INNKEEPER": "S" * 20}


@pytest.mark.asyncio
async def test_google_speaks_the_mapped_voice(auth_client: AsyncClient, monkeypatch):
    # Arrange
    await _seed_tts("google", {ARIA: {"google": "Kore"}})
    captured = _capture_speech(monkeypatch)

    # Act
    mapped = await auth_client.post(
        "/api/tts/generate", json={"text": "Hi", "voice_override": ARIA}
    )
    mapped_voice = captured["voice"]
    unmapped = await auth_client.post(
        "/api/tts/generate", json={"text": "Hi", "voice_override": ROGER}
    )

    # Assert
    assert mapped.status_code == unmapped.status_code == 200
    assert mapped_voice == "Kore"
    assert captured["voice"] == "Puck"


@pytest.mark.asyncio
async def test_openai_compatible_speaks_the_mapped_voice(auth_client: AsyncClient, monkeypatch):
    # Arrange
    await _seed_tts(
        "custom_openai",
        {ARIA: {"custom_openai": "af_bella"}},
        selected_model="kokoro",
        custom_openai_url="http://localhost:8880/v1",
        custom_openai_voice="af_heart",
    )
    captured = _capture_speech(monkeypatch)

    # Act
    mapped = await auth_client.post(
        "/api/tts/generate", json={"text": "Hi", "voice_override": ARIA}
    )
    mapped_voice = captured["speech_endpoint"].voice
    await auth_client.post("/api/tts/generate", json={"text": "Hi", "voice_override": ROGER})

    # Assert
    assert mapped.status_code == 200
    assert mapped_voice == "af_bella"
    assert captured["speech_endpoint"].voice == "af_heart"


@pytest.mark.asyncio
async def test_admin_saves_imports_and_exports_the_table(auth_client: AsyncClient):
    # Arrange
    await _seed_tts("google", {})

    # Act
    saved = await auth_client.put(
        "/api/settings/voice-map", json={"items": [{"id": ARIA, "google": "kore"}]}
    )
    rejected = await auth_client.put(
        "/api/settings/voice-map", json={"items": [{"id": ARIA, "google": "nope"}]}
    )
    table = (await auth_client.get("/api/settings/voice-map")).json()
    exported = (
        await auth_client.post("/api/settings/voice-map/export", json={"format": "csv"})
    ).json()
    imported = (
        await auth_client.post(
            "/api/settings/voice-map/import",
            json={"format": "csv", "content": "name,google_voice\nRoger,Charon\n"},
        )
    ).json()
    voices = (await auth_client.get("/api/tts/voices")).json()

    # Assert
    assert saved.status_code == 200
    assert rejected.status_code == 400
    assert next(r for r in table["items"] if r["id"] == ARIA)["google"] == "Kore"
    assert table["google_voices"]
    assert exported["filename"].endswith(".csv")
    assert "Kore" in exported["content"]
    assert next(r for r in imported["items"] if r["id"] == ROGER)["google"] == "Charon"
    assert imported["matched"] == 1
    assert voices["supports_npc_voices"] is True
    assert voices["provider_voices"] == {ARIA: "Kore"}
