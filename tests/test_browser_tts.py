"""Browser speech: the free TTS provider that the player's browser speaks (no server audio)."""

from httpx import AsyncClient

from backend.core.api_keys import key_providers
from backend.core.models_config import TTS_PROVIDERS
from backend.engine.audio.browser_tts import is_browser_provider, uses_vocal_tags
from tests.conftest import TestSessionLocal
from tests.server_settings_helpers import seed_server_settings


async def _enable_browser_tts() -> None:
    async with TestSessionLocal() as session:
        await seed_server_settings(
            session, tts_settings={"enabled": True, "provider": "browser", "use_vocal_tags": True}
        )
        await session.commit()


def test_browser_provider_is_listed_and_needs_no_key():
    assert "browser" in {p["id"] for p in TTS_PROVIDERS}
    assert "browser" not in {p["id"] for p in key_providers()}
    assert is_browser_provider(" Browser ") is True


def test_browser_speech_never_asks_for_vocal_tags():
    assert uses_vocal_tags({"provider": "browser", "use_vocal_tags": True}) is False
    assert uses_vocal_tags({"provider": "google", "use_vocal_tags": True}) is True
    assert uses_vocal_tags({"provider": "google", "use_vocal_tags": False}) is False


async def test_server_creates_no_audio_for_browser_speech(auth_client: AsyncClient, setup_test_db):
    # Arrange
    await _enable_browser_tts()

    # Act
    generate = await auth_client.post("/api/tts/generate", json={"text": "Hello"})
    stream = await auth_client.post("/api/tts/stream", json={"text": "Hello"})

    # Assert
    assert generate.status_code == 409
    assert "browser" in generate.json()["detail"]
    assert stream.status_code == 409


async def test_connection_test_lets_the_client_play_the_sample(
    auth_client: AsyncClient, setup_test_db
):
    await _enable_browser_tts()

    resp = await auth_client.post("/api/tts/test-connection")

    assert resp.status_code == 200
    assert resp.json() == {"status": "success", "browser": True, "message": "Browser voice"}


def test_browser_voice_choice_is_cleaned_and_kept():
    from backend.api.routes.settings_normalization import normalize_tts_settings

    normalized = normalize_tts_settings(
        {
            "provider": "browser",
            "browser_voice": "  Microsoft Katja  Online ",
            "browser_character_voices": ["Hedda", "", "Hedda", "Google Deutsch", 5],
        }
    )

    assert normalized["browser_voice"] == "Microsoft Katja Online"
    assert normalized["browser_character_voices"] == ["Hedda", "Google Deutsch", "5"]
    assert normalize_tts_settings({"provider": "google"})["browser_character_voices"] == []


async def test_admin_saves_browser_voices(auth_client: AsyncClient, setup_test_db):
    payload = {
        "enabled": True,
        "provider": "browser",
        "browser_voice": "Microsoft Katja Online (Natural) - German",
        "browser_character_voices": ["Microsoft Hedda - German"],
    }

    resp = await auth_client.post("/api/settings/tts", json=payload)
    settings_resp = await auth_client.get("/api/settings")

    assert resp.status_code == 200
    tts = settings_resp.json()["tts_settings"]
    assert tts["browser_voice"] == "Microsoft Katja Online (Natural) - German"
    assert tts["browser_character_voices"] == ["Microsoft Hedda - German"]
