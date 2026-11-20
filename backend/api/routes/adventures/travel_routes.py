"""``GET /{game_id}/travel/options``: the fast travel points the player can travel to.

Returns ``{"blocked": "<reason or empty>", "points": [{scene_id, label, section_id, available,
reason, minutes, hops, solo_passage}]}`` (see ``fast_travel_plan.py``). The player's map shows
them; choosing one sends ``/fast_travel <scene id>`` as a regular message.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.fast_travel_plan import load_travel_plan
from backend.api.routes.adventures.logic import AdventureLogic
from backend.api.routes.adventures.session_adventure import load_session_adventure
from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.models.user import User

router = APIRouter(tags=["Gameplay"])


@router.get("/{game_id}/travel/options")
async def get_travel_options(
    game_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Unlocked fast travel points with route time, or why travel is not possible."""
    state = await AdventureLogic.resolve_session_state(db, game_id, user_id=current_user.id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found.")
    adventure = await load_session_adventure(db, state)
    plan = await load_travel_plan(db, state, adventure)
    return plan.as_dict()
