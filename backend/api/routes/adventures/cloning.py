"""API endpoints for adventure duplication/cloning."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.logic import AdventureLogic
from backend.api.routes.adventures.schemas import AdventureTemplateResponse
from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.engine.adventures.adventure_cloner import AdventureCloner
from backend.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Adventures"])


class DuplicateAdventureRequest(BaseModel):
    """Optional payload when duplicating an adventure."""

    title: Optional[str] = Field(
        default=None,
        description="Optional custom title for the duplicate adventure (max 50 chars).",
        max_length=50,
    )


@router.post("/{template_id}/duplicate", response_model=AdventureTemplateResponse, status_code=201)
@router.post("/{template_id}/copy", response_model=AdventureTemplateResponse, status_code=201)
async def duplicate_adventure(
    template_id: str,
    payload: Optional[DuplicateAdventureRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Duplicate an existing adventure blueprint, world content, and disk assets."""
    custom_title = payload.title if payload else None
    cloned = await AdventureCloner.clone_adventure(
        db=db,
        template_id=template_id,
        current_user=current_user,
        custom_title=custom_title,
    )

    response_data = AdventureTemplateResponse.model_validate(cloned).model_dump()
    response_data["scripts"] = cloned.scripts
    response_data["init_script"] = cloned.init_script
    response_data["awards"] = AdventureLogic.build_awards_payload(
        user_earned_awards=None,
        adventure_awards=cloned.awards,
        adventure_id=cloned.id,
    )
    return response_data
