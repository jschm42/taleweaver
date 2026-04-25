import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from backend.core.database import get_db
from backend.core.auth import get_current_user
from backend.core.config import settings
from backend.models.user import User
from backend.models.adventure_template import AdventureTemplate
from backend.models.game_session import GameSession
from backend.models.session_state import SessionState
from backend.models.world_entity import WorldScene
from backend.engine.world_generator import WorldGenerator
from backend.api.routes.adventures.schemas import (
    AdventureTemplateSummaryResponse, AdventureTemplateResponse,
    CreateAdventureTemplatePayload, AdventureTemplateUpdate
)
from backend.api.routes.adventures.logic import AdventureLogic

router = APIRouter(tags=["Adventures"])
logger = logging.getLogger(__name__)

@router.get("/templates", response_model=List[AdventureTemplateSummaryResponse])
async def list_templates(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list:
    """Returns all adventure templates and optional active session metadata."""
    template_rows = await db.execute(select(AdventureTemplate).where(AdventureTemplate.owner_id == current_user.id))
    templates = template_rows.scalars().all()

    session_rows = await db.execute(
        select(GameSession, SessionState, WorldScene.label)
        .join(SessionState, SessionState.session_id == GameSession.id)
        .outerjoin(WorldScene, (WorldScene.template_id == GameSession.template_id) & (WorldScene.id == SessionState.current_scene_id))
        .where((GameSession.user_id == current_user.id) & (GameSession.status == "active"))
        .order_by(GameSession.created_at.desc())
    )
    latest_by_template = {}
    for game_session, state, scene_label in session_rows.all():
        if game_session.template_id not in latest_by_template:
            latest_by_template[game_session.template_id] = (game_session, state, scene_label)

    response = []
    for template in templates:
        latest = latest_by_template.get(template.id)
        game_session, state, scene_label = (latest if latest else (None, None, None))
        response.append(AdventureTemplateSummaryResponse(
            template_id=template.id, title=template.title, teaser=template.teaser,
            image_url=template.image_url, is_ready=template.is_ready,
            creation_status=template.creation_status, creation_error=template.creation_error,
            selected_tone=template.selected_tone,
            progress=AdventureLogic.calculate_quest_progress(template.quests),
            quest_count=len(template.quests or []),
            completed_quest_count=len([q for q in (template.quests or []) if q.get("status") == "completed"]),
            active_game_id=(game_session.id if game_session else None),
            has_active_session=(game_session is not None),
            scene_id=(state.current_scene_id if state else None),
            current_scene_name=(scene_label if scene_label else None),
        ))
    return response

@router.get("/{template_id}", response_model=AdventureTemplateResponse)
async def get_adventure(
    template_id: str, 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns the details of a single adventure by its ID."""
    result = await db.execute(select(AdventureTemplate).where((AdventureTemplate.id == template_id) & (AdventureTemplate.owner_id == current_user.id)))
    adv = result.scalars().first()
    if not adv:
        raise HTTPException(status_code=404, detail="AdventureTemplate not found.")
    
    user_earned_keys = {ea.get("key") for ea in (current_user.earned_awards or []) if ea.get("template_id") == adv.id}
    enriched_awards = [{**aw, "is_earned": aw.get("key") in user_earned_keys} for aw in (adv.awards or [])]
    
    response_data = AdventureTemplateResponse.model_validate(adv).model_dump()
    response_data["awards"] = enriched_awards
    return response_data

@router.delete("/{template_id}", status_code=200)
async def delete_adventure(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete an adventure template and all associated scenes, entities, maps, etc."""
    result = await db.execute(select(AdventureTemplate).where((AdventureTemplate.id == template_id) & (AdventureTemplate.owner_id == current_user.id)))
    adv = result.scalars().first()
    if not adv:
        raise HTTPException(status_code=404, detail="AdventureTemplate not found.")
    await db.delete(adv)
    await db.commit()
    return {"status": "deleted", "template_id": template_id}
