"""Full save-state dump of a game session, used by checkpoints.

A snapshot holds the gameplay fields of the avatar, the session state and the game session,
plus every session-scoped world entity and exit row (positions, locks, clones, contents).
Player preferences (narration style, skin, debug mode, ...) are not part of a save state.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.avatar import Avatar
from backend.models.game_session import GameSession
from backend.models.session_state import SessionState
from backend.models.world_entity import WorldEntity, WorldExit

AVATAR_FIELDS = (
    "hp",
    "max_hp",
    "stamina",
    "max_stamina",
    "mana",
    "max_mana",
    "exp",
    "strength",
    "intelligence",
    "wisdom",
    "dexterity",
    "charisma",
    "armor_class",
    "stats",
    "inventory",
    "equipment",
    "status_effects",
)
STATE_FIELDS = (
    "current_scene_id",
    "in_game_time",
    "time_system",
    "time_config",
    "inventory",
    "entity_states",
    "exit_states",
    "discovered_scenes",
    "quests",
    "world_memories",
    "world_rumors",
    "compressed_history",
    "plot",
    "rules",
    "completed_condition",
    "gameover_condition",
    "completed_guard_expression",
    "gameover_guard_expression",
    "active_sequence_id",
    "active_sequence_order",
    "is_completed",
    "is_walkthrough_revealed",
)
SESSION_FIELDS = ("status", "status_note")
_ROW_SKIPPED = frozenset({"pk", "template_id", "session_id", "created_at", "updated_at"})


def _dump_fields(obj: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    return {f: deepcopy(getattr(obj, f)) for f in fields}


def _load_fields(obj: Any, data: dict[str, Any], fields: tuple[str, ...]) -> None:
    """Sets the fields present in ``data``; older snapshots simply lack the newer keys."""
    for f in (f for f in fields if f in data):
        setattr(obj, f, deepcopy(data[f]))


def _row_columns(model: Any) -> list[str]:
    return [c.key for c in model.__table__.columns if c.key not in _ROW_SKIPPED]


def _dump_row(row: Any) -> dict[str, Any]:
    return {key: deepcopy(getattr(row, key)) for key in _row_columns(type(row))}


async def _session_rows(db: AsyncSession, model: Any, session_id: str) -> list[Any]:
    res = await db.execute(select(model).where(model.session_id == session_id))
    return list(res.scalars().all())


def dump_session(game_session: GameSession, state: SessionState, avatar: Avatar) -> dict[str, Any]:
    return {
        "avatar": _dump_fields(avatar, AVATAR_FIELDS),
        "session_state": _dump_fields(state, STATE_FIELDS),
        "game_session": _dump_fields(game_session, SESSION_FIELDS),
    }


async def dump_world(db: AsyncSession, session_id: str) -> dict[str, Any]:
    return {
        "entities": [_dump_row(r) for r in await _session_rows(db, WorldEntity, session_id)],
        "exits": [_dump_row(r) for r in await _session_rows(db, WorldExit, session_id)],
    }


def restore_session(
    snapshot: dict[str, Any], game_session: GameSession, state: SessionState, avatar: Avatar
) -> None:
    _load_fields(avatar, snapshot.get("avatar") or {}, AVATAR_FIELDS)
    _load_fields(state, snapshot.get("session_state") or {}, STATE_FIELDS)
    _load_fields(game_session, snapshot.get("game_session") or {}, SESSION_FIELDS)


async def _restore_rows(
    db: AsyncSession, model: Any, state: SessionState, saved_rows: list[dict[str, Any]]
) -> None:
    """Makes the session's rows of ``model`` match the saved rows (update, delete, re-add)."""
    saved = {row["id"]: row for row in saved_rows if row.get("id")}
    columns = _row_columns(model)
    current = {row.id: row for row in await _session_rows(db, model, state.session_id)}
    stale = [row_id for row_id in current if row_id not in saved]
    if stale:
        await db.execute(
            delete(model).where(model.session_id == state.session_id, model.id.in_(stale))
        )
    for row_id, data in saved.items():
        row = current.get(row_id)
        if row is None:
            row = model(template_id=state.template_id, session_id=state.session_id)
            db.add(row)
        for key in (k for k in columns if k in data):
            setattr(row, key, deepcopy(data[key]))


async def restore_world(db: AsyncSession, state: SessionState, world: dict[str, Any]) -> None:
    """Restores the session's world rows; snapshots without a world dump leave them as they are."""
    if not isinstance(world, dict):
        return
    await _restore_rows(db, WorldEntity, state, list(world.get("entities") or []))
    await _restore_rows(db, WorldExit, state, list(world.get("exits") or []))


def encode(snapshot: dict[str, Any]) -> dict[str, Any]:
    return jsonable_encoder(snapshot)
