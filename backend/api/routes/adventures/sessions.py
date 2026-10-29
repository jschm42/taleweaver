import logging
import os
import shutil
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures import session_copier
from backend.api.routes.adventures.logic import AdventureLogic
from backend.api.routes.adventures.schemas import GameSessionResponse
from backend.api.routes.adventures.session_assets import (
    cleanup_stale_empty_session_dirs as _cleanup_stale_empty_session_dirs,
)
from backend.api.routes.adventures.session_items import (
    backfill_item_from_entity,
    iter_avatar_items,
)
from backend.api.routes.adventures.session_sequence_label import active_sequence_title
from backend.api.routes.adventures.session_starter import start_session
from backend.core.auth import get_current_user
from backend.core.config import settings
from backend.core.database import get_db
from backend.core.ui_theme import UI_SKIN_AUTO
from backend.engine.adventures.adventure_updates import is_legacy_session
from backend.engine.sessions.session_checkpoint_service import SessionCheckpointService
from backend.engine.sessions.session_exporter import SessionExporter
from backend.engine.sessions.session_importer import SessionImporter
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.chat import ChatMessage
from backend.models.game_session import GameSession
from backend.models.session_checkpoint import SessionCheckpoint
from backend.models.session_state import SessionState
from backend.models.user import User
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene
from backend.models.world_map import WorldMap
from backend.schemas.checkpoint import RestoreCheckpointResponse, SessionCheckpointResponse
from backend.schemas.session import GameSessionUpdate
from backend.utils.download_headers import attachment_disposition
from backend.utils.path_security import ensure_within_data_dir, sanitize_path_component

router = APIRouter(tags=["Sessions"])
# The session list sweeps stale session folders at most hourly (startup always sweeps).
SESSION_DIR_CLEANUP_INTERVAL_SECONDS = 3600.0
# _cleanup_stale_empty_session_dirs keeps its old name: backend.main imports it from here.
logger = logging.getLogger(__name__)

ITEM_INTEGRITY_FIELDS = [
    "stat_modifier_strength",
    "stat_modifier_dexterity",
    "stat_modifier_intelligence",
    "stat_modifier_wisdom",
    "stat_modifier_charisma",
    "stat_modifier_armor_class",
    "hp_change",
    "stamina_change",
    "mana_change",
]


