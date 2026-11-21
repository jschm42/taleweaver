"""Session expansion endpoints: regions built after the session started.

- ``GET /{game_id}/expansion``: ``{"pending": [{id, label, description}]}``
- ``POST /{game_id}/expansion``: copies every pending region into the session and returns
  ``{"added": [...]}`` (``session_expansion.py``). The play view offers it once on load.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.logic import AdventureLogic
from backend.api.routes.adventures.session_expansion import expand_session, pending_sections
from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.models.user import User

router = APIRouter(tags=["Gameplay"])


def _summary(sections: list[dict]) -> list[dict]:
    return [{"id": s["id"], "label": s["label"], "description": s["description"]} for s in sections]


async def _owned_state(db: AsyncSession, game_id: str, user: User):
    state = await AdventureLogic.resolve_session_state(db, game_id, user_id=user.id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found.")
    return state


@router.get("/{game_id}/expansion")
async def get_session_expansion(
    game_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Regions the author built after this session started."""
    state = await _owned_state(db, game_id, current_user)
    return {"pending": _summary(await pending_sections(db, state))}


@router.post("/{game_id}/expansion")
async def apply_session_expansion(
    game_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Adds every pending region to this session; existing progress is not touched."""
    state = await _owned_state(db, game_id, current_user)
    return {"added": _summary(await expand_session(db, state))}
