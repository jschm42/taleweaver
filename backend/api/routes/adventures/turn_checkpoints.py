"""Checkpoints of one player turn: queued during the turn, written once at its end.

Automatic checkpoints are taken when the turn changed the scene or the active sequence,
whatever moved the player (exit, map, script teleport, GM). ``/save`` queues a manual save
here; ``tw.save()`` writes its save at once (``SessionCheckpointService.save_from_script``).
"""

from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.engine.sessions.session_checkpoint_service import (
    REASON_SCENE_CHANGE,
    REASON_SEQUENCE_CHANGE,
    SAVE_REASONS,
    SessionCheckpointService,
    clean_save_label,
    save_message,
)
from backend.models.world_entity import WorldScene


def _anchor(state: Any) -> tuple[Any, Any]:
    return (state.current_scene_id, state.active_sequence_id)


async def _scene_label(db: AsyncSession, state: Any) -> Optional[str]:
    res = await db.execute(
        select(WorldScene.label)
        .where(
            WorldScene.id == state.current_scene_id,
            or_(
                WorldScene.session_id == state.session_id,
                WorldScene.template_id == state.template_id,
            ),
        )
        .order_by(WorldScene.session_id.is_(None))
    )
    return res.scalars().first()


class TurnCheckpoints:
    def __init__(self) -> None:
        self.pending: dict[str, Optional[str]] = {}
        self.scene_label: Optional[str] = None
        self.anchor: Optional[tuple[Any, Any]] = None

    def start_turn(self, state: Any) -> None:
        self.anchor = _anchor(state)

    def queue(
        self, reason: str, *, scene_label: Optional[str] = None, label: Optional[str] = None
    ) -> None:
        self.pending[reason] = clean_save_label(label) or self.pending.get(reason)
        if scene_label:
            self.scene_label = scene_label

    def _queue_boundary(self, state: Any) -> None:
        if self.anchor is None:
            return
        scene_before, sequence_before = self.anchor
        if state.current_scene_id != scene_before:
            self.queue(REASON_SCENE_CHANGE)
        if state.active_sequence_id != sequence_before:
            self.queue(REASON_SEQUENCE_CHANGE)

    async def persist(self, manager: Any) -> list[str]:
        """Writes the queued checkpoints and returns their SSE events."""
        state = manager.state
        if state is None:
            return []
        self._queue_boundary(state)
        self.anchor = _anchor(state)
        if not self.pending:
            return []
        events: list[str] = []
        scene_label = self.scene_label or await _scene_label(manager.db, state)
        for reason, label in sorted(self.pending.items()):
            events.extend(await self._write(manager, reason, label, scene_label))
        await manager.db.commit()
        self.pending.clear()
        self.scene_label = None
        return events

    @staticmethod
    async def _write(
        manager: Any, reason: str, label: Optional[str], scene_label: Optional[str]
    ) -> list[str]:
        events: list[str] = []
        if reason in SAVE_REASONS:
            # Saved before the checkpoint, so restoring the save keeps its confirmation line.
            message = save_message(label)
            await manager._save_chat_message("system", message)
            events.append(
                f"event: system\ndata: {json.dumps({'role': 'system', 'content': message})}\n\n"
            )
        checkpoint = await SessionCheckpointService.create_checkpoint(
            manager.db, manager.state.session_id, reason, scene_label=scene_label, label=label
        )
        created = checkpoint.created_at.isoformat() if checkpoint.created_at else None
        payload = {"id": checkpoint.id, "trigger_reason": reason, "created_at": created}
        events.append(f"event: checkpoint\ndata: {json.dumps(payload)}\n\n")
        return events
