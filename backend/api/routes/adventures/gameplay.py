from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any, cast
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from backend.api.routes.adventures.chat_snapshot import (
    apply_pending_sequence_progress,
    build_awards_for_snapshot,
    build_session_map,
    load_chat_history,
    load_entity_names,
    load_full_world_debug,
    resolve_prompt_suggestions,
)
from backend.api.routes.adventures.dialog_routes import ensure_no_pending_dialog
from backend.api.routes.adventures.gameplay_logic import (
    WALKTHROUGH_REVEAL_COST,
    GameTurnManager,
)
from backend.api.routes.adventures.logic import AdventureLogic
from backend.api.routes.adventures.schemas import (
    ChatRequest,
    ChatResponse,
    TerminalEpilogueRequest,
    TerminalEpilogueResponse,
    TranslateTextRequest,
    TranslateTextResponse,
)
from backend.api.routes.adventures.session_adventure import load_session_adventure
from backend.api.routes.adventures.session_debug_payload import build_session_debug_payload
from backend.api.routes.adventures.unlock_service import (
    SwitchFlipRunner,
    add_system_message,
    avatar_has_item,
    award_unlock_xp,
    enforce_container_guard,
    enforce_exit_guard,
    fire_container_unlock_success,
    inventory_item_name,
    load_avatar,
    load_session_object,
    mark_container_unlocked,
    open_exit,
    require_avatar,
    require_value,
    resolve_switch_flip,
)
from backend.core.auth import get_current_user
from backend.core.config import settings
from backend.core.database import get_db
from backend.core.llm_router import GameMasterLLM
from backend.core.prompts import (
    BABLE_FISH_TRANSLATION_SYSTEM_PROMPT,
    BABLE_FISH_TRANSLATION_USER_PROMPT_TEMPLATE,
)
from backend.engine.adventure_updates import is_legacy_session
from backend.engine.scripting.dialog import client_dialog, pending_dialog
from backend.engine.sequence_walkthrough import (
    format_walkthrough_steps,
    sequence_walkthrough_steps,
)
from backend.engine.trigger_service import TriggerService
from backend.models.avatar import Avatar
from backend.models.chat import ChatMessage
from backend.models.game_session import GameSession
from backend.models.session_state import SessionState
from backend.models.user import User
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene
from backend.services.session_activity import mark_session_played

router = APIRouter(tags=["Gameplay"])
logger = logging.getLogger(__name__)

TERMINAL_EPILOGUE_STATE_KEY = "__terminal_epilogue__"
# Hard-coded, static error message used for any client-visible turn failure path.
# A module-level constant lets static-analysis tools verify that no exception text is
# ever forwarded to the response body.
CLIENT_TURN_ERROR_DETAIL = "Unable to process this turn."
INVALID_CONTAINER_CODE_MESSAGE = (
    "The lock gives a mocking click. That code won't open this container."
)


class ContainerUnlockCodeRequest(BaseModel):
    code: str


