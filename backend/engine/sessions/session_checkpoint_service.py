"""Session checkpoints: full save states created automatically and on request."""

from __future__ import annotations

from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.engine.sessions import session_snapshot
from backend.models.avatar import Avatar
from backend.models.chat import ChatMessage
from backend.models.game_session import GameSession
from backend.models.session_checkpoint import SessionCheckpoint
from backend.models.session_state import SessionState
from backend.schemas.checkpoint import SessionCheckpointResponse

MAX_CHECKPOINTS_PER_SESSION = 5
MAX_SAVES_PER_SESSION = 10

REASON_SCENE_CHANGE = "SCENE_CHANGE"
REASON_SEQUENCE_CHANGE = "SEQUENCE_CHANGE"
REASON_MANUAL_SAVE = "MANUAL_SAVE"
REASON_SCRIPT_SAVE = "SCRIPT_SAVE"
# Saves the player or a script asked for are kept apart from the automatic checkpoints,
# so a run of scene changes never pushes them out.
SAVE_REASONS = frozenset({REASON_MANUAL_SAVE, REASON_SCRIPT_SAVE})

MAX_SAVE_LABEL_LENGTH = 80


def clean_save_label(raw: Any) -> str | None:
    return " ".join(str(raw or "").split())[:MAX_SAVE_LABEL_LENGTH] or None


def save_message(label: str | None) -> str:
    return f"Game saved: {label}" if label else "Game saved."


_FIXED_TITLES = {
    "QUEST_UPDATE": "Checkpoint: Quest Update",
    "AWARD_GRANTED": "Checkpoint: Award Granted",
    REASON_SEQUENCE_CHANGE: "Checkpoint: New Chapter",
    REASON_MANUAL_SAVE: "Save: Manual Save",
    REASON_SCRIPT_SAVE: "Save: Story Save",
}


def _reason_title(reason: str, snapshot: dict[str, Any]) -> str:
    scene_label = str(snapshot.get("scene_label") or "").strip()
    label = str(snapshot.get("label") or "").strip()
    norm = str(reason or "").upper()
    if norm in SAVE_REASONS and label:
        return f"Save: {label}"
    if norm == REASON_SCENE_CHANGE:
        return (
            f"Checkpoint: Arrived at {scene_label}" if scene_label else "Checkpoint: Scene Changed"
        )
    if norm in _FIXED_TITLES:
        return _FIXED_TITLES[norm]
    if "WORLD_MEMOR" in norm:
        return "Checkpoint: World Memory Updated"
    return f"Checkpoint: {reason.replace('_', ' ').title()}" if reason else "Checkpoint"


