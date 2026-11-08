"""An adventure's audio library (``AdventureTemplate.audio_tracks``) and its track entries.

Tracks are generated (from a prompt) or uploaded in the editor's Audio tab; scenes pick one with
``WorldScene.audio_track_id``. A track without ``url`` is planned but has no audio yet (the
World-Builder writes such tracks with a prompt, the editor renders them later).

Track entry::

    {"id": "crypt_theme", "name": "Crypt Theme", "prompt": "...", "url": "/data/..." | None,
     "source": "generated" | "uploaded" | "planned", "reference_scene_id": "CRYPT" | None,
     "created_at": "2026-11-07T18:00:00+00:00"}
"""

from __future__ import annotations

import re
import secrets
import unicodedata
from datetime import UTC, datetime
from typing import Any, Optional

from backend.engine.audio.audio_assets import local_audio_url

TRACK_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,50}$")
TRACK_SOURCES = ("generated", "uploaded", "planned")
MAX_TRACKS = 200
MAX_NAME_CHARS = 100
MAX_PROMPT_CHARS = 1000


def new_track_id() -> str:
    return secrets.token_hex(6)


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _text(value: Any, limit: int) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def normalize_track(raw: Any, template_id: Optional[str]) -> Optional[dict[str, Any]]:
    """A clean track entry, or None when ``raw`` has no usable id."""
    if not isinstance(raw, dict):
        return None
    track_id = str(raw.get("id") or "").strip()
    if not TRACK_ID_RE.fullmatch(track_id):
        return None
    url = local_audio_url(raw.get("url"), template_id)
    source = str(raw.get("source") or "").strip().lower()
    if source not in TRACK_SOURCES:
        source = "generated" if url else "planned"
    return {
        "id": track_id,
        "name": _text(raw.get("name"), MAX_NAME_CHARS) or track_id,
        "prompt": _text(raw.get("prompt"), MAX_PROMPT_CHARS),
        "url": url,
        "source": source,
        "reference_scene_id": _text(raw.get("reference_scene_id"), 50) or None,
        "created_at": str(raw.get("created_at") or "")[:40] or None,
    }


def normalize_tracks(raw: Any, template_id: Optional[str]) -> list[dict[str, Any]]:
    """Valid, unique tracks (first entry per id wins), at most ``MAX_TRACKS``."""
    tracks: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in raw if isinstance(raw, list) else []:
        track = normalize_track(entry, template_id)
        if track is None or track["id"] in seen:
            continue
        seen.add(track["id"])
        tracks.append(track)
    return tracks[:MAX_TRACKS]


def find_track(tracks: Any, track_id: Optional[str]) -> Optional[dict[str, Any]]:
    if not track_id or not isinstance(tracks, list):
        return None
    return next((t for t in tracks if isinstance(t, dict) and t.get("id") == track_id), None)


def track_id_or_none(value: Any) -> Optional[str]:
    """A scene's ``audio_track_id`` value: a valid id or None."""
    text = str(value or "").strip()
    return text if TRACK_ID_RE.fullmatch(text) else None


def title_track_or_none(value: Any, tracks: Any) -> Optional[str]:
    """``value`` when it names a track of ``tracks`` (the title track), else None."""
    track_id = track_id_or_none(value)
    return track_id if find_track(tracks, track_id) else None


# IDs the author types or that are suggested: letters, digits and underscores, max 30
# characters, stored in upper case (e.g. CRYPT_THEME). Older random or World-Builder ids stay
# valid (TRACK_ID_RE) until the author changes them.
EDITABLE_ID_RE = re.compile(r"^[A-Z0-9_]{1,30}$")
MAX_EDITABLE_ID_CHARS = 30


def suggest_track_id(text: Any, taken: set[str]) -> str:
    """Upper-case id from a name or file name, unique among ``taken`` (``crypt theme.mp3`` ->
    ``CRYPT_THEME``; ``CRYPT_THEME_2`` when that is taken)."""
    plain = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode()
    base = re.sub(r"[^A-Za-z0-9]+", "_", plain).strip("_").upper()[:MAX_EDITABLE_ID_CHARS]
    base = base or "TRACK"
    candidate, number = base, 2
    while candidate in taken:
        suffix = f"_{number}"
        candidate = base[: MAX_EDITABLE_ID_CHARS - len(suffix)].rstrip("_") + suffix
        number += 1
    return candidate


def check_track_id(value: Any, taken: set[str]) -> str:
    """The id the author typed, upper-cased; ``ValueError`` when invalid or already used."""
    track_id = str(value or "").strip().upper()
    if not EDITABLE_ID_RE.fullmatch(track_id):
        raise ValueError(
            "Track IDs use only letters, digits and underscores, at most 30 characters."
        )
    if track_id in taken:
        raise ValueError(f"The track ID '{track_id}' is already used in this adventure.")
    return track_id