@router.get("/sessions", response_model=list[GameSessionResponse])
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list:
    """Returns all game sessions for the current user."""
    all_session_ids_res = await db.execute(select(GameSession.id))
    all_session_ids = {sid for sid in all_session_ids_res.scalars().all() if isinstance(sid, str)}
    removed_dirs = _cleanup_stale_empty_session_dirs(
        active_session_ids=all_session_ids,
        max_age_days=max(0, int(getattr(settings, "SESSION_EMPTY_DIR_CLEANUP_DAYS", 7))),
        min_interval_seconds=SESSION_DIR_CLEANUP_INTERVAL_SECONDS,
    )
    if removed_dirs:
        logger.info("Removed %s stale empty session directories.", removed_dirs)

    result = await db.execute(
        select(GameSession, SessionState, AdventureTemplate, WorldScene.label, Avatar.profile_image)
        .outerjoin(SessionState, SessionState.session_id == GameSession.id)
        .outerjoin(AdventureTemplate, GameSession.template_id == AdventureTemplate.id)
        .outerjoin(Avatar, Avatar.id == SessionState.avatar_id)
        .outerjoin(
            WorldScene,
            (WorldScene.id == SessionState.current_scene_id)
            & (WorldScene.session_id == GameSession.id),
        )
        .where(GameSession.user_id == current_user.id)
        .distinct()
    )
    rows = result.all()
    user_earned_awards = current_user.earned_awards or []

    return [
        GameSessionResponse(
            game_id=g.id,
            template_id=g.template_id,
            adventure_id=g.template_id,
            avatar_id=g.avatar_id,
            profile_image=AdventureLogic.resolve_session_asset(
                s, "protagonist", avatar_profile_image
            ),
            adventure_title=a.title if a else (g.adventure_title or "Unknown"),
            adventure_version=a.version
            if a
            else (AdventureLogic.extract_manifest_snapshot(s).get("adventure") or {}).get(
                "version"
            ),
            image_url=AdventureLogic.resolve_session_asset(
                s, "cover", a.image_url if a else g.adventure_image_url
            ),
            scene_id=s.current_scene_id if s else "START",
            current_scene_name=scene_label or ("Exploring..." if s else "Archived"),
            current_sequence_name=active_sequence_title(a, s),
            in_game_time=s.in_game_time if s else 0,
            is_ready=a.is_ready if a else True,
            creation_status=a.creation_status if a else "Ready",
            creation_error=a.creation_error if a else None,
            selected_tone=a.selected_tone
            if a
            else (AdventureLogic.extract_manifest_snapshot(s).get("adventure") or {}).get(
                "selected_tone"
            ),
            progress=AdventureLogic.calculate_quest_progress(
                s.quests if s else (a.quests if a else None)
            ),
            quest_count=len((s.quests if s else (a.quests if a else None)) or []),
            completed_quest_count=len(
                [
                    q
                    for q in ((s.quests if s else (a.quests if a else None)) or [])
                    if q.get("status") == "completed"
                ]
            ),
            award_count=len(
                (
                    a.awards
                    if a
                    else (AdventureLogic.extract_manifest_snapshot(s).get("adventure") or {}).get(
                        "awards"
                    )
                )
                or []
            ),
            earned_award_count=len(
                [
                    aw
                    for aw in ((a.awards if a else None) or [])
                    if any(
                        ea.get("key") == aw.get("key")
                        and (ea.get("template_id") == a.id or ea.get("adventure_id") == a.id)
                        for ea in user_earned_awards
                    )
                ]
            ),
            created_at=g.created_at,
            last_played_at=g.last_played_at,
            status=g.status,
            status_note=g.status_note,
            copied_from_id=g.copied_from_id,
            is_legacy_format=is_legacy_session(session=g, state=s, template=a),
            rule_enforcement_mode=a.rule_enforcement_mode
            if a
            else (
                (AdventureLogic.extract_manifest_snapshot(s).get("adventure") or {}).get(
                    "rule_enforcement_mode"
                )
                or "rpg"
            ),
            selected_image_styles=a.selected_image_styles
            if a
            else (
                (AdventureLogic.extract_manifest_snapshot(s).get("adventure") or {}).get(
                    "selected_image_styles"
                )
                or (s.selected_image_styles if s else None)
            ),
        )
        for g, s, a, scene_label, avatar_profile_image in rows
    ]


@router.post("/{template_id}/sessions/start", status_code=201)
async def start_session_for_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Creates a new active session for a template and returns its identifiers."""
    adv_res = await db.execute(select(AdventureTemplate).where(AdventureTemplate.id == template_id))
    adventure = adv_res.scalars().first()
    if not adventure:
        raise HTTPException(status_code=404, detail="AdventureTemplate not found.")

    # Allow if user is owner OR if adventure is ready (public-ready)
    if adventure.owner_id != current_user.id and not adventure.is_ready:
        raise HTTPException(status_code=403, detail="You do not have access to this adventure yet.")

    # Disallow starting sessions on legacy/outdated format adventures
    from backend.engine.adventures.adventure_updates import (
        check_template_update,
        scan_available_adventure_files,
    )

    files = scan_available_adventure_files()
    update_info = check_template_update(adventure, files)
    if update_info["is_legacy_format"] or not update_info["can_start"]:
        raise HTTPException(
            status_code=400,
            detail="This adventure uses an outdated format and is no longer usable. Please update the adventure first.",
        )

    return await start_session(db, adventure, current_user)


@router.post("/{template_id}/reset")
async def reset_adventure(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Resets a template into a fresh state while preserving any already-generated image URLs on the template/world data."""
    # Verify ownership
    adv = await db.get(AdventureTemplate, template_id)
    if not adv or adv.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Adventure template not found.")

    # Remove session-bound rows and leave template-level images intact.
    # Only delete rows that belong to active sessions (session_id IS NOT NULL).
    await db.execute(delete(GameSession).where(GameSession.template_id == template_id))
    await db.execute(delete(SessionState).where(SessionState.template_id == template_id))
    await db.execute(
        delete(WorldEntity).where(
            (WorldEntity.template_id == template_id) & (WorldEntity.session_id.isnot(None))
        )
    )
    await db.execute(
        delete(WorldScene).where(
            (WorldScene.template_id == template_id) & (WorldScene.session_id.isnot(None))
        )
    )
    await db.execute(
        delete(WorldExit).where(
            (WorldExit.template_id == template_id) & (WorldExit.session_id.isnot(None))
        )
    )
    await db.commit()
    return {"status": "success"}


