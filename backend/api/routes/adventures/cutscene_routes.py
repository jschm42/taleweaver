"""Cut-scenes in play: the snapshot field and the player's confirmation.

The next queued cut-scene reaches the client as ``cutscene`` in ``GET /chat`` and in the
pre-narration ``state`` stream event (``cutscene_snapshot``). After it was shown (or skipped)
the client sends ``POST /{game_id}/cutscene/seen {token}``, which removes it from the queue and
returns the next one, if any. Spec: docs/specs/cutscenes.md.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from backend.api.routes.adventures.logic import AdventureLogic
from backend.api.routes.adventures.session_adventure import load_session_adventure
from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.engine.cutscenes.queue import client_cutscene, drop_unknown, mark_seen
from backend.models.session_state import SessionState
from backend.models.user import User

router = APIRouter(tags=["Gameplay"])


class CutsceneSeenRequest(BaseModel):
    token: str = Field(..., min_length=1, max_length=64)


def cutscene_snapshot(state: SessionState, adventure: Any) -> Optional[dict[str, Any]]:
    """The cut-scene the client shows next, or None."""
    return client_cutscene(
        state.entity_states,
        getattr(adventure, "cutscenes", None),
        getattr(adventure, "audio_tracks", None),
        state.template_id,
    )


@router.post("/{game_id}/cutscene/seen")
async def mark_cutscene_seen(
    game_id: str,
    payload: CutsceneSeenRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Removes a shown cut-scene from the queue; returns the next one (``cutscene``) or None."""
    state = await AdventureLogic.resolve_session_state(db, game_id, user_id=current_user.id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found.")
    adventure = await load_session_adventure(db, state)
    entity_states = dict(state.entity_states or {})
    changed = mark_seen(entity_states, payload.token)
    changed = drop_unknown(entity_states, getattr(adventure, "cutscenes", None)) or changed
    if changed:
        state.entity_states = entity_states
        flag_modified(state, "entity_states")
        await db.commit()
    return {"cutscene": cutscene_snapshot(state, adventure)}