class SessionCheckpointService:
    @staticmethod
    async def _load_context(
        db: AsyncSession, session_id: str
    ) -> tuple[GameSession, SessionState, Avatar]:
        session_res = await db.execute(select(GameSession).where(GameSession.id == session_id))
        game_session = session_res.scalars().first()
        if not game_session:
            raise ValueError("Session not found.")

        state_res = await db.execute(
            select(SessionState).where(SessionState.session_id == session_id)
        )
        state = state_res.scalars().first()
        if not state:
            raise ValueError("Session state not found.")

        avatar_res = await db.execute(select(Avatar).where(Avatar.id == state.avatar_id))
        avatar = avatar_res.scalars().first()
        if not avatar:
            raise ValueError("Session avatar not found.")

        return game_session, state, avatar

    @staticmethod
    async def _message_ids(db: AsyncSession, session_id: str) -> list[str]:
        msg_res = await db.execute(
            select(ChatMessage.id)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        )
        return list(msg_res.scalars().all())

    @staticmethod
    async def _prune_old_checkpoints(db: AsyncSession, session_id: str, is_save: bool) -> None:
        """Keeps the newest automatic checkpoints and, separately, the newest saves."""
        kind = SessionCheckpoint.trigger_reason.in_(SAVE_REASONS)
        cp_res = await db.execute(
            select(SessionCheckpoint.id)
            .where(SessionCheckpoint.session_id == session_id, kind if is_save else ~kind)
            .order_by(SessionCheckpoint.created_at.desc(), SessionCheckpoint.id.desc())
        )
        keep = MAX_SAVES_PER_SESSION if is_save else MAX_CHECKPOINTS_PER_SESSION
        stale_ids = list(cp_res.scalars().all())[keep:]
        if stale_ids:
            await db.execute(delete(SessionCheckpoint).where(SessionCheckpoint.id.in_(stale_ids)))

    @staticmethod
    async def create_checkpoint(
        db: AsyncSession,
        session_id: str,
        trigger_reason: str,
        scene_label: str | None = None,
        label: str | None = None,
    ) -> SessionCheckpoint:
        game_session, state, avatar = await SessionCheckpointService._load_context(db, session_id)
        await db.flush()  # the world dump reads the rows, including pending changes
        message_ids = await SessionCheckpointService._message_ids(db, session_id)

        snapshot = session_snapshot.dump_session(game_session, state, avatar)
        snapshot["world"] = await session_snapshot.dump_world(db, session_id)
        snapshot["scene_label"] = scene_label
        snapshot["label"] = label

        checkpoint = SessionCheckpoint(
            session_id=session_id,
            message_index=len(message_ids),
            state_snapshot=session_snapshot.encode(snapshot),
            trigger_reason=trigger_reason,
        )
        db.add(checkpoint)
        await db.flush()

        await SessionCheckpointService._prune_old_checkpoints(
            db, session_id, is_save=trigger_reason in SAVE_REASONS
        )
        return checkpoint

    @staticmethod
    async def save_from_script(db: AsyncSession, session_id: str, labels: list[str]) -> list[str]:
        """Writes the saves ``tw.save()`` asked for; returns their system messages.

        The confirmation line is stored before the checkpoint, so restoring keeps it.
        """
        messages: list[str] = []
        for raw in labels:
            label = clean_save_label(raw)
            message = save_message(label)
            db.add(ChatMessage(session_id=session_id, role="system", content=message))
            await db.flush()
            await SessionCheckpointService.create_checkpoint(
                db, session_id, REASON_SCRIPT_SAVE, label=label
            )
            messages.append(message)
        return messages

    @staticmethod
    async def list_checkpoints(
        db: AsyncSession, session_id: str
    ) -> list[SessionCheckpointResponse]:
        cp_res = await db.execute(
            select(SessionCheckpoint)
            .where(SessionCheckpoint.session_id == session_id)
            .order_by(SessionCheckpoint.created_at.desc(), SessionCheckpoint.id.desc())
        )
        checkpoints = list(cp_res.scalars().all())
        return [
            SessionCheckpointResponse(
                id=cp.id,
                session_id=cp.session_id,
                message_index=cp.message_index,
                trigger_reason=cp.trigger_reason,
                title=_reason_title(cp.trigger_reason, cp.state_snapshot or {}),
                created_at=cp.created_at,
            )
            for cp in checkpoints
        ]

    @staticmethod
    async def restore_checkpoint(db: AsyncSession, session_id: str, checkpoint_id: str) -> int:
        cp_res = await db.execute(
            select(SessionCheckpoint).where(
                SessionCheckpoint.id == checkpoint_id,
                SessionCheckpoint.session_id == session_id,
            )
        )
        checkpoint = cp_res.scalars().first()
        if not checkpoint:
            raise ValueError("Checkpoint not found.")

        game_session, state, avatar = await SessionCheckpointService._load_context(db, session_id)
        snapshot = checkpoint.state_snapshot or {}
        session_snapshot.restore_session(snapshot, game_session, state, avatar)
        await session_snapshot.restore_world(db, state, snapshot.get("world"))

        message_ids = await SessionCheckpointService._message_ids(db, session_id)
        stale_ids = message_ids[checkpoint.message_index :]
        if stale_ids:
            await db.execute(delete(ChatMessage).where(ChatMessage.id.in_(stale_ids)))

        return len(stale_ids)
