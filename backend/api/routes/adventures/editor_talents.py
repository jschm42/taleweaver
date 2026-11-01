"""Editor endpoint for the protagonist's non-combat talents (e.g. Mind Reading)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from backend.api.routes.adventures.editor import (
    _get_owned_adventure_or_404,
    _get_template_avatar,
    _sanitize_editor_id,
)
from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.engine.rules.talents import MAX_TALENTS
from backend.engine.scripting.sandbox import SafeAstInterpreter
from backend.engine.world.combat_profile_schemas import TalentSchema
from backend.models.adventure_template import AdventureTemplate
from backend.models.user import User

router = APIRouter(tags=["Editor"])

_REF_FIELDS = (
    "unlock_required_item_id",
    "unlock_required_scene_id",
    "unlock_required_defeated_npc_id",
)


class TalentsUpdateRequest(BaseModel):
    talents: list[TalentSchema] = Field(default_factory=list, max_length=MAX_TALENTS)


def _syntax_errors(talent: dict[str, Any]) -> list[str]:
    script = talent.get("on_use_script") or ""
    guard = talent.get("unlock_guard_expression") or ""
    errors = [f"on_use_script: {e}" for e in SafeAstInterpreter.check_syntax(script)]
    errors += [
        f"unlock_guard_expression: {e}" for e in SafeAstInterpreter.check_expression_syntax(guard)
    ]
    return errors


def _serialize_talent(talent: TalentSchema) -> dict[str, Any]:
    data = {**talent.model_dump(exclude_none=True), "id": talent.id.strip().upper()}
    _sanitize_editor_id(data["id"], "talent id")
    for field in _REF_FIELDS:
        value = str(data.get(field) or "").strip()
        if value:
            data[field] = _sanitize_editor_id(value, field)
        else:
            data.pop(field, None)
    errors = _syntax_errors(data)
    if errors:
        raise HTTPException(status_code=400, detail=f"{data['id']}: " + "; ".join(errors))
    return data


def serialize_talents(talents: list[TalentSchema]) -> list[dict[str, Any]]:
    serialized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for talent in talents:
        data = _serialize_talent(talent)
        if data["id"] in seen:
            raise HTTPException(status_code=400, detail=f"Duplicate talent id: {data['id']}")
        seen.add(data["id"])
        serialized.append(data)
    return serialized


def _update_manifest(adv: AdventureTemplate, talents: list[dict[str, Any]]) -> None:
    if not isinstance(adv.original_manifest, dict):
        return
    manifest = deepcopy(adv.original_manifest)
    if isinstance(manifest.get("protagonist"), dict):
        manifest["protagonist"]["talents"] = talents
    adv.original_manifest = manifest
    flag_modified(adv, "original_manifest")


@router.put("/{template_id}/editor/talents")
async def update_talents(
    template_id: str,
    payload: TalentsUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Replaces the protagonist's talents; unlocked ones are available from the start."""
    adv = await _get_owned_adventure_or_404(db, template_id, current_user.id)
    avatar = await _get_template_avatar(db, template_id)
    if not avatar:
        raise HTTPException(status_code=404, detail="Protagonist not found")
    talents = serialize_talents(payload.talents)

    stats = dict(avatar.stats or {})
    stats["talents"] = talents
    stats["unlocked_talents"] = [t["id"] for t in talents if not t.get("is_locked")]
    stats.pop("talent_uses", None)
    avatar.stats = stats
    flag_modified(avatar, "stats")
    _update_manifest(adv, talents)
    await db.commit()
    return {"status": "success", "talents": talents}
