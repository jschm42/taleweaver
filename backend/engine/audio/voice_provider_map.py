"""Per-provider voice ids for the voices of the voice list (``elevenlabs_voices``).

The voice list is the one set of character voices for every speech provider. NPCs and the
protagonist store the ElevenLabs id of their list voice; this map (``ServerSettings.voice_provider_map``,
managed by admins) says which voice Google TTS and the OpenAI-compatible server use for that list
voice. A list voice without an id for the active provider is spoken in the narrator (GM) voice.
Until an admin saves the mapping (column ``NULL``), the suggestions in the voice list
(``google_voice`` / ``openai_compatible_voice``) are used; a saved mapping replaces them completely.

Stored shape: ``{elevenlabs_id: {"google": "Kore", "custom_openai": "af_heart"}}``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final, Optional

from backend.core.tts_voices import GOOGLE_TTS_VOICE_LIST
from backend.engine.audio.elevenlabs_voices import (
    VoiceOption,
    load_voice_catalog,
    looks_like_voice_id,
)

GOOGLE_PROVIDER: Final = "google"
COMPATIBLE_PROVIDER: Final = "custom_openai"
ELEVENLABS_PROVIDER: Final = "elevenlabs"
# Providers whose voice ids come from this map (ElevenLabs uses the list ids themselves).
MAPPED_PROVIDERS: Final = (GOOGLE_PROVIDER, COMPATIBLE_PROVIDER)
MAX_VOICE_ID_CHARS: Final = 200

VoiceProviderMap = dict[str, dict[str, str]]

_GOOGLE_BY_LOWER: Final = {name.lower(): name for name in GOOGLE_TTS_VOICE_LIST}


class VoiceMapError(ValueError):
    """A provider voice id that cannot be stored (message is safe to show)."""


def _clean_compatible_voice(value: str) -> str:
    if len(value) > MAX_VOICE_ID_CHARS:
        raise VoiceMapError(
            f"Voice id '{value[:40]}…' is longer than {MAX_VOICE_ID_CHARS} characters."
        )
    if any(ord(char) < 32 for char in value):
        raise VoiceMapError("Voice ids must not contain control characters.")
    return value


def clean_provider_voice(provider: str, value: object) -> str:
    """The voice id as stored ("" = narrator voice); raises ``VoiceMapError`` when invalid."""
    text = str(value or "").strip()
    if not text:
        return ""
    if provider == GOOGLE_PROVIDER:
        name = _GOOGLE_BY_LOWER.get(text.lower())
        if not name:
            raise VoiceMapError(f"'{text}' is not a Google TTS voice.")
        return name
    return _clean_compatible_voice(text)


def _clean_entry(raw: object) -> dict[str, str]:
    if not isinstance(raw, Mapping):
        return {}
    entry: dict[str, str] = {}
    for provider in MAPPED_PROVIDERS:
        try:
            voice = clean_provider_voice(provider, raw.get(provider))
        except VoiceMapError:
            continue
        if voice:
            entry[provider] = voice
    return entry


def normalize_voice_map(raw: object) -> VoiceProviderMap:
    """The stored map without invalid keys, unknown providers or empty cells (never raises)."""
    if not isinstance(raw, Mapping):
        return {}
    cleaned: VoiceProviderMap = {}
    for voice_id, entry in raw.items():
        if not looks_like_voice_id(voice_id):
            continue
        if cleaned_entry := _clean_entry(entry):
            cleaned[str(voice_id)] = cleaned_entry
    return cleaned


def _suggestion(voice: VoiceOption, provider: str) -> str:
    """The voice list's suggested voice for ``provider`` ("" = none)."""
    if provider == GOOGLE_PROVIDER:
        return voice.get("google_voice") or ""
    return voice.get("openai_compatible_voice") or ""


