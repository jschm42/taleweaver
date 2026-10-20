"""REST endpoints driving the autonomous play-agent from the in-game control panel."""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.agent_settings import (
    AgentSettingsUpdate,
    apply_settings_update,
    build_agent_snapshot,
)
from backend.api.routes.adventures.agent_turn_stream import ensure_agent_active, stream_agent_turn
from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.models.user import User

router = APIRouter(tags=["Play-Agent"])


@router.post("/{game_id}/agent/turn")
async def run_agent_turn(
    game_id: str,
    current_user: User = Depends(get_current_user),
):
    """Computes an agent decision based on walkthrough & game state, then executes the turn."""
    await ensure_agent_active(game_id, current_user)
    return StreamingResponse(
        stream_agent_turn(game_id, current_user),
        media_type="text/event-stream",
        headers={"X-Taleweaver-Turn-Id": uuid4().hex},
    )


@router.patch("/{game_id}/agent/settings")
async def update_agent_settings(
    game_id: str,
    payload: AgentSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Updates play-agent mode, personality and options for a session."""
    manager = GameTurnManager(db, game_id, current_user)
    if not await manager.initialize():
        raise HTTPException(status_code=404, detail="Game session not found.")
    try:
        apply_settings_update(manager.state, payload, current_user.llm_settings)
    except ValueError:
        raise HTTPException(status_code=400, detail="Unknown play-agent personality.") from None
    await db.commit()
    return build_agent_snapshot(manager.state)
