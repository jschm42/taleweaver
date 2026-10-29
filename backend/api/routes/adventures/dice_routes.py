"""Instant die rolls (``/roll``) without the narration turn pipeline."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.logic import AdventureLogic
from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.engine.rules.dice_command import RollCommandError, roll_from_args
from backend.models.chat import ChatMessage
from backend.models.user import User

router = APIRouter(tags=["Gameplay"])


class RollRequest(BaseModel):
    """Arguments after ``/roll`` as typed by the player (e.g. ``"20"`` or ``"d12"``)."""

    args: str = Field(default="", max_length=20)


@router.post("/{game_id}/roll")
async def roll_die_command(
    game_id: str,
    payload: RollRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Rolls one die, stores the result as a system message and returns it immediately."""
    state = await AdventureLogic.resolve_session_state(db, game_id, user_id=current_user.id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found.")
    try:
        content = roll_from_args(payload.args)
    except RollCommandError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    message = ChatMessage(session_id=state.session_id, role="system", content=content)
    db.add(message)
    await db.commit()
    return message.to_client_dict()
