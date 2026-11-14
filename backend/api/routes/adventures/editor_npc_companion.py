"""Editor endpoint for an NPC's companion (sidekick) settings, see ``backend/engine/party``."""

from __future__ import annotations

from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from backend.api.routes.adventures.editor import _get_owned_adventure_or_404, _sanitize_editor_id
from backend.api.routes.adventures.editor_npc_combat import _update_manifest
from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.engine.party.companion_config import COMPANION_KEY, normalize_companion
from backend.models.user import User
from backend.models.world_entity import WorldEntity

router = APIRouter(tags=["Editor"])


class CompanionSettings(BaseModel):
    recruitable: bool = True
    starts_in_party: bool = False
    tactics: Literal["BALANCED", "OFFENSIVE", "DEFENSIVE", "SUPPORT"] = "BALANCED"
    banter: Literal["NORMAL", "QUIET", "CHATTY"] = "NORMAL"
    downed_recovery: float = Field(default=0.25, gt=0, le=1)


class NpcCompanionUpdateRequest(BaseModel):
    npc_id: str
    # None turns the NPC back into an ordinary NPC.
    companion: Optional[CompanionSettings] = None


@router.put("/{template_id}/editor/npc-companion")
async def update_npc_companion(
    template_id: str,
    payload: NpcCompanionUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Makes an NPC a companion (or an ordinary NPC again) and stores its settings."""
    adv = await _get_owned_adventure_or_404(db, template_id, current_user.id)
    npc_id = _sanitize_editor_id(payload.npc_id, "npc_id")
    res = await db.execute(
        select(WorldEntity).where(
            WorldEntity.template_id == template_id,
            WorldEntity.session_id.is_(None),
            WorldEntity.entity_type == "NPC",
            WorldEntity.id == npc_id,
        )
    )
    npc = res.scalars().first()
    if not npc:
        raise HTTPException(status_code=404, detail="NPC not found")

    raw = payload.companion.model_dump() if payload.companion else None
    values: dict[str, Any] = {COMPANION_KEY: normalize_companion(raw)}
    npc.metadata_json = {**(npc.metadata_json or {}), **values}
    flag_modified(npc, "metadata_json")
    _update_manifest(adv, npc_id, values)
    await db.commit()
    return {"status": "success", **values}
