"""Debug inspector downloads: all session images as one ZIP, single NPCs / items as .twe.

``GET /adventures/{game_id}/session-debug/images.zip`` collects the images of the session's
scenes (template scenes and dynamically generated ones), NPCs and objects (session rows,
including dynamic spawns) plus the protagonist portrait. Only local ``/data/...`` files are
packed; remote URLs and missing files are listed in ``missing.txt`` inside the archive.

``GET /adventures/{game_id}/session-debug/export/{entity_id}`` downloads one session NPC or
item (dynamic spawns too) as the editor's ``.twe`` bundle, with its current session values.

Like the inspector itself both need the session's owner and debug mode. Every path goes
through ``backend.utils.path_security`` (CWE-22).
"""

from __future__ import annotations

import asyncio
import io
import os
import re
import zipfile
from dataclasses import dataclass, field
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.entity_transfer_service import export_entity_bundle
from backend.api.routes.adventures.logic import AdventureLogic
from backend.api.routes.adventures.session_adventure import load_session_adventure
from backend.core.auth import get_current_user
from backend.core.config import settings
from backend.core.database import get_db
from backend.engine.adventures.entity_bundle import BUNDLE_EXTENSION, EntityBundleError
from backend.models.avatar import Avatar
from backend.models.session_state import SessionState
from backend.models.user import User
from backend.models.world_entity import WorldEntity, WorldScene
from backend.utils.download_headers import attachment_disposition
from backend.utils.path_security import data_url_to_local_path

router = APIRouter(tags=["Gameplay"])

_UNSAFE_NAME = re.compile(r"[^A-Za-z0-9_-]+")
_ENTITY_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_FOLDERS = {"NPC": "npcs", "OBJECT": "items"}


@dataclass
class ImageRef:
    """One image to pack: folder in the archive, entity id and name, its /data URL."""

    folder: str
    entity_id: str
    name: str
    url: str


@dataclass
class ZipResult:
    data: bytes
    packed: int = 0
    missing: list[str] = field(default_factory=list)


def _clean(text: Any, limit: int = 40) -> str:
    return _UNSAFE_NAME.sub("_", str(text or "")).strip("_")[:limit]


def _image_url(row: Any, entity_states: dict[str, Any]) -> str:
    override = entity_states.get(str(getattr(row, "id", "") or ""))
    if isinstance(override, dict) and override.get("image_url"):
        return str(override["image_url"])
    return str(getattr(row, "image_url", "") or "")


def _local_path(url: str) -> Optional[str]:
    """The validated local file of a /data URL (query string dropped), or None."""
    path = data_url_to_local_path(url.split("?", 1)[0].split("#", 1)[0])
    return path if path and os.path.isfile(path) else None


def _archive_name(ref: ImageRef, path: str, used: set[str]) -> str:
    ext = os.path.splitext(path)[1].lower() or ".png"
    base = f"{ref.folder}/{_clean(ref.entity_id) or 'item'}"
    label = _clean(ref.name)
    stem = f"{base}__{label}" if label else base
    name, counter = f"{stem}{ext}", 2
    while name in used:
        name, counter = f"{stem}_{counter}{ext}", counter + 1
    used.add(name)
    return name


def build_image_zip(refs: list[ImageRef]) -> ZipResult:
    """Packs the referenced local images (stored, they are compressed already)."""
    buffer = io.BytesIO()
    result = ZipResult(data=b"")
    used: set[str] = set()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        for ref in refs:
            path = _local_path(ref.url)
            if path is None:
                result.missing.append(f"{ref.folder}/{ref.entity_id}: {ref.url}")
                continue
            archive.write(path, _archive_name(ref, path, used))
            result.packed += 1
        if result.missing:
            archive.writestr("missing.txt", "\n".join(result.missing) + "\n")
    result.data = buffer.getvalue()
    return result


