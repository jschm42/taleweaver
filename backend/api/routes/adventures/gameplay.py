import logging
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.api.routes.adventures.logic import AdventureLogic
from backend.api.routes.adventures.schemas import (
    ChatRequest,
    ChatResponse,
    TerminalEpilogueRequest,
    TerminalEpilogueResponse,
)
from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.engine.map_engine import MapEngine
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.chat import ChatMessage
from backend.models.game_session import GameSession
from backend.models.session_state import SessionState
from backend.models.user import User
from backend.models.world_entity import WorldEntity, WorldScene
from backend.models.world_map import WorldMap

router = APIRouter(tags=["Gameplay"])
logger = logging.getLogger(__name__)

TERMINAL_EPILOGUE_STATE_KEY = "__terminal_epilogue__"


def _terminal_flags_from_state(state: SessionState) -> tuple[bool, bool]:
    """Returns (pending_terminal_epilogue, input_locked) for the current session state."""
    status = state.session.status if state.session else None
    epilogue_state = (state.exit_states or {}).get(TERMINAL_EPILOGUE_STATE_KEY) or {}
    if not isinstance(epilogue_state, dict):
        epilogue_state = {}

    completed_sent = bool(epilogue_state.get("completed_sent"))
    game_over_sent = bool(epilogue_state.get("game_over_sent"))

    pending_terminal_epilogue = (status == "completed" and not completed_sent) or (
        status == "game_over" and not game_over_sent
    )
    input_locked = status == "game_over" and game_over_sent
    return pending_terminal_epilogue, input_locked

async def _get_npc_metadata(template_id: str | None, session_id: str | None, db: AsyncSession) -> dict:
    if session_id:
        npc_query = select(WorldEntity).where(WorldEntity.session_id == session_id, WorldEntity.entity_type.in_(["NPC", "npc"]))
    elif template_id:
        npc_query = select(WorldEntity).where(WorldEntity.template_id == template_id, WorldEntity.entity_type.in_(["NPC", "npc"]))
    else:
        return {}
    npc_res = await db.execute(npc_query)
    metadata = {}
    for npc in npc_res.scalars().all():
        data = {
            "name": npc.name,
            "description": npc.description,
            "image_url": npc.image_url,
            "voice": npc.voice,
            "entity_type": "NPC",
        }
        metadata[npc.id] = data
    return metadata

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
    
    world_map = await AdventureLogic.get_or_create_map(db, state.template_id, session_id=state.session_id)
    
    entities = await AdventureLogic.build_session_entities(db, state)
    
    scene_image = AdventureLogic.resolve_session_asset(state, state.current_scene_id)
    if not scene_image:
        scene_res = await db.execute(select(WorldScene).where(WorldScene.id == state.current_scene_id, WorldScene.session_id == state.session_id))
        scene = scene_res.scalars().first()
        if not scene:
            scene_res = await db.execute(select(WorldScene).where(WorldScene.id == state.current_scene_id, WorldScene.template_id == state.template_id))
        scene = scene_res.scalars().first()
        scene_image = scene.image_url if scene else None

    pending_terminal_epilogue, input_locked = _terminal_flags_from_state(state)

    return ChatResponse(
        messages=history,
        sheet=await AdventureLogic.build_sheet_snapshot(avatar, state, db),
        combat=AdventureLogic.get_combat_snapshot(state),
        mermaid=MapEngine.to_mermaid(world_map) if world_map else None,
        map_data=MapEngine.to_dict(world_map) if world_map else None,
        nodes=await AdventureLogic.get_all_scene_metadata(db, state.template_id, session_id=state.session_id),
        entities=entities,
        npc_metadata=await _get_npc_metadata(state.template_id, state.session_id, db),
        image_url=scene_image,
        adventure_image=AdventureLogic.resolve_session_asset(state, "cover", adventure.image_url if adventure else None),
        quests=state.quests,
        awards=[
            {
                **aw,
                "is_earned": any(
                    ea.get("key") == aw.get("key")
                    and ea.get("template_id") == (adventure.id if adventure else state.template_id)
                    for ea in (current_user.earned_awards or [])
                ),
            }
            for aw in ((adventure.awards if adventure else (AdventureLogic.extract_manifest_snapshot(state).get("adventure") or {}).get("awards")) or [])
        ],
        is_completed=state.is_completed,
        game_over=state.session.status == "game_over" if state.session else False,
        game_completed=state.session.status == "completed" if state.session else False,
        status_note=state.session.status_note if state.session else None,
        input_locked=input_locked,
        pending_terminal_epilogue=pending_terminal_epilogue,
    )

@router.post("/{game_id}/chat")
async def post_chat_message(
    game_id: str,
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Processes a user message and returns a streaming response."""
    try:
        manager = GameTurnManager(db, game_id, current_user)
        return StreamingResponse(
            manager.process_turn(payload.content, auto_visualize=payload.auto_visualize, language=payload.language), 
            media_type="text/event-stream"
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to start chat turn for session %s", game_id)
        raise HTTPException(status_code=500, detail="Unable to process this turn.")


@router.post("/{game_id}/terminal-epilogue", response_model=TerminalEpilogueResponse)
async def create_terminal_epilogue(
    game_id: str,
    payload: TerminalEpilogueRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Creates the one-time terminal epilogue for completed or game-over sessions."""
    manager = GameTurnManager(db, game_id, current_user)
    return await cast(Any, manager).create_terminal_epilogue(language=payload.language)

@router.get("/{game_id}/walkthrough")
async def get_walkthrough(
    game_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns the walkthrough for the current session if revealed or in debug mode."""
    res = await db.execute(
        select(SessionState)
        .join(GameSession, GameSession.id == SessionState.session_id)
        .where(SessionState.session_id == game_id, GameSession.user_id == current_user.id)
    )
    state = res.scalars().first()
    if not state:
        raise HTTPException(status_code=404, detail="Session state not found.")
    
    # Check if revealed or debug enabled
    from backend.core.config import settings
    if not state.is_walkthrough_revealed and not settings.TALEWEAVER_DEBUG_ENABLED:
        raise HTTPException(status_code=403, detail="The walkthrough is not revealed yet.")

    return {"walkthrough": state.walkthrough or "No walkthrough available for this adventure."}