async def _require_session_state(
    db: AsyncSession, game_id: str, current_user: User
) -> SessionState:
    state = await AdventureLogic.resolve_session_state(db, game_id, user_id=current_user.id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found.")
    return state


def _terminal_flags_from_state(state: SessionState) -> tuple[bool, bool]:
    """Returns (pending_terminal_epilogue, input_locked) for the current session state."""
    status = state.session.status if state.session else None
    epilogue_state = (state.exit_states or {}).get(TERMINAL_EPILOGUE_STATE_KEY) or {}
    if not isinstance(epilogue_state, dict):
        epilogue_state = {}

    completed_sent = bool(epilogue_state.get("completed_sent"))
    game_over_sent = bool(epilogue_state.get("game_over_sent"))

    pending_terminal_epilogue = (status == "completed" and not completed_sent) or (
        status == "game_over" and not game_over_sent
    )
    input_locked = status == "game_over" and game_over_sent
    return pending_terminal_epilogue, input_locked


@router.get("/{game_id}/session-debug")
async def get_session_debug(
    game_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Unified debug inspector endpoint for active game sessions. Requires debug mode to be enabled."""
    state = await AdventureLogic.resolve_session_state(db, game_id, user_id=current_user.id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found.")

    is_debug = bool(settings.TALEWEAVER_DEBUG_ENABLED or state.is_debug_enabled)
    if not is_debug:
        raise HTTPException(
            status_code=403,
            detail="Debug mode is not enabled for this session. Type /debug on to activate.",
        )

    adventure = await load_session_adventure(db, state)

    cv_res = await db.execute(select(Avatar).where(Avatar.id == state.avatar_id))
    avatar = cv_res.scalars().first()

    return await build_session_debug_payload(db, state, adventure, avatar)


@router.get("/{game_id}/chat", response_model=ChatResponse)
async def get_chat_history(
    game_id: str,
    include_full_world: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieves full chat history and current UI state for a game session."""
    state = await AdventureLogic.resolve_session_state(db, game_id, user_id=current_user.id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found.")

    adventure = await load_session_adventure(db, state)

    cv_res = await db.execute(select(Avatar).where(Avatar.id == state.avatar_id))
    avatar = cv_res.scalars().first()

    # Before the terminal flags: completing the final sequence here ends the adventure.
    await apply_pending_sequence_progress(db, state, adventure, avatar, current_user)
    map_dict = await build_session_map(db, state)
    entities = await AdventureLogic.build_session_entities(db, state)
    scene_image = await AdventureLogic.resolve_scene_image(db, state, state.current_scene_id)
    pending_terminal_epilogue, input_locked = _terminal_flags_from_state(state)
    full_world_debug = await load_full_world_debug(db, state, include_full_world)
    prompt_suggestions = await resolve_prompt_suggestions(db, state, current_user)
    history = await load_chat_history(db, state.session_id)
    session_status = state.session.status if state.session else None
    await mark_session_played(db, state.session_id)

    return ChatResponse(
        messages=history,
        sheet=await AdventureLogic.build_sheet_snapshot(avatar, state, db),
        combat=AdventureLogic.get_combat_snapshot(state),
        map_data=map_dict,
        nodes=await AdventureLogic.get_all_scene_metadata(
            db, state.template_id, session_id=state.session_id
        ),
        entities=entities,
        npc_metadata=await AdventureLogic.get_npc_metadata(
            db, state.template_id, session_id=state.session_id
        ),
        entity_names=await load_entity_names(db, state.session_id),
        image_url=scene_image,
        adventure_image=AdventureLogic.resolve_session_asset(
            state, "cover", adventure.image_url if adventure else None
        ),
        active_sequence=AdventureLogic.resolve_active_sequence(adventure, state),
        scene_id=state.current_scene_id,
        sequence_id=state.active_sequence_id,
        quests=state.quests,
        awards=build_awards_for_snapshot(state, adventure, current_user),
        is_completed=state.is_completed,
        game_over=session_status == "game_over",
        game_completed=session_status == "completed",
        status_note=state.session.status_note if state.session else None,
        input_locked=input_locked,
        pending_terminal_epilogue=pending_terminal_epilogue,
        prompt_suggestions=prompt_suggestions,
        world_memories=state.world_memories or [],
        world_rumors=state.world_rumors or [],
        is_legacy_format=is_legacy_session(session=state.session, state=state, template=adventure),
        full_world=full_world_debug,
        pending_dialog=None
        if session_status in {"completed", "game_over"}
        else client_dialog(pending_dialog(state.entity_states)),
    )


@router.post("/{game_id}/chat")
async def post_chat_message(
    game_id: str,
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Processes a user message and returns a streaming response."""
    await ensure_no_pending_dialog(db, game_id, current_user)
    try:
        manager = GameTurnManager(db, game_id, current_user)
        turn_id = uuid4().hex

        async def _stream_with_turn_id(
            source: AsyncGenerator[str, None],
        ) -> AsyncGenerator[str, None]:
            try:
                async for chunk in source:
                    if isinstance(chunk, str) and chunk.startswith("event:"):
                        yield f"id: {turn_id}\n{chunk}"
                    else:
                        yield chunk
            except Exception:
                # Never forward the exception text to the client — log
                # server-side, yield only the static error message.
                logger.exception("Chat stream failed for session %s", game_id)
                yield (
                    f"id: {turn_id}\n"
                    "event: error\n"
                    f"data: {json.dumps({'detail': CLIENT_TURN_ERROR_DETAIL, 'retryable': True})}\n\n"
                )

        try:
            turn_stream = manager.process_turn(
                payload.content,
                auto_visualize=payload.auto_visualize,
                language=payload.language,
            )
        except Exception:
            logger.exception("Failed to initialize chat stream for session %s", game_id)
            raise HTTPException(status_code=500, detail=CLIENT_TURN_ERROR_DETAIL) from None

        return StreamingResponse(
            _stream_with_turn_id(turn_stream),
            media_type="text/event-stream",
            headers={"X-Taleweaver-Turn-Id": turn_id},
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to start chat turn for session %s", game_id)
        raise HTTPException(status_code=500, detail=CLIENT_TURN_ERROR_DETAIL) from None


@router.post("/{game_id}/terminal-epilogue", response_model=TerminalEpilogueResponse)
async def create_terminal_epilogue(
    game_id: str,
    payload: TerminalEpilogueRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Creates the one-time terminal epilogue for completed or game-over sessions."""
    manager = GameTurnManager(db, game_id, current_user)
    return await cast(Any, manager).create_terminal_epilogue(language=payload.language)


@router.post("/{game_id}/translate-text", response_model=TranslateTextResponse)
async def translate_text(
    game_id: str,
    payload: TranslateTextRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Translates arbitrary session text into the requested language (Bable Fish target)."""
    state = await AdventureLogic.resolve_session_state(db, game_id, user_id=current_user.id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found.")

    source_text = str(payload.text or "").strip()
    if not source_text:
        raise HTTPException(status_code=400, detail="Text is required.")

    target_language = str(payload.language or "").strip()
    if not target_language:
        raise HTTPException(status_code=400, detail="Target language is required.")

    llm_settings = current_user.llm_settings or {}
    small_model_provider = (
        llm_settings.get("small_model_provider")
        or llm_settings.get("complex_model_provider")
        or llm_settings.get("preferred_provider")
        or "openai"
    )
    small_model = llm_settings.get("small_model") or "gpt-4o-mini"

    try:
        llm = GameMasterLLM(current_user, provider=small_model_provider, model_category="small")
    except ValueError:
        logger.warning("Invalid LLM configuration for translation (user %s)", current_user.id)
        raise HTTPException(
            status_code=400, detail="Selected translation model is unavailable."
        ) from None

    system_prompt = BABLE_FISH_TRANSLATION_SYSTEM_PROMPT
    user_prompt = BABLE_FISH_TRANSLATION_USER_PROMPT_TEMPLATE.format(
        target_language=target_language,
        source_text=source_text,
    )

    try:
        translated = await llm.aexecute_simple_task(
            system_prompt,
            user_prompt,
            small_model,
            adventure_id=state.template_id,
            game_id=state.session_id,
            operation="translate_text_log",
            phase="translation",
            metadata={"target_language": target_language},
        )
    except Exception as exc:
        logger.exception("Text translation failed for session %s", game_id, exc_info=exc)
        raise HTTPException(status_code=502, detail="Translation failed.") from None

    cleaned = str(translated or "").strip()
    if cleaned.startswith("```") and cleaned.endswith("```"):
        cleaned = cleaned.strip("`").strip()

    return TranslateTextResponse(translated_text=cleaned or source_text, language=target_language)


@router.get("/{game_id}/walkthrough")
async def get_walkthrough(
    game_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns the walkthrough status and payload for the current session."""
    state = await AdventureLogic.resolve_session_state(db, game_id, user_id=current_user.id)
    if not state:
        raise HTTPException(status_code=404, detail="Session state not found.")

    res = await db.execute(
        select(GameSession, Avatar)
        .outerjoin(Avatar, Avatar.id == GameSession.avatar_id)
        .where(GameSession.id == state.session_id)
    )
    row = res.first()
    session, avatar = row if row else (None, None)

    adventure = await load_session_adventure(db, state)
    all_steps = sequence_walkthrough_steps(
        getattr(adventure, "sequences", None), state.active_sequence_id
    )
    if not all_steps:
        return {
            "available": False,
            "revealed": False,
            "current_xp": avatar.exp if avatar else 0,
            "reveal_cost": WALKTHROUGH_REVEAL_COST,
            "message": "No walkthrough available for this adventure yet.",
            "preview": "No walkthrough available for this adventure yet.",
            "steps": [],
        }

    is_revealed = bool(state.is_walkthrough_revealed or settings.TALEWEAVER_DEBUG_ENABLED)
    if is_revealed:
        return {
            "available": True,
            "revealed": True,
            "current_xp": avatar.exp if avatar else 0,
            "reveal_cost": WALKTHROUGH_REVEAL_COST,
            "walkthrough": format_walkthrough_steps(all_steps),
            "steps": all_steps,
            "message": "Walkthrough unlocked.",
            "preview": "Walkthrough unlocked.",
        }

    return {
        "available": True,
        "revealed": False,
        "current_xp": avatar.exp if avatar else 0,
        "reveal_cost": WALKTHROUGH_REVEAL_COST,
        "preview": "The strategy guide is sealed. Reveal it to permanently view the walkthrough for this session.",
        "message": "The strategy guide is sealed. Reveal it to permanently view the walkthrough for this session.",
        "steps": [],
    }


@router.get("/{game_id}/suggestions")
async def get_prompt_suggestions(
    game_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns stored or freshly generated spoiler-safe prompt suggestions."""
    state = await AdventureLogic.resolve_session_state(db, game_id, user_id=current_user.id)
    if not state:
        raise HTTPException(status_code=404, detail="Session state not found.")

    manager = GameTurnManager(db, state.session_id, current_user)
    if not await manager.initialize():
        raise HTTPException(status_code=404, detail="Failed to initialize session.")

    suggestions = manager.suggestions.extract_prompt_suggestions(manager.state.exit_states or {})
    if not suggestions:
        last_response = await manager.suggestions.load_last_assistant_message()
        suggestions = await manager.suggestions.generate_prompt_suggestions(last_response)
        await db.commit()

    return {"suggestions": suggestions}


@router.post("/{game_id}/suggestions")
@router.post("/{game_id}/shuffle")
async def shuffle_prompt_suggestions(
    game_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Regenerates up to 5 spoiler-safe prompt suggestions for the current session."""
    state = await AdventureLogic.resolve_session_state(db, game_id, user_id=current_user.id)
    if not state:
        raise HTTPException(status_code=404, detail="Session state not found.")

    manager = GameTurnManager(db, state.session_id, current_user)
    if not await manager.initialize():
        raise HTTPException(status_code=404, detail="Failed to initialize session.")

    last_response = await manager.suggestions.load_last_assistant_message()
    suggestions = await manager.suggestions.generate_prompt_suggestions(last_response)
    await db.commit()

    return {"suggestions": suggestions}


@router.post("/{game_id}/text-logs/{entity_id}/read")
async def mark_text_log_read(
    game_id: str,
    entity_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Marks a READABLE object as read in session-scoped state overrides."""
    state = await AdventureLogic.resolve_session_state(db, game_id, user_id=current_user.id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found.")

    clean_id = (entity_id or "").strip()
    ent_res = await db.execute(
        select(WorldEntity)
        .where(
            or_(
                WorldEntity.session_id == state.session_id,
                and_(
                    WorldEntity.template_id == state.template_id,
                    WorldEntity.session_id.is_(None),
                ),
            ),
            or_(
                WorldEntity.id == clean_id,
                func.lower(WorldEntity.id) == clean_id.lower(),
            ),
        )
        .order_by(WorldEntity.session_id.is_(None))
    )
    entity = ent_res.scalars().first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found in this session.")

    if entity.entity_type != "OBJECT" or str(entity.item_type or "").upper() != "READABLE":
        raise HTTPException(status_code=400, detail="Entity is not a readable text log.")

    entity_states = dict(state.entity_states or {})
    current_entry = entity_states.get(entity.id)
    override_entry = dict(current_entry) if isinstance(current_entry, dict) else {}
    already_read = bool(override_entry.get("is_read"))
    override_entry["is_read"] = True
    entity_states[entity.id] = override_entry

    state.entity_states = entity_states
    flag_modified(state, "entity_states")

    # Read hooks fire on the first read only; reopening the text must not repeat them.
    meta = dict(entity.metadata_json or {})
    if not already_read and (meta.get("on_read_script") or meta.get("on_read_text")):
        await TriggerService.execute_trigger(
            db,
            state,
            "on_read",
            entity.id,
            script_code=meta.get("on_read_script"),
            narrative_text=meta.get("on_read_text"),
        )

    await db.commit()

    return {"status": "ok", "entity_id": entity.id, "is_read": True}


@router.post("/{game_id}/containers/{entity_id}/unlock-code")
async def unlock_container_with_code(
    game_id: str,
    entity_id: str,
    payload: ContainerUnlockCodeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Deterministically unlocks a container when the provided code matches code_to_unlock."""
    state = await _require_session_state(db, game_id, current_user)
    entity = await load_session_object(db, state, entity_id, "CONTAINER", "Container not found.")
    metadata_json = dict(entity.metadata_json or {})
    expected_code = require_value(
        metadata_json.get("code_to_unlock"), "This container does not require a code."
    )
    submitted_code = require_value(payload.code, "Code is required.")
    if submitted_code.lower() != expected_code.lower():
        raise HTTPException(status_code=403, detail=INVALID_CONTAINER_CODE_MESSAGE)

    await enforce_container_guard(db, state, entity, metadata_json)

    # Only the first unlock grants XP.
    if mark_container_unlocked(state, entity.id):
        avatar = await load_avatar(db, state)
        if avatar:
            xp_reward = award_unlock_xp(avatar, metadata_json)
            add_system_message(db, state, f"Unlocked {entity.name} with the correct code!")
            add_system_message(db, state, f"you gained {xp_reward} XP")
        await fire_container_unlock_success(db, state, entity, metadata_json)

    await db.commit()
    return {"status": "ok", "entity_id": entity.id, "locked": False}


class ContainerUnlockItemRequest(BaseModel):
    item_id: str


@router.post("/{game_id}/containers/{entity_id}/unlock-item")
async def unlock_container_with_item(
    game_id: str,
    entity_id: str,
    payload: ContainerUnlockItemRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Deterministically unlocks a container when the player possesses the required item."""
    state = await _require_session_state(db, game_id, current_user)
    entity = await load_session_object(db, state, entity_id, "CONTAINER", "Container not found.")
    metadata_json = dict(entity.metadata_json or {})
    expected_item_id = require_value(
        metadata_json.get("item_to_unlock"), "This container does not require an item to unlock."
    ).upper()
    submitted_item_id = require_value(payload.item_id, "Item ID is required.").upper()
    if submitted_item_id != expected_item_id:
        raise HTTPException(status_code=403, detail="This item cannot unlock this container.")

    avatar = await require_avatar(db, state)
    if not avatar_has_item(avatar, submitted_item_id):
        raise HTTPException(status_code=403, detail="You do not possess the required key item.")

    await enforce_container_guard(db, state, entity, metadata_json)

    # Only the first unlock grants XP.
    if mark_container_unlocked(state, entity.id):
        xp_reward = award_unlock_xp(avatar, metadata_json)
        item_name = inventory_item_name(avatar, submitted_item_id)
        add_system_message(db, state, f"Unlocked {entity.name} using {item_name}!")
        add_system_message(db, state, f"you gained {xp_reward} XP")
        await fire_container_unlock_success(db, state, entity, metadata_json)

    await db.commit()
    return {"status": "ok", "entity_id": entity.id, "locked": False}


@router.post("/{game_id}/containers/{entity_id}/unlock")
async def unlock_container(
    game_id: str,
    entity_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Deterministically unlocks a container directly (evaluating unlock_expression if present)."""
    state = await _require_session_state(db, game_id, current_user)
    entity = await load_session_object(db, state, entity_id, "CONTAINER", "Container not found.")
    metadata_json = dict(entity.metadata_json or {})
    if metadata_json.get("code_to_unlock"):
        raise HTTPException(status_code=400, detail="This container requires a passcode.")
    if metadata_json.get("item_to_unlock"):
        raise HTTPException(status_code=400, detail="This container requires a key item.")

    await enforce_container_guard(db, state, entity, metadata_json)

    # Only the first unlock grants XP.
    if mark_container_unlocked(state, entity.id):
        avatar = await load_avatar(db, state)
        if avatar:
            award_unlock_xp(avatar, metadata_json)
            add_system_message(db, state, f"Unlocked {entity.name}!")
        await fire_container_unlock_success(db, state, entity, metadata_json)

    await db.commit()
    return {"status": "ok", "entity_id": entity.id, "locked": False}


class SwitchFlipCodeRequest(BaseModel):
    target_state: str
    code: str


class SwitchFlipItemRequest(BaseModel):
    target_state: str
    item_id: str


@router.post("/{game_id}/switches/{entity_id}/flip-code")
async def flip_switch_with_code(
    game_id: str,
    entity_id: str,
    payload: SwitchFlipCodeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Deterministically flips a switch when the provided code matches the transition gate code."""
    state = await _require_session_state(db, game_id, current_user)
    flip = await resolve_switch_flip(db, state, entity_id, payload.target_state)
    required_code = require_value(
        flip.gates.get("code"), "This transition does not require a code."
    )
    submitted_code = require_value(payload.code, "Code is required.")

    runner = await SwitchFlipRunner.create(db, game_id, current_user, state, flip)
    if submitted_code.lower() != required_code.lower():
        await runner.fail(flip.fail_message or "Incorrect code. The switch does not move.")
    await runner.enforce_gate_expression()
    return await runner.succeed(
        state, f"{flip.entity.name} switched to {flip.target_label} using the correct code."
    )


@router.post("/{game_id}/switches/{entity_id}/flip-item")
async def flip_switch_with_item(
    game_id: str,
    entity_id: str,
    payload: SwitchFlipItemRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Deterministically flips a switch when the player possesses the required item."""
    state = await _require_session_state(db, game_id, current_user)
    flip = await resolve_switch_flip(db, state, entity_id, payload.target_state)
    required_item_id = require_value(
        flip.gates.get("item"), "This transition does not require an item."
    ).upper()
    submitted_item_id = require_value(payload.item_id, "Item ID is required.").upper()

    runner = await SwitchFlipRunner.create(db, game_id, current_user, state, flip)
    if submitted_item_id != required_item_id:
        await runner.fail(flip.fail_message or "This item cannot activate the switch.")

    avatar = await require_avatar(db, state)
    if not avatar_has_item(avatar, submitted_item_id):
        await runner.fail("You do not possess the required item.")
    await runner.enforce_gate_expression()

    item_name = inventory_item_name(avatar, submitted_item_id)
    return await runner.succeed(
        state, f"{flip.entity.name} switched to {flip.target_label} using {item_name}."
    )


# ---------------------------------------------------------------------------
# Exit unlock & traversal endpoints
# ---------------------------------------------------------------------------

INVALID_EXIT_CODE_MESSAGE = "That code does not open this way."


async def _resolve_session_exit(
    db: AsyncSession, state: SessionState, exit_id: str
) -> WorldExit | None:
    """Returns the exit used for the current session, preferring the session-scoped row."""
    clean_id = (exit_id or "").strip()
    res = await db.execute(
        select(WorldExit)
        .where(
            or_(
                WorldExit.session_id == state.session_id,
                and_(
                    WorldExit.template_id == state.template_id,
                    WorldExit.session_id.is_(None),
                ),
            ),
            or_(
                WorldExit.id == clean_id,
                func.lower(WorldExit.id) == clean_id.lower(),
            ),
        )
        .order_by(WorldExit.session_id.is_(None))
    )
    resolved = res.scalars().first()
    if not resolved:
        return None

    # If it is template-scoped, try to find the corresponding session-scoped exit
    if resolved.session_id is None:
        session_res = await db.execute(
            select(WorldExit).where(
                WorldExit.session_id == state.session_id,
                WorldExit.from_scene_id == resolved.from_scene_id,
                WorldExit.to_scene_id == resolved.to_scene_id,
            )
        )
        session_exit = session_res.scalars().first()
        if session_exit:
            return session_exit

    return resolved


async def _require_session_exit(db: AsyncSession, state: SessionState, exit_id: str) -> WorldExit:
    world_exit = await _resolve_session_exit(db, state, exit_id)
    if not world_exit:
        raise HTTPException(status_code=404, detail="Exit not found.")
    return world_exit


class ExitUnlockCodeRequest(BaseModel):
    code: str


class ExitUnlockItemRequest(BaseModel):
    item_id: str


@router.post("/{game_id}/exits/{exit_id}/unlock-code")
async def unlock_exit_with_code(
    game_id: str,
    exit_id: str,
    payload: ExitUnlockCodeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Unlocks an exit by validating a submitted access code."""
    state = await _require_session_state(db, game_id, current_user)
    world_exit = await _require_session_exit(db, state, exit_id)
    expected = require_value(world_exit.code_to_unlock, "This exit does not require a code.")
    submitted = require_value(payload.code, "Code is required.")
    if submitted.lower() != expected.lower():
        raise HTTPException(status_code=403, detail=INVALID_EXIT_CODE_MESSAGE)

    await enforce_exit_guard(db, state, world_exit)
    return await open_exit(
        db,
        state,
        world_exit,
        f"{world_exit.label or 'The exit'} accepts the code and the way is open.",
    )


@router.post("/{game_id}/exits/{exit_id}/unlock-item")
async def unlock_exit_with_item(
    game_id: str,
    exit_id: str,
    payload: ExitUnlockItemRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Unlocks an exit when the player possesses the required key item."""
    state = await _require_session_state(db, game_id, current_user)
    world_exit = await _require_session_exit(db, state, exit_id)
    expected_item = require_value(
        world_exit.item_to_unlock, "This exit does not require an item to unlock."
    ).upper()
    submitted_item = require_value(payload.item_id, "Item ID is required.").upper()
    if submitted_item != expected_item:
        raise HTTPException(status_code=403, detail="This item cannot unlock this exit.")

    avatar = await require_avatar(db, state)
    if not avatar_has_item(avatar, submitted_item):
        raise HTTPException(status_code=403, detail="You do not possess the required key item.")
    item_name = inventory_item_name(avatar, submitted_item)

    await enforce_exit_guard(db, state, world_exit)
    return await open_exit(
        db,
        state,
        world_exit,
        f"{world_exit.label or 'The exit'} yields to {item_name} and the way is open.",
    )


@router.post("/{game_id}/exits/{exit_id}/unlock")
async def unlock_exit(
    game_id: str,
    exit_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Deterministically unlocks an exit directly (evaluating unlock_expression if present)."""
    state = await _require_session_state(db, game_id, current_user)
    world_exit = await _require_session_exit(db, state, exit_id)
    if world_exit.code_to_unlock:
        raise HTTPException(status_code=400, detail="This exit requires a passcode.")
    if world_exit.item_to_unlock:
        raise HTTPException(status_code=400, detail="This exit requires a key item.")

    await enforce_exit_guard(db, state, world_exit)
    return await open_exit(
        db, state, world_exit, f"{world_exit.label or 'The exit'} unlocks and the way is open."
    )


async def _fire_gameplay_exit_triggers(
    db: AsyncSession,
    state: SessionState,
    world_exit: WorldExit,
    current_scene_id: str,
) -> None:
    """Executes on_leave_scene, on_open_exit, and on_exit_used triggers."""
    old_sc_res = await db.execute(
        select(WorldScene)
        .where(
            or_(
                WorldScene.session_id == state.session_id,
                and_(WorldScene.template_id == state.template_id, WorldScene.session_id.is_(None)),
            ),
            WorldScene.id == current_scene_id,
        )
        .order_by(WorldScene.session_id.is_(None))
    )
    old_scene = old_sc_res.scalars().first()
    if old_scene and (old_scene.on_leave_scene_script or old_scene.on_leave_scene_text):
        await TriggerService.execute_trigger(
            db,
            state,
            "on_leave_scene",
            old_scene.id,
            script_code=old_scene.on_leave_scene_script,
            narrative_text=old_scene.on_leave_scene_text,
        )

    if world_exit.on_open_exit_script or world_exit.on_open_exit_text:
        await TriggerService.execute_trigger(
            db,
            state,
            "on_open_exit",
            world_exit.id,
            script_code=world_exit.on_open_exit_script,
            narrative_text=world_exit.on_open_exit_text,
        )

    if getattr(world_exit, "on_exit_used_script", None) or getattr(
        world_exit, "on_exit_used_text", None
    ):
        await TriggerService.execute_trigger(
            db,
            state,
            "on_exit_used",
            world_exit.id,
            script_code=world_exit.on_exit_used_script,
            narrative_text=world_exit.on_exit_used_text,
        )


@router.post("/{game_id}/exits/{exit_id}/traverse")
async def traverse_exit(
    game_id: str,
    exit_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Moves the player through an unlocked exit to the target scene."""
    state = await AdventureLogic.resolve_session_state(db, game_id, user_id=current_user.id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found.")

    world_exit = await _resolve_session_exit(db, state, exit_id)
    if not world_exit:
        raise HTTPException(status_code=404, detail="Exit not found.")

    if world_exit.is_locked:
        raise HTTPException(
            status_code=403, detail=str(world_exit.lock_description or "The way is locked.")
        )

    current_scene_id = str(state.current_scene_id or "").strip().upper()
    if world_exit.from_scene_id == current_scene_id:
        target_scene_id = world_exit.to_scene_id
    elif (
        world_exit.exit_type.lower() == "bidirectional"
        and world_exit.to_scene_id == current_scene_id
    ):
        target_scene_id = world_exit.from_scene_id
    else:
        raise HTTPException(
            status_code=400, detail="This exit does not connect to the current scene."
        )

    scene_res = await db.execute(
        select(WorldScene)
        .where(
            or_(
                WorldScene.session_id == state.session_id,
                and_(
                    WorldScene.template_id == state.template_id,
                    WorldScene.session_id.is_(None),
                ),
            ),
            WorldScene.id == target_scene_id,
        )
        .order_by(WorldScene.session_id.is_(None))
    )
    scene = scene_res.scalars().first()
    if not scene:
        raise HTTPException(status_code=400, detail="The target scene is not available.")

    await _fire_gameplay_exit_triggers(db, state, world_exit, current_scene_id)

    state.current_scene_id = target_scene_id

    db.add(
        ChatMessage(
            session_id=state.session_id,
            role="system",
            content=f"You pass through {world_exit.label or 'the exit'} into {scene.label}.",
        )
    )

    if scene.on_enter_scene_script or scene.on_enter_scene_text:
        await TriggerService.execute_trigger(
            db,
            state,
            "on_enter_scene",
            scene.id,
            script_code=scene.on_enter_scene_script,
            narrative_text=scene.on_enter_scene_text,
        )

    await db.commit()
    return {"status": "ok", "exit_id": world_exit.id, "scene_id": target_scene_id}
