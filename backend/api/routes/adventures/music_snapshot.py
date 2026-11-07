"""The ``music`` field of ``GET /chat``: what the client should play, and its render status.

Building the snapshot also starts rendering every track the session requested but has no
file for yet (within the per-session generation limit), so the client's regular state sync
drives generation without a separate job queue.
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.global_settings import read_server_settings
from backend.core.music_settings import is_music_available, normalize_music_settings
from backend.engine.audio.music_generation import ensure_generation, mark_failed, track_status
from backend.engine.audio.music_state import read_music_state
from backend.models.session_state import SessionState

LIMIT_MESSAGE = "This session reached its music generation limit."


def _start_missing_tracks(session_id: str, tracks: dict[str, dict], raw: Optional[dict]) -> None:
    limit = normalize_music_settings(raw)["max_generations_per_session"]
    for index, (track_id, track) in enumerate(tracks.items()):
        if index >= limit:
            if track_status(session_id, track_id)[0] == "pending":
                mark_failed(session_id, track_id, LIMIT_MESSAGE)
            continue
        ensure_generation(session_id, track_id, track, raw)


def _now_payload(session_id: str, music: dict[str, Any]) -> Optional[dict[str, Any]]:
    now = music.get("now")
    if not now:
        return None
    status, detail = track_status(session_id, now["id"])
    track = music["tracks"].get(now["id"]) or {}
    return {
        "id": now["id"],
        "name": track.get("name"),
        "status": status,
        "url": detail if status == "ready" else None,
        "error": detail if status == "failed" else None,
        "loop": bool(now.get("loop", True)),
        "fade": float(now.get("fade", 2.0)),
    }


async def build_music_snapshot(db: AsyncSession, state: SessionState) -> Optional[dict[str, Any]]:
    """Return the client music payload, or None when the session never requested music."""
    music = read_music_state(state.entity_states)
    if not music["tracks"] or not state.session_id:
        return None
    raw = (await read_server_settings(db)).music_settings
    enabled = is_music_available(raw)
    if enabled:
        _start_missing_tracks(state.session_id, music["tracks"], raw)
    return {
        "enabled": enabled,
        "rev": music["rev"],
        "volume": music["volume"],
        "now": _now_payload(state.session_id, music),
    }
