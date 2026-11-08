"""Paged chat history: the story feed loads the newest messages first and older ones on scroll.

Messages are ordered by ``created_at`` with the id as tie-breaker (several messages of one
flush share a timestamp). A page is cut so it starts at a player message where possible, so an
exchange (player action, events, narration) is not split across two pages.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.logic import AdventureLogic
from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.models.chat import ChatMessage
from backend.models.user import User

router = APIRouter(tags=["Gameplay"])

DEFAULT_PAGE_SIZE = 150
MAX_PAGE_SIZE = 500


@dataclass
class HistoryPage:
    messages: list[dict[str, Any]] = field(default_factory=list)
    has_more: bool = False


class ChatHistoryPageResponse(BaseModel):
    messages: list[dict[str, Any]]
    has_more: bool


def _start_at_player_action(rows: list[ChatMessage]) -> list[ChatMessage]:
    """Drops the leading messages of a cut-off exchange; the next older page brings them."""
    first_user = next((i for i, row in enumerate(rows) if row.role == "user"), None)
    if not first_user:
        return rows
    return rows[first_user:]


async def _older_than(db: AsyncSession, session_id: str, before_id: str) -> Optional[Any]:
    """Filter for messages older than ``before_id``, or None if that message is unknown."""
    res = await db.execute(
        select(ChatMessage.created_at, ChatMessage.id).where(
            ChatMessage.session_id == session_id, ChatMessage.id == before_id
        )
    )
    cursor = res.first()
    if cursor is None:
        return None
    created_at, cursor_id = cursor
    return or_(
        ChatMessage.created_at < created_at,
        and_(ChatMessage.created_at == created_at, ChatMessage.id < cursor_id),
    )


async def load_history_page(
    db: AsyncSession, session_id: str, limit: int, before_id: Optional[str] = None
) -> HistoryPage:
    """The newest ``limit`` messages (older than ``before_id`` if given), oldest first."""
    query = select(ChatMessage).where(ChatMessage.session_id == session_id)
    if before_id:
        older = await _older_than(db, session_id, before_id)
        if older is None:
            return HistoryPage()
        query = query.where(older)
    res = await db.execute(
        query.order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc()).limit(limit + 1)
    )
    rows = list(res.scalars().all())
    has_more = len(rows) > limit
    rows = list(reversed(rows[:limit]))
    if has_more:
        rows = _start_at_player_action(rows)
    return HistoryPage([row.to_client_dict() for row in rows], has_more)


async def _visited_sequences(db: AsyncSession, session_id: str, adventure: Any) -> list[dict]:
    """The adventure's sequences that already appear in the chat history.

    Only these are sent to the client, so later chapters are not revealed.
    """
    res = await db.execute(
        select(ChatMessage.sequence_id)
        .where(ChatMessage.session_id == session_id, ChatMessage.sequence_id.is_not(None))
        .distinct()
    )
    visited = {seq_id for (seq_id,) in res.all()}
    sequences = getattr(adventure, "sequences", None) or []
    return [seq for seq in sequences if isinstance(seq, dict) and seq.get("id") in visited]


async def visited_sequence_titles(
    db: AsyncSession, session_id: str, adventure: Any
) -> dict[str, str]:
    """Sequence id -> title for every sequence the chat already reached."""
    return {
        str(seq["id"]): str(seq.get("title") or seq["id"])
        for seq in await _visited_sequences(db, session_id, adventure)
    }


async def visited_sequence_details(
    db: AsyncSession, session_id: str, adventure: Any
) -> dict[str, dict[str, Any]]:
    """Sequence id -> what the chat's chapter banner shows (title, number, description)."""
    dynamic = getattr(adventure, "sequence_progression_mode", "linear") == "dynamic"
    return {
        str(seq["id"]): {
            "title": str(seq.get("title") or seq["id"]),
            "order": seq.get("order"),
            "description": str(seq.get("description") or ""),
            "dynamic": dynamic or seq.get("progression_mode") == "dynamic",
        }
        for seq in await _visited_sequences(db, session_id, adventure)
    }


@router.get("/{game_id}/chat/history", response_model=ChatHistoryPageResponse)
async def get_chat_history_page(
    game_id: str,
    before: str = Query(..., min_length=1, max_length=36),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Older chat messages for the story feed, loaded when the reader scrolls up."""
    state = await AdventureLogic.resolve_session_state(db, game_id, user_id=current_user.id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found.")
    page = await load_history_page(db, state.session_id, limit, before_id=before)
    return ChatHistoryPageResponse(messages=page.messages, has_more=page.has_more)
