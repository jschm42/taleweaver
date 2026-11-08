"""The ``music`` field of ``GET /chat``: what the client should play, and its render status.

Priority: a script track (``tw.music``) > the track the current scene selected from the
adventure's music library (``WorldScene.music_track_id``) > silence. The payload id is the track
id, so walking between scenes that share a track keeps it playing; a scene without a track fades
the music out. ``tw.music.stop()`` silences scene music too, ``tw.music.release()`` hands control
back to it.

Building the snapshot also starts rendering every script track the session requested but has no
file for yet (within the per-session generation limit), so the client's regular state sync
drives generation without a separate job queue. Library tracks are rendered or uploaded in the
editor's Music tab; play time never renders them.
"""

from __future__ import annotations

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
from backend.engine.audio.music_library import find_track, normalize_tracks
from backend.engine.audio.music_state import read_music_state
from backend.models.adventure_template import AdventureTemplate
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


async def _scene_track_id(db: AsyncSession, state: SessionState) -> Optional[str]:
    """Track of the current scene: the session copy's choice, else the template scene's.

    Sessions started before a scene got its track keep NULL in their copy; the template scene
    then decides, so newly assigned music reaches running sessions too.
    """
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
    return next((row.music_track_id for row in ordered if row.music_track_id), None)


def _track_payload(track: dict[str, Any], url: str) -> dict[str, Any]:
    return {
        # The track id identifies the music: two scenes with the same track keep it playing.
        "id": f"track:{track['id']}",
        "name": track.get("name"),
        "status": "ready",
        "url": url,
        "error": None,
        "loop": True,
        "fade": SCENE_FADE_SECONDS,
        "source": "scene",
    }


async def _scene_music(db: AsyncSession, state: SessionState) -> tuple[Optional[dict], bool]:
    """(payload of the scene's track or None, whether the adventure has any music at all)."""
    template = await db.get(AdventureTemplate, state.template_id) if state.template_id else None
    tracks = normalize_tracks(getattr(template, "music_tracks", None), state.template_id)
    if not tracks or not getattr(template, "music_enabled", True):
        return None, False
    track = find_track(tracks, await _scene_track_id(db, state))
    url = _existing(track.get("url")) if track else None
    return (_track_payload(track, url) if track and url else None), True


async def build_music_snapshot(
    db: AsyncSession, state: SessionState, adventure: Any = None, user: Any = None
) -> Optional[dict[str, Any]]:
    """Return the client music payload, or None when the session has no music at all.

    ``now`` is None in a scene without a track: the client fades the previous music out.
    """
    del adventure  # the library is read from the live template, see _scene_music
    if not state.session_id:
        return None
    music = read_music_state(state.entity_states)
    raw = (await read_server_settings(db)).music_settings
    enabled = is_music_available(raw)
    if enabled and music["tracks"]:
        api_key = music_api_key(user, normalize_music_settings(raw))
        _start_missing_tracks(state.session_id, music["tracks"], raw, api_key)
    now = _script_payload(state.session_id, music)
    has_library = False
    if now is None and not music["silenced"]:
        now, has_library = await _scene_music(db, state)
    if now is None and not (music["tracks"] or music["silenced"] or has_library):
        return None
    return {
        "enabled": enabled,
        "rev": music["rev"],
        "volume": music["volume"],
        "now": now,
    }
