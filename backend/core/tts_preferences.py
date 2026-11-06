"""Per-player Auto-Speak preferences (which story voices are read aloud automatically).

The profile keeps them in ``User.game_settings["tts_preferences"]`` as defaults for new
sessions; every session carries its own copy in ``entity_states[TTS_AUTO_SPEAK_KEY]``.
"""

from typing import Any, Optional

TTS_PREFERENCES_KEY = "tts_preferences"
TTS_AUTO_SPEAK_KEY = "__tts_auto_speak__"

DEFAULT_TTS_PREFERENCES: dict[str, bool] = {
    "enabled": True,
    "gm": True,
    "protagonist": True,
    "npcs": True,
    "system": False,
    "readables": True,
}

# game_settings keys that belong to one player; they stay in User.game_settings, never in ServerSettings.
USER_SCOPED_GAME_SETTING_KEYS = (TTS_PREFERENCES_KEY,)


def resolve_tts_preferences(game_settings: Optional[dict[str, Any]]) -> dict[str, Any]:
    """Return the stored preferences of a player, or a fresh copy of the defaults."""
    stored = (game_settings or {}).get(TTS_PREFERENCES_KEY)
    return dict(stored or DEFAULT_TTS_PREFERENCES)


def with_user_scoped_settings(
    shared: Optional[dict[str, Any]], personal: Optional[dict[str, Any]]
) -> dict[str, Any]:
    """Merge shared game settings with the player-owned keys of ``personal``."""
    merged = {
        key: value
        for key, value in (shared or {}).items()
        if key not in USER_SCOPED_GAME_SETTING_KEYS
    }
    for key in USER_SCOPED_GAME_SETTING_KEYS:
        if key in (personal or {}):
            merged[key] = personal[key]
    return merged
