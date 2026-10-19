"""Create/delete endpoints for quests, awards, and scripts."""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.editing.common import (
    _get_owned_adventure_or_404,
    _sanitize_editor_id,
)
from backend.api.routes.adventures.editing.schemas import (
    AwardCreateRequest,
    QuestCreateRequest,
    ScriptCreateRequest,
)
from backend.api.routes.adventures.schemas import (
    ScriptValidateRequest,
    ScriptValidateResponse,
)
from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.engine.scripting import SafeAstInterpreter
from backend.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Editor"])


@router.post("/{template_id}/editor/quest")
async def create_editor_quest(
    template_id: str,
    payload: QuestCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    adv = await _get_owned_adventure_or_404(db, template_id, current_user.id)

    quest_id = _sanitize_editor_id(payload.id, "id")
    quests = list(adv.quests or [])
    if any(str(q.get("id") or "") == quest_id for q in quests):
        raise HTTPException(status_code=409, detail="quest id already exists")

    quest = {
        "id": quest_id,
        "title": str(payload.title or "").strip(),
        "description": str(payload.description or "").strip(),
        "goal": str(payload.goal or "").strip(),
        "impact": str(payload.impact or "").strip(),
        "exp_reward": int(payload.exp_reward or 0),
        "is_main": bool(payload.is_main),
        "status": "open",
    }
    if not quest["title"]:
        raise HTTPException(status_code=400, detail="title is required")

    quests.append(quest)
    adv.quests = quests
    await db.commit()
    return {"status": "success", "quest": quest}


@router.delete("/{template_id}/editor/quest/{quest_id}")
async def delete_editor_quest(
    template_id: str,
    quest_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    adv = await _get_owned_adventure_or_404(db, template_id, current_user.id)
    quest_id = _sanitize_editor_id(quest_id, "quest_id")

    quests = list(adv.quests or [])
    filtered = [q for q in quests if str(q.get("id") or "") != quest_id]
    if len(filtered) == len(quests):
        raise HTTPException(status_code=404, detail="Quest not found")

    adv.quests = filtered
    await db.commit()
    return {"status": "success", "deleted_quest_id": quest_id}


@router.post("/{template_id}/editor/award")
async def create_editor_award(
    template_id: str,
    payload: AwardCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    adv = await _get_owned_adventure_or_404(db, template_id, current_user.id)

    award_key = _sanitize_editor_id(payload.key, "key")
    awards = list(adv.awards or [])
    if any(str(a.get("key") or "") == award_key for a in awards):
        raise HTTPException(status_code=409, detail="award key already exists")

    award = {
        "key": award_key,
        "title": str(payload.title or "").strip(),
        "description": str(payload.description or "").strip(),
        "tier": payload.tier,
        "requirement": str(payload.requirement or "").strip(),
        "is_earned": bool(payload.is_earned),
    }
    if not award["title"]:
        raise HTTPException(status_code=400, detail="title is required")

    awards.append(award)
    adv.awards = awards
    await db.commit()
    return {"status": "success", "award": award}


@router.delete("/{template_id}/editor/award/{award_key}")
async def delete_editor_award(
    template_id: str,
    award_key: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    adv = await _get_owned_adventure_or_404(db, template_id, current_user.id)
    award_key = _sanitize_editor_id(award_key, "award_key")

    awards = list(adv.awards or [])
    filtered = [a for a in awards if str(a.get("key") or "") != award_key]
    if len(filtered) == len(awards):
        raise HTTPException(status_code=404, detail="Award not found")

    adv.awards = filtered
    await db.commit()
    return {"status": "success", "deleted_award_key": award_key}


@router.post("/{template_id}/editor/script/validate", response_model=ScriptValidateResponse)
async def validate_editor_script(
    template_id: str,
    payload: ScriptValidateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ScriptValidateResponse:
    """Validates python script syntax and security sandbox rules."""
    await _get_owned_adventure_or_404(db, template_id, current_user.id)
    errors = SafeAstInterpreter.check_syntax(payload.code)
    warnings: list[str] = []

    valid_triggers = {
        "on_init",
        "on_turn_start",
        "on_enter_scene",
        "on_interact",
        "on_turn_end",
        "on_logic_pass_done",
        "on_narration_done",
    }
    if payload.trigger and payload.trigger not in valid_triggers:
        errors.append(
            f"Invalid trigger '{payload.trigger}'. Must be one of: {', '.join(sorted(valid_triggers))}."
        )

    return ScriptValidateResponse(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )


@router.post("/{template_id}/editor/script")
async def save_editor_script(
    template_id: str,
    payload: ScriptCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Creates or updates a single script in the adventure manifest."""
    adv = await _get_owned_adventure_or_404(db, template_id, current_user.id)

    errors = SafeAstInterpreter.check_syntax(payload.code)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))

    script_id = _sanitize_editor_id(payload.id or f"script_{uuid.uuid4().hex[:8]}", "script_id")
    scripts = list(adv.scripts)

    script_data = {
        "id": script_id,
        "name": str(payload.name or script_id).strip(),
        "trigger": str(payload.trigger or "on_turn_start").strip(),
        "target": str(payload.target).strip() if payload.target else None,
        "code": payload.code,
        "priority": int(payload.priority or 100),
        "is_active": bool(payload.is_active),
    }

    existing_idx = next(
        (i for i, s in enumerate(scripts) if str(s.get("id") or "") == script_id), None
    )
    if existing_idx is not None:
        scripts[existing_idx] = script_data
    else:
        scripts.append(script_data)

    adv.scripts = scripts
    await db.commit()
    return {"status": "success", "script": script_data, "scripts": scripts}


@router.delete("/{template_id}/editor/script/{script_id}")
async def delete_editor_script(
    template_id: str,
    script_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Deletes a script from the adventure manifest."""
    adv = await _get_owned_adventure_or_404(db, template_id, current_user.id)
    script_id = _sanitize_editor_id(script_id, "script_id")

    scripts = list(adv.scripts)
    filtered = [s for s in scripts if str(s.get("id") or "") != script_id]
    if len(filtered) == len(scripts):
        raise HTTPException(status_code=404, detail="Script not found")

    adv.scripts = filtered
    await db.commit()
    return {"status": "success", "deleted_script_id": script_id, "scripts": filtered}
