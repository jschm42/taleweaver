"""Editor endpoint that writes a region's description or brief with the small model.

``POST /{template_id}/editor/sections/generate-text`` takes the field and the Regions page
draft (the region plus the full region list, so unsaved regions work) and returns the text.
Nothing is stored: the editor puts the text into the draft, where the author reviews and saves
it. Prompt: ``engine/world/section_text.py``.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.editing.common import _get_owned_adventure_or_404
from backend.api.routes.adventures.templates import _small_model_choice, _tone_name
from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.core.llm_router import GameMasterLLM
from backend.engine.world.section_text import (
    SECTION_TEXT_SYSTEM_PROMPT,
    build_section_text_prompt,
    clean_section_text,
)
from backend.engine.world.sections import normalize_sections, section_id_or_none
from backend.models.user import User
from backend.models.world_entity import WorldScene

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Editor"])


class SectionTextRequest(BaseModel):
    field: Literal["description", "brief"]
    section_id: str = Field(..., min_length=1, max_length=100)
    sections: list[dict[str, Any]] = Field(..., min_length=1, max_length=64)


class SectionTextResponse(BaseModel):
    generated_text: str


async def _region_scenes(
    db: AsyncSession, template_id: str, section_id: str
) -> list[tuple[str, str]]:
    rows = await db.execute(
        select(WorldScene.label, WorldScene.description).where(
            (WorldScene.template_id == template_id) & (WorldScene.section_id == section_id)
        )
    )
    return [(label or "", description or "") for label, description in rows.all()]


@router.post("/{template_id}/editor/sections/generate-text", response_model=SectionTextResponse)
async def generate_section_text(
    template_id: str,
    payload: SectionTextRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SectionTextResponse:
    """A description or brief for one region of the draft (nothing is stored)."""
    adv = await _get_owned_adventure_or_404(db, template_id, current_user.id)
    sections = normalize_sections(payload.sections)
    section_id = section_id_or_none(payload.section_id)
    section = next((s for s in sections if s["id"] == section_id), None)
    if section is None:
        raise HTTPException(status_code=400, detail="The region is not in the draft.")
    scenes = await _region_scenes(db, template_id, section["id"])
    provider, model = _small_model_choice(current_user)
    llm = GameMasterLLM(user=current_user, provider=provider, model_category="small")
    try:
        text = await llm.aexecute_simple_task(
            system_prompt=SECTION_TEXT_SYSTEM_PROMPT.format(
                language=adv.language or "English", tone=_tone_name(adv)
            ),
            user_prompt=build_section_text_prompt(adv, section, sections, scenes, payload.field),
            model=model,
        )
    except Exception as exc:
        logger.error("Region %s generation failed for %s: %s", payload.field, template_id, exc)
        raise HTTPException(
            status_code=500, detail=f"Failed to write the {payload.field}."
        ) from exc
    return SectionTextResponse(generated_text=clean_section_text(text, payload.field))
