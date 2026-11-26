"""Shared read-only inspection helpers for game sessions, chats, checkpoints, and integrity."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.session_expansion import pending_sections
from backend.api.routes.adventures.session_items import (
    backfill_item_from_entity,
    iter_avatar_items,
)
from backend.api.routes.adventures.sessions import ITEM_INTEGRITY_FIELDS
from backend.models.avatar import Avatar
from backend.models.chat import ChatMessage
from backend.models.game_session import GameSession
from backend.models.session_checkpoint import SessionCheckpoint
from backend.models.session_state import SessionState
from backend.models.user import User
from backend.models.world_entity import WorldEntity


async def list_sessions(
    db: AsyncSession,
    *,
    owner_id: Optional[str] = None,
    template_id: Optional[str] = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """List game sessions with current scene, user, and avatar context."""
    stmt = (
        select(GameSession, SessionState, Avatar, User)
        .outerjoin(SessionState, SessionState.session_id == GameSession.id)
        .outerjoin(Avatar, Avatar.id == GameSession.avatar_id)
        .outerjoin(User, User.id == GameSession.user_id)
        .order_by(desc(GameSession.updated_at))
        .limit(limit)
    )
    if owner_id is not None:
        stmt = stmt.where(GameSession.user_id == owner_id)
    if template_id is not None:
        stmt = stmt.where(GameSession.template_id == template_id)

    rows = (await db.execute(stmt)).all()
    return [
        {
            "session_id": g.id,
            "adventure_title": g.adventure_title,
            "template_id": g.template_id,
            "status": g.status,
            "user_id": g.user_id,
            "username": u.username if u else None,
            "avatar_name": av.name if av else None,
            "current_scene": s.current_scene_id if s else None,
            "in_game_time": s.in_game_time if s else 0,
            "updated_at": g.updated_at.isoformat() if g.updated_at else None,
        }
        for g, s, av, u in rows
    ]


async def resolve_game_session(
    db: AsyncSession, session_id: str, *, owner_id: Optional[str] = None
) -> tuple[GameSession, Optional[SessionState], Optional[Avatar], Optional[User]]:
    """Resolve a game session by exact ID or unique ID prefix."""
    sid = session_id.strip()
    if not sid:
        raise ValueError("Session ID must not be empty.")

    base = (
        select(GameSession, SessionState, Avatar, User)
        .outerjoin(SessionState, SessionState.session_id == GameSession.id)
        .outerjoin(Avatar, Avatar.id == GameSession.avatar_id)
        .outerjoin(User, User.id == GameSession.user_id)
    )
    if owner_id is not None:
        base = base.where(GameSession.user_id == owner_id)

    exact = (await db.execute(base.where(GameSession.id == sid))).first()
    if exact is not None:
        return exact

    prefix_rows = (await db.execute(base.where(GameSession.id.startswith(sid)).limit(10))).all()
    if len(prefix_rows) == 1:
        return prefix_rows[0]
    if not prefix_rows:
        raise LookupError(f"Session '{sid}' not found.")
    ids = ", ".join(row[0].id for row in prefix_rows)
    raise ValueError(f"Session prefix '{sid}' is ambiguous: {ids}")


async def _session_world_entities(
    db: AsyncSession, game: GameSession, state: Optional[SessionState], *, hidden_only: bool
) -> list[dict[str, Any]]:
    rows = (
        (
            await db.execute(
                select(WorldEntity)
                .where(WorldEntity.session_id == game.id)
                .order_by(WorldEntity.id)
            )
        )
        .scalars()
        .all()
    )
    if not rows and game.template_id:
        rows = (
            (
                await db.execute(
                    select(WorldEntity)
                    .where(
                        WorldEntity.template_id == game.template_id,
                        WorldEntity.session_id.is_(None),
                    )
                    .order_by(WorldEntity.id)
                )
            )
            .scalars()
            .all()
        )
    overrides = (state.entity_states or {}) if state else {}
    entities: list[dict[str, Any]] = []
    for ent in rows:
        ov = overrides.get(ent.id, {})
        eff_hidden = bool(ov.get("is_hidden", ent.is_hidden))
        if hidden_only and not eff_hidden:
            continue
        entities.append(
            {
                "id": ent.id,
                "name": ent.name,
                "entity_type": ent.entity_type,
                "item_type": ent.item_type,
                "current_scene_id": ov.get("current_scene_id", ent.current_scene_id),
                "is_hidden": eff_hidden,
                "is_in_inventory": bool(ov.get("is_in_inventory", ent.is_in_inventory)),
                "overridden": bool(ov),
                "override": ov or None,
            }
        )
    return entities


def _serialize_avatar(avatar: Optional[Avatar]) -> Optional[dict[str, Any]]:
    if avatar is None:
        return None
    return {
        "id": avatar.id,
        "name": avatar.name,
        "role": avatar.role,
        "hp": avatar.hp,
        "max_hp": avatar.max_hp,
        "mana": avatar.mana,
        "max_mana": avatar.max_mana,
        "stamina": avatar.stamina,
        "max_stamina": avatar.max_stamina,
        "stats": {
            "strength": avatar.strength,
            "dexterity": avatar.dexterity,
            "intelligence": avatar.intelligence,
            "wisdom": avatar.wisdom,
            "charisma": avatar.charisma,
            "armor_class": avatar.armor_class,
        },
        "inventory": avatar.inventory or [],
        "equipment": avatar.equipment or {},
        "status_effects": avatar.status_effects or [],
    }


def _serialize_state(
    state: Optional[SessionState], pending: list[dict[str, Any]]
) -> Optional[dict[str, Any]]:
    if state is None:
        return None
    return {
        "current_scene_id": state.current_scene_id,
        "in_game_time": state.in_game_time,
        "time_system": state.time_system,
        "active_sequence_id": state.active_sequence_id,
        "active_sequence_order": state.active_sequence_order,
        "discovered_scenes": state.discovered_scenes or [],
        "quests": state.quests or [],
        "world_memories": state.world_memories or [],
        "world_rumors": state.world_rumors or [],
        "entity_overrides": state.entity_states or {},
        "exit_overrides": state.exit_states or {},
        "is_completed": bool(state.is_completed),
        "is_debug_enabled": bool(state.is_debug_enabled),
        "pending_sections": [
            {"id": s["id"], "label": s["label"]} for s in pending if isinstance(s, dict)
        ],
    }


async def get_session_state(
    db: AsyncSession,
    session_id: str,
    *,
    owner_id: Optional[str] = None,
    include_entities: bool = True,
    hidden_only: bool = False,
) -> dict[str, Any]:
    """Return full runtime state, avatar inventory/stats, and overrides for a session."""
    game, state, avatar, user = await resolve_game_session(db, session_id, owner_id=owner_id)
    pending = await pending_sections(db, state) if state else []
    payload: dict[str, Any] = {
        "session": {
            "id": game.id,
            "template_id": game.template_id,
            "adventure_title": game.adventure_title,
            "status": game.status,
            "status_note": game.status_note,
            "user_id": game.user_id,
            "username": user.username if user else None,
            "created_at": game.created_at.isoformat() if game.created_at else None,
            "updated_at": game.updated_at.isoformat() if game.updated_at else None,
        },
        "avatar": _serialize_avatar(avatar),
        "state": _serialize_state(state, pending),
    }
    if include_entities:
        payload["entities"] = await _session_world_entities(
            db, game, state, hidden_only=hidden_only
        )
    return payload


async def get_session_chat(
    db: AsyncSession,
    session_id: str,
    *,
    owner_id: Optional[str] = None,
    limit: int = 30,
    offset: int = 0,
) -> dict[str, Any]:
    """Return paginated dialogue turns for a session in chronological order."""
    game, _, _, _ = await resolve_game_session(db, session_id, owner_id=owner_id)
    total = int(
        (
            await db.execute(
                select(func.count())
                .select_from(ChatMessage)
                .where(ChatMessage.session_id == game.id)
            )
        ).scalar_one()
    )
    rows = (
        (
            await db.execute(
                select(ChatMessage)
                .where(ChatMessage.session_id == game.id)
                .order_by(ChatMessage.created_at.asc())
                .offset(offset)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return {
        "session_id": game.id,
        "total": total,
        "offset": offset,
        "limit": limit,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in rows
        ],
    }


async def get_session_checkpoints(
    db: AsyncSession, session_id: str, *, owner_id: Optional[str] = None
) -> list[dict[str, Any]]:
    """List saved checkpoints for a session."""
    game, _, _, _ = await resolve_game_session(db, session_id, owner_id=owner_id)
    rows = (
        (
            await db.execute(
                select(SessionCheckpoint)
                .where(SessionCheckpoint.session_id == game.id)
                .order_by(desc(SessionCheckpoint.created_at))
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": cp.id,
            "message_index": cp.message_index,
            "trigger_reason": cp.trigger_reason,
            "scene_id": (
                cp.state_snapshot.get("current_scene_id")
                if isinstance(cp.state_snapshot, dict)
                else None
            ),
            "created_at": cp.created_at.isoformat() if cp.created_at else None,
        }
        for cp in rows
    ]


async def check_session_integrity(
    db: AsyncSession, session_id: str, *, owner_id: Optional[str] = None
) -> dict[str, Any]:
    """Verify session avatar inventory/equipment fields against template object definitions."""
    game, _, avatar, _ = await resolve_game_session(db, session_id, owner_id=owner_id)
    if avatar is None:
        raise LookupError(f"Avatar not found for session '{game.id}'.")

    entities_by_id: dict[str, WorldEntity] = {}
    if game.template_id:
        ent_rows = (
            (
                await db.execute(
                    select(WorldEntity).where(
                        WorldEntity.template_id == game.template_id,
                        WorldEntity.session_id.is_(None),
                        WorldEntity.entity_type == "OBJECT",
                    )
                )
            )
            .scalars()
            .all()
        )
        entities_by_id = {ent.id: ent for ent in ent_rows if ent.id}

    issues: list[dict[str, Any]] = []
    checked_items = 0
    for location, item in iter_avatar_items(avatar):
        item_id = item.get("id")
        if not item_id:
            continue
        checked_items += 1
        entity = entities_by_id.get(item_id)
        if entity is None:
            continue
        expected = backfill_item_from_entity(item, entity)
        for field in ITEM_INTEGRITY_FIELDS:
            if item.get(field) is None and expected.get(field) is not None:
                issues.append(
                    {
                        "location": location,
                        "item_id": item_id,
                        "item_name": item.get("name") or entity.name,
                        "field": field,
                        "current": None,
                        "expected": expected.get(field),
                    }
                )

    return {
        "status": "ok" if not issues else "issues_found",
        "session_id": game.id,
        "template_id": game.template_id,
        "checked_items": checked_items,
        "issue_count": len(issues),
        "issues": issues,
    }
