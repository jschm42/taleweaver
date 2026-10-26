"""Tests for the global TTS settings normalization (auto-speak default, retired fields)."""

from backend.api.routes.settings_normalization import normalize_tts_settings


def test_auto_speak_is_on_by_default():
    # Arrange / Act
    settings = normalize_tts_settings({"provider": "elevenlabs"})

    # Assert
    assert settings["auto_speak"] is True


def test_auto_speak_off_is_kept():
    # Arrange / Act
    settings = normalize_tts_settings({"provider": "elevenlabs", "auto_speak": False})

    # Assert
    assert settings["auto_speak"] is False


def test_retired_text_chunking_setting_is_dropped():
    # Arrange / Act
    settings = normalize_tts_settings({"provider": "google", "use_text_chunking": True})

    # Assert
    assert "use_text_chunking" not in settings
