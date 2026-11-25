"""Editor endpoints for the adventure's cut-scenes (``AdventureTemplate.cutscenes``).

- ``PUT  .../editor/cutscenes {cutscenes, intro_cutscene_id}``: stores the whole list
  (normalized) and the adventure's intro cut-scene (shown when a session starts).
- ``POST .../editor/cutscenes/image-prompt {title, text, image_style}``: the default prompt of a
  slide plus the style (the cut-scene's override, else the adventure's) and tone.
- ``POST .../editor/cutscenes/image {prompt, image_style, use_style, use_tone, quality}``: draws
  a slide image with the simple (LQ) or advanced (HQ) image model and returns its URL; the editor
  puts it into its draft and saves with the PUT.
- ``POST .../editor/cutscenes/image/upload`` (form: ``file``): an own slide image.

Spec: docs/specs/cutscenes.md.
"""

from __future__ import annotations

import copy
import uuid
from copy import deepcopy
from typing import Any, Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from backend.api.routes.adventures.editing.common import _get_owned_adventure_or_404
from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.core.style_catalog import resolve_tone_instruction
from backend.engine.cutscenes.images import default_slide_prompt, style_instruction
from backend.engine.cutscenes.library import (
    MAX_STYLE_CHARS,
    cutscene_ref_or_none,
    normalize_cutscenes,
)
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User

router = APIRouter(tags=["Editor"])
_BASE = "/{template_id}/editor/cutscenes"


class CutscenesUpdate(BaseModel):
    cutscenes: list[dict[str, Any]] = Field(default_factory=list)
    # Shown right after a new session starts; must name one of ``cutscenes``.
    intro_cutscene_id: str | None = Field(default=None, max_length=40)
    # Shown when the adventure is won (before the ending card); must name one of ``cutscenes``.
    win_cutscene_id: str | None = Field(default=None, max_length=40)
    # Shown on game over (before the ending card); must name one of ``cutscenes``.
    game_over_cutscene_id: str | None = Field(default=None, max_length=40)


class SlidePromptRequest(BaseModel):
    title: str = Field(default="", max_length=200)
    text: str = Field(default="", max_length=2000)
    image_style: str = Field(default="", max_length=MAX_STYLE_CHARS)


class SlideImageRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=4000)
    image_style: str = Field(default="", max_length=MAX_STYLE_CHARS)
    use_style: bool = True
    use_tone: bool = False
    # "simple" = the fast LQ image model, "advanced" = the high-fidelity HQ model.
    quality: Literal["simple", "advanced"] = "advanced"


def _style(adv: AdventureTemplate, user: User, image_style: str) -> str:
    catalog = getattr(user, "image_styles_catalog", None)
    return style_instruction(image_style, adv.selected_image_styles, catalog)


def _tone(adv: AdventureTemplate, user: User) -> str:
    return resolve_tone_instruction(adv.selected_tone, getattr(user, "tone_catalog", None) or [])


def store_cutscenes(adv: AdventureTemplate, cutscenes: Any) -> list[dict[str, Any]]:
    """Saves the normalized list and mirrors it into ``original_manifest``."""
    adv.cutscenes = normalize_cutscenes(cutscenes) or None  # type: ignore[assignment]
    if isinstance(adv.original_manifest, dict):
        manifest = deepcopy(adv.original_manifest)
        manifest["cutscenes"] = deepcopy(adv.cutscenes or [])
        adv.original_manifest = manifest  # type: ignore[assignment]
        flag_modified(adv, "original_manifest")
    return list(adv.cutscenes or [])


@router.put(_BASE)
async def update_cutscenes(
    template_id: str,
    payload: CutscenesUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    adv = await _get_owned_adventure_or_404(db, template_id, current_user.id)
    cutscenes = store_cutscenes(adv, payload.cutscenes)
    intro = cutscene_ref_or_none(payload.intro_cutscene_id, cutscenes)
    win = cutscene_ref_or_none(payload.win_cutscene_id, cutscenes)
    game_over = cutscene_ref_or_none(payload.game_over_cutscene_id, cutscenes)
    adv.intro_cutscene_id = intro  # type: ignore[assignment]
    adv.win_cutscene_id = win  # type: ignore[assignment]
    adv.game_over_cutscene_id = game_over  # type: ignore[assignment]
    await db.commit()
    return {
        "cutscenes": cutscenes,
        "intro_cutscene_id": intro,
        "win_cutscene_id": win,
        "game_over_cutscene_id": game_over,
    }


@router.post(f"{_BASE}/image-prompt")
async def get_slide_prompt(
    template_id: str,
    payload: SlidePromptRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """The default prompt of a slide and the style and tone that can be added to it."""
    adv = await _get_owned_adventure_or_404(db, template_id, current_user.id)
    return {
        "prompt": default_slide_prompt(str(adv.title or ""), payload.title, payload.text),
        "style": _style(adv, current_user, payload.image_style),
        "tone": _tone(adv, current_user),
    }


@router.post(f"{_BASE}/image")
async def generate_slide_image(
    template_id: str,
    payload: SlideImageRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Draws one slide image (image model); the URL goes into the editor's draft."""
    from backend.engine.media.media_engine import MediaEngine

    adv = await _get_owned_adventure_or_404(db, template_id, current_user.id)
    tone = _tone(adv, current_user) if payload.use_tone else ""
    prompt = f"{payload.prompt.strip()} Mood: {tone}" if tone else payload.prompt.strip()
    keys = current_user.encrypted_api_keys
    try:
        url = await MediaEngine.generate_scene_image(
            prompt,
            template_id,
            {"t2i_settings": current_user.t2i_settings, "adventure_title": adv.title},
            copy.copy(keys) if keys else {},
            style_instruction=_style(adv, current_user, payload.image_style)
            if payload.use_style
            else None,
            use_advanced_model=payload.quality == "advanced",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not url:
        raise HTTPException(status_code=502, detail="The image model returned no image.")
    return {"url": url, "prompt": prompt}


@router.post(f"{_BASE}/image/upload")
async def upload_slide_image(
    template_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """An own slide image (PNG, JPEG or WEBP; checked like every visual upload)."""
    from backend.api.routes.adventures.assets import (
        _store_uploaded_visual,
        _validate_upload_content,
    )

    adv = await _get_owned_adventure_or_404(db, template_id, current_user.id)
    content = await file.read()
    _validate_upload_content(content, file.content_type, "cutscene")
    url = _store_uploaded_visual(
        adv.id, "cutscene", file.content_type, f"slide_{uuid.uuid4().hex[:12]}", content
    )
    return {"url": url}
