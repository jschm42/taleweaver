"""Editor endpoints for world sections (regions): the section list and scene assignment.

The sections live in ``AdventureTemplate.world_sections`` (``engine/world/sections.py``) and are
mirrored into ``original_manifest["sections"]`` like the audio library. Each scene names its
section in ``WorldScene.section_id``; the manifest's scene entries mirror it, so sessions
started later and exports see the same assignment.

A planned section (``stub``) has no scenes. Assigning scenes to one makes it ``built``;
marking a section with scenes as planned is rejected.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from backend.api.routes.adventures.editing.common import _get_owned_adventure_or_404
from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.engine.world.sections import (
    MAX_SECTIONS,
    is_stub,
    normalize_sections,
    section_id_or_none,
)
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User
from backend.models.world_entity import WorldScene

router = APIRouter(tags=["Editor"])

MAX_ASSIGNED_SCENES = 500


class SectionListUpdateRequest(BaseModel):
    """The complete section list; sections left out are deleted (their scenes become free)."""

    sections: list[dict[str, Any]] = Field(default_factory=list, max_length=MAX_SECTIONS)


class SectionAssignRequest(BaseModel):
    """Moves scenes into a section; an empty ``section_id`` takes them out of any section."""

    section_id: Optional[str] = None
    scene_ids: list[str] = Field(..., min_length=1, max_length=MAX_ASSIGNED_SCENES)


async def template_scenes(db: AsyncSession, template_id: str) -> list[WorldScene]:
    res = await db.execute(
        select(WorldScene).where(
            WorldScene.template_id == template_id, WorldScene.session_id.is_(None)
        )
    )
    return list(res.scalars().all())


def store_sections(adv: AdventureTemplate, sections: list[dict[str, Any]]) -> None:
    """Writes the section list to the column and mirrors it into the manifest."""
    adv.world_sections = sections or None  # type: ignore[assignment]
    flag_modified(adv, "world_sections")
    manifest = deepcopy(adv.original_manifest) if isinstance(adv.original_manifest, dict) else {}
    manifest["sections"] = deepcopy(sections)
    adv.original_manifest = manifest  # type: ignore[assignment]
    flag_modified(adv, "original_manifest")


def sync_manifest_scene_sections(adv: AdventureTemplate, scenes: list[WorldScene]) -> None:
    """Mirrors each scene's section into the manifest's scene entries."""
    if not isinstance(adv.original_manifest, dict):
        return
    manifest = deepcopy(adv.original_manifest)
    by_id = {scene.id: scene.section_id for scene in scenes}
    for entry in manifest.get("scenes") or []:
        if isinstance(entry, dict) and entry.get("id") in by_id:
            entry["section_id"] = by_id[entry["id"]]
    adv.original_manifest = manifest  # type: ignore[assignment]
    flag_modified(adv, "original_manifest")


def resolve_target_section(adv: AdventureTemplate, raw_section_id: Optional[str]) -> Optional[str]:
    """The section scenes go into (a stub becomes built); None takes them out of sections."""
    target = section_id_or_none(raw_section_id)
    if target is None:
        return None
    sections = normalize_sections(adv.world_sections)
    section = next((s for s in sections if s["id"] == target), None)
    if section is None:
        raise HTTPException(status_code=404, detail=f"Section '{target}' not found.")
    if is_stub(section):
        section["status"] = "built"
        store_sections(adv, sections)
    return target


def _check_stubs_are_empty(sections: list[dict[str, Any]], scenes: list[WorldScene]) -> None:
    used = {scene.section_id for scene in scenes if scene.section_id}
    for section in sections:
        if is_stub(section) and section["id"] in used:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Section '{section['id']}' has scenes and cannot be marked as planned. "
                    "Move its scenes to another section first."
                ),
            )


@router.put("/{template_id}/editor/sections")
async def update_editor_sections(
    template_id: str,
    payload: SectionListUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Replaces the section list; scenes of deleted sections lose their section."""
    adv = await _get_owned_adventure_or_404(db, template_id, current_user.id)
    sections = normalize_sections(payload.sections)
    known = {section["id"] for section in sections}
    scenes = await template_scenes(db, template_id)
    cleared = [scene for scene in scenes if scene.section_id and scene.section_id not in known]
    for scene in cleared:
        scene.section_id = None
    _check_stubs_are_empty(sections, scenes)
    store_sections(adv, sections)
    sync_manifest_scene_sections(adv, scenes)
    await db.commit()
    return {"sections": sections, "cleared_scene_ids": sorted(scene.id for scene in cleared)}


@router.post("/{template_id}/editor/sections/assign")
async def assign_scenes_to_section(
    template_id: str,
    payload: SectionAssignRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Moves scenes into a section (or out of every section)."""
    adv = await _get_owned_adventure_or_404(db, template_id, current_user.id)
    wanted = {str(raw or "").strip().upper() for raw in payload.scene_ids} - {""}
    scenes = await template_scenes(db, template_id)
    chosen = [scene for scene in scenes if scene.id in wanted]
    missing = sorted(wanted - {scene.id for scene in chosen})
    if missing:
        raise HTTPException(status_code=404, detail=f"Scenes not found: {', '.join(missing)}")
    target = resolve_target_section(adv, payload.section_id)
    for scene in chosen:
        scene.section_id = target
    sync_manifest_scene_sections(adv, scenes)
    await db.commit()
    return {
        "section_id": target,
        "scene_ids": sorted(scene.id for scene in chosen),
        "sections": normalize_sections(adv.world_sections),
    }


def patched_section_id(
    adv: Optional[AdventureTemplate], raw_section_id: Any, current: Optional[str]
) -> Optional[str]:
    """Section for an AI fix patch: like the editor, but an unknown id keeps the current one."""
    if adv is None:
        return current
    try:
        return resolve_target_section(adv, None if raw_section_id is None else str(raw_section_id))
    except HTTPException:
        return current