@router.delete("/sessions/{game_id}", status_code=200)
async def delete_session(
    game_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(GameSession).where(
            (GameSession.id == game_id) & (GameSession.user_id == current_user.id)
        )
    )
    game_session = result.scalars().first()
    if not game_session:
        raise HTTPException(status_code=404, detail="Session not found.")

    avatar_id = game_session.avatar_id

    # Explicitly remove session-bound rows that may not be ORM-cascaded.
    await db.execute(delete(SessionCheckpoint).where(SessionCheckpoint.session_id == game_id))
    await db.execute(delete(ChatMessage).where(ChatMessage.session_id == game_id))
    await db.execute(delete(SessionState).where(SessionState.session_id == game_id))
    await db.execute(delete(WorldEntity).where(WorldEntity.session_id == game_id))
    await db.execute(delete(WorldScene).where(WorldScene.session_id == game_id))
    await db.execute(delete(WorldExit).where(WorldExit.session_id == game_id))
    await db.execute(delete(WorldMap).where(WorldMap.session_id == game_id))

    await db.delete(game_session)

    # Remove avatar only if no other session references it.
    other_session_res = await db.execute(
        select(GameSession.id)
        .where(GameSession.avatar_id == avatar_id, GameSession.id != game_id)
        .limit(1)
    )
    if not other_session_res.scalar_one_or_none():
        avatar_res = await db.execute(select(Avatar).where(Avatar.id == avatar_id))
        avatar = avatar_res.scalars().first()
        if avatar:
            await db.delete(avatar)

    await db.commit()

    # Remove session-bound files from disk.
    safe_game_id = sanitize_path_component(str(game_session.id))
    if safe_game_id:
        session_dir = ensure_within_data_dir(
            os.path.join(settings.DATA_DIR, "adventures", "sessions", safe_game_id)
        )
        if os.path.isdir(session_dir):
            try:
                shutil.rmtree(session_dir)
            except OSError:
                logger.exception("Failed to remove session directory for %s", game_id)
    else:
        logger.warning("Skipping session directory cleanup due to invalid session id: %s", game_id)

    return {"status": "deleted", "game_id": game_id}


