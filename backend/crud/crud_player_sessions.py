"""Paged adventure history of a player: filters, search, sorting and per-status counts.

The list only loads the columns it shows. ``SessionState.entity_states`` (large) is read
just for sessions whose template was deleted, to recover their sequences from the snapshot.
"""

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel
from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.crud.crud_profile import normalize_public_data_url
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.game_session import GameSession
from backend.models.session_state import SessionState
from backend.models.user import User

# Must match AdventureLogic's snapshot key; duplicated to keep this module free of route imports.
SESSION_MANIFEST_SNAPSHOT_KEY = "__manifest_snapshot__"
SESSION_STATUSES = ("active", "completed", "game_over", "archived")
SessionSort = Literal["recent", "oldest", "title", "xp"]
MAX_PAGE_SIZE = 100


class SequenceProgress(BaseModel):
    id: Optional[str] = None
    title: str
    exp_reward: int = 0
    completed: bool = False
    active: bool = False


class PlayerSessionSummary(BaseModel):
    game_id: str
    template_id: Optional[str] = None
    adventure_title: str
    image_url: Optional[str] = None
    avatar_name: Optional[str] = None
    avatar_image: Optional[str] = None
    status: str = "active"
    status_note: Optional[str] = None
    xp: int = 0
    sequences: list[SequenceProgress] = []
    sequences_completed: int = 0
    sequences_total: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_played_at: Optional[datetime] = None


class PlayerSessionPage(BaseModel):
    items: list[PlayerSessionSummary]
    # Sessions matching status filter and search.
    total: int
    # Per status (plus "all") for the search alone: the numbers on the filter chips.
    counts: dict[str, int]
    # Per status (plus "all") without any filter: the profile stats.
    totals: dict[str, int]


class SessionListQuery(BaseModel):
    status: Optional[str] = None
    search: str = ""
    sort: SessionSort = "recent"
    limit: int = 20
    offset: int = 0


_TITLE = func.coalesce(AdventureTemplate.title, GameSession.adventure_title, "")
_ORDER_BY = {
    "recent": (
        func.coalesce(GameSession.last_played_at, GameSession.updated_at).desc(),
        GameSession.id.desc(),
    ),
    "oldest": (GameSession.created_at.asc(), GameSession.id.asc()),
    "title": (func.lower(_TITLE).asc(), GameSession.id.asc()),
    "xp": (func.coalesce(Avatar.exp, 0).desc(), GameSession.id.desc()),
}


def _joined(query: Select, user_id: str, search: str) -> Select:
    """Join template and avatar, restrict to the user, apply the text search."""
    query = (
        query.outerjoin(AdventureTemplate, GameSession.template_id == AdventureTemplate.id)
        .outerjoin(Avatar, Avatar.id == GameSession.avatar_id)
        .where(GameSession.user_id == user_id)
    )
    term = search.strip()
    if not term:
        return query
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    pattern = f"%{escaped}%"
    return query.where(
        or_(_TITLE.ilike(pattern, escape="\\"), Avatar.name.ilike(pattern, escape="\\"))
    )


async def _status_counts(db: AsyncSession, user_id: str, search: str) -> dict[str, int]:
    query = _joined(
        select(GameSession.status, func.count()).select_from(GameSession), user_id, search
    ).group_by(GameSession.status)
    counts = dict.fromkeys(SESSION_STATUSES, 0)
    for status, count in (await db.execute(query)).all():
        counts[status] = counts.get(status, 0) + count
    counts["all"] = sum(counts.values())
    return counts


async def _snapshot_sequences_by_id(db: AsyncSession, session_ids: list[str]) -> dict[str, list]:
    """Sequences from the manifest snapshot, for sessions whose template is gone."""
    if not session_ids:
        return {}
    rows = await db.execute(
        select(SessionState.session_id, SessionState.entity_states).where(
            SessionState.session_id.in_(session_ids)
        )
    )
    return {session_id: _snapshot_sequences(states) for session_id, states in rows.all()}


