import logging
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from backend.core.database import get_db, AsyncSessionLocal
from backend.core.auth import get_current_user
from backend.core.config import settings
from backend.models.user import User
from backend.models.adventure_template import AdventureTemplate
from backend.models.game_session import GameSession
from backend.models.session_state import SessionState
from backend.models.avatar import Avatar
from backend.models.world_entity import WorldScene
from backend.engine.world_generator import WorldGenerator
from backend.api.routes.adventures.schemas import (
    AdventureTemplateSummaryResponse, AdventureTemplateResponse,
    CreateAdventureTemplatePayload, AdventureTemplateUpdate
)
from backend.api.routes.adventures.logic import AdventureLogic
from backend.utils.text_utils import generate_adventure_id

router = APIRouter(tags=["Adventures"], redirect_slashes=False)
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
            origin_id=template.origin_id,
            is_adventure_generator=template.is_adventure_generator,
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


@router.post("/", status_code=201)
async def create_adventure(
    payload: CreateAdventureTemplatePayload,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Creates a new adventure template, initializes the protagonist avatar and first game session,
    and starts the background world generation task.
    """
    # 1. Create the template record
    new_id = payload.id or generate_adventure_id(payload.title)
    
    # Backward compatibility for pacing configs
    pacing_minutes = payload.pacing_minutes or payload.time_per_turn
    if payload.pacing and isinstance(payload.pacing, dict):
         pacing_minutes = payload.pacing.get("minutes_per_turn", pacing_minutes)

    adv = AdventureTemplate(
        id=new_id,
        owner_id=current_user.id,
        title=payload.title,
        original_prompt=payload.original_prompt,
        strict_rules=payload.rule_enforcement_mode != "chat",
        rule_enforcement_mode=payload.rule_enforcement_mode or "rpg",
        time_per_turn=payload.time_per_turn,
        pacing_minutes=pacing_minutes,
        clock_enabled=payload.clock_enabled or False,
        generate_scene_images=payload.generate_scene_images,
        generate_npc_images=payload.generate_npc_images,
        generate_item_images=payload.generate_item_images,
        selected_image_styles=payload.selected_image_styles,
        selected_tone=payload.selected_tone,
        min_scenes=payload.min_scenes,
        max_scenes=payload.max_scenes,
        award_generation_enabled=payload.award_generation_enabled,
        min_awards=payload.min_awards,
        max_awards=payload.max_awards,
        is_ready=False,
        creation_status="Initializing...",
        original_manifest=payload.original_manifest,
        language=payload.language,
        is_adventure_generator=payload.is_adventure_generator
    )
    db.add(adv)
    
    # 2. Create the Avatar
    avatar = Avatar(
        user_id=current_user.id,
        template_id=new_id,
        name=payload.avatar_name or f"Hero of {payload.title}",
        role="Protagonist",
        description="A mysterious wanderer...",
        hp=200, stamina=200, mana=200, exp=0,
        stats={"str": 10, "int": 10, "wis": 10, "dex": 10, "cha": 10, "ac": 10},
    )
    db.add(avatar)
    await db.flush() # Ensure avatar.id is available
    
    # 3. Create the first GameSession
    session = GameSession(
        user_id=current_user.id,
        avatar_id=avatar.id,
        template_id=new_id,
        adventure_title=payload.title,
        status="active"
    )
    db.add(session)
    await db.commit()
    
    # 4. Trigger background generation
    async def run_gen():
        # We need a fresh session for background task to avoid closure issues
        async with AsyncSessionLocal() as bg_db:
            try:
                # Refresh user in new session
                user_res = await bg_db.execute(select(User).where(User.id == current_user.id))
                bg_user = user_res.scalars().first()
                
                await WorldGenerator.generate_world(
                    db=bg_db,
                    user=bg_user,
                    template_id=new_id,
                    title=payload.title,
                    original_prompt=payload.original_prompt or "",
                    generate_scene_images=payload.generate_scene_images,
                    generate_npc_images=payload.generate_npc_images,
                    generate_item_images=payload.generate_item_images,
                    min_scenes=payload.min_scenes,
                    max_scenes=payload.max_scenes,
                    award_generation_enabled=payload.award_generation_enabled,
                    min_awards=payload.min_awards,
                    max_awards=payload.max_awards,
                    selected_image_styles=adv.selected_image_styles,
                    language=payload.language
                )

                # Finalize template
                adv_res = await bg_db.execute(select(AdventureTemplate).where(AdventureTemplate.id == new_id))
                bg_adv = adv_res.scalars().first()
                if bg_adv:
                    bg_adv.is_ready = True
                    bg_adv.creation_status = "Ready"
                    await bg_db.commit()
            except Exception as e:
                logger.error(f"Background generation failed for {new_id}: {e}")
                # Record error in template
                adv_res = await bg_db.execute(select(AdventureTemplate).where(AdventureTemplate.id == new_id))
                bg_adv = adv_res.scalars().first()
                if bg_adv:
                    bg_adv.creation_status = "Failed"
                    bg_adv.creation_error = str(e)
                    await bg_db.commit()

    background_tasks.add_task(run_gen)
    
    return {
        "game_id": session.id,
        "adventure_id": new_id,
        "avatar_id": avatar.id
    }

@router.patch("/{template_id}", response_model=AdventureTemplateResponse)
async def update_adventure(
    template_id: str,
    payload: AdventureTemplateUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Partially updates an adventure template's metadata, narrative fields, or configuration."""
    result = await db.execute(select(AdventureTemplate).where((AdventureTemplate.id == template_id) & (AdventureTemplate.owner_id == current_user.id)))
    adv = result.scalars().first()
    if not adv:
        raise HTTPException(status_code=404, detail="AdventureTemplate not found.")

    update_data = payload.model_dump(exclude_unset=True)
    
    # Apply updates to template
    for field, value in update_data.items():
        setattr(adv, field, value)

    # Sync strict_rules internally if mode changed
    if "rule_enforcement_mode" in update_data:
        adv.strict_rules = (update_data["rule_enforcement_mode"] != "chat")

    # Sync to active sessions if narrative fields changed
    narrative_fields = {"plot", "rules", "walkthrough", "completed_condition", "gameover_condition"}
    if any(f in update_data for f in narrative_fields):
        from backend.models.session_state import SessionState
        session_res = await db.execute(select(SessionState).where(SessionState.template_id == template_id))
        active_states = session_res.scalars().all()
        for state in active_states:
            for f in narrative_fields:
                if f in update_data:
                    setattr(state, f, update_data[f])

    await db.commit()
    await db.refresh(adv)
    
    # Enrich awards for response
    user_earned_keys = {ea.get("key") for ea in (current_user.earned_awards or []) if ea.get("template_id") == adv.id}
    enriched_awards = [{**aw, "is_earned": aw.get("key") in user_earned_keys} for aw in (adv.awards or [])]
    
    response_data = AdventureTemplateResponse.model_validate(adv).model_dump()
    response_data["awards"] = enriched_awards
    return response_data

@router.get("/{template_id}/status")
async def get_adventure_status(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieves the generation status and potential errors for an adventure."""
    result = await db.execute(select(AdventureTemplate).where((AdventureTemplate.id == template_id) & (AdventureTemplate.owner_id == current_user.id)))
    adv = result.scalars().first()
    if not adv:
        raise HTTPException(status_code=404, detail="AdventureTemplate not found.")
    
    return {
        "status": adv.creation_status or "Unknown",
        "is_ready": adv.is_ready,
        "error": adv.creation_error
    }

@router.post("/{template_id}/cancel")
async def cancel_adventure(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cancels an active adventure generation."""
    result = await db.execute(select(AdventureTemplate).where((AdventureTemplate.id == template_id) & (AdventureTemplate.owner_id == current_user.id)))
    adv = result.scalars().first()
    if not adv:
        raise HTTPException(status_code=404, detail="AdventureTemplate not found.")
    
    if not adv.is_ready:
        adv.creation_status = "Cancelled"
        await db.commit()
    
    return {"status": "cancelled"}

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
    
    await AdventureLogic.delete_adventure(db, template_id)
    return {"status": "deleted", "template_id": template_id}

@router.get("/{template_id}/export/adv")
async def export_adventure_adv(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Exports the adventure as a pure .adv JSON manifest."""
    from backend.engine.adventure_exporter import AdventureExporter
    try:
        manifest = await AdventureExporter.build_full_manifest(db, template_id)
        return manifest
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Export failed")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{template_id}/export/adz")
async def export_adventure_adz(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Exports the adventure as a portable .adz (ZIP) bundle including assets."""
    from backend.engine.adventure_exporter import AdventureExporter
    import io
    try:
        zip_data = await AdventureExporter.export_adz(db, template_id)
        return StreamingResponse(
            io.BytesIO(zip_data),
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename=adventure_{template_id}.adz"}
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("ADZ Export failed")
        raise HTTPException(status_code=500, detail=str(e))
