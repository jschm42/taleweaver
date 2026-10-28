"""Shared steps of the deterministic container / exit / switch unlock endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.engine.switch_service import SwitchService
from backend.engine.switch_states import state_label
from backend.engine.trigger_service import TriggerService
from backend.models.avatar import Avatar
from backend.models.chat import ChatMessage
from backend.models.session_state import SessionState
from backend.models.user import User
from backend.models.world_entity import WorldEntity

DEFAULT_UNLOCK_XP = 100


def add_system_message(db: AsyncSession, state: SessionState, content: str) -> None:
    db.add(ChatMessage(session_id=state.session_id, role="system", content=content))


async def load_session_object(
    db: AsyncSession, state: SessionState, entity_id: str, item_type: str, not_found: str
) -> WorldEntity:
    """Session-scoped OBJECT entity of the given item type, or HTTP 404."""
    res = await db.execute(
        select(WorldEntity).where(
            WorldEntity.session_id == state.session_id, WorldEntity.id == entity_id
        )
    )
    entity = res.scalars().first()
    is_match = (
        entity is not None
        and entity.entity_type == "OBJECT"
        and str(entity.item_type or "").upper() == item_type
    )
    if not is_match:
        raise HTTPException(status_code=404, detail=not_found)
    return entity


async def load_avatar(db: AsyncSession, state: SessionState) -> Avatar | None:
    res = await db.execute(select(Avatar).where(Avatar.id == state.avatar_id))
    return res.scalars().first()


async def require_avatar(db: AsyncSession, state: SessionState) -> Avatar:
    avatar = await load_avatar(db, state)
    if not avatar:
        raise HTTPException(status_code=404, detail="Avatar not found.")
    return avatar


def _normalized_item_id(item: Any) -> str:
    raw = item.get("id") if isinstance(item, dict) else item
    return str(raw or "").strip().upper()


def avatar_has_item(avatar: Avatar, item_id: str) -> bool:
    return item_id in {_normalized_item_id(item) for item in (avatar.inventory or [])}


def inventory_item_name(avatar: Avatar, item_id: str) -> str:
    """Display name of an inventory item for narration (falls back to the ID)."""
    for item in avatar.inventory or []:
        if isinstance(item, dict) and _normalized_item_id(item) == item_id:
            return item.get("name") or item_id
    return item_id


def require_value(value: Any, detail: str) -> str:
    """Stripped string value, or HTTP 400 when empty."""
    cleaned = str(value or "").strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail=detail)
    return cleaned


async def enforce_unlock_guard(
    db: AsyncSession,
    state: SessionState,
    target_id: str,
    expression: str | None,
    failure_script: str | None,
    failure_text: str | None,
) -> None:
    """Evaluates an unlock_expression guard; fires on_unlock_failure and raises 403 if unmet."""
    if not expression:
        return
    passed, err = await TriggerService.evaluate_guard(db, state, expression)
    if passed:
        return
    if failure_script or failure_text:
        await TriggerService.execute_trigger(
            db,
            state,
            "on_unlock_failure",
            target_id,
            script_code=failure_script,
            narrative_text=failure_text or err,
        )
        await db.commit()
    raise HTTPException(status_code=403, detail=failure_text or err or "Guard condition not met.")


async def fire_unlock_success(
    db: AsyncSession,
    state: SessionState,
    target_id: str,
    success_script: str | None,
    success_text: str | None,
) -> None:
    if not (success_script or success_text):
        return
    await TriggerService.execute_trigger(
        db,
        state,
        "on_unlock_success",
        target_id,
        script_code=success_script,
        narrative_text=success_text,
    )


async def enforce_container_guard(
    db: AsyncSession, state: SessionState, entity: WorldEntity, metadata_json: dict
) -> None:
    await enforce_unlock_guard(
        db,
        state,
        entity.id,
        metadata_json.get("unlock_expression"),
        metadata_json.get("on_unlock_failure_script"),
        metadata_json.get("on_unlock_failure_text"),
    )


async def fire_container_unlock_success(
    db: AsyncSession, state: SessionState, entity: WorldEntity, metadata_json: dict
) -> None:
    await fire_unlock_success(
        db,
        state,
        entity.id,
        metadata_json.get("on_unlock_success_script"),
        metadata_json.get("on_unlock_success_text"),
    )


def mark_container_unlocked(state: SessionState, entity_id: str) -> bool:
    """Stores locked=False in the session; returns whether it was locked before (XP once)."""
    entity_states = dict(state.entity_states or {})
    entry = dict(entity_states.get(entity_id) or {})
    was_locked = entry.get("locked") if "locked" in entry else True
    entry["locked"] = False
    entity_states[entity_id] = entry
    state.entity_states = entity_states
    return bool(was_locked)


def award_unlock_xp(avatar: Avatar, metadata_json: dict) -> int:
    xp_reward = (
        metadata_json.get("exp_reward") or metadata_json.get("xp_reward") or DEFAULT_UNLOCK_XP
    )
    avatar.exp = (avatar.exp or 0) + xp_reward
    return xp_reward


async def enforce_exit_guard(db: AsyncSession, state: SessionState, world_exit: Any) -> None:
    await enforce_unlock_guard(
        db,
        state,
        world_exit.id,
        world_exit.unlock_expression,
        world_exit.on_unlock_failure_script,
        world_exit.on_unlock_failure_text,
    )


async def open_exit(db: AsyncSession, state: SessionState, world_exit: Any, message: str) -> dict:
    """Unlocks the exit, narrates it, fires on_unlock_success, and commits."""
    world_exit.is_locked = False
    add_system_message(db, state, message)
    await fire_unlock_success(
        db,
        state,
        world_exit.id,
        world_exit.on_unlock_success_script,
        world_exit.on_unlock_success_text,
    )
    await db.commit()
    return {"status": "ok", "exit_id": world_exit.id, "is_locked": False}


# ---------------------------------------------------------------------------
# Switches
# ---------------------------------------------------------------------------


@dataclass
class SwitchFlip:
    """A validated switch state change (current -> target) and its transition definition."""

    entity: WorldEntity
    config: dict
    transition: dict
    gates: dict
    target_state: str
    session_states: dict
    entry: dict

    @property
    def fail_message(self) -> str:
        return str(self.transition.get("fail_message") or "").strip()

    @property
    def target_label(self) -> str:
        """In-game text of the target state (its label, or the ID)."""
        return state_label(self.config, self.target_state)


async def resolve_switch_flip(
    db: AsyncSession, state: SessionState, entity_id: str, requested_state: str
) -> SwitchFlip:
    """Validates the requested target state and finds the matching transition (HTTP 4xx otherwise)."""
    entity = await load_session_object(db, state, entity_id, "SWITCH", "Switch not found.")
    config = SwitchService.resolve_switch_config(entity)
    allowed_states = [
        str(s).strip().upper() for s in (config.get("states") or []) if str(s).strip()
    ]

    target_state = str(requested_state or "").strip().upper()
    if target_state not in allowed_states:
        raise HTTPException(status_code=400, detail=f"Invalid target state '{target_state}'.")

    session_states = dict(state.entity_states or {})
    entry = dict(session_states.get(entity.id) or {})
    configured_current = str(config.get("initial_state") or allowed_states[0]).strip().upper()
    current_state = str(entry.get("switch_state") or configured_current).strip().upper()
    if current_state == target_state:
        raise HTTPException(status_code=400, detail=f"Switch is already in state '{target_state}'.")

    transition = SwitchService.resolve_transition(config, current_state, target_state)
    if transition is None:
        raise HTTPException(
            status_code=400, detail="No transition definition found for this state change."
        )
    gates = transition.get("gates") if isinstance(transition.get("gates"), dict) else {}
    return SwitchFlip(entity, config, transition, gates, target_state, session_states, entry)


class SwitchFlipRunner:
    """Runs switch transition triggers through the scripting engine of the session."""

    def __init__(self, db: AsyncSession, manager: GameTurnManager, flip: SwitchFlip, context: Any):
        self.db = db
        self.manager = manager
        self.flip = flip
        self.context = context
        self.runner = manager._get_script_runner()

    @classmethod
    async def create(
        cls, db: AsyncSession, game_id: str, user: User, state: SessionState, flip: SwitchFlip
    ) -> SwitchFlipRunner:
        manager = GameTurnManager(db=db, game_id=game_id, user=user, state=state)
        await manager.initialize()
        context = await manager._build_script_context()
        return cls(db, manager, flip, context)

    async def _run_triggers(self, success: bool) -> None:
        SwitchService.execute_transition_triggers(
            runner=self.runner,
            config=self.flip.config,
            transition=self.flip.transition,
            success=success,
            context=self.context,
            switch_id=self.flip.entity.id,
        )
        await self.manager._apply_script_changeset(self.context.changeset)

    async def fail(self, detail: str) -> None:
        """Fires the failure triggers, commits them, and rejects the flip with HTTP 403."""
        await self._run_triggers(success=False)
        await self.db.commit()
        raise HTTPException(status_code=403, detail=detail)

    async def enforce_gate_expression(self) -> None:
        gates = self.flip.gates
        expr = str(gates.get("expression") or gates.get("condition") or "").strip()
        if not expr:
            return
        passed, err = SwitchService.evaluate_gate_expression(expr, self.context)
        if not passed:
            await self.fail(self.flip.fail_message or err or "Guard condition not met.")

    async def succeed(self, state: SessionState, message: str) -> dict:
        flip = self.flip
        flip.entry["switch_state"] = flip.target_state
        flip.session_states[flip.entity.id] = flip.entry
        state.entity_states = flip.session_states

        await self._run_triggers(success=True)
        outcomes = flip.config.get("outcomes")
        await self.manager._apply_switch_outcomes(
            outcomes if isinstance(outcomes, list) else [], flip.target_state
        )
        add_system_message(self.db, state, message)
        await self.db.commit()
        return {"status": "ok", "entity_id": flip.entity.id, "switch_state": flip.target_state}
