from __future__ import annotations
import logging
import os
from copy import deepcopy

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.logic import AdventureLogic
from backend.api.routes.adventures.schemas import (
    AdventureTemplateResponse,
    AdventureTemplateSummaryResponse,
    AdventureTemplateUpdate,
    CreateAdventureTemplatePayload,
)
from backend.core.auth import get_current_user
from backend.core.config import settings
from backend.core.database import AsyncSessionLocal, get_db
from backend.engine.world_generator import WorldGenerator, is_image_moderation_error
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.game_session import GameSession
from backend.models.session_state import SessionState
from backend.models.user import User
from backend.models.world_entity import WorldEntity, WorldScene
from backend.utils.text_utils import generate_adventure_id, generate_session_id

router = APIRouter(tags=["Adventures"])
logger = logging.getLogger(__name__)

@router.get("/templates", response_model=list[AdventureTemplateSummaryResponse])
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
            version=template.version,
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
            cover_source_adventure_id=template.cover_source_adventure_id,
            cover_source_adventure_name=template.cover_source_adventure_name,
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
    # Allow only one active portal generation per user at a time.
    active_generation_query = await db.execute(
        select(AdventureTemplate.id)
        .where(AdventureTemplate.owner_id == current_user.id)
        .where(AdventureTemplate.is_ready.is_(False))
        .where(
            or_(
                AdventureTemplate.creation_status.is_(None),
                AdventureTemplate.creation_status.notin_(["Failed", "Cancelled"]),
            )
        )
        .limit(1)
    )
    active_generation_id = active_generation_query.scalar_one_or_none()
    if active_generation_id:
        raise HTTPException(
            status_code=409,
            detail="Adventure generation already running for this user. Please wait until it finishes or cancel it.",
        )

    # 1. Create the template record
    new_id = payload.id or generate_adventure_id(payload.title)
    
    # Backward compatibility for pacing configs
    pacing_minutes = payload.pacing_minutes or payload.time_per_turn
    if payload.pacing and isinstance(payload.pacing, dict):
        pacing_minutes = payload.pacing.get("minutes_per_turn", pacing_minutes)

    chat_mode = (payload.rule_enforcement_mode or "rpg") == "chat"

    source_template = None
    cover_source_manifest = None
    cover_source_adventure_id_value = None
    if payload.cover_source_adventure_id:
        source_res = await db.execute(
            select(AdventureTemplate).where(
                AdventureTemplate.id == payload.cover_source_adventure_id,
                AdventureTemplate.owner_id == current_user.id,
            )
        )
        source_template = source_res.scalars().first()
        if not source_template:
            raise HTTPException(status_code=404, detail="Cover source adventure not found.")
        cover_source_adventure_id_value = source_template.id
        cover_source_manifest = deepcopy(source_template.original_manifest or {})

    cover_source_name = payload.cover_source_adventure_name
    if source_template and not cover_source_name:
        cover_source_name = source_template.title

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
        award_generation_enabled=False if chat_mode else payload.award_generation_enabled,
        min_awards=payload.min_awards,
        max_awards=payload.max_awards,
        can_damage_npcs=payload.can_damage_npcs,
        npcs_can_damage_protagonist=payload.npcs_can_damage_protagonist,
        is_ready=False,
        creation_status="Initializing...",
        original_manifest=payload.original_manifest,
        teaser=payload.teaser,
        version=payload.version,
        language=payload.language,
        intro_text=payload.intro_text,
        is_adventure_generator=payload.is_adventure_generator,
        cover_source_adventure_id=(source_template.id if source_template else None),
        cover_source_adventure_name=cover_source_name,
        cover_similarity_percent=max(0, min(100, int(payload.cover_similarity_percent or 0))),
        allow_reuse_source_assets=bool(payload.allow_reuse_source_assets),
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
        id=generate_session_id(payload.title),
        user_id=current_user.id,
        avatar_id=avatar.id,
        template_id=new_id,
        adventure_title=payload.title,
        status="active"
    )
    db.add(session)
    await db.flush()

    # Ensure a concrete session filesystem root exists for session-bound artifacts (e.g. TTS).
    os.makedirs(os.path.join(settings.DATA_DIR, "adventures", "sessions", session.id), exist_ok=True)

    # Create an initial SessionState (GameState alias) to capture template snapshot and asset mapping for newly created session.
    manifest_snapshot = AdventureLogic.build_session_manifest_snapshot(adv)

    # Build entity image map from any existing template entities
    ent_rows = await db.execute(select(WorldEntity).where(WorldEntity.template_id == new_id))
    template_entities = ent_rows.scalars().all()
    entity_images = {e.id: e.image_url for e in template_entities if getattr(e, "id", None)}

    asset_snapshot = {
        "cover": adv.image_url,
        "protagonist": avatar.profile_image,
        "entity_images": entity_images,
    }

    new_state = SessionState(
        session_id=session.id,
        user_id=current_user.id,
        template_id=new_id,
        avatar_id=avatar.id,
        current_scene_id="START",
        in_game_time=0,
        quests=deepcopy(adv.quests or []),
        entity_states={
            AdventureLogic.SESSION_MANIFEST_SNAPSHOT_KEY: manifest_snapshot,
            "__asset_snapshot__": asset_snapshot,
        },
        start_datetime=AdventureLogic.resolve_start_datetime(adv.original_manifest),
        plot=adv.plot,
        rules=adv.rules,
        walkthrough=adv.walkthrough,
        completed_condition=adv.completed_condition,
        gameover_condition=adv.gameover_condition,
        tts_director_notes=adv.tts_director_notes,
        selected_image_styles=deepcopy(adv.selected_image_styles),
        selected_tone=deepcopy(adv.selected_tone),
    )
    db.add(new_state)

    await db.commit()
    
    # 4. Trigger background generation
    async def run_gen():
        # We need a fresh session for background task to avoid closure issues
        import backend.core.database as core_database
        async with core_database.AsyncSessionLocal() as bg_db:
            try:
                # Refresh user in new session
                user_res = await bg_db.execute(select(User).where(User.id == current_user.id))
                bg_user = user_res.scalars().first()
                
                # Set intermediate status
                adv_res = await bg_db.execute(select(AdventureTemplate).where(AdventureTemplate.id == new_id))
                bg_adv = adv_res.scalars().first()
                if bg_adv:
                    bg_adv.creation_status = "Generating world structure"
                    await bg_db.commit()
                
                await WorldGenerator.generate_world(
                    db=bg_db,
                    user=bg_user,
                    template_id=new_id,
                    title=payload.title,
                    original_prompt=payload.original_prompt or "",
                    generate_scene_images=payload.generate_scene_images,
                    generate_npc_images=payload.generate_npc_images,
                    generate_item_images=payload.generate_item_images,
                    automatic_npc_voice_assignment=payload.automatic_npc_voice_assignment,
                    min_scenes=payload.min_scenes,
                    max_scenes=payload.max_scenes,
                    quest_generation_enabled=not chat_mode,
                    award_generation_enabled=False if chat_mode else payload.award_generation_enabled,
                    min_awards=payload.min_awards,
                    max_awards=payload.max_awards,
                    can_damage_npcs=payload.can_damage_npcs,
                    npcs_can_damage_protagonist=payload.npcs_can_damage_protagonist,
                    selected_image_styles=adv.selected_image_styles,
                    language=payload.language,
                    cover_source_manifest=cover_source_manifest,
                    cover_source_adventure_id=cover_source_adventure_id_value,
                    cover_source_adventure_name=(cover_source_name if source_template else None),
                    cover_similarity_percent=max(0, min(100, int(payload.cover_similarity_percent or 0))),
                    allow_reuse_source_assets=bool(payload.allow_reuse_source_assets),
                )

                # Finalize template
                adv_res = await bg_db.execute(select(AdventureTemplate).where(AdventureTemplate.id == new_id))
                bg_adv = adv_res.scalars().first()
                if bg_adv:
                    bg_adv.is_ready = True
                    bg_adv.creation_status = "Ready"
                    await bg_db.commit()
            except Exception as e:
                logger.exception(f"Background generation failed for {new_id}: {e}")
                # Record error in template
                adv_res = await bg_db.execute(select(AdventureTemplate).where(AdventureTemplate.id == new_id))
                bg_adv = adv_res.scalars().first()
                if bg_adv:
                    scene_count_res = await bg_db.execute(
                        select(WorldScene.id).where(WorldScene.template_id == new_id).limit(1)
                    )
                    entity_count_res = await bg_db.execute(
                        select(WorldEntity.id).where(WorldEntity.template_id == new_id).limit(1)
                    )
                    has_world_data = bool(scene_count_res.scalar_one_or_none() or entity_count_res.scalar_one_or_none())

                    if is_image_moderation_error(e):
                        bg_adv.is_ready = True
                        bg_adv.creation_status = "Ready"
                        bg_adv.creation_error = (
                            "Notice: One or more images were blocked by safety filters and replaced with placeholders. "
                            "You can regenerate them later in the editor."
                        )
                        await bg_db.commit()
                        return

                    bg_adv.creation_status = "Failed"
                    bg_adv.creation_error = str(e)
                    await bg_db.commit()

    background_tasks.add_task(run_gen)
    
    return {
        "game_id": session.id,
        "adventure_id": new_id,
        "avatar_id": avatar.id
    }

