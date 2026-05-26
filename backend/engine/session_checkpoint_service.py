from __future__ import annotations

from copy import deepcopy
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.avatar import Avatar
from backend.models.chat import ChatMessage
from backend.models.game_session import GameSession
from backend.models.session_checkpoint import SessionCheckpoint
from backend.models.session_state import SessionState
from backend.schemas.checkpoint import SessionCheckpointResponse

MAX_CHECKPOINTS_PER_SESSION = 5


def _reason_title(reason: str, snapshot: dict[str, Any]) -> str:
    scene_label = str(snapshot.get("scene_label") or "").strip()
    if reason == "SCENE_CHANGE":
        if scene_label:
            return f"Checkpoint: Arrived at {scene_label}"
        return "Checkpoint: Scene Changed"
    if reason == "QUEST_UPDATE":
        return "Checkpoint: Quest Update"
    if reason == "AWARD_GRANTED":
        return "Checkpoint: Award Granted"
    return "Checkpoint"


class SessionCheckpointService:
    @staticmethod
    async def _load_context(db: AsyncSession, session_id: str) -> tuple[GameSession, SessionState, Avatar]:
        session_res = await db.execute(select(GameSession).where(GameSession.id == session_id))
        game_session = session_res.scalars().first()
        if not game_session:
            raise ValueError("Session not found.")

        state_res = await db.execute(select(SessionState).where(SessionState.session_id == session_id))
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
    def _build_snapshot(state: SessionState, avatar: Avatar, scene_label: str | None = None) -> dict[str, Any]:
        return {
            "avatar": {
                "hp": avatar.hp,
                "max_hp": avatar.max_hp,
                "stamina": avatar.stamina,
                "max_stamina": avatar.max_stamina,
                "mana": avatar.mana,
                "max_mana": avatar.max_mana,
                "exp": avatar.exp,
                "strength": avatar.strength,
                "intelligence": avatar.intelligence,
                "wisdom": avatar.wisdom,
                "dexterity": avatar.dexterity,
                "charisma": avatar.charisma,
                "armor_class": avatar.armor_class,
                "stats": deepcopy(avatar.stats or {}),
                "inventory": deepcopy(avatar.inventory or []),
                "equipment": deepcopy(avatar.equipment or {}),
                "status_effects": deepcopy(avatar.status_effects or []),
            },
            "session_state": {
                "current_scene_id": state.current_scene_id,
                "in_game_time": state.in_game_time,
                "time_system": state.time_system,
                "time_config": deepcopy(state.time_config or {}),
                "inventory": deepcopy(state.inventory or []),
                "entity_states": deepcopy(state.entity_states or {}),
                "exit_states": deepcopy(state.exit_states or {}),
                "discovered_scenes": deepcopy(state.discovered_scenes or []),
                "quests": deepcopy(state.quests or []),
                "is_completed": bool(state.is_completed),
                "scene_label": scene_label,
            },
            "scene_label": scene_label,
        }

    @staticmethod
    async def _prune_old_checkpoints(db: AsyncSession, session_id: str, keep: int = MAX_CHECKPOINTS_PER_SESSION) -> None:
        cp_res = await db.execute(
            select(SessionCheckpoint.id)
            .where(SessionCheckpoint.session_id == session_id)
            .order_by(SessionCheckpoint.created_at.desc(), SessionCheckpoint.id.desc())
        )
        checkpoint_ids = list(cp_res.scalars().all())
        stale_ids = checkpoint_ids[keep:]
        if stale_ids:
            await db.execute(delete(SessionCheckpoint).where(SessionCheckpoint.id.in_(stale_ids)))

    @staticmethod
    async def create_checkpoint(
        db: AsyncSession,
        session_id: str,
        trigger_reason: str,
        scene_label: str | None = None,
    ) -> SessionCheckpoint:
        _, state, avatar = await SessionCheckpointService._load_context(db, session_id)
        message_ids = await SessionCheckpointService._message_ids(db, session_id)

        snapshot = SessionCheckpointService._build_snapshot(state, avatar, scene_label=scene_label)
        payload = jsonable_encoder(snapshot)

        checkpoint = SessionCheckpoint(
            session_id=session_id,
            message_index=len(message_ids),
            state_snapshot=payload,
            trigger_reason=trigger_reason,
        )
        db.add(checkpoint)
        await db.flush()

        await SessionCheckpointService._prune_old_checkpoints(db, session_id)
        return checkpoint

    @staticmethod
    async def list_checkpoints(db: AsyncSession, session_id: str) -> list[SessionCheckpointResponse]:
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

        _, state, avatar = await SessionCheckpointService._load_context(db, session_id)
        snapshot = checkpoint.state_snapshot or {}
        avatar_snapshot = snapshot.get("avatar") or {}
        state_snapshot = snapshot.get("session_state") or {}

        avatar.hp = int(avatar_snapshot.get("hp", avatar.hp))
        avatar.max_hp = int(avatar_snapshot.get("max_hp", avatar.max_hp))
        avatar.stamina = int(avatar_snapshot.get("stamina", avatar.stamina))
        avatar.max_stamina = int(avatar_snapshot.get("max_stamina", avatar.max_stamina))
        avatar.mana = int(avatar_snapshot.get("mana", avatar.mana))
        avatar.max_mana = int(avatar_snapshot.get("max_mana", avatar.max_mana))
        avatar.exp = int(avatar_snapshot.get("exp", avatar.exp))
        avatar.strength = int(avatar_snapshot.get("strength", avatar.strength))
        avatar.intelligence = int(avatar_snapshot.get("intelligence", avatar.intelligence))
        avatar.wisdom = int(avatar_snapshot.get("wisdom", avatar.wisdom))
        avatar.dexterity = int(avatar_snapshot.get("dexterity", avatar.dexterity))
        avatar.charisma = int(avatar_snapshot.get("charisma", avatar.charisma))
        avatar.armor_class = int(avatar_snapshot.get("armor_class", avatar.armor_class))
        avatar.stats = deepcopy(avatar_snapshot.get("stats") or {})
        avatar.inventory = deepcopy(avatar_snapshot.get("inventory") or [])
        avatar.equipment = deepcopy(avatar_snapshot.get("equipment") or {})
        avatar.status_effects = deepcopy(avatar_snapshot.get("status_effects") or [])

        state.current_scene_id = str(state_snapshot.get("current_scene_id") or state.current_scene_id)
        state.in_game_time = int(state_snapshot.get("in_game_time", state.in_game_time or 0))
        state.time_system = str(state_snapshot.get("time_system") or state.time_system)
        state.time_config = deepcopy(state_snapshot.get("time_config") or {})
        state.inventory = deepcopy(state_snapshot.get("inventory") or [])
        state.entity_states = deepcopy(state_snapshot.get("entity_states") or {})
        state.exit_states = deepcopy(state_snapshot.get("exit_states") or {})
        state.discovered_scenes = deepcopy(state_snapshot.get("discovered_scenes") or [])
        state.quests = deepcopy(state_snapshot.get("quests") or [])
        state.is_completed = bool(state_snapshot.get("is_completed", state.is_completed))

        message_ids = await SessionCheckpointService._message_ids(db, session_id)
        stale_ids = message_ids[checkpoint.message_index :]
        if stale_ids:
            await db.execute(delete(ChatMessage).where(ChatMessage.id.in_(stale_ids)))

        return len(stale_ids)
