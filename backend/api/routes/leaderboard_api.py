"""Leaderboard routes: rank players by XP, awards and quest outcomes."""

from __future__ import annotations

import logging
from collections import Counter
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.crud.crud_profile import normalize_public_data_url
from backend.models.avatar import Avatar
from backend.models.game_session import GameSession
from backend.models.session_state import SessionState
from backend.models.user import User

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])
logger = logging.getLogger(__name__)

USER_DEP = Depends(get_current_user)
DB_DEP = Depends(get_db)


class LeaderboardEntry(BaseModel):
    id: str
    username: str
    profile_image_url: Optional[str] = None
    bio: Optional[str] = None
    rank: int
    total_xp: int
    completed_quests: int
    failed_quests: int
    total_awards: int
    adventure_count: int
    earned_awards: list[dict[str, Any]] = []


class LeaderboardResponse(BaseModel):
    players: list[LeaderboardEntry]
    total_players: int


async def _xp_by_user(db: AsyncSession) -> dict[str, int]:
    rows = await db.execute(
        select(Avatar.user_id, func.coalesce(func.sum(Avatar.exp), 0)).group_by(Avatar.user_id)
    )
    return {user_id: int(total or 0) for user_id, total in rows.all()}


async def _adventures_by_user(db: AsyncSession) -> dict[str, int]:
    adventure_key = func.coalesce(GameSession.template_id, GameSession.id)
    rows = await db.execute(
        select(GameSession.user_id, func.count(func.distinct(adventure_key))).group_by(
            GameSession.user_id
        )
    )
    return {user_id: int(count or 0) for user_id, count in rows.all()}


def _tally_quests(quests: Any, completed: Counter[str], failed: Counter[str], user_id: str) -> None:
    if not isinstance(quests, list):
        return
    for quest in quests:
        if not isinstance(quest, dict):
            continue
        status = str(quest.get("status") or "").lower()
        completed[user_id] += status == "completed"
        failed[user_id] += status == "failed"


async def _quests_by_user(db: AsyncSession) -> tuple[Counter[str], Counter[str]]:
    rows = await db.execute(
        select(func.coalesce(SessionState.user_id, GameSession.user_id), SessionState.quests).join(
            GameSession, SessionState.session_id == GameSession.id
        )
    )
    completed: Counter[str] = Counter()
    failed: Counter[str] = Counter()
    for user_id, quests in rows.all():
        _tally_quests(quests, completed, failed, user_id)
    return completed, failed


def _awards_of(user: User) -> list[dict[str, Any]]:
    awards = user.earned_awards or []
    return [award for award in awards if isinstance(award, dict)]


def _sort_key(entry: LeaderboardEntry) -> tuple[int, int, int, int, str]:
    return (
        -entry.total_xp,
        -entry.total_awards,
        -entry.completed_quests,
        entry.failed_quests,
        entry.username.lower(),
    )


async def _build_leaderboard(db: AsyncSession) -> list[LeaderboardEntry]:
    users = (await db.execute(select(User))).scalars().all()
    xp = await _xp_by_user(db)
    adventures = await _adventures_by_user(db)
    completed, failed = await _quests_by_user(db)

    entries: list[LeaderboardEntry] = []
    for user in users:
        awards = _awards_of(user)
        entries.append(
            LeaderboardEntry(
                id=user.id,
                username=user.username,
                profile_image_url=normalize_public_data_url(user.profile_image_url),
                bio=user.bio,
                rank=0,
                total_xp=xp.get(user.id, 0),
                completed_quests=completed.get(user.id, 0),
                failed_quests=failed.get(user.id, 0),
                total_awards=len(awards),
                adventure_count=adventures.get(user.id, 0),
                earned_awards=awards,
            )
        )

    entries.sort(key=_sort_key)
    for index, entry in enumerate(entries, start=1):
        entry.rank = index
    return entries


@router.get("", response_model=LeaderboardResponse)
async def get_leaderboard(
    current_user: User = USER_DEP, db: AsyncSession = DB_DEP
) -> LeaderboardResponse:
    entries = await _build_leaderboard(db)
    logger.debug("Leaderboard built with %d players for user %s", len(entries), current_user.id)
    return LeaderboardResponse(players=entries, total_players=len(entries))


@router.get("/player/{user_id}", response_model=LeaderboardEntry)
async def get_leaderboard_player(
    user_id: str, current_user: User = USER_DEP, db: AsyncSession = DB_DEP
) -> LeaderboardEntry:
    entries = await _build_leaderboard(db)
    entry = next((e for e in entries if e.id == user_id), None)
    if entry is None:
        raise HTTPException(status_code=404, detail="Player not found")
    return entry


@router.get("/player/{user_id}/awards", response_model=list[dict[str, Any]])
async def get_leaderboard_player_awards(
    user_id: str, current_user: User = USER_DEP, db: AsyncSession = DB_DEP
) -> list[dict[str, Any]]:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Player not found")
    return _awards_of(user)