@router.delete("/sessions/{game_id}/messages/{message_id}", status_code=200)
async def delete_chat_message(
    game_id: str,
    message_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Deletes a single chat message from the session history in debug mode."""
    session_res = await db.execute(
        select(GameSession).where(
            (GameSession.id == game_id) & (GameSession.user_id == current_user.id)
        )
    )
    game_session = session_res.scalars().first()
    if not game_session:
        raise HTTPException(status_code=404, detail="Session not found.")

    state_res = await db.execute(select(SessionState).where(SessionState.session_id == game_id))
    state = state_res.scalars().first()
    is_debug = settings.TALEWEAVER_DEBUG_ENABLED or (state and state.is_debug_enabled)
    if not is_debug:
        raise HTTPException(status_code=403, detail="Not in debug mode.")

    msg_res = await db.execute(
        select(ChatMessage).where(
            (ChatMessage.id == message_id) & (ChatMessage.session_id == game_id)
        )
    )
    message = msg_res.scalars().first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found.")

    await db.delete(message)
    await db.commit()
    return {"status": "deleted", "message_id": message_id}


@router.get("/sessions/{game_id}/integrity/items", status_code=200)
async def check_session_item_integrity(
    game_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Checks if session avatar item modifiers/effects match available template object data."""
    session_res = await db.execute(
        select(GameSession).where(
            (GameSession.id == game_id) & (GameSession.user_id == current_user.id)
        )
    )
    game_session = session_res.scalars().first()
    if not game_session:
        raise HTTPException(status_code=404, detail="Session not found.")

    avatar_res = await db.execute(select(Avatar).where(Avatar.id == game_session.avatar_id))
    avatar = avatar_res.scalars().first()
    if not avatar:
        raise HTTPException(status_code=404, detail="Session avatar not found.")

    template_entities_res = await db.execute(
        select(WorldEntity).where(
            WorldEntity.template_id == game_session.template_id,
            WorldEntity.entity_type == "OBJECT",
        )
    )
    entities_by_id = {ent.id: ent for ent in template_entities_res.scalars().all() if ent.id}

    issues: list[dict[str, Any]] = []
    checked_items = 0

    for location, item in iter_avatar_items(avatar):
        item_id = item.get("id")
        if not item_id:
            continue
        checked_items += 1

        entity = entities_by_id.get(item_id)
        if not entity:
            continue

        expected = backfill_item_from_entity(item, entity)
        for field in ITEM_INTEGRITY_FIELDS:
            current_value = item.get(field)
            expected_value = expected.get(field)
            if current_value is None and expected_value is not None:
                issues.append(
                    {
                        "location": location,
                        "item_id": item_id,
                        "item_name": item.get("name") or entity.name,
                        "field": field,
                        "current": current_value,
                        "expected": expected_value,
                    }
                )

    return {
        "status": "ok",
        "game_id": game_id,
        "template_id": game_session.template_id,
        "checked_items": checked_items,
        "issue_count": len(issues),
        "issues": issues,
    }


@router.post("/sessions/{game_id}/copy", status_code=201)
async def copy_session(
    game_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Creates a full duplicate/copy of an existing session."""
    return await session_copier.copy_session(db, game_id, current_user)


# ---------------------------------------------------------------------------
# /{template_id}/state  (adventure-scoped convenience routes used by the UI)
# ---------------------------------------------------------------------------


@router.get("/{template_id}/state")
async def get_adventure_state(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Returns a lightweight snapshot of the most-recent session state for a template."""
    state_res = await db.execute(
        select(SessionState)
        .join(GameSession, GameSession.id == SessionState.session_id)
        .where(
            GameSession.template_id == template_id,
            GameSession.user_id == current_user.id,
        )
        .order_by(GameSession.created_at.desc())
        .limit(1)
    )
    state = state_res.scalars().first()
    if not state:
        raise HTTPException(status_code=404, detail="No session found for this adventure.")

    game_session_res = await db.execute(
        select(GameSession).where(GameSession.id == state.session_id)
    )
    game_session = game_session_res.scalars().first()

    return {
        "scene_id": state.current_scene_id,
        "in_game_time": state.in_game_time or 0,
        "is_paused": bool(game_session and game_session.status == "paused"),
        "session_id": state.session_id,
    }


@router.patch("/{template_id}/state")
async def update_adventure_state(
    template_id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Patches the most-recent active session state for a template (e.g. scene_id, in_game_time)."""
    state_res = await db.execute(
        select(SessionState)
        .join(GameSession, GameSession.id == SessionState.session_id)
        .where(
            GameSession.template_id == template_id,
            GameSession.user_id == current_user.id,
            GameSession.status == "active",
        )
        .order_by(GameSession.created_at.desc())
        .limit(1)
    )
    state = state_res.scalars().first()
    if not state:
        raise HTTPException(status_code=404, detail="No active session found for this adventure.")

    if "scene_id" in payload:
        state.current_scene_id = payload["scene_id"]
    if "in_game_time" in payload:
        state.in_game_time = payload["in_game_time"]

    await db.commit()
    await db.refresh(state)

    game_session_res = await db.execute(
        select(GameSession).where(GameSession.id == state.session_id)
    )
    game_session = game_session_res.scalars().first()

    return {
        "scene_id": state.current_scene_id,
        "in_game_time": state.in_game_time or 0,
        "is_paused": bool(game_session and game_session.status == "paused"),
        "session_id": state.session_id,
    }


@router.post("/{template_id}/pause")
async def pause_adventure(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Pauses the most-recent active session for a template."""
    session_res = await db.execute(
        select(GameSession)
        .where(
            GameSession.template_id == template_id,
            GameSession.user_id == current_user.id,
            GameSession.status == "active",
        )
        .order_by(GameSession.created_at.desc())
        .limit(1)
    )
    game_session = session_res.scalars().first()
    if not game_session:
        raise HTTPException(status_code=404, detail="No active session found for this adventure.")

    game_session.status = "paused"
    await db.commit()
    return {"status": "paused", "game_id": game_session.id}


@router.post("/{template_id}/resume")
async def resume_adventure(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Resumes the most-recently paused session for a template."""
    session_res = await db.execute(
        select(GameSession)
        .where(
            GameSession.template_id == template_id,
            GameSession.user_id == current_user.id,
            GameSession.status == "paused",
        )
        .order_by(GameSession.created_at.desc())
        .limit(1)
    )
    game_session = session_res.scalars().first()
    if not game_session:
        raise HTTPException(status_code=404, detail="No paused session found for this adventure.")

    game_session.status = "active"
    await db.commit()
    return {"status": "active", "game_id": game_session.id}


async def _get_session_response(
    db: AsyncSession, game_id: str, current_user_id: str
) -> GameSessionResponse:
    # Query single session with joins
    result = await db.execute(
        select(GameSession, SessionState, AdventureTemplate, WorldScene.label, Avatar.profile_image)
        .outerjoin(SessionState, SessionState.session_id == GameSession.id)
        .outerjoin(AdventureTemplate, GameSession.template_id == AdventureTemplate.id)
        .outerjoin(Avatar, Avatar.id == SessionState.avatar_id)
        .outerjoin(
            WorldScene,
            (WorldScene.id == SessionState.current_scene_id)
            & (WorldScene.session_id == GameSession.id),
        )
        .where((GameSession.id == game_id) & (GameSession.user_id == current_user_id))
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Session not found.")

    g, s, a, scene_label, avatar_profile_image = row

    # We can fetch earned awards here
    user_res = await db.execute(select(User).where(User.id == current_user_id))
    current_user = user_res.scalar_one()
    user_earned_awards = current_user.earned_awards or []

    return GameSessionResponse(
        game_id=g.id,
        template_id=g.template_id,
        adventure_id=g.template_id,
        avatar_id=g.avatar_id,
        profile_image=AdventureLogic.resolve_session_asset(s, "protagonist", avatar_profile_image),
        adventure_title=a.title if a else (g.adventure_title or "Unknown"),
        adventure_version=a.version
        if a
        else (AdventureLogic.extract_manifest_snapshot(s).get("adventure") or {}).get("version"),
        creator=a.creator if a else None,
        copyright=a.copyright if a else None,
        license=a.license if a else None,
        license_url=a.license_url if a else None,
        image_url=AdventureLogic.resolve_session_asset(
            s, "cover", a.image_url if a else g.adventure_image_url
        ),
        scene_id=s.current_scene_id if s else "START",
        current_scene_name=scene_label or ("Exploring..." if s else "Archived"),
        in_game_time=s.in_game_time if s else 0,
        is_ready=a.is_ready if a else True,
        creation_status=a.creation_status if a else "Ready",
        creation_error=a.creation_error if a else None,
        selected_tone=a.selected_tone
        if a
        else (AdventureLogic.extract_manifest_snapshot(s).get("adventure") or {}).get(
            "selected_tone"
        ),
        progress=AdventureLogic.calculate_quest_progress(
            s.quests if s else (a.quests if a else None)
        ),
        quest_count=len((s.quests if s else (a.quests if a else None)) or []),
        completed_quest_count=len(
            [
                q
                for q in ((s.quests if s else (a.quests if a else None)) or [])
                if q.get("status") == "completed"
            ]
        ),
        award_count=len(
            (
                a.awards
                if a
                else (AdventureLogic.extract_manifest_snapshot(s).get("adventure") or {}).get(
                    "awards"
                )
            )
            or []
        ),
        earned_award_count=len(
            [
                aw
                for aw in ((a.awards if a else None) or [])
                if any(
                    ea.get("key") == aw.get("key")
                    and (ea.get("template_id") == a.id or ea.get("adventure_id") == a.id)
                    for ea in user_earned_awards
                )
            ]
        ),
        created_at=g.created_at,
        status=g.status,
        status_note=g.status_note,
        copied_from_id=g.copied_from_id,
        is_legacy_format=is_legacy_session(session=g, state=s, template=a),
        rule_enforcement_mode=a.rule_enforcement_mode
        if a
        else (
            (AdventureLogic.extract_manifest_snapshot(s).get("adventure") or {}).get(
                "rule_enforcement_mode"
            )
            or "rpg"
        ),
        selected_image_styles=a.selected_image_styles
        if a
        else (
            (AdventureLogic.extract_manifest_snapshot(s).get("adventure") or {}).get(
                "selected_image_styles"
            )
            or (s.selected_image_styles if s else None)
        ),
        max_memory_turns=getattr(s, "max_memory_turns", 10) if s else 10,
        enable_history_compression=getattr(s, "enable_history_compression", True) if s else True,
    )


@router.patch("/sessions/{game_id}", response_model=GameSessionResponse)
async def update_session(
    game_id: str,
    payload: GameSessionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(GameSession).where(
            (GameSession.id == game_id) & (GameSession.user_id == current_user.id)
        )
    )
    game_session = result.scalars().first()
    if not game_session:
        raise HTTPException(status_code=404, detail="Session not found.")

    if payload.status is not None:
        game_session.status = payload.status
    if payload.status_note is not None:
        game_session.status_note = payload.status_note
    state_fields = (
        payload.max_memory_turns,
        payload.enable_history_compression,
        payload.narration_style,
        payload.ui_skin,
    )
    if any(value is not None for value in state_fields):
        state_res = await db.execute(select(SessionState).where(SessionState.session_id == game_id))
        session_state = state_res.scalars().first()
        if session_state:
            if payload.max_memory_turns is not None:
                session_state.max_memory_turns = max(1, min(100, int(payload.max_memory_turns)))
            if payload.enable_history_compression is not None:
                session_state.enable_history_compression = payload.enable_history_compression
            if payload.narration_style is not None:
                session_state.narration_style = payload.narration_style
            if payload.ui_skin is not None:
                session_state.ui_skin = None if payload.ui_skin == UI_SKIN_AUTO else payload.ui_skin

    await db.commit()

    return await _get_session_response(db, game_id, current_user.id)


@router.get("/sessions/{game_id}/checkpoints", response_model=list[SessionCheckpointResponse])
async def list_session_checkpoints(
    game_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[SessionCheckpointResponse]:
    session_res = await db.execute(
        select(GameSession).where(
            (GameSession.id == game_id) & (GameSession.user_id == current_user.id)
        )
    )
    game_session = session_res.scalars().first()
    if not game_session:
        raise HTTPException(status_code=404, detail="Session not found.")

    return await SessionCheckpointService.list_checkpoints(db, game_id)


@router.post(
    "/sessions/{game_id}/checkpoints/{checkpoint_id}/restore",
    response_model=RestoreCheckpointResponse,
)
async def restore_session_checkpoint(
    game_id: str,
    checkpoint_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RestoreCheckpointResponse:
    session_res = await db.execute(
        select(GameSession).where(
            (GameSession.id == game_id) & (GameSession.user_id == current_user.id)
        )
    )
    game_session = session_res.scalars().first()
    if not game_session:
        raise HTTPException(status_code=404, detail="Session not found.")

    try:
        deleted_messages = await SessionCheckpointService.restore_checkpoint(
            db, game_id, checkpoint_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    # Event-table pruning is intentionally deferred until a dedicated event store exists.
    logger.info(
        "Checkpoint restore for session %s pruned %s chat messages.", game_id, deleted_messages
    )
    await db.commit()

    return RestoreCheckpointResponse(
        status="restored",
        checkpoint_id=checkpoint_id,
        deleted_messages=deleted_messages,
    )


@router.get("/sessions/{game_id}/export")
async def export_session_ads(
    game_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Exports the session as a portable .ads (ZIP) bundle including assets."""
    import io

    try:
        # Verify ownership
        result = await db.execute(
            select(GameSession).where(
                (GameSession.id == game_id) & (GameSession.user_id == current_user.id)
            )
        )
        if not result.scalars().first():
            raise HTTPException(status_code=404, detail="Session not found.")

        zip_data = await SessionExporter.export_ads(db, game_id)
        return StreamingResponse(
            io.BytesIO(zip_data),
            media_type="application/zip",
            headers={"Content-Disposition": attachment_disposition(f"session_{game_id}.ads")},
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.exception("ADS Export failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/sessions/import")
async def import_session_ads(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Import a game session from a portable .ads (ZIP) file."""
    try:
        content = await file.read()
        new_session_id = await SessionImporter.import_ads(db, content, owner_id=current_user.id)
        if not new_session_id:
            raise HTTPException(
                status_code=400, detail="The ADS file is invalid or could not be processed."
            )
        return {
            "status": "success",
            "game_id": new_session_id,
            "message": "Session imported successfully.",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("ADS Import failed")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {e!s}") from e
