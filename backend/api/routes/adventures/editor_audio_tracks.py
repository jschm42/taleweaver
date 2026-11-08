"""Read-modify-write of an adventure's audio library, scene assignment and upload checks.

``audio_tracks`` is a JSON column, and background renders finish while the author keeps
editing, so every change goes through ``update_tracks`` under a per-adventure lock (one backend
process). The library and the scenes' track ids are mirrored into ``original_manifest``, so a
template reset or a World-Builder re-apply keeps them.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from copy import deepcopy
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from backend.engine.audio.audio_assets import delete_library_audio
from backend.engine.audio.audio_library import (
    check_track_id,
    find_track,
    normalize_tracks,
    suggest_track_id,
)
from backend.models.adventure_template import AdventureTemplate
from backend.models.world_entity import WorldScene

MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # same as one ADZ entry, so exports stay importable

_locks: dict[str, asyncio.Lock] = {}

TrackChange = Callable[[list[dict[str, Any]]], Any]


def _lock(template_id: str) -> asyncio.Lock:
    return _locks.setdefault(template_id, asyncio.Lock())


def _mirror_tracks(adventure: AdventureTemplate) -> None:
    if not isinstance(adventure.original_manifest, dict):
        return
    manifest = deepcopy(adventure.original_manifest)
    manifest["audio_tracks"] = deepcopy(adventure.audio_tracks or [])
    adventure.original_manifest = manifest  # type: ignore[assignment]
    flag_modified(adventure, "original_manifest")


async def update_tracks(db: AsyncSession, template_id: str, change: TrackChange) -> Any:
    """Apply ``change(tracks)`` to the library and commit; returns what ``change`` returned."""
    async with _lock(template_id):
        adventure = await db.get(AdventureTemplate, template_id)
        if adventure is None:
            raise HTTPException(status_code=404, detail="Adventure template not found")
        await db.refresh(adventure, ["audio_tracks", "original_manifest"])
        tracks = normalize_tracks(adventure.audio_tracks, template_id)
        result = change(tracks)
        adventure.audio_tracks = tracks  # type: ignore[assignment]
        flag_modified(adventure, "audio_tracks")
        _mirror_tracks(adventure)
        await db.commit()
        return result


def require_track(tracks: list[dict[str, Any]], track_id: str) -> dict[str, Any]:
    track = find_track(tracks, track_id)
    if track is None:
        raise HTTPException(status_code=404, detail="Track not found")
    return track


async def template_scenes(db: AsyncSession, template_id: str) -> list[WorldScene]:
    rows = await db.execute(
        select(WorldScene).where(
            WorldScene.template_id == template_id, WorldScene.session_id.is_(None)
        )
    )
    return list(rows.scalars())


def _mirror_scene(adventure: AdventureTemplate, scene: WorldScene) -> None:
    if not isinstance(adventure.original_manifest, dict):
        return
    manifest = deepcopy(adventure.original_manifest)
    for entry in manifest.get("scenes") or []:
        if isinstance(entry, dict) and entry.get("id") == scene.id:
            entry["audio_track_id"] = scene.audio_track_id
    adventure.original_manifest = manifest  # type: ignore[assignment]
    flag_modified(adventure, "original_manifest")


async def assign_scene_track(
    db: AsyncSession, adventure: AdventureTemplate, scene_id: str, track_id: Optional[str]
) -> WorldScene:
    scene = next((s for s in await template_scenes(db, adventure.id) if s.id == scene_id), None)
    if scene is None:
        raise HTTPException(status_code=404, detail="Scene not found")
    if (
        track_id
        and find_track(normalize_tracks(adventure.audio_tracks, adventure.id), track_id) is None
    ):
        raise HTTPException(status_code=404, detail="Track not found")
    scene.audio_track_id = track_id or None
    _mirror_scene(adventure, scene)
    await db.commit()
    return scene


async def release_track(db: AsyncSession, adventure: AdventureTemplate, track_id: str) -> None:
    """Unassign a deleted track from every template scene."""
    for scene in await template_scenes(db, adventure.id):
        if scene.audio_track_id == track_id:
            scene.audio_track_id = None
            _mirror_scene(adventure, scene)
    await db.commit()


async def rename_track_references(
    db: AsyncSession, adventure: AdventureTemplate, old_id: str, new_id: str
) -> None:
    """Point every scene and the title track at the renamed track."""
    for scene in await template_scenes(db, adventure.id):
        if scene.audio_track_id == old_id:
            scene.audio_track_id = new_id
            _mirror_scene(adventure, scene)
    if adventure.title_track_id == old_id:
        adventure.title_track_id = new_id  # type: ignore[assignment]
    await db.commit()


def replace_file(track: dict[str, Any], url: str, template_id: str) -> None:
    """Point ``track`` at a new file and delete the old one (own audio folder only)."""
    old = track.get("url")
    track["url"] = url
    if old and old != url:
        delete_library_audio(old, template_id)


def sniff_audio(data: bytes, filename: str) -> str:
    """File extension for uploaded audio, decided by its content (not the file name)."""
    head = data[:12]
    name = filename.lower()
    if head.startswith(b"ID3") or (len(head) > 1 and head[0] == 0xFF and head[1] & 0xE0 == 0xE0):
        return "mp3"
    if head.startswith(b"RIFF") and head[8:12] == b"WAVE":
        return "wav"
    if head.startswith(b"OggS"):
        return "opus" if name.endswith(".opus") else "ogg"
    if head.startswith(b"fLaC"):
        return "flac"
    if head[4:8] == b"ftyp":
        return "m4a"
    raise HTTPException(
        status_code=400, detail="Unsupported audio file. Use MP3, WAV, OGG/Opus, FLAC or M4A."
    )


# --- track ids --------------------------------------------------------------------------


def new_track_id_for(wanted: Optional[str], fallback_text: str, taken: set[str]) -> str:
    """The author's id (validated) or one suggested from ``fallback_text``."""
    if not (wanted or "").strip():
        return suggest_track_id(fallback_text, taken)
    try:
        return check_track_id(wanted, taken)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def add_track_change(track: dict[str, Any], explicit: bool, fallback_text: str) -> TrackChange:
    """Library change that appends ``track``; a suggested id that got taken meanwhile is
    suggested again, a typed one is rejected."""

    def change(tracks: list[dict[str, Any]]) -> None:
        taken = {t["id"] for t in tracks}
        if track["id"] in taken:
            if explicit:
                raise HTTPException(
                    status_code=409, detail=f"The track ID '{track['id']}' is already used."
                )
            track["id"] = suggest_track_id(fallback_text, taken)
        tracks.append(track)

    return change


def taken_track_ids(adventure: AdventureTemplate) -> set[str]:
    return {t["id"] for t in normalize_tracks(adventure.audio_tracks, adventure.id)}


def renamed_track_id(
    jobs: Any, template_id: str, track_id: str, wanted: Optional[str], taken: set[str]
) -> Optional[str]:
    """The new id of a rename, or None when the id stays."""
    wanted = (wanted or "").strip().upper()
    if not wanted or wanted == track_id:
        return None
    running = jobs.matching(template_id=template_id, track_id=track_id)
    if any(status.get("status") == "running" for _meta, status in running):
        raise HTTPException(
            status_code=409, detail="Wait until the track finished rendering, then rename it."
        )
    return new_track_id_for(wanted, wanted, taken - {track_id})
