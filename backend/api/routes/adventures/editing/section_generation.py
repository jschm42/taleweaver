"""Editor endpoints that generate regions with the World-Builder LLM.

- ``POST /{template_id}/editor/sections/{section_id}/generate``: builds a planned region in the
  background. The section is ``generating`` meanwhile; afterwards it is ``built``, or back to
  ``stub`` with its ``generation_error``. The editor polls its assets to see the result.
- ``POST /{template_id}/editor/sections/{section_id}/generate/preview``: the prompt's blocks with
  token estimates for the given context options, without an LLM call.
- ``POST /{template_id}/editor/sections/plan``: returns a proposal of planned regions from
  the adventure's plot. Nothing is stored; the author reviews and saves it on the Regions page.

Spec: docs/specs/world_sections.md (9.3-9.4), docs/specs/region_builder.md (8).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.editing.common import _get_owned_adventure_or_404
from backend.api.routes.adventures.editing.section_builder_models import SectionGenerateRequest
from backend.api.routes.adventures.editing.section_crud import store_sections
from backend.core import database
from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.core.global_settings import apply_global_settings
from backend.engine.world.section_generator import (
    SectionGenerationError,
    generate_section,
    normalize_settings,
    plan_sections,
    preview_section_prompt,
)
from backend.engine.world.sections import normalize_sections, section_id_or_none
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Editor"])

# Running generations (template id, section id); keeps the tasks referenced.
_RUNNING: dict[tuple[str, str], asyncio.Task[Any]] = {}
MAX_ERROR_LENGTH = 600


class SectionPlanRequest(BaseModel):
    count: int = Field(default=3, ge=1, le=8)
    direction: str = Field(default="", max_length=2000)


def session_factory() -> Any:
    """The session factory of background generations (tests swap it)."""
    return database.AsyncSessionLocal


def _set_status(
    adv: AdventureTemplate,
    section_id: str,
    status: str,
    error: str = "",
    brief: str | None = None,
    settings: dict[str, Any] | None = None,
) -> None:
    sections = normalize_sections(adv.world_sections)
    for section in sections:
        if section["id"] != section_id:
            continue
        section["status"] = status
        section["generation_error"] = error[:MAX_ERROR_LENGTH]
        if brief is not None:
            section["brief"] = brief.strip()
        if settings is not None:
            section["generation_settings"] = settings
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


async def _fix_region(db: AsyncSession, template_id: str, user: User, baseline: set[Any]) -> str:
    """Validate & fix afterwards, limited to the findings the region introduced (structural
    checks only; each fix is one LLM call, capped like a new adventure's pass)."""
    from backend.api.routes.adventures.editing.auto_fix import run_post_generation_auto_fix

    try:
        report = await run_post_generation_auto_fix(
            db, template_id, user, include_ai=False, skip_signatures=baseline
        )
    except Exception:
        logger.exception("Region auto-fix failed for %s", template_id)
        await db.rollback()
        return "Validate & fix did not finish; check the Validation page."
    return f"Validate & fix: {report.fixed} of {report.findings_total} new finding(s) fixed."


async def run_generation(
    template_id: str, section_id: str, user_id: str, settings: dict[str, Any] | None = None
) -> None:
    """The background job: generate and merge, or put the region back to planned."""
    async with session_factory()() as db:
        try:
            user = await apply_global_settings(db, await db.get(User, user_id))
            baseline = set(await _findings(db, template_id))
            notes = await generate_section(db, template_id, section_id, user, settings)
            if normalize_settings(settings)["options"]["auto_validate_and_fix"]:
                notes.append(await _fix_region(db, template_id, user, baseline))
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


async def _reject_blueprint_errors(
    db: AsyncSession, template_id: str, section_id: str, payload: SectionGenerateRequest
) -> None:
    """A region blueprint with errors is refused before the job starts (400)."""
    report = await preview_section_prompt(db, template_id, section_id, None, payload.brief)
    issues = (report.get("blueprint") or {}).get("issues") or []
    errors = [f"line {i['line']}: {i['message']}" for i in issues if i["severity"] == "error"]
    if errors:
        raise HTTPException(
            status_code=400, detail="The region blueprint has errors: " + "; ".join(errors[:5])
        )


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
    await _reject_blueprint_errors(db, template_id, section_key, payload)
    _set_status(
        adv, section_key, "generating", brief=payload.brief, settings=payload.stored_settings()
    )
    await db.commit()
    task = asyncio.create_task(
        run_generation(template_id, section_key, current_user.id, payload.settings())
    )
    _RUNNING[(template_id, section_key)] = task
    return {"status": "generating", "section_id": section_key}


@router.post("/{template_id}/editor/sections/{section_id}/generate/preview")
async def preview_section_generation(
    template_id: str,
    section_id: str,
    payload: SectionGenerateRequest,
    include_prompt: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Blocks and token estimates of the region prompt for these settings (no LLM call)."""
    adv = await _get_owned_adventure_or_404(db, template_id, current_user.id)
    section_key = section_id_or_none(section_id) or ""
    _planned_section(adv, section_key)
    return await preview_section_prompt(
        db,
        template_id,
        section_key,
        payload.settings(),
        payload.brief,
        include_prompt,
        gateways=payload.gateways,
    )


@router.post("/{template_id}/editor/sections/plan")
async def plan_editor_sections(
    template_id: str,
    payload: SectionPlanRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """A proposal of planned regions from the adventure's plot (nothing is stored)."""
    await _get_owned_adventure_or_404(db, template_id, current_user.id)
    try:
        return await plan_sections(db, template_id, current_user, payload.count, payload.direction)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
