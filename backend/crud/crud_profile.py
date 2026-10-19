"""Read models for the player profile: account stats and adventure session history."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.game_session import GameSession
from backend.models.session_state import SessionState
from backend.models.user import User

# Must match AdventureLogic's snapshot key; duplicated to keep this module free of route imports.
SESSION_MANIFEST_SNAPSHOT_KEY = "__manifest_snapshot__"


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


def normalize_public_data_url(url: Optional[str]) -> Optional[str]:
    """Heal legacy malformed media URLs such as /data/data/users/..."""
    if not url:
        return url
    normalized = url.replace("\\", "/")
    while normalized.startswith("/data/data/"):
        normalized = normalized.replace("/data/data/", "/data/", 1)
    return normalized


async def _session_xp_by_id(db: AsyncSession, user_id: str) -> dict[str, int]:
    rows = await db.execute(
        select(GameSession.id, Avatar.exp)
        .join(Avatar, GameSession.avatar_id == Avatar.id)
        .where(GameSession.user_id == user_id)
    )
    return {session_id: exp or 0 for session_id, exp in rows.all()}


async def build_user_profile_data(db: AsyncSession, user: User) -> dict[str, Any]:
    """Assemble the payload for UserResponse including aggregated stats."""
    adventure_count = (
        await db.execute(
            # Sessions of deleted templates (NULL template_id) still count individually.
            select(
                func.count(func.distinct(func.coalesce(GameSession.template_id, GameSession.id)))
            ).where(GameSession.user_id == user.id)
        )
    ).scalar() or 0
    total_xp = (
        await db.execute(select(func.sum(Avatar.exp)).where(Avatar.user_id == user.id))
    ).scalar() or 0
    session_xp = await _session_xp_by_id(db, user.id)

    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "profile_image_url": normalize_public_data_url(user.profile_image_url),
        "bio": user.bio,
        "default_language": user.default_language,
        "earned_awards": user.earned_awards or [],
        "is_admin": user.role == "admin",
        "adventure_count": adventure_count,
        "total_xp": total_xp,
        "game_log": [
            {**entry, "xp": session_xp.get(entry.get("session_id"), 0)}
            for entry in (user.game_log or [])
        ],
        "has_imported_defaults": user.has_imported_defaults,
        "recovery_codes_remaining": user.recovery_codes_remaining,
    }


def _snapshot_sequences(state: Optional[SessionState]) -> list:
    raw = (state.entity_states or {}) if state else {}
    snapshot = raw.get(SESSION_MANIFEST_SNAPSHOT_KEY) if isinstance(raw, dict) else None
    if not isinstance(snapshot, dict):
        return []
    for source in (snapshot.get("original_manifest"), snapshot.get("adventure")):
        if isinstance(source, dict) and isinstance(source.get("sequences"), list):
            return source["sequences"]
    return []


def _build_sequence_progress(
    raw_sequences: list, state: Optional[SessionState], session_status: str
) -> list[SequenceProgress]:
    sequences = sorted(
        (s for s in raw_sequences if isinstance(s, dict)), key=lambda s: s.get("order", 1)
    )
    if not sequences:
        return []

    finished_all = bool(state and state.is_completed) or session_status == "completed"
    active_id = state.active_sequence_id if state else None
    active_idx = next((i for i, s in enumerate(sequences) if s.get("id") == active_id), 0)

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


async def list_player_sessions(db: AsyncSession, user: User) -> list[PlayerSessionSummary]:
    """All sessions of the user with XP and sequence progress, newest first."""
    rows = await db.execute(
        select(GameSession, SessionState, AdventureTemplate, Avatar)
        .outerjoin(SessionState, SessionState.session_id == GameSession.id)
        .outerjoin(AdventureTemplate, GameSession.template_id == AdventureTemplate.id)
        .outerjoin(Avatar, Avatar.id == GameSession.avatar_id)
        .where(GameSession.user_id == user.id)
        .order_by(GameSession.updated_at.desc())
    )

    summaries: list[PlayerSessionSummary] = []
    for session, state, template, avatar in rows.all():
        raw_sequences = (template.sequences if template else None) or _snapshot_sequences(state)
        sequences = _build_sequence_progress(raw_sequences, state, session.status)
        summaries.append(
            PlayerSessionSummary(
                game_id=session.id,
                template_id=session.template_id,
                adventure_title=(template.title if template else None)
                or session.adventure_title
                or "Unknown Adventure",
                image_url=normalize_public_data_url(
                    (template.image_url if template else None) or session.adventure_image_url
                ),
                avatar_name=avatar.name if avatar else None,
                avatar_image=normalize_public_data_url(avatar.profile_image if avatar else None),
                status=session.status,
                status_note=session.status_note,
                xp=(avatar.exp or 0) if avatar else 0,
                sequences=sequences,
                sequences_completed=sum(1 for s in sequences if s.completed),
                sequences_total=len(sequences),
                created_at=session.created_at,
                updated_at=session.updated_at,
            )
        )
    return summaries
