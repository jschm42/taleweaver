"""Editor endpoints that generate regions with the World-Builder LLM.

- ``POST /{template_id}/editor/sections/{section_id}/generate``: builds a planned region in the
  background. The section is ``generating`` meanwhile; afterwards it is ``built``, or back to
  ``stub`` with its ``generation_error``. The editor polls its assets to see the result.
- ``POST /{template_id}/editor/sections/plan``: returns a proposal (campaign outline plus
  planned regions). Nothing is stored; the author reviews and saves it on the Regions page.
- ``POST`` / ``DELETE /{template_id}/editor/sections/map-image``: draws (or removes) the
  world map image from the regions (``engine/world/section_map_image.py``).

Spec: docs/specs/world_sections.md (9.3-9.4).
"""

from __future__ import annotations

import asyncio
import copy
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.editing.common import _get_owned_adventure_or_404
from backend.api.routes.adventures.editing.section_crud import store_sections
from backend.core import database
from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.core.global_settings import apply_global_settings
from backend.engine.world.section_generator import (
    SectionGenerationError,
    generate_section,
    plan_sections,
)
from backend.engine.world.section_map_image import world_map_prompt
from backend.engine.world.sections import normalize_sections, section_id_or_none
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Editor"])

# Running generations (template id, section id); keeps the tasks referenced.
_RUNNING: dict[tuple[str, str], asyncio.Task[Any]] = {}
MAX_ERROR_LENGTH = 600


class SectionGenerateRequest(BaseModel):
    brief: str | None = Field(default=None, max_length=4000)


class SectionPlanRequest(BaseModel):
    count: int = Field(default=3, ge=1, le=8)
    direction: str = Field(default="", max_length=2000)


def session_factory() -> Any:
    """The session factory of background generations (tests swap it)."""
    return database.AsyncSessionLocal


def _set_status(
    adv: AdventureTemplate, section_id: str, status: str, error: str = "", brief: str | None = None
) -> None:
    sections = normalize_sections(adv.world_sections)
    for section in sections:
        if section["id"] != section_id:
            continue
        section["status"] = status
        section["generation_error"] = error[:MAX_ERROR_LENGTH]
        if brief is not None:
            section["brief"] = brief.strip()
    store_sections(adv, sections)


async def _store_notes(
    db: AsyncSession, template_id: str, section_id: str, notes: list[str]
) -> None:
    adv = await db.get(AdventureTemplate, template_id)
    if adv is None:
        return
    sections = normalize_sections(adv.world_sections)
    for section in sections:
        if section["id"] == section_id:
            section["generation_notes"] = notes
    store_sections(adv, sections)
    await db.commit()


async def _findings(db: AsyncSession, template_id: str) -> dict[Any, Any]:
    """Signatures of the adventure's validation findings (lazy import: the editor router
    imports this module, and the change-set module imports the editor endpoints)."""
    from backend.api.routes.adventures.editing.change_set import structural_findings
    from backend.api.routes.adventures.editing.validation import _finding_signature

    return {_finding_signature(f): f for f in await structural_findings(db, template_id)}


async def _new_findings(db: AsyncSession, template_id: str, baseline: set[Any]) -> list[str]:
    """Validation findings the generated region introduced (the Validation page has details)."""
    after = await _findings(db, template_id)
    return [f"{f.severity}: {f.message}" for key, f in after.items() if key not in baseline]


async def run_generation(template_id: str, section_id: str, user_id: str) -> None:
    """The background job: generate and merge, or put the region back to planned."""
    async with session_factory()() as db:
        try:
            user = await apply_global_settings(db, await db.get(User, user_id))
            baseline = set(await _findings(db, template_id))
            notes = await generate_section(db, template_id, section_id, user)
            notes.extend(await _new_findings(db, template_id, baseline))
            await _store_notes(db, template_id, section_id, notes)
        except Exception as exc:
            await db.rollback()
            detail = (
                str(exc)
                if isinstance(exc, (SectionGenerationError, ValueError))
                else "The generation failed."
            )
            logger.warning("Region generation %s/%s failed: %s", template_id, section_id, exc)
            adv = await db.get(AdventureTemplate, template_id)
            if adv is not None:
                _set_status(adv, section_id, "stub", detail)
                await db.commit()
        finally:
            _RUNNING.pop((template_id, section_id), None)


def _planned_section(adv: AdventureTemplate, section_id: str) -> dict[str, Any]:
    section = next(
        (s for s in normalize_sections(adv.world_sections) if s["id"] == section_id), None
    )
    if section is None:
        raise HTTPException(status_code=404, detail=f"Region '{section_id}' not found.")
    if section["status"] == "built":
        raise HTTPException(status_code=409, detail="Only planned regions can be generated.")
    return section


@router.post("/{template_id}/editor/sections/{section_id}/generate", status_code=202)
async def start_section_generation(
    template_id: str,
    section_id: str,
    payload: SectionGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Starts generating a planned region; poll the editor assets for the result."""
    adv = await _get_owned_adventure_or_404(db, template_id, current_user.id)
    section_key = section_id_or_none(section_id) or ""
    _planned_section(adv, section_key)
    if (template_id, section_key) in _RUNNING:
        raise HTTPException(status_code=409, detail="This region is already being generated.")
    _set_status(adv, section_key, "generating", brief=payload.brief)
    await db.commit()
    task = asyncio.create_task(run_generation(template_id, section_key, current_user.id))
    _RUNNING[(template_id, section_key)] = task
    return {"status": "generating", "section_id": section_key}


@router.post("/{template_id}/editor/sections/plan")
async def plan_editor_sections(
    template_id: str,
    payload: SectionPlanRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """A proposal of planned regions and a campaign outline (nothing is stored)."""
    await _get_owned_adventure_or_404(db, template_id, current_user.id)
    try:
        return await plan_sections(db, template_id, current_user, payload.count, payload.direction)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{template_id}/editor/sections/map-image")
async def generate_world_map_image(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Draws the world map image from the regions and their positions (image model)."""
    from backend.core.style_catalog import resolve_style_instruction
    from backend.engine.media.media_engine import MediaEngine

    adv = await _get_owned_adventure_or_404(db, template_id, current_user.id)
    if not normalize_sections(adv.world_sections):
        raise HTTPException(status_code=400, detail="Add regions before drawing the world map.")
    keys = current_user.encrypted_api_keys
    try:
        url = await MediaEngine.generate_scene_image(
            world_map_prompt(adv),
            template_id,
            {"t2i_settings": current_user.t2i_settings},
            copy.copy(keys) if keys else {},
            style_instruction=resolve_style_instruction(
                adv.selected_image_styles, current_user.image_styles_catalog
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not url:
        raise HTTPException(status_code=502, detail="The image model returned no image.")
    adv.world_map_image_url = url
    await db.commit()
    return {"world_map_image_url": url}


@router.delete("/{template_id}/editor/sections/map-image")
async def remove_world_map_image(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Removes the world map image (the file stays in the adventure's library)."""
    adv = await _get_owned_adventure_or_404(db, template_id, current_user.id)
    adv.world_map_image_url = None
    await db.commit()
    return {"world_map_image_url": None}
