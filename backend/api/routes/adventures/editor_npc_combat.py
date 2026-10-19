"""Editor endpoint for NPC combat behaviour: attack on sight, attack trigger rules, special chance."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from backend.api.routes.adventures.editor import _get_owned_adventure_or_404, _sanitize_editor_id
from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.engine.scripting.sandbox import SafeAstInterpreter
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User
from backend.models.world_entity import WorldEntity

router = APIRouter(tags=["Editor"])

RULE_ID_FIELDS = ("required_item_id", "required_scene_id", "required_defeated_npc_id")


class AttackTrigger(BaseModel):
    required_item_id: Optional[str] = None
    required_scene_id: Optional[str] = None
    required_defeated_npc_id: Optional[str] = None
    guard_expression: Optional[str] = Field(default=None, max_length=2000)


class NpcCombatUpdateRequest(BaseModel):
    npc_id: str
    attack_mode: Literal["PASSIVE", "ATTACK_ON_SIGHT"] = "PASSIVE"
    attack_trigger: Optional[AttackTrigger] = None
    special_chance: int = Field(default=40, ge=0, le=100)


def _clean_trigger(trigger: Optional[AttackTrigger]) -> dict[str, Any] | None:
    """Normalizes the trigger and rejects unsafe IDs or invalid guard syntax."""
    if trigger is None:
        return None
    cleaned: dict[str, Any] = {}
    for field in RULE_ID_FIELDS:
        value = str(getattr(trigger, field) or "").strip()
        if value:
            cleaned[field] = _sanitize_editor_id(value, field)
    guard = str(trigger.guard_expression or "").strip()
    errors = SafeAstInterpreter.check_expression_syntax(guard)
    if errors:
        raise HTTPException(status_code=400, detail="guard_expression: " + "; ".join(errors))
    if guard:
        cleaned["guard_expression"] = guard
    return cleaned or None


def _update_manifest(adv: AdventureTemplate, npc_id: str, values: dict[str, Any]) -> None:
    if not isinstance(adv.original_manifest, dict):
        return
    manifest = deepcopy(adv.original_manifest)
    for npc in manifest.get("npcs") or []:
        if isinstance(npc, dict) and npc.get("id") == npc_id:
            npc.update(values)
    adv.original_manifest = manifest
    flag_modified(adv, "original_manifest")


@router.put("/{template_id}/editor/npc-combat")
async def update_npc_combat(
    template_id: str,
    payload: NpcCombatUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Stores how and when an NPC attacks the protagonist."""
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

    values = {
        "attack_mode": payload.attack_mode,
        "attack_trigger": _clean_trigger(payload.attack_trigger),
        "special_chance": payload.special_chance,
    }
    npc.metadata_json = {**(npc.metadata_json or {}), **values}
    flag_modified(npc, "metadata_json")
    _update_manifest(adv, npc_id, values)
    await db.commit()
    return {"status": "success", **values}
