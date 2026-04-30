import logging
from typing import List, Optional
from copy import deepcopy
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.core.database import get_db
from backend.core.auth import get_current_user
from backend.models.user import User
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.game_session import GameSession
from backend.models.session_state import SessionState
from backend.models.world_entity import WorldScene
from backend.api.routes.adventures.schemas import GameSessionResponse
from backend.api.routes.adventures.logic import AdventureLogic

router = APIRouter(tags=["Sessions"])
logger = logging.getLogger(__name__)

async def _resolve_session_asset(state: SessionState, key: str, fallback: Optional[str] = None) -> Optional[str]:
    # Placeholder or import from logic if needed
    return AdventureLogic.resolve_session_asset(state, key, fallback)

@router.get("/sessions", response_model=List[GameSessionResponse])
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list:
    """Returns all game sessions for the current user."""
    result = await db.execute(
        select(GameSession, SessionState, AdventureTemplate, WorldScene.label, Avatar.profile_image)
        .join(SessionState, SessionState.session_id == GameSession.id)
        .outerjoin(AdventureTemplate, GameSession.template_id == AdventureTemplate.id)
        .outerjoin(Avatar, Avatar.id == SessionState.avatar_id)
        .outerjoin(WorldScene, (WorldScene.template_id == GameSession.template_id) & (WorldScene.id == SessionState.current_scene_id))
        .where(GameSession.user_id == current_user.id)
    )
    rows = result.all()
    user_earned_awards = current_user.earned_awards or []
    
    return [
        GameSessionResponse(
            game_id=g.id, template_id=g.template_id, adventure_id=g.template_id, avatar_id=g.avatar_id,
            profile_image=AdventureLogic.resolve_session_asset(s, "protagonist", avatar_profile_image),
            adventure_title=a.title if a else (g.adventure_title or "Unknown"),
            image_url=AdventureLogic.resolve_session_asset(s, "cover", a.image_url if a else g.adventure_image_url),
            scene_id=s.current_scene_id, current_scene_name=scene_label or "Exploring...",
            in_game_time=s.in_game_time,
            is_ready=a.is_ready if a else True, creation_status=a.creation_status if a else "Ready",
            creation_error=a.creation_error if a else None, selected_tone=a.selected_tone if a else None,
            progress=AdventureLogic.calculate_quest_progress(s.quests if s else (a.quests if a else None)),
            quest_count=len((s.quests if s else (a.quests if a else None)) or []),
            completed_quest_count=len([q for q in ((s.quests if s else (a.quests if a else None)) or []) if q.get("status") == "completed"]),
            award_count=len((a.awards if a else None) or []),
            earned_award_count=len([aw for aw in ((a.awards if a else None) or []) if any(ea.get("key") == aw.get("key") and ea.get("template_id") == a.id for ea in user_earned_awards)]),
            created_at=g.created_at,
            status=g.status,
            status_note=g.status_note,
        )
        for g, s, a, scene_label, avatar_profile_image in rows
    ]

from backend.models.world_entity import WorldScene, WorldExit, WorldEntity