def _snapshot_sequences(entity_states: Any) -> list:
    raw = entity_states if isinstance(entity_states, dict) else {}
    snapshot = raw.get(SESSION_MANIFEST_SNAPSHOT_KEY)
    if not isinstance(snapshot, dict):
        return []
    for source in (snapshot.get("original_manifest"), snapshot.get("adventure")):
        if isinstance(source, dict) and isinstance(source.get("sequences"), list):
            return source["sequences"]
    return []


def build_sequence_progress(
    raw_sequences: list,
    is_completed: Optional[bool],
    active_sequence_id: Optional[str],
    session_status: str,
) -> list[SequenceProgress]:
    sequences = sorted(
        (s for s in raw_sequences if isinstance(s, dict)), key=lambda s: s.get("order", 1)
    )
    if not sequences:
        return []

    finished_all = bool(is_completed) or session_status == "completed"
    active_idx = next((i for i, s in enumerate(sequences) if s.get("id") == active_sequence_id), 0)
    return [
        SequenceProgress(
            id=seq.get("id"),
            title=seq.get("title") or seq.get("id") or f"Chapter {idx + 1}",
            exp_reward=int(seq.get("exp_reward") or 0),
            completed=finished_all or idx < active_idx,
            active=not finished_all and idx == active_idx and session_status == "active",
        )
        for idx, seq in enumerate(sequences)
    ]


def _summary(row: Any, raw_sequences: list) -> PlayerSessionSummary:
    session = row.GameSession
    sequences = build_sequence_progress(
        raw_sequences, row.is_completed, row.active_sequence_id, session.status
    )
    return PlayerSessionSummary(
        game_id=session.id,
        template_id=session.template_id,
        adventure_title=row.template_title or session.adventure_title or "Unknown Adventure",
        image_url=normalize_public_data_url(row.template_image or session.adventure_image_url),
        avatar_name=row.avatar_name,
        avatar_image=normalize_public_data_url(row.avatar_image),
        status=session.status,
        status_note=session.status_note,
        xp=row.avatar_exp or 0,
        sequences=sequences,
        sequences_completed=sum(1 for s in sequences if s.completed),
        sequences_total=len(sequences),
        created_at=session.created_at,
        updated_at=session.updated_at,
        last_played_at=session.last_played_at,
    )


async def _page_rows(db: AsyncSession, user: User, params: SessionListQuery) -> list[Any]:
    query = _joined(
        select(
            GameSession,
            AdventureTemplate.title.label("template_title"),
            AdventureTemplate.image_url.label("template_image"),
            AdventureTemplate.sequences.label("template_sequences"),
            Avatar.name.label("avatar_name"),
            Avatar.profile_image.label("avatar_image"),
            Avatar.exp.label("avatar_exp"),
            SessionState.is_completed,
            SessionState.active_sequence_id,
        )
        .select_from(GameSession)
        .outerjoin(SessionState, SessionState.session_id == GameSession.id),
        user.id,
        params.search,
    )
    if params.status:
        query = query.where(GameSession.status == params.status)
    query = query.order_by(*_ORDER_BY[params.sort]).limit(params.limit).offset(params.offset)
    return list((await db.execute(query)).all())


async def list_player_sessions(
    db: AsyncSession, user: User, params: Optional[SessionListQuery] = None
) -> PlayerSessionPage:
    """One page of the user's sessions with XP, sequence progress and status counts."""
    params = params or SessionListQuery()
    params.limit = max(1, min(params.limit, MAX_PAGE_SIZE))
    params.offset = max(0, params.offset)

    rows = await _page_rows(db, user, params)
    missing = [r.GameSession.id for r in rows if not r.template_sequences]
    snapshots = await _snapshot_sequences_by_id(db, missing)
    items = [_summary(r, r.template_sequences or snapshots.get(r.GameSession.id, [])) for r in rows]

    counts = await _status_counts(db, user.id, params.search)
    totals = counts if not params.search.strip() else await _status_counts(db, user.id, "")
    total = counts.get(params.status, 0) if params.status else counts["all"]
    return PlayerSessionPage(items=items, total=total, counts=counts, totals=totals)