async def _scene_refs(db: AsyncSession, state: SessionState) -> list[ImageRef]:
    """Template scenes plus the session's own (dynamic) scenes; session rows win."""
    rows = (
        (
            await db.execute(
                select(WorldScene).where(
                    or_(
                        WorldScene.session_id == state.session_id,
                        WorldScene.template_id == state.template_id,
                    )
                )
            )
        )
        .scalars()
        .all()
    )
    by_id: dict[str, WorldScene] = {}
    for scene in rows:
        if scene.id not in by_id or scene.session_id == state.session_id:
            by_id[scene.id] = scene
    return [
        ImageRef("scenes", scene.id, scene.label or "", str(scene.image_url))
        for scene in by_id.values()
        if scene.image_url
    ]


async def collect_session_images(db: AsyncSession, state: SessionState) -> list[ImageRef]:
    """Every image URL of the session: scenes, NPCs, items and the protagonist."""
    entity_states = dict(state.entity_states or {})
    refs = await _scene_refs(db, state)
    entities = (
        (await db.execute(select(WorldEntity).where(WorldEntity.session_id == state.session_id)))
        .scalars()
        .all()
    )
    for entity in entities:
        url = _image_url(entity, entity_states)
        folder = _FOLDERS.get(str(entity.entity_type or "").upper())
        if url and folder:
            refs.append(ImageRef(folder, entity.id, entity.name or "", url))
    avatar = (
        (await db.execute(select(Avatar).where(Avatar.id == state.avatar_id))).scalars().first()
    )
    if avatar is not None and avatar.profile_image:
        refs.append(ImageRef("protagonist", "PROTAGONIST", avatar.name or "", avatar.profile_image))
    return refs


@router.get("/{game_id}/session-debug/images.zip")
async def download_session_images(
    game_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """All scene, NPC and item images of the session (incl. dynamic ones) as a ZIP."""
    state = await _debug_session(db, game_id, current_user)
    refs = await collect_session_images(db, state)
    result = await asyncio.to_thread(build_image_zip, refs)
    if not result.packed:
        raise HTTPException(status_code=404, detail="This session has no stored images yet.")
    filename = f"session_{_clean(state.session_id, 36) or 'images'}_images.zip"
    return StreamingResponse(
        io.BytesIO(result.data),
        media_type="application/zip",
        headers={"Content-Disposition": attachment_disposition(filename)},
    )


async def _debug_session(db: AsyncSession, game_id: str, user: User) -> SessionState:
    """The caller's own session with debug mode on (404 / 403 otherwise)."""
    state = await AdventureLogic.resolve_session_state(db, game_id, user_id=user.id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found.")
    if not (settings.TALEWEAVER_DEBUG_ENABLED or state.is_debug_enabled):
        raise HTTPException(status_code=403, detail="Debug mode is not enabled for this session.")
    return state


@router.get("/{game_id}/session-debug/export/{entity_id}")
async def export_session_entity(
    game_id: str,
    entity_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """One NPC or item of the session (with its image) as a .twe bundle, like the editor's."""
    state = await _debug_session(db, game_id, current_user)
    if not _ENTITY_ID.match(entity_id or ""):
        raise HTTPException(status_code=400, detail="Invalid entity id.")
    entity = (
        (
            await db.execute(
                select(WorldEntity).where(
                    WorldEntity.session_id == state.session_id, WorldEntity.id == entity_id
                )
            )
        )
        .scalars()
        .first()
    )
    if entity is None:
        raise HTTPException(status_code=404, detail="Entity not found.")
    adventure = await load_session_adventure(db, state)
    try:
        data = export_entity_bundle(adventure, entity)
    except EntityBundleError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    kind = "npc" if str(entity.entity_type or "").upper() == "NPC" else "item"
    filename = f"{kind}_{_clean(entity.name or entity.id, 60) or kind}.{BUNDLE_EXTENSION}"
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/zip",
        headers={"Content-Disposition": attachment_disposition(filename)},
    )
