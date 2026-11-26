"""Editor endpoints for the world map tiles (``AdventureTemplate.world_map_layout``).

The world map is a grid of 16:9 image tiles (``engine/world/world_map_layout.py``). A tile is
addressed by ``col`` / ``row``; a tile right of or below the grid grows it by one.

- ``GET    .../map-image/prompt?col=&row=``: the tile's default prompt plus the adventure's
  image style and tone, so the author can edit the prompt.
- ``POST   .../map-image {col, row, prompt, use_style, use_tone}``: draws a tile (image model).
- ``POST   .../map-image/upload`` (form: ``col``, ``row``, ``file``): an own image as a tile.
- ``DELETE .../map-image?col=&row=``: removes a tile; empty last columns/rows are dropped.

Growing or shrinking the grid rescales the region positions, so every region stays over the
same spot of the drawn map. Spec: docs/specs/world_sections.md (phase 4).
"""

from __future__ import annotations

import copy
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.editing.common import _get_owned_adventure_or_404
from backend.api.routes.adventures.editing.section_crud import store_sections
from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.core.style_catalog import resolve_style_instruction, resolve_tone_instruction
from backend.engine.world.sections import normalize_sections
from backend.engine.world.world_map_layout import (
    MAX_GRID,
    compose_map_prompt,
    grid_size,
    layout_or_none,
    normalize_layout,
    place_tile,
    remove_tile,
    rescale_sections,
    tile_prompt,
)
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User

router = APIRouter(tags=["Editor"])
_BASE = "/{template_id}/editor/sections/map-image"


class MapTileRequest(BaseModel):
    """Empty ``prompt`` = the tile's default prompt from the regions."""

    col: int = Field(default=0, ge=0, le=MAX_GRID - 1)
    row: int = Field(default=0, ge=0, le=MAX_GRID - 1)
    prompt: str | None = Field(default=None, max_length=4000)
    use_style: bool = True
    use_tone: bool = True


def _style(adv: AdventureTemplate, user: User) -> str:
    return resolve_style_instruction(
        adv.selected_image_styles, getattr(user, "image_styles_catalog", None)
    )


def _tone(adv: AdventureTemplate, user: User) -> str:
    return resolve_tone_instruction(adv.selected_tone, getattr(user, "tone_catalog", None) or [])


async def _adventure_with_regions(
    db: AsyncSession, template_id: str, user: User
) -> AdventureTemplate:
    adv = await _get_owned_adventure_or_404(db, template_id, user.id)
    if not normalize_sections(adv.world_sections):
        raise HTTPException(status_code=400, detail="Add regions before drawing the world map.")
    return adv


def _store_layout(adv: AdventureTemplate, layout: dict[str, Any]) -> dict[str, Any]:
    """Saves the new layout; region positions follow a changed grid size."""
    before, after = grid_size(adv.world_map_layout), grid_size(layout)
    if before != after:
        sections = normalize_sections(adv.world_sections)
        store_sections(adv, rescale_sections(sections, before, after))
    adv.world_map_layout = layout_or_none(layout)
    return {"world_map_layout": adv.world_map_layout}


def _placed(adv: AdventureTemplate, col: int, row: int, url: str) -> dict[str, Any]:
    try:
        return place_tile(adv.world_map_layout, col, row, url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(f"{_BASE}/prompt")
async def get_world_map_prompt(
    template_id: str,
    col: int = Query(default=0, ge=0, le=MAX_GRID - 1),
    row: int = Query(default=0, ge=0, le=MAX_GRID - 1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """The default prompt of a tile and the style and tone that can be added to it."""
    adv = await _adventure_with_regions(db, template_id, current_user)
    return {
        "prompt": tile_prompt(adv, normalize_layout(adv.world_map_layout), col, row),
        "style": _style(adv, current_user),
        "tone": _tone(adv, current_user),
    }


@router.post(_BASE)
async def generate_world_map_tile(
    template_id: str,
    payload: MapTileRequest | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Draws one tile of the world map (image model) and stores it."""
    from backend.engine.media.media_engine import MediaEngine

    request = payload or MapTileRequest()
    adv = await _adventure_with_regions(db, template_id, current_user)
    _placed(adv, request.col, request.row, "check")  # validates the cell before the slow call
    default = tile_prompt(adv, normalize_layout(adv.world_map_layout), request.col, request.row)
    tone = _tone(adv, current_user) if request.use_tone else ""
    prompt = compose_map_prompt((request.prompt or "").strip() or default, tone)
    keys = current_user.encrypted_api_keys
    try:
        url = await MediaEngine.generate_scene_image(
            prompt,
            template_id,
            {"t2i_settings": current_user.t2i_settings, "adventure_title": adv.title},
            copy.copy(keys) if keys else {},
            style_instruction=_style(adv, current_user) if request.use_style else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not url:
        raise HTTPException(status_code=502, detail="The image model returned no image.")
    result = _store_layout(adv, _placed(adv, request.col, request.row, url))
    await db.commit()
    return {**result, "prompt": prompt}


@router.post(f"{_BASE}/upload")
async def upload_world_map_tile(
    template_id: str,
    col: int = Form(default=0, ge=0, le=MAX_GRID - 1),
    row: int = Form(default=0, ge=0, le=MAX_GRID - 1),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """An own image as a tile (PNG, JPEG or WEBP; checked like every visual upload)."""
    from backend.api.routes.adventures.assets import (
        _store_uploaded_visual,
        _validate_upload_content,
    )

    adv = await _get_owned_adventure_or_404(db, template_id, current_user.id)
    _placed(adv, col, row, "check")
    content = await file.read()
    _validate_upload_content(content, file.content_type, "world_map")
    url = _store_uploaded_visual(
        adv.id, "world_map", file.content_type, f"tile_{col}_{row}", content
    )
    result = _store_layout(adv, _placed(adv, col, row, url))
    await db.commit()
    return result


@router.delete(_BASE)
async def remove_world_map_tile(
    template_id: str,
    col: int = Query(default=0, ge=0, le=MAX_GRID - 1),
    row: int = Query(default=0, ge=0, le=MAX_GRID - 1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Removes one tile (the file stays in the adventure's library)."""
    adv = await _get_owned_adventure_or_404(db, template_id, current_user.id)
    result = _store_layout(adv, remove_tile(adv.world_map_layout, col, row))
    await db.commit()
    return result
