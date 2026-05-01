import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.core.database import get_db
from backend.core.auth import get_current_user
from backend.models.user import User
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.chat import ChatMessage
from backend.models.world_entity import WorldScene, WorldEntity
from backend.models.world_map import WorldMap
from backend.engine.map_engine import MapEngine
from backend.api.routes.adventures.schemas import ChatRequest, ChatResponse
from backend.api.routes.adventures.logic import AdventureLogic
from backend.api.routes.adventures.gameplay_logic import GameTurnManager

router = APIRouter(tags=["Gameplay"])
logger = logging.getLogger(__name__)

async def _get_npc_metadata(template_id: str, db: AsyncSession) -> dict:
    npc_res = await db.execute(select(WorldEntity).where(WorldEntity.template_id == template_id, WorldEntity.entity_type.in_(["NPC", "npc"])))
    metadata = {}
    for npc in npc_res.scalars().all():
        data = {"name": npc.name, "description": npc.description, "image_url": npc.image_url, "entity_type": "NPC"}
        metadata[npc.id] = data
        metadata[npc.name] = data
    return metadata

async def _enrich_map_nodes(template_id: str, nodes: dict, db: AsyncSession) -> dict:
    scene_res = await db.execute(select(WorldScene).where(WorldScene.template_id == template_id))
    db_scenes = {s.id: s for s in scene_res.scalars().all()}
    for node_id, node in nodes.items():
        if node_id in db_scenes:
            node["label"] = db_scenes[node_id].label
            node["description"] = db_scenes[node_id].description
    return nodes

@router.get("/{game_id}/chat", response_model=ChatResponse)
async def get_chat_history(
    game_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieves full chat history and current UI state for a game session."""
    state = await AdventureLogic.resolve_session_state(db, game_id, user_id=current_user.id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found.")

    adv_res = await db.execute(select(AdventureTemplate).where(AdventureTemplate.id == state.template_id))
    adventure = adv_res.scalars().first()
    
    cv_res = await db.execute(select(Avatar).where(Avatar.id == state.avatar_id))
    avatar = cv_res.scalars().first()

    chat_res = await db.execute(select(ChatMessage).where(ChatMessage.session_id == state.session_id).order_by(ChatMessage.created_at.asc()))
    history = [{"role": m.role, "content": m.content} for m in chat_res.scalars().all()]
    
    map_res = await db.execute(select(WorldMap).where(WorldMap.template_id == state.template_id))
    world_map = map_res.scalars().first()
    
    entities = await AdventureLogic.build_session_entities(db, state)
    
    scene_image = AdventureLogic.resolve_session_asset(state, state.current_scene_id)
    if not scene_image:
        scene_res = await db.execute(select(WorldScene).where(WorldScene.id == state.current_scene_id, WorldScene.template_id == state.template_id))
        scene = scene_res.scalars().first()
        scene_image = scene.image_url if scene else None

    return ChatResponse(
        messages=history,
        sheet=await AdventureLogic.build_sheet_snapshot(avatar, state, db),
        combat=AdventureLogic.get_combat_snapshot(state),
        mermaid=MapEngine.to_mermaid(world_map) if world_map else None,
        nodes=await _enrich_map_nodes(state.template_id, world_map.nodes if world_map else {}, db),
        entities=entities,
        npc_metadata=await _get_npc_metadata(state.template_id, db),
        image_url=scene_image,
        adventure_image=AdventureLogic.resolve_session_asset(state, "cover", adventure.image_url if adventure else None),
        quests=state.quests,
        awards=[{**aw, "is_earned": any(ea.get("key") == aw.get("key") and ea.get("template_id") == adventure.id for ea in (current_user.earned_awards or []))} for aw in (adventure.awards or [])],
        is_completed=state.is_completed,
        game_over=state.session.status == "game_over" if state.session else False,
        game_completed=state.session.status == "completed" if state.session else False,
        status_note=state.session.status_note if state.session else None,
    )

@router.post("/{game_id}/chat")
async def post_chat_message(
    game_id: str,
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Processes a user message and returns a streaming response."""
    manager = GameTurnManager(db, game_id, current_user)
    return StreamingResponse(
        manager.process_turn(payload.content, auto_visualize=payload.auto_visualize, language=payload.language), 
        media_type="text/event-stream"
    )
