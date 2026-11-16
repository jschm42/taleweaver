"""Browser speech: the free TTS option that runs in the player's browser (Web Speech API).

With the provider ``browser`` the server never creates audio. The frontend reads the
narration with ``speechSynthesis`` (``frontend/src/services/browserTts.ts``), so the provider
needs no API key and works offline with the operating system's voices. Browser voices cannot
render vocal tags like ``[whispers]``, so the narration prompt does not ask for them.
"""

from __future__ import annotations

from typing import Any, Final

BROWSER_TTS_PROVIDER: Final = "browser"
# Browser voices are chosen by name in the admin dialog (``tts_settings``): the narrator voice
# and the voices characters may use. Each player's browser uses those it has, else picks itself.
MAX_BROWSER_VOICE_NAME: Final = 200
MAX_BROWSER_CHARACTER_VOICES: Final = 40
NO_SERVER_AUDIO_DETAIL: Final = (
    "Browser speech is spoken by the player's browser; the server creates no audio for it."
)


def is_browser_provider(provider: Any) -> bool:
    return str(provider or "").strip().lower() == BROWSER_TTS_PROVIDER


def _voice_name(value: Any) -> str:
    return " ".join(str(value or "").split())[:MAX_BROWSER_VOICE_NAME]


def normalize_browser_voices(settings: dict[str, Any]) -> None:
    """Cleans ``browser_voice`` (narrator, "" = automatic) and ``browser_character_voices``."""
    settings["browser_voice"] = _voice_name(settings.get("browser_voice"))
    raw = settings.get("browser_character_voices")
    names = [_voice_name(name) for name in (raw if isinstance(raw, list) else [])]
    unique = list(dict.fromkeys(name for name in names if name))
    settings["browser_character_voices"] = unique[:MAX_BROWSER_CHARACTER_VOICES]


def uses_vocal_tags(tts_settings: dict[str, Any] | None) -> bool:
    """Whether the narration should carry vocal tags for the configured TTS provider."""
    settings = tts_settings or {}
    if is_browser_provider(settings.get("provider")):
        return False
    return bool(settings.get("use_vocal_tags", True))
