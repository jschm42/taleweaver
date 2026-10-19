"""Editor endpoints to export/import a protagonist, NPC, or item as a ``.twe`` bundle."""

from __future__ import annotations

import io
import re
from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.editor import (
    _get_owned_adventure_or_404,
    _get_template_avatar,
    _sanitize_object_id,
)
from backend.api.routes.adventures.entity_transfer_service import (
    export_entity_bundle,
    export_protagonist_bundle,
    import_entity_bundle,
    import_protagonist_bundle,
)
from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.engine.entity_bundle import (
    BUNDLE_EXTENSION,
    MAX_BUNDLE_BYTES,
    EntityBundleError,
    unpack_entity_bundle,
)
from backend.models.user import User
from backend.models.world_entity import WorldEntity

router = APIRouter(tags=["Editor"])

_FILENAME_UNSAFE = re.compile(r"[^A-Za-z0-9_-]+")


def _bundle_response(data: bytes, kind: str, label: str) -> StreamingResponse:
    safe_label = _FILENAME_UNSAFE.sub("_", label).strip("_")[:60] or kind
    filename = f"{kind}_{safe_label}.{BUNDLE_EXTENSION}"
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{template_id}/editor/transfer/protagonist")
async def export_protagonist(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Downloads the protagonist (profile, stats, portrait) as a .twe bundle."""
    adv = await _get_owned_adventure_or_404(db, template_id, current_user.id)
    avatar = await _get_template_avatar(db, template_id)
    if not avatar:
        raise HTTPException(status_code=404, detail="Protagonist not found")
    return _bundle_response(export_protagonist_bundle(adv, avatar), "protagonist", avatar.name)


@router.get("/{template_id}/editor/transfer/entity/{entity_id}")
async def export_entity(
    template_id: str,
    entity_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Downloads a single NPC or item (including its image) as a .twe bundle."""
    adv = await _get_owned_adventure_or_404(db, template_id, current_user.id)
    entity_id = _sanitize_object_id(entity_id, "entity_id")
    res = await db.execute(
        select(WorldEntity).where(
            WorldEntity.template_id == template_id,
            WorldEntity.session_id.is_(None),
            WorldEntity.id == entity_id,
        )
    )
    entity = res.scalars().first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    try:
        data = export_entity_bundle(adv, entity)
    except EntityBundleError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    kind = "npc" if entity.entity_type == "NPC" else "item"
    return _bundle_response(data, kind, entity.name or entity.id)


@router.post("/{template_id}/editor/transfer/import")
async def import_entity(
    template_id: str,
    expected_kind: Optional[Literal["protagonist", "npc", "item"]] = Form(default=None),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Imports a .twe bundle. NPCs/items are added as new entities; a protagonist replaces the current one."""
    adv = await _get_owned_adventure_or_404(db, template_id, current_user.id)
    content = await file.read(MAX_BUNDLE_BYTES + 1)
    try:
        bundle = unpack_entity_bundle(content)
    except EntityBundleError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if expected_kind and bundle.kind != expected_kind:
        raise HTTPException(
            status_code=400,
            detail=f"This file contains a {bundle.kind}, but a {expected_kind} was expected.",
        )

    importer = import_protagonist_bundle if bundle.kind == "protagonist" else import_entity_bundle
    try:
        result = await importer(db, adv, bundle)
    except EntityBundleError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "status": "success",
        "kind": result.kind,
        "entity_id": result.entity_id,
        "name": result.name,
        "has_image": bool(bundle.image_bytes),
        "warnings": result.warnings,
    }
