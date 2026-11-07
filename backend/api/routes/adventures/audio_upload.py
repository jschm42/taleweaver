"""Scene background music upload: validates the audio file, stores it and links it to the scene."""

from __future__ import annotations

import os
import re
import uuid
from typing import Optional

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.editing.entity_update.scene_exit import sync_scene_manifest
from backend.core.config import settings
from backend.models.adventure_template import AdventureTemplate
from backend.models.world_entity import WorldScene
from backend.utils.path_security import (
    assert_within_base_dir,
    assert_within_data_dir,
    ensure_within_data_dir,
    local_path_to_data_url,
    safe_data_path,
    sanitize_path_component,
)

MAX_AUDIO_UPLOAD_BYTES = 25 * 1024 * 1024
_ALLOWED_AUDIO_EXTENSIONS = {"mp3", "ogg", "wav"}


def _audio_extension(filename: Optional[str]) -> str:
    """Lower-case extension of the uploaded file name; 400 unless it is mp3, ogg or wav."""
    name = os.path.basename(filename or "")
    ext = name.rsplit(".", 1)[-1].strip().lower() if "." in name else ""
    if ext not in _ALLOWED_AUDIO_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Audio file must be .mp3, .ogg or .wav.")
    return ext


def _is_mp3(content: bytes) -> bool:
    # ID3 tag, or a bare MPEG frame header (11 sync bits set).
    return content.startswith(b"ID3") or (
        len(content) > 1 and content[0] == 0xFF and (content[1] & 0xE0) == 0xE0
    )


def _matches_format(content: bytes, ext: str) -> bool:
    """Checks the file signature, so a renamed non-audio file is rejected."""
    match ext:
        case "mp3":
            return _is_mp3(content)
        case "ogg":
            return content.startswith(b"OggS")
        case "wav":
            return content[:4] == b"RIFF" and content[8:12] == b"WAVE"
    return False


async def read_audio_upload(file: UploadFile) -> tuple[bytes, str]:
    """Reads the upload (at most MAX_AUDIO_UPLOAD_BYTES) and returns (content, extension)."""
    ext = _audio_extension(file.filename)
    content = await file.read(MAX_AUDIO_UPLOAD_BYTES + 1)
    if len(content) > MAX_AUDIO_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Audio file is too large (max 25 MB).")
    if not content or not _matches_format(content, ext):
        raise HTTPException(status_code=400, detail="File content is not a valid audio file.")
    return content, ext


def _audio_storage_path(template_id: str, scene_id: str, ext: str) -> str:
    """New file path below DATA_DIR/adventures/library/<template>/audio (created if missing)."""
    storage_dir = ensure_within_data_dir(
        safe_data_path("adventures", "library", template_id, "audio")
    )
    os.makedirs(storage_dir, exist_ok=True)
    token = re.sub(r"[^A-Za-z0-9_-]+", "-", scene_id).strip("-")[:96] or "scene"
    candidate = ensure_within_data_dir(
        os.path.join(storage_dir, f"{token}_{uuid.uuid4().hex}.{ext}")
    )
    return assert_within_base_dir(candidate, assert_within_data_dir(storage_dir))


def _write_audio_file(path: str, content: bytes) -> str:
    """Writes the audio file and returns its public /data URL."""
    data_root = os.path.abspath(os.path.realpath(settings.DATA_DIR))
    resolved = os.path.abspath(os.path.realpath(assert_within_data_dir(path)))
    if os.path.commonpath([resolved, data_root]) != data_root:
        raise HTTPException(status_code=400, detail="Invalid upload path.")
    with open(resolved, "wb") as f:
        f.write(content)
    return local_path_to_data_url(resolved)


async def _load_template_scene(db: AsyncSession, template_id: str, scene_id: str) -> WorldScene:
    res = await db.execute(
        select(WorldScene).where(
            WorldScene.template_id == template_id,
            WorldScene.session_id.is_(None),
            WorldScene.id == scene_id,
        )
    )
    scene = res.scalars().first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found for this adventure")
    return scene


async def upload_scene_music(
    db: AsyncSession, adv: AdventureTemplate, scene_id: str, file: UploadFile
) -> str:
    """Stores the uploaded audio as the scene's music, syncs the manifest and commits.

    Returns the new ``music_url``. The caller has checked that the user owns ``adv``.
    """
    if not scene_id or sanitize_path_component(scene_id) != scene_id:
        raise HTTPException(status_code=400, detail="Invalid scene ID format.")
    scene = await _load_template_scene(db, adv.id, scene_id)
    content, ext = await read_audio_upload(file)

    music_url = _write_audio_file(_audio_storage_path(adv.id, scene.id, ext), content)
    scene.music_url = music_url
    sync_scene_manifest(adv, scene)
    await db.commit()
    return music_url
