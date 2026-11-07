"""The ``music`` field of ``GET /chat``: what the client should play, and its render status.

Priority: a script track (``tw.music``) > the current scene's loop > the adventure's main theme
> silence. ``tw.music.stop()`` silences scene and theme music too, ``tw.music.release()`` hands
control back to them.

Building the snapshot also starts rendering every script track the session requested but has no
file for yet (within the per-session generation limit), so the client's regular state sync
drives generation without a separate job queue. Scene and theme music are rendered in the
editor; play time never renders them.
"""

from __future__ import annotations

import hashlib
import os
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.global_settings import read_server_settings
from backend.core.music_settings import (
    is_music_available,
    music_api_key,
    normalize_music_settings,
)
from backend.engine.audio.music_generation import ensure_generation, mark_failed, track_status
from backend.engine.audio.music_state import read_music_state
from backend.models.session_state import SessionState
from backend.models.world_entity import WorldScene
from backend.utils.path_security import data_url_to_local_path

LIMIT_MESSAGE = "This session reached its music generation limit."
SCENE_FADE_SECONDS = 3.0


def _start_missing_tracks(
    session_id: str, tracks: dict[str, dict], raw: Optional[dict], api_key: Optional[str]
) -> None:
    limit = normalize_music_settings(raw)["max_generations_per_session"]
    for index, (track_id, track) in enumerate(tracks.items()):
        if index >= limit:
            if track_status(session_id, track_id)[0] == "pending":
                mark_failed(session_id, track_id, LIMIT_MESSAGE)
            continue
        ensure_generation(session_id, track_id, track, raw, api_key)


def _script_payload(session_id: str, music: dict[str, Any]) -> Optional[dict[str, Any]]:
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
        "source": "script",
    }


def _existing(url: Optional[str]) -> Optional[str]:
    path = data_url_to_local_path(url)
    return url if path and os.path.isfile(path) else None


async def _scene_music_url(db: AsyncSession, state: SessionState) -> tuple[Optional[str], str]:
    """Music of the current scene: the session copy first, then the template scene."""
    rows = (
        await db.execute(
            select(WorldScene).where(
                WorldScene.id == state.current_scene_id,
                (WorldScene.session_id == state.session_id)
                | ((WorldScene.template_id == state.template_id) & WorldScene.session_id.is_(None)),
            )
        )
    ).scalars()
    ordered = sorted(rows, key=lambda row: row.session_id is None)
    for row in ordered:
        url = _existing(row.music_url)
        if url:
            return url, str(row.label or row.id)
    return None, ""


def _ambient_payload(url: str, name: str, source: str) -> dict[str, Any]:
    return {
        "id": f"{source}:{hashlib.sha256(url.encode('utf-8')).hexdigest()[:16]}",
        "name": name,
        "status": "ready",
        "url": url,
        "error": None,
        "loop": True,
        "fade": SCENE_FADE_SECONDS,
        "source": source,
    }


async def _ambient(db: AsyncSession, state: SessionState, adventure: Any) -> Optional[dict]:
    if adventure is not None and not getattr(adventure, "music_enabled", True):
        return None
    url, name = await _scene_music_url(db, state)
    if url:
        return _ambient_payload(url, name, "scene")
    theme = _existing(getattr(adventure, "music_url", None))
    return _ambient_payload(theme, "Main theme", "theme") if theme else None


async def build_music_snapshot(
    db: AsyncSession, state: SessionState, adventure: Any = None, user: Any = None
) -> Optional[dict[str, Any]]:
    """Return the client music payload, or None when the session has no music at all."""
    if not state.session_id:
        return None
    music = read_music_state(state.entity_states)
    raw = (await read_server_settings(db)).music_settings
    enabled = is_music_available(raw)
    if enabled and music["tracks"]:
        api_key = music_api_key(user, normalize_music_settings(raw))
        _start_missing_tracks(state.session_id, music["tracks"], raw, api_key)
    now = _script_payload(state.session_id, music)
    if now is None and not music["silenced"]:
        now = await _ambient(db, state, adventure)
    if now is None and not music["tracks"] and not music["silenced"]:
        return None
    return {
        "enabled": enabled,
        "rev": music["rev"],
        "volume": music["volume"],
        "now": now,
    }
