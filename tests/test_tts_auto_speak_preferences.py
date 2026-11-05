"""Tests for per-player Auto-Speak preferences and the session state settings helper."""

from unittest.mock import patch

from backend.api.routes.adventures import session_state_settings
from backend.api.routes.adventures.session_state_settings import apply_state_settings
from backend.core.tts_preferences import (
    DEFAULT_TTS_PREFERENCES,
    TTS_AUTO_SPEAK_KEY,
    TTS_PREFERENCES_KEY,
    resolve_tts_preferences,
    with_user_scoped_settings,
)
from backend.models.session_state import SessionState
from backend.schemas.session import GameSessionUpdate


def test_default_auto_speak_settings():
    # Arrange / Act
    defaults = DEFAULT_TTS_PREFERENCES

    # Assert
    assert defaults == {
        "enabled": True,
        "gm": True,
        "protagonist": True,
        "npcs": True,
        "system": False,
        "readables": True,
    }


def test_resolve_tts_preferences_defaults():
    # Arrange
    inputs = [None, {}, {"theme": "dark"}, {TTS_PREFERENCES_KEY: None}]

    for game_settings in inputs:
        # Act
        resolved = resolve_tts_preferences(game_settings)

        # Assert
        assert resolved == DEFAULT_TTS_PREFERENCES
        assert resolved is not DEFAULT_TTS_PREFERENCES


def test_resolve_tts_preferences_custom():
    # Arrange
    custom = {**DEFAULT_TTS_PREFERENCES, "npcs": False, "system": True}
    game_settings = {TTS_PREFERENCES_KEY: custom, "theme": "dark"}

    # Act
    resolved = resolve_tts_preferences(game_settings)
    resolved["gm"] = False

    # Assert
    assert resolved["npcs"] is False
    assert resolved["system"] is True
    assert custom["gm"] is True


def test_with_user_scoped_settings_preserves_player_prefs():
    # Arrange
    player_prefs = {**DEFAULT_TTS_PREFERENCES, "gm": False}
    admin_prefs = {**DEFAULT_TTS_PREFERENCES, "system": True}
    shared = {"theme": "dark", "font_size": 16, TTS_PREFERENCES_KEY: admin_prefs}
    personal = {"theme": "light", TTS_PREFERENCES_KEY: player_prefs}

    # Act
    merged = with_user_scoped_settings(shared, personal)
    merged_without_personal = with_user_scoped_settings(shared, None)

    # Assert
    assert merged == {"theme": "dark", "font_size": 16, TTS_PREFERENCES_KEY: player_prefs}
    assert merged_without_personal == {"theme": "dark", "font_size": 16}


def test_apply_state_settings_updates_auto_speak():
    # Arrange
    state = SessionState(entity_states={"door_1": {"open": True}}, narration_style="terse")
    payload = GameSessionUpdate(tts_auto_speak={"gm": False, "system": 1, "unknown": True})

    # Act
    with patch.object(session_state_settings, "flag_modified") as flag_modified:
        apply_state_settings(state, payload)

    # Assert
    assert state.entity_states["door_1"] == {"open": True}
    assert state.entity_states[TTS_AUTO_SPEAK_KEY] == {
        **DEFAULT_TTS_PREFERENCES,
        "gm": False,
        "system": True,
    }
    assert state.narration_style == "terse"
    flag_modified.assert_called_once_with(state, "entity_states")
