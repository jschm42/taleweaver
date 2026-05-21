from __future__ import annotations
import logging
from typing import Any, AsyncGenerator, cast
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select, or_
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
from backend.models.world_entity import WorldEntity, WorldScene, WorldExit

router = APIRouter(tags=["Gameplay"])
logger = logging.getLogger(__name__)

TERMINAL_EPILOGUE_STATE_KEY = "__terminal_epilogue__"


class ContainerUnlockCodeRequest(BaseModel):
    code: str


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
    history = [{"id": m.id, "role": m.role, "content": m.content} for m in chat_res.scalars().all()]
    
    world_map = await AdventureLogic.get_or_create_map(db, state.template_id, session_id=state.session_id)
    map_dict = MapEngine.to_dict(world_map) if world_map else None
    
    # Augment with adjacent unvisited scenes
    if world_map and world_map.current_scene_id:
        current_node = world_map.nodes.get(world_map.current_scene_id)
        raw_current_id = current_node.get("id") if current_node else None
        
        if raw_current_id:
            exit_query = select(WorldExit).where(
                or_(
                    WorldExit.session_id == state.session_id,
                    WorldExit.template_id == state.template_id
                )
            )
            exits_res = await db.execute(exit_query)
            exits = list(exits_res.scalars().all())
            map_dict = MapEngine.augment_map_data(map_dict, exits, raw_current_id)

    entities = await AdventureLogic.build_session_entities(db, state)
    
    scene_image = await AdventureLogic.resolve_scene_image(db, state, state.current_scene_id)
    pending_terminal_epilogue, input_locked = _terminal_flags_from_state(state)

    return ChatResponse(
        messages=history,
        sheet=await AdventureLogic.build_sheet_snapshot(avatar, state, db),
        combat=AdventureLogic.get_combat_snapshot(state),
        map_data=map_dict,
        nodes=await AdventureLogic.get_all_scene_metadata(db, state.template_id, session_id=state.session_id),
        entities=entities,
        npc_metadata=await AdventureLogic.get_npc_metadata(db, state.template_id, session_id=state.session_id),
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
        turn_id = uuid4().hex

        async def _stream_with_turn_id(source: AsyncGenerator[str, None]) -> AsyncGenerator[str, None]:
            async for chunk in source:
                if isinstance(chunk, str) and chunk.startswith("event:"):
                    yield f"id: {turn_id}\n{chunk}"
                else:
                    yield chunk

        return StreamingResponse(
            _stream_with_turn_id(
                manager.process_turn(payload.content, auto_visualize=payload.auto_visualize, language=payload.language)
            ),
            media_type="text/event-stream",
            headers={"X-Taleweaver-Turn-Id": turn_id},
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to start chat turn for session %s", game_id)
        raise HTTPException(status_code=500, detail="Unable to process this turn.") from exc


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


@router.post("/{game_id}/text-logs/{entity_id}/read")
async def mark_text_log_read(
    game_id: str,
    entity_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Marks a READABLE object as read in session-scoped state overrides."""
    state = await AdventureLogic.resolve_session_state(db, game_id, user_id=current_user.id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found.")

    ent_res = await db.execute(
        select(WorldEntity).where(
            WorldEntity.session_id == state.session_id,
            WorldEntity.id == entity_id,
        )
    )
    entity = ent_res.scalars().first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found in this session.")

    if entity.entity_type != "OBJECT" or str(entity.item_type or "").upper() != "READABLE":
        raise HTTPException(status_code=400, detail="Entity is not a readable text log.")

    entity_states = dict(state.entity_states or {})
    current_entry = entity_states.get(entity.id)
    override_entry = dict(current_entry) if isinstance(current_entry, dict) else {}
    override_entry["is_read"] = True
    entity_states[entity.id] = override_entry

    state.entity_states = entity_states
    await db.commit()

    return {"status": "ok", "entity_id": entity.id, "is_read": True}


@router.post("/{game_id}/containers/{entity_id}/unlock-code")
async def unlock_container_with_code(
    game_id: str,
    entity_id: str,
    payload: ContainerUnlockCodeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Deterministically unlocks a container when the provided code matches code_to_unlock."""
    state = await AdventureLogic.resolve_session_state(db, game_id, user_id=current_user.id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found.")

    ent_res = await db.execute(
        select(WorldEntity).where(
            WorldEntity.session_id == state.session_id,
            WorldEntity.id == entity_id,
        )
    )
    entity = ent_res.scalars().first()
    if not entity or entity.entity_type != "OBJECT" or str(entity.item_type or "").upper() != "CONTAINER":
        raise HTTPException(status_code=404, detail="Container not found.")

    metadata_json = dict(entity.metadata_json or {})
    expected_code = str(metadata_json.get("code_to_unlock") or "").strip()
    if not expected_code:
        raise HTTPException(status_code=400, detail="This container does not require a code.")

    submitted_code = str(payload.code or "").strip()
    if not submitted_code:
        raise HTTPException(status_code=400, detail="Code is required.")
    if submitted_code.lower() != expected_code.lower():
        raise HTTPException(status_code=403, detail="Invalid access code.")

    entity_states = dict(state.entity_states or {})
    entry = dict(entity_states.get(entity.id) or {})
    entry["locked"] = False
    entity_states[entity.id] = entry
    state.entity_states = entity_states
    await db.commit()

    return {"status": "ok", "entity_id": entity.id, "locked": False}
