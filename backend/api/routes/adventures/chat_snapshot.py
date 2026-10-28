"""Building blocks of the session snapshot returned by GET /{game_id}/chat."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.api.routes.adventures.logic import AdventureLogic
from backend.api.routes.adventures.out_of_turn_progress import (
    FINAL_SEQUENCE_NOTE,
    TERMINAL_STATUSES,
)
from backend.core.config import settings
from backend.engine.map_engine import MapEngine
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.chat import ChatMessage
from backend.models.session_state import SessionState
from backend.models.user import User
from backend.models.world_entity import WorldExit, WorldScene

logger = logging.getLogger(__name__)


async def load_chat_history(db: AsyncSession, session_id: str) -> list[dict[str, Any]]:
    chat_res = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
    )
    return [m.to_client_dict() for m in chat_res.scalars().all()]


async def _session_scene_images(db: AsyncSession, state: SessionState) -> dict[str, str]:
    """Scene id -> image URL of this session's own scene copies."""
    res = await db.execute(
        select(WorldScene.id, WorldScene.image_url).where(WorldScene.session_id == state.session_id)
    )
    return {scene_id: url for scene_id, url in res.all() if url}


async def build_session_map(db: AsyncSession, state: SessionState) -> dict[str, Any] | None:
    """The session's own map, augmented with adjacent unvisited scenes."""
    world_map = await AdventureLogic.get_or_create_map(
        db, state.template_id, session_id=state.session_id
    )
    if not world_map:
        return None
    map_dict = MapEngine.to_dict(world_map)
    map_dict["current_scene_id"] = MapEngine._safe_id(state.current_scene_id)
    # A node keeps the image it had when the scene was first visited, so prefer the session
    # scene's current image (e.g. regenerated since); heal the rest.
    scene_images = await _session_scene_images(db, state)
    for node in map_dict.get("nodes", {}).values():
        if not isinstance(node, dict):
            continue
        image_url = scene_images.get(str(node.get("id") or "")) or node.get("image_url")
        if image_url:
            node["image_url"] = AdventureLogic.resolve_existing_data_asset_url(image_url)

    exits_res = await db.execute(
        select(WorldExit).where(
            or_(
                WorldExit.session_id == state.session_id, WorldExit.template_id == state.template_id
            )
        )
    )
    return MapEngine.augment_map_data(
        map_dict, list(exits_res.scalars().all()), state.current_scene_id
    )


async def load_full_world_debug(db: AsyncSession, state: SessionState, requested: bool) -> Any:
    if not requested or not (settings.TALEWEAVER_DEBUG_ENABLED or state.is_debug_enabled):
        return None
    try:
        from backend.api.routes.adventures.editor import _build_adventure_editor_assets

        return await _build_adventure_editor_assets(state.template_id, db)
    except Exception as exc:
        logger.warning("Could not build full_world debug payload: %s", exc)
        return None


async def resolve_prompt_suggestions(
    db: AsyncSession, state: SessionState, current_user: User
) -> list[str]:
    """Stored suggestions, or player-only fallback suggestions built on session load."""
    prompt_suggestions = GameTurnManager.extract_prompt_suggestions(state.exit_states or {})
    if prompt_suggestions:
        return prompt_suggestions
    try:
        manager = GameTurnManager(db, state.session_id, current_user)
        if not await manager.initialize():
            return prompt_suggestions
        ctx = await manager.suggestions.build_player_only_suggestion_context()
        prompt_suggestions = manager.suggestions.fallback_prompt_suggestions(
            scene_label=ctx.get("scene_label", ""),
            visible_objects=ctx.get("visible_objects", []),
            visible_npcs=ctx.get("visible_npcs", []),
            inventory_items=ctx.get("inventory_items", []),
        )
        manager.suggestions.set_prompt_suggestions_state(prompt_suggestions)
        await db.commit()
    except Exception as exc:
        logger.warning("Could not build fallback prompt suggestions on session load: %s", exc)
    return prompt_suggestions


async def apply_pending_sequence_progress(
    db: AsyncSession,
    state: SessionState,
    adventure: AdventureTemplate | None,
    avatar: Avatar | None,
    user: User,
) -> bool:
    """Evaluates sequence progress on load; returns True when new system messages were saved.

    Completing the final sequence here also ends the adventure, like it does during a turn.
    """
    if not (adventure and avatar):
        return False
    seq_messages = AdventureLogic.evaluate_sequence_progress(
        adventure=adventure, state=state, avatar=avatar
    )
    if not seq_messages:
        return False
    for seq_msg in seq_messages:
        db.add(ChatMessage(session_id=state.session_id, role="system", content=seq_msg))
    session_status = state.session.status if state.session else None
    if state.is_completed is True and session_status not in TERMINAL_STATUSES:
        manager = GameTurnManager(
            db, state.session_id, user, state=state, adventure=adventure, avatar=avatar
        )
        await manager._finalize_session("completed", FINAL_SEQUENCE_NOTE)
    await db.commit()
    return True


def build_awards_for_snapshot(
    state: SessionState, adventure: AdventureTemplate | None, current_user: User
) -> list[dict[str, Any]]:
    if adventure:
        adventure_awards = adventure.awards
    else:
        manifest_adventure = AdventureLogic.extract_manifest_snapshot(state).get("adventure") or {}
        adventure_awards = manifest_adventure.get("awards")
    return AdventureLogic.build_awards_payload(
        user_earned_awards=current_user.earned_awards,
        adventure_awards=adventure_awards or [],
        adventure_id=adventure.id if adventure else state.template_id,
        session_id=state.session_id,
    )
