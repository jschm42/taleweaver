"""Editor endpoint that discards a region the Region Builder built.

``POST /{template_id}/editor/sections/{section_id}/discard`` removes what the region added and
plans it again (``engine/manifest_apply/section_discard.py``). Spec:
docs/specs/region_builder.md (phase D).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.editing.common import _get_owned_adventure_or_404
from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.engine.manifest_apply.section_discard import SectionDiscardError, discard_section
from backend.engine.world.sections import section_id_or_none
from backend.models.user import User

router = APIRouter(tags=["Editor"])


@router.post("/{template_id}/editor/sections/{section_id}/discard")
async def discard_editor_section(
    template_id: str,
    section_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Takes a built region out again; it becomes a planned region that can be rebuilt."""
    await _get_owned_adventure_or_404(db, template_id, current_user.id)
    try:
        removed = await discard_section(db, template_id, section_id_or_none(section_id) or "")
    except SectionDiscardError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"status": "stub", "removed": removed}