def suggested_voice_map(voices: list[VoiceOption]) -> VoiceProviderMap:
    """The voice list's own suggestions (invalid ones are dropped)."""
    return normalize_voice_map(
        {v["id"]: {p: _suggestion(v, p) for p in MAPPED_PROVIDERS} for v in voices}
    )


def effective_voice_map(
    saved: object, voices: Optional[list[VoiceOption]] = None
) -> VoiceProviderMap:
    """The saved mapping, or the voice list's suggestions while none was ever saved."""
    if saved is None:
        return suggested_voice_map(voices if voices is not None else load_voice_catalog())
    return normalize_voice_map(saved)


def provider_voice(
    voice_map: Mapping[str, Mapping[str, str]], provider: str, list_voice: object
) -> Optional[str]:
    """The voice ``provider`` speaks for a list voice, ``None`` for the narrator voice."""
    if not isinstance(list_voice, str):
        return None
    if provider == ELEVENLABS_PROVIDER:
        return list_voice if looks_like_voice_id(list_voice) else None
    voice = (voice_map.get(list_voice) or {}).get(provider)
    return voice or None


def provider_voices(voice_map: Mapping[str, Mapping[str, str]], provider: str) -> dict[str, str]:
    """List voice id -> voice of ``provider`` for every mapped list voice."""
    return {
        list_id: voice
        for list_id in voice_map
        if (voice := provider_voice(voice_map, provider, list_id))
    }


def supports_character_voices(provider: str, voice_map: Mapping[str, Mapping[str, str]]) -> bool:
    """ElevenLabs always; the other providers once at least one list voice has an id for them."""
    return provider == ELEVENLABS_PROVIDER or bool(provider_voices(voice_map, provider))


def voices_sounding_like(
    voice_map: Mapping[str, Mapping[str, str]], provider: str, narrator_voice: str
) -> list[str]:
    """List voices that the provider speaks with the narrator voice (casting avoids them)."""
    if not narrator_voice:
        return []
    if provider == ELEVENLABS_PROVIDER:
        return [narrator_voice]
    wanted = narrator_voice.lower()
    return [
        list_id
        for list_id, voice in provider_voices(voice_map, provider).items()
        if voice.lower() == wanted
    ]


def mapping_rows(
    voices: list[VoiceOption], voice_map: Mapping[str, Mapping[str, str]]
) -> list[dict[str, Any]]:
    """One row per list voice: traits, ElevenLabs id, mapped and suggested provider voices."""
    return [
        {
            "id": voice["id"],
            "name": voice["name"],
            "gender": voice["gender"],
            "age": voice["age"],
            "accent": voice["accent"],
            "description": voice["description"],
            "good_for": list(voice.get("good_for") or voice.get("best_for") or []),
            "best_for": list(voice.get("best_for") or voice.get("good_for") or []),
            "elevenlabs": voice["id"],
            **{p: (voice_map.get(voice["id"]) or {}).get(p, "") for p in MAPPED_PROVIDERS},
            **{f"suggested_{p}": _suggestion(voice, p) for p in MAPPED_PROVIDERS},
        }
        for voice in voices
    ]


def build_voice_map(
    rows: list[Mapping[str, Any]], known_ids: set[str]
) -> tuple[VoiceProviderMap, list[str]]:
    """The map for edited rows (strict) plus the ids of rows that are not in the voice list.

    Raises ``VoiceMapError`` naming the row when a cell holds an invalid voice id.
    """
    voice_map: VoiceProviderMap = {}
    unknown: list[str] = []
    for row in rows:
        list_id = str(row.get("id") or "").strip()
        if list_id not in known_ids:
            unknown.append(list_id or str(row.get("name") or "?"))
            continue
        entry = {}
        for provider in MAPPED_PROVIDERS:
            try:
                voice = clean_provider_voice(provider, row.get(provider))
            except VoiceMapError as exc:
                raise VoiceMapError(f"{row.get('name') or list_id}: {exc}") from None
            if voice:
                entry[provider] = voice
        if entry:
            voice_map[list_id] = entry
    return voice_map, unknown
