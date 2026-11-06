"""Applies the in-game settings dialog (PATCH /sessions/{id}) to a session's state."""

from typing import Any

from sqlalchemy.orm.attributes import flag_modified

from backend.core.tts_preferences import DEFAULT_TTS_PREFERENCES, TTS_AUTO_SPEAK_KEY
from backend.core.ui_theme import UI_SKIN_AUTO
from backend.models.session_state import SessionState
from backend.schemas.session import GameSessionUpdate


def has_state_settings(payload: GameSessionUpdate) -> bool:
    """True when the payload touches anything stored on the SessionState row."""
    return any(
        value is not None
        for value in (
            payload.max_memory_turns,
            payload.enable_history_compression,
            payload.narration_style,
            payload.ui_skin,
            payload.tts_auto_speak,
        )
    )


def _clean_auto_speak(raw: dict[str, Any]) -> dict[str, bool]:
    return {key: bool(raw.get(key, default)) for key, default in DEFAULT_TTS_PREFERENCES.items()}


def _apply_auto_speak(state: SessionState, raw: dict[str, Any]) -> None:
    state.entity_states = {
        **(state.entity_states or {}),
        TTS_AUTO_SPEAK_KEY: _clean_auto_speak(raw),
    }
    flag_modified(state, "entity_states")


def apply_state_settings(state: SessionState, payload: GameSessionUpdate) -> None:
    """Copy every provided setting onto ``state``; omitted fields stay untouched."""
    if payload.max_memory_turns is not None:
        state.max_memory_turns = max(1, min(100, int(payload.max_memory_turns)))
    if payload.enable_history_compression is not None:
        state.enable_history_compression = payload.enable_history_compression
    if payload.narration_style is not None:
        state.narration_style = payload.narration_style
    if payload.ui_skin is not None:
        state.ui_skin = None if payload.ui_skin == UI_SKIN_AUTO else payload.ui_skin
    if payload.tts_auto_speak is not None:
        _apply_auto_speak(state, payload.tts_auto_speak)