@router.post("/{template_id}/reset")
async def reset_adventure(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Rebuilds the template world data from original_manifest, preserving existing image URLs."""
    from sqlalchemy import delete as sa_delete

    result = await db.execute(
        select(AdventureTemplate).where(
            (AdventureTemplate.id == template_id) & (AdventureTemplate.owner_id == current_user.id)
        )
    )
    adv = result.scalars().first()
    if not adv:
        raise HTTPException(status_code=404, detail="AdventureTemplate not found.")
    if not adv.original_manifest:
        raise HTTPException(status_code=400, detail="No original manifest to reset from.")

    manifest = adv.original_manifest

    # Collect existing image URLs so they survive the reset.
    existing_scene_images: dict[str, str | None] = {}
    existing_entity_images: dict[str, str | None] = {}

    scene_res = await db.execute(select(WorldScene).where(WorldScene.template_id == template_id))
    for s in scene_res.scalars().all():
        existing_scene_images[s.id] = s.image_url

    entity_res = await db.execute(select(WorldEntity).where(WorldEntity.template_id == template_id))
    for e in entity_res.scalars().all():
        existing_entity_images[e.id] = e.image_url

    # Wipe old template-level world data.
    await db.execute(sa_delete(WorldScene).where(WorldScene.template_id == template_id))
    await db.execute(sa_delete(WorldEntity).where(WorldEntity.template_id == template_id))

    # Rebuild scenes from manifest.
    for scene_def in manifest.get("scenes", []):
        scene_id = scene_def.get("id")
        if not scene_id:
            continue
        db.add(WorldScene(
            id=scene_id,
            template_id=template_id,
            label=scene_def.get("name") or scene_def.get("label") or scene_id,
            description=scene_def.get("description", ""),
            image_url=existing_scene_images.get(scene_id),
        ))

    # Rebuild NPCs from manifest.
    for npc_def in manifest.get("npcs", []):
        npc_id = npc_def.get("id")
        if not npc_id:
            continue
        db.add(WorldEntity(
            id=npc_id,
            template_id=template_id,
            entity_type="NPC",
            name=npc_def.get("name", ""),
            description=npc_def.get("description", ""),
            current_scene_id=npc_def.get("start_scene_id"),
            image_url=existing_entity_images.get(npc_id),
        ))

    # Rebuild objects from manifest.
    for obj_def in manifest.get("objects", []):
        obj_id = obj_def.get("id")
        if not obj_id:
            continue
        db.add(WorldEntity(
            id=obj_id,
            template_id=template_id,
            entity_type="OBJECT",
            name=obj_def.get("name", ""),
            description=obj_def.get("description", ""),
            current_scene_id=obj_def.get("start_scene_id"),
            image_url=existing_entity_images.get(obj_id),
        ))

    # Restore protagonist image from manifest protagonist data.
    prot_def = manifest.get("protagonist", {})
    if prot_def:
        av_res = await db.execute(select(Avatar).where(Avatar.template_id == template_id))
        avatar = av_res.scalars().first()
        if avatar:
            # Restore static fields; preserve generated profile_image.
            avatar.name = prot_def.get("name") or avatar.name
            avatar.role = prot_def.get("role") or avatar.role
            avatar.description = prot_def.get("description") or avatar.description

    await db.commit()
    return {"status": "reset", "template_id": template_id}


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

    # Sync strict_rules internally if mode changed (but not if strict_rules was patched directly)
    if "rule_enforcement_mode" in update_data and "strict_rules" not in update_data:
        adv.strict_rules = (update_data["rule_enforcement_mode"] != "chat")

    # Sync to active sessions if narrative fields changed
    narrative_fields = {"plot", "rules", "walkthrough", "completed_condition", "gameover_condition", "tts_director_notes"}
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


@router.get("/{template_id}/state")
async def get_adventure_state(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns the current runtime state for the latest session of this template for the user."""
    state = await AdventureLogic.resolve_session_state(db, template_id, user_id=current_user.id)
    if not state:
        raise HTTPException(status_code=404, detail="Session state not found.")

    is_paused = False
    if state.session and getattr(state.session, "status", None):
        is_paused = state.session.status == "paused"

    return {
        "scene_id": state.current_scene_id,
        "in_game_time": state.in_game_time,
        "is_paused": is_paused,
    }


@router.patch("/{template_id}/state")
async def patch_adventure_state(
    template_id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Patch mutable fields on the active session state (e.g. scene_id)."""
    state = await AdventureLogic.resolve_session_state(db, template_id, user_id=current_user.id)
    if not state:
        raise HTTPException(status_code=404, detail="Session state not found.")

    updated = False
    if "scene_id" in payload:
        state.current_scene_id = payload.get("scene_id")
        updated = True
    if "in_game_time" in payload:
        try:
            state.in_game_time = int(payload.get("in_game_time"))
            updated = True
        except Exception:
            pass

    if updated:
        await db.commit()

    return {
        "scene_id": state.current_scene_id,
        "in_game_time": state.in_game_time,
    }


@router.post("/{template_id}/pause")
async def pause_adventure(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Pause the most recent session for this user/template."""
    res = await db.execute(select(GameSession).where(GameSession.template_id == template_id).order_by(GameSession.updated_at.desc()))
    session = next(iter(res.scalars().all()), None)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found.")

    session.status = "paused"
    await db.commit()
    return {"status": "paused"}


@router.post("/{template_id}/resume")
async def resume_adventure(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Resume a paused session for this user/template."""
    res = await db.execute(select(GameSession).where(GameSession.template_id == template_id).order_by(GameSession.updated_at.desc()))
    session = next(iter(res.scalars().all()), None)
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found.")

    session.status = "active"
    await db.commit()
    return {"status": "active"}

@router.post("/{template_id}/cancel")
async def cancel_adventure_generation(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Signals a background generation task to stop by updating the template status."""
    result = await db.execute(select(AdventureTemplate).where((AdventureTemplate.id == template_id) & (AdventureTemplate.owner_id == current_user.id)))
    adv = result.scalars().first()
    if not adv:
        raise HTTPException(status_code=404, detail="AdventureTemplate not found.")
    
    if adv.is_ready:
        raise HTTPException(status_code=400, detail="Generation already finished.")
        
    adv.creation_status = "Cancelled"
    await db.commit()
    return {"status": "Cancelled"}

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

@router.get("/{template_id}/export/manifest")
async def export_adventure_manifest(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Exports the raw/original manifest stored in the template with minor backfills if needed."""
    from copy import deepcopy
    from typing import Any
    from backend.models.world_entity import WorldEntity

    result = await db.execute(
        select(AdventureTemplate).where(
            (AdventureTemplate.id == template_id) & (AdventureTemplate.owner_id == current_user.id)
        )
    )
    adventure = result.scalars().first()
    if not adventure or not adventure.original_manifest:
        raise HTTPException(status_code=404, detail="Original manifest not found.")

    manifest = deepcopy(adventure.original_manifest)

    # Backfill basic metadata if not present in the original manifest
    if "version" not in manifest:
        manifest["version"] = adventure.version or "1.0"
    if "id" not in manifest:
        manifest["id"] = adventure.id
    if "title" not in manifest:
        manifest["title"] = adventure.title
    if "time_per_turn" not in manifest:
        manifest["time_per_turn"] = adventure.time_per_turn
    if "generate_npc_images" not in manifest:
        manifest["generate_npc_images"] = adventure.generate_npc_images or False
    if "generate_item_images" not in manifest:
        manifest["generate_item_images"] = adventure.generate_item_images or False
    if "automatic_cover_generation" not in manifest:
        manifest["automatic_cover_generation"] = False
    if "cover_source_adventure_id" not in manifest:
        manifest["cover_source_adventure_id"] = adventure.cover_source_adventure_id
    if "cover_source_adventure_name" not in manifest:
        manifest["cover_source_adventure_name"] = adventure.cover_source_adventure_name
    if "cover_similarity_percent" not in manifest:
        manifest["cover_similarity_percent"] = adventure.cover_similarity_percent
    if "allow_reuse_source_assets" not in manifest:
        manifest["allow_reuse_source_assets"] = adventure.allow_reuse_source_assets

    # Backfill start_scene_id for items/objects from WorldEntity table if missing in original manifest,
    # but only if the scene ID exists in the original manifest's scenes.

    # Extract items from legacy protagonist format and normalize to ID references
    protagonist = manifest.get("protagonist")
    if isinstance(protagonist, dict):
        objects = manifest.setdefault("objects", [])
        
        def add_object_if_new(obj_dict):
            if not obj_dict or not obj_dict.get("id"): return
            # Normalize to OBJECT entity_type if missing
            obj_copy = dict(obj_dict)
            if "entity_type" not in obj_copy:
                obj_copy["entity_type"] = "OBJECT"
            if not any(o.get("id") == obj_copy["id"] for o in objects):
                objects.append(obj_copy)

        inv = protagonist.get("starting_inventory", [])
        cleaned_inv = []
        for item in inv:
            if isinstance(item, dict):
                add_object_if_new(item)
                cleaned_inv.append(item.get("id"))
            else:
                cleaned_inv.append(item)
        if "starting_inventory" in protagonist:
            protagonist["starting_inventory"] = cleaned_inv

        equip = protagonist.get("starting_equipment", {})
        cleaned_equip = {}
        for slot, item in equip.items():
            if isinstance(item, dict):
                add_object_if_new(item)
                cleaned_equip[slot] = item.get("id")
            else:
                cleaned_equip[slot] = item
                
        # Clean up legacy root-level equipment slots
        legacy_slots = ["Head", "Neck", "Chest", "Back", "Hands", "Waist", "Legs", "Feet", "MainHand", "OffHand", "Fingers", "Trinket"]
        for slot in legacy_slots:
            if slot in protagonist:
                item = protagonist[slot]
                if isinstance(item, dict):
                    add_object_if_new(item)
                    protagonist[slot] = item.get("id")
                    cleaned_equip[slot] = item.get("id")
                else:
                    cleaned_equip[slot] = item
                # Remove from root to keep it clean if desired, or just replace with ID.
                # Since the user sees it at root and it should be references, replacing with ID is fine.
                protagonist.pop(slot, None) # Let's move it entirely to starting_equipment

        # Collect objects in scene
        items_in_scene = set()
        for obj in objects:
            scene_id = obj.get("current_scene_id") or obj.get("start_scene_id")
            if scene_id and scene_id != "INVENTORY":
                items_in_scene.add(obj.get("id"))

        # Priority Deduplication: Scene > Inventory > Equipped
        final_inv = []
        for item_id in cleaned_inv:
            if not item_id: continue
            if item_id in items_in_scene: continue
            if item_id not in final_inv:
                final_inv.append(item_id)
        
        final_equip = {}
        for slot, item_id in cleaned_equip.items():
            if not item_id: continue
            if item_id in items_in_scene: continue
            if item_id in final_inv: continue
            if item_id in final_equip.values(): continue
            final_equip[slot] = item_id

        protagonist["starting_inventory"] = final_inv
        
        if final_equip:
            protagonist["starting_equipment"] = final_equip
        else:
            protagonist.pop("starting_equipment", None)

    entity_res = await db.execute(
        select(WorldEntity.id, WorldEntity.current_scene_id)
        .where(WorldEntity.template_id == template_id)
    )
    entity_scene_map = {row.id: row.current_scene_id for row in entity_res.all() if row.id}
    valid_scene_ids = {
        s.get("id") for s in manifest.get("scenes", []) if isinstance(s, dict) and s.get("id")
    }

    def _ensure_item_locations(items: list[dict[str, Any]] | None) -> list[dict[str, Any]] | None:
        if not items:
            return items

        normalized_items: list[dict[str, Any]] = []
        for item in items:
            item_copy = dict(item)
            item_id = item_copy.get("id")
            if not item_copy.get("start_scene_id") and item_id in entity_scene_map:
                scene_id = entity_scene_map[item_id]
                if scene_id in valid_scene_ids:
                    item_copy["start_scene_id"] = scene_id
            normalized_items.append(item_copy)
        return normalized_items

    items_res = _ensure_item_locations(manifest.get("items"))
    if items_res is not None:
        manifest["items"] = items_res
    elif "items" in manifest:
        manifest.pop("items")

    objects_res = _ensure_item_locations(manifest.get("objects"))
    if objects_res is not None:
        manifest["objects"] = objects_res
    elif "objects" in manifest:
        manifest.pop("objects")

    return manifest

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
    import io

    from backend.engine.adventure_exporter import AdventureExporter
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


@router.get("/{template_id}/export/session")
async def export_adventure_session(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Exports a minimal session payload for the template (useful for import/preview)."""
    # Find template-level avatar if present
    av_res = await db.execute(select(Avatar).where(Avatar.template_id == template_id))
    avatar = av_res.scalars().first()
    if not avatar:
        raise HTTPException(status_code=404, detail="Avatar not found for template.")

    avatar_payload = {
        "name": avatar.name,
        "role": avatar.role,
        "description": avatar.description,
        "profile_image": avatar.profile_image,
        "hp": avatar.hp,
        "stamina": avatar.stamina,
        "mana": avatar.mana,
        "inventory": avatar.inventory or [],
        "equipment": avatar.equipment or {},
    }

    return {"avatar": avatar_payload}

