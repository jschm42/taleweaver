"""The curated ElevenLabs voice list used for per-character voices.

The list lives in ``backend/core/elevenlabs_voices.json`` and can be overridden without code changes
by ``DATA_DIR/voices/elevenlabs_voices.json``. The editor voice picker, automatic casting and the
world builder only offer voices from this list. It is reloaded when the file changes.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Final, Optional, TypedDict

from backend.core.config import settings

logger = logging.getLogger(__name__)

BUNDLED_VOICE_LIST: Final = (
    Path(__file__).resolve().parent.parent / "core" / "elevenlabs_voices.json"
)
# ElevenLabs voice ids are 20 alphanumeric characters (e.g. 21m00Tcm4TlvDq8ikWAM).
_VOICE_ID_PATTERN: Final = re.compile(r"^[A-Za-z0-9]{20}$")


class VoiceOption(TypedDict):
    id: str
    name: str
    gender: Optional[str]
    age: str
    accent: str
    description: str
    good_for: list[str]


_cache: dict[str, Any] = {"key": None, "voices": []}


def looks_like_voice_id(value: object) -> bool:
    return isinstance(value, str) and bool(_VOICE_ID_PATTERN.match(value))


def voice_list_path() -> Path:
    override = Path(settings.DATA_DIR) / "voices" / "elevenlabs_voices.json"
    return override if override.is_file() else BUNDLED_VOICE_LIST


def _text(raw: dict[str, Any], key: str) -> str:
    return str(raw.get(key) or "").strip()


def _to_option(raw: Any) -> Optional[VoiceOption]:
    if not isinstance(raw, dict) or not looks_like_voice_id(raw.get("id")):
        return None
    gender = _text(raw, "gender").lower()
    good_for = raw.get("good_for") if isinstance(raw.get("good_for"), list) else []
    return VoiceOption(
        id=str(raw["id"]),
        name=_text(raw, "name") or str(raw["id"]),
        gender=gender if gender in ("female", "male") else None,
        age=_text(raw, "age"),
        accent=_text(raw, "accent"),
        description=_text(raw, "description"),
        good_for=[str(item) for item in good_for if item],
    )


def _read_voice_list(path: Path) -> list[VoiceOption]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        logger.exception("Could not read the voice list %s; per-character voices are off.", path)
        return []
    entries = data.get("voices") if isinstance(data, dict) else data
    options = [option for raw in entries or [] if (option := _to_option(raw))]
    skipped = len(entries or []) - len(options)
    if skipped:
        logger.warning("Voice list %s: skipped %d entries without a valid id.", path, skipped)
    return options


def load_voice_catalog() -> list[VoiceOption]:
    """All voices from the voice list (cached until the file changes)."""
    path = voice_list_path()
    try:
        key = (str(path), path.stat().st_mtime_ns)
    except OSError:
        return []
    if _cache["key"] != key:
        _cache["key"] = key
        _cache["voices"] = _read_voice_list(path)
    return list(_cache["voices"])


def resolve_voice_reference(value: object, voices: list[VoiceOption]) -> Optional[str]:
    """Voice id for an id or a voice name from the list (the world builder may write names)."""
    if not isinstance(value, str) or not value.strip():
        return None
    wanted = value.strip()
    for voice in voices:
        if wanted == voice["id"] or wanted.lower() == voice["name"].lower():
            return voice["id"]
    return None