@router.post("/{template_id}/sessions/start", status_code=201)
async def start_session_for_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Creates a new active session for a template and returns its identifiers."""
    adv_res = await db.execute(select(AdventureTemplate).where(AdventureTemplate.id == template_id))
    adventure = adv_res.scalars().first()
    if not adventure:
        raise HTTPException(status_code=404, detail="AdventureTemplate not found.")

    # Allow if user is owner OR if adventure is ready (public-ready)
    if adventure.owner_id != current_user.id and not adventure.is_ready:
        raise HTTPException(status_code=403, detail="You do not have access to this adventure yet.")

    # 1. Create a fresh Avatar for this session
    # We always create a new Avatar to ensure each session is independent and starts fresh
    prot = (adventure.original_manifest or {}).get("protagonist", {})
    avatar = Avatar(
        user_id=current_user.id, 
        template_id=template_id, 
        name=prot.get("name", "You"),
        role=prot.get("role"), 
        description=prot.get("description"), 
        profile_image=prot.get("profile_image"),
        hp=prot.get("hp", 200), 
        max_hp=prot.get("hp", 200), 
        stamina=prot.get("stamina", 200), 
        max_stamina=prot.get("stamina", 200), 
        mana=prot.get("mana", 200), 
        max_mana=prot.get("mana", 200),
        stats=prot.get("stats", {}), 
        inventory=deepcopy(prot.get("inventory", [])),
        equipment=deepcopy(prot.get("equipment", {
            "Head": None, "Chest": None, "Arms": None, "Legs": None, 
            "Hands": None, "Feet": None, "Ring_1": None, "Ring_2": None, 
            "Amulet": None, "Main_Hand": None, "Off_Hand": None
        })),
        status_effects=deepcopy(prot.get("status_effects", [])),
    )
    db.add(avatar)
    await db.flush()

    scene_res = await db.execute(select(WorldScene.id).where(WorldScene.template_id == template_id).order_by(WorldScene.id.asc()).limit(1))
    first_scene_id = scene_res.scalar_one_or_none() or "START"

    new_session = GameSession(
        user_id=current_user.id,
        avatar_id=avatar.id,
        template_id=template_id,
        adventure_title=adventure.title,
        adventure_image_url=adventure.image_url,
        status="active"
    )
    db.add(new_session)
    await db.flush()

    # Create SessionState with narrative snapshot
    new_state = SessionState(
        session_id=new_session.id, user_id=current_user.id, template_id=template_id, avatar_id=avatar.id,
        current_scene_id=first_scene_id, in_game_time=0, quests=deepcopy(adventure.quests or []),
        start_datetime=AdventureLogic.resolve_start_datetime(adventure.original_manifest),
        plot=adventure.plot,
        rules=adventure.rules,
        walkthrough=adventure.walkthrough,
        completed_condition=adventure.completed_condition,
        gameover_condition=adventure.gameover_condition
    )
    db.add(new_state)
    
    # --- DEEP CLONE WORLD DATA ---
    # 1. Clone Scenes
    scenes_res = await db.execute(select(WorldScene).where(WorldScene.template_id == template_id))
    scenes = scenes_res.scalars().all()
    for s in scenes:
        new_s = WorldScene(
            id=s.id, session_id=new_session.id, template_id=None,
            label=s.label, description=s.description, image_url=s.image_url
        )
        db.add(new_s)
    
    # 2. Clone Exits
    exits_res = await db.execute(select(WorldExit).where(WorldExit.template_id == template_id))
    exits = exits_res.scalars().all()
    for e in exits:
        new_e = WorldExit(
            session_id=new_session.id, template_id=None,
            from_scene_id=e.from_scene_id, to_scene_id=e.to_scene_id,
            label=e.label, is_locked=e.is_locked, lock_description=e.lock_description
        )
        db.add(new_e)
        
    # 3. Clone Entities
    entities_res = await db.execute(select(WorldEntity).where(WorldEntity.template_id == template_id))
    entities = entities_res.scalars().all()
    for ent in entities:
        new_ent = WorldEntity(
            id=ent.id, session_id=new_session.id, template_id=None,
            entity_type=ent.entity_type, name=ent.name, description=ent.description,
            current_scene_id=ent.current_scene_id, spatial_position=ent.spatial_position,
            image_url=ent.image_url, item_type=ent.item_type, wearable_slots=ent.wearable_slots,
            is_in_inventory=ent.is_in_inventory, is_hidden=ent.is_hidden, is_portable=ent.is_portable,
            combination_ingredients=ent.combination_ingredients, reveals_item_id=ent.reveals_item_id,
            is_final_state=ent.is_final_state, state_comment=ent.state_comment,
            npc_type=ent.npc_type, movement_type=ent.movement_type,
            hp=ent.hp, max_hp=ent.max_hp, mana=ent.mana, max_mana=ent.max_mana, stamina=ent.stamina, max_stamina=ent.max_stamina,
            stat_modifier_strength=ent.stat_modifier_strength, stat_modifier_dexterity=ent.stat_modifier_dexterity,
            stat_modifier_intelligence=ent.stat_modifier_intelligence, stat_modifier_wisdom=ent.stat_modifier_wisdom,
            stat_modifier_charisma=ent.stat_modifier_charisma, stat_modifier_armor_class=ent.stat_modifier_armor_class,
            inventory=deepcopy(ent.inventory), metadata_json=deepcopy(ent.metadata_json)
        )
        db.add(new_ent)

    await db.commit()
    return {"game_id": new_session.id, "template_id": template_id, "avatar_id": avatar.id}

@router.delete("/sessions/{game_id}", status_code=200)
async def delete_session(game_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(GameSession).where((GameSession.id == game_id) & (GameSession.user_id == current_user.id)))
    game_session = result.scalars().first()
    if not game_session:
        raise HTTPException(status_code=404, detail="Session not found.")
    avatar_id = game_session.avatar_id
    await db.delete(game_session)
    
    # Also delete the associated avatar as it was session-specific
    avatar_res = await db.execute(select(Avatar).where(Avatar.id == avatar_id))
    avatar = avatar_res.scalars().first()
    if avatar:
        await db.delete(avatar)
        
    await db.commit()
    return {"status": "deleted", "game_id": game_id}
