"""An adventure's music library (``AdventureTemplate.music_tracks``) and its track entries.

Tracks are generated (from a prompt) or uploaded in the editor's Music tab; scenes pick one with
``WorldScene.music_track_id``. A track without ``url`` is planned but has no audio yet (the
World-Builder writes such tracks with a prompt, the editor renders them later).

Track entry::

    {"id": "crypt_theme", "name": "Crypt Theme", "prompt": "...", "url": "/data/..." | None,
     "source": "generated" | "uploaded" | "planned", "reference_scene_id": "CRYPT" | None,
     "created_at": "2026-11-07T18:00:00+00:00"}
"""

from __future__ import annotations

import re
import secrets
from datetime import UTC, datetime
from typing import Any, Optional

from backend.engine.audio.music_assets import local_music_url

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
    url = local_music_url(raw.get("url"), template_id)
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
    """A scene's ``music_track_id`` value: a valid id or None."""
    text = str(value or "").strip()
    return text if TRACK_ID_RE.fullmatch(text) else None


def title_track_or_none(value: Any, tracks: Any) -> Optional[str]:
    """``value`` when it names a track of ``tracks`` (the title song), else None."""
    track_id = track_id_or_none(value)
    return track_id if find_track(tracks, track_id) else None
