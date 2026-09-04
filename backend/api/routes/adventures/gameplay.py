from __future__ import annotations
import logging
from typing import Any, AsyncGenerator, cast
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings

from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.api.routes.adventures.logic import AdventureLogic
from backend.api.routes.adventures.schemas import (
    ChatRequest,
    ChatResponse,
    TerminalEpilogueRequest,
    TerminalEpilogueResponse,
    TranslateTextRequest,
    TranslateTextResponse,
)
from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.core.llm_router import GameMasterLLM
from backend.core.prompts import (
    BABLE_FISH_TRANSLATION_SYSTEM_PROMPT,
    BABLE_FISH_TRANSLATION_USER_PROMPT_TEMPLATE,
)
from backend.engine.map_engine import MapEngine
from backend.models.adventure_template import AdventureTemplate
from backend.models.avatar import Avatar
from backend.models.chat import ChatMessage
from backend.models.game_session import GameSession
from backend.models.session_state import SessionState
from backend.models.user import User
from backend.models.world_entity import WorldEntity, WorldScene, WorldExit

router = APIRouter(tags=["Gameplay"])
logger = logging.getLogger(__name__)

TERMINAL_EPILOGUE_STATE_KEY = "__terminal_epilogue__"
INVALID_CONTAINER_CODE_MESSAGE = "The lock gives a mocking click. That code won't open this container."


class ContainerUnlockCodeRequest(BaseModel):
    code: str


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

async def _build_session_debug_payload(
    db: AsyncSession,
    state: SessionState,
    adventure: AdventureTemplate | None,
    avatar: Avatar | None,
    current_user: User,
) -> dict[str, Any]:
    """Assembles unified debug data including all NPCs with stats/locations, full map with NPC indicators, and complete items matrix."""
    # 1. Scenes
    scenes_res = await db.execute(
        select(WorldScene).where(
            or_(
                WorldScene.session_id == state.session_id,
                and_(WorldScene.template_id == state.template_id, WorldScene.session_id.is_(None)),
            )
        ).order_by(WorldScene.id)
    )
    scenes_all = scenes_res.scalars().all()
    scene_lookup: dict[str, WorldScene] = {}
    for s in scenes_all:
        if s.id not in scene_lookup or s.session_id == state.session_id:
            scene_lookup[s.id] = s

    scene_names: dict[str, str] = {s.id: (s.label or s.id) for s in scene_lookup.values()}

    # 2. Exits
    exits_res = await db.execute(
        select(WorldExit).where(
            or_(
                WorldExit.session_id == state.session_id,
                and_(WorldExit.template_id == state.template_id, WorldExit.session_id.is_(None)),
            )
        )
    )
    exits_all = exits_res.scalars().all()
    exit_lookup: dict[str, WorldExit] = {}
    for ex in exits_all:
        key = f"{ex.from_scene_id}->{ex.to_scene_id}"
        if key not in exit_lookup or ex.session_id == state.session_id:
            exit_lookup[key] = ex

    exit_overrides = state.exit_states or {}
    exits_data = []
    for ex in exit_lookup.values():
        over = exit_overrides.get(ex.id, {})
        exits_data.append({
            "id": ex.id,
            "from_scene_id": ex.from_scene_id,
            "to_scene_id": ex.to_scene_id,
            "label": ex.label or "Passage",
            "is_locked": bool(over.get("is_locked", ex.is_locked)),
            "is_secret": bool(over.get("is_secret", getattr(ex, "is_secret", False))),
            "lock_description": ex.lock_description,
        })

    # 3. Entities
    ent_res = await db.execute(
        select(WorldEntity).where(
            or_(
                WorldEntity.session_id == state.session_id,
                and_(WorldEntity.template_id == state.template_id, WorldEntity.session_id.is_(None)),
            )
        ).order_by(WorldEntity.id)
    )
    entities_all = ent_res.scalars().all()
    entity_lookup: dict[str, WorldEntity] = {}
    for ent in entities_all:
        if ent.id not in entity_lookup or ent.session_id == state.session_id:
            entity_lookup[ent.id] = ent

    entity_overrides = state.entity_states or {}

    # 4. NPCs & scene_npcs mapping
    npcs_data = []
    scene_npcs: dict[str, list[dict[str, Any]]] = {}
    for s_id in scene_lookup.keys():
        scene_npcs[s_id] = []

    for ent in entity_lookup.values():
        if ent.entity_type != "NPC":
            continue
        over = entity_overrides.get(ent.id, {})
        loc_id = over.get("current_scene_id") or getattr(ent, "current_scene_id", None) or getattr(ent, "start_scene_id", None) or "UNKNOWN"
        loc_name = scene_names.get(loc_id, loc_id)
        hp = over.get("hp", getattr(ent, "hp", 100) if getattr(ent, "hp", None) is not None else 100)
        max_hp = over.get("max_hp", getattr(ent, "max_hp", 100) if getattr(ent, "max_hp", None) is not None else 100)
        stamina = over.get("stamina", getattr(ent, "stamina", 50) if getattr(ent, "stamina", None) is not None else 50)
        max_stamina = over.get("max_stamina", getattr(ent, "max_stamina", 50) if getattr(ent, "max_stamina", None) is not None else 50)
        mana = over.get("mana", getattr(ent, "mana", 50) if getattr(ent, "mana", None) is not None else 50)
        max_mana = over.get("max_mana", getattr(ent, "max_mana", 50) if getattr(ent, "max_mana", None) is not None else 50)
        is_defeated = bool(over.get("is_defeated", False))
        is_alive = not is_defeated and hp > 0
        is_hidden = bool(over.get("is_hidden", getattr(ent, "is_hidden", False)))
        is_hostile = bool(over.get("is_hostile", getattr(ent, "is_hostile", False)))
        inv = over.get("inventory", getattr(ent, "inventory", None) or [])

        npc_info = {
            "id": ent.id,
            "name": ent.name,
            "description": getattr(ent, "description", "") or "",
            "role": getattr(ent, "role", None) or getattr(ent, "npc_type", None) or (getattr(ent, "metadata_json", None) or {}).get("role") or "NPC",
            "image_url": getattr(ent, "image_url", None),
            "current_scene_id": loc_id,
            "current_scene_name": loc_name,
            "start_scene_id": getattr(ent, "start_scene_id", None) or getattr(ent, "current_scene_id", "UNKNOWN"),
            "hp": hp,
            "max_hp": max_hp,
            "stamina": stamina,
            "max_stamina": max_stamina,
            "mana": mana,
            "max_mana": max_mana,
            "is_alive": is_alive,
            "is_defeated": is_defeated,
            "is_hidden": is_hidden,
            "is_hostile": is_hostile,
            "inventory": inv,
            "is_in_current_scene": loc_id == state.current_scene_id,
            "stats": {
                "strength": getattr(ent, "stat_modifier_strength", 0) or 10,
                "dexterity": getattr(ent, "stat_modifier_dexterity", 0) or 10,
                "intelligence": getattr(ent, "stat_modifier_intelligence", 0) or 10,
                "wisdom": getattr(ent, "stat_modifier_wisdom", 0) or 10,
                "charisma": getattr(ent, "stat_modifier_charisma", 0) or 10,
                "armor_class": getattr(ent, "stat_modifier_armor_class", 0) or 10,
            },
        }
        npcs_data.append(npc_info)

        if loc_id not in scene_npcs:
            scene_npcs[loc_id] = []
        scene_npcs[loc_id].append({
            "id": ent.id,
            "name": ent.name,
            "image_url": ent.image_url,
            "hp": hp,
            "max_hp": max_hp,
            "is_alive": is_alive,
            "is_hidden": is_hidden,
        })

    # 5. Items Matrix (Avatar, Scenes, Containers, NPCs)
    items_data = []

    # A) Avatar inventory
    if avatar and avatar.inventory:
        for itm in avatar.inventory:
            if isinstance(itm, dict):
                items_data.append({
                    "id": itm.get("id") or itm.get("key") or itm.get("name"),
                    "name": itm.get("name") or "Unnamed Item",
                    "description": itm.get("description") or "",
                    "item_type": itm.get("item_type") or "PICKABLE",
                    "slot": itm.get("slot"),
                    "image_url": itm.get("image_url"),
                    "location_type": "avatar",
                    "location_id": avatar.id,
                    "location_name": f"Hero ({avatar.name})",
                    "is_hidden": False,
                    "is_portable": True,
                    "is_locked": False,
                    "switch_state": None,
                    "is_open": False,
                    "metadata": itm.get("metadata_json") or {},
                })

    # B) Scene entities (non-NPC)
    for ent in entity_lookup.values():
        if ent.entity_type == "NPC":
            continue
        over = entity_overrides.get(ent.id, {})
        loc_id = over.get("current_scene_id") or getattr(ent, "current_scene_id", None) or getattr(ent, "start_scene_id", None) or "UNKNOWN"
        loc_name = scene_names.get(loc_id, loc_id)
        is_hidden = bool(over.get("is_hidden", getattr(ent, "is_hidden", False)))
        is_locked = bool(over.get("is_locked", getattr(ent, "is_locked", False)))
        switch_state = over.get("switch_state", getattr(ent, "switch_state", None))
        is_open = bool(over.get("is_open", getattr(ent, "is_open", False)))
        is_portable = getattr(ent, "is_portable", True) if getattr(ent, "is_portable", None) is not None else True

        items_data.append({
            "id": ent.id,
            "name": ent.name,
            "description": ent.description or "",
            "item_type": ent.item_type or ent.entity_type or "OBJECT",
            "slot": getattr(ent, "slot", None),
            "image_url": ent.image_url,
            "location_type": "scene",
            "location_id": loc_id,
            "location_name": loc_name,
            "is_hidden": is_hidden,
            "is_portable": is_portable,
            "is_locked": is_locked,
            "switch_state": switch_state,
            "is_open": is_open,
            "metadata": ent.metadata_json or {},
        })

        # Items inside containers
        ent_inv = over.get("inventory", getattr(ent, "inventory", None) or [])
        if ent_inv and isinstance(ent_inv, list):
            for c_itm in ent_inv:
                if isinstance(c_itm, dict):
                    items_data.append({
                        "id": c_itm.get("id") or c_itm.get("name"),
                        "name": c_itm.get("name") or "Unnamed Item",
                        "description": c_itm.get("description") or "",
                        "item_type": c_itm.get("item_type") or "PICKABLE",
                        "slot": c_itm.get("slot"),
                        "image_url": c_itm.get("image_url"),
                        "location_type": "container",
                        "location_id": ent.id,
                        "location_name": f"{ent.name} (in {loc_name})",
                        "is_hidden": is_hidden,
                        "is_portable": True,
                        "is_locked": False,
                        "switch_state": None,
                        "is_open": False,
                        "metadata": c_itm.get("metadata_json") or {},
                    })

    # C) NPC inventory items
    for npc in npcs_data:
        for n_itm in npc["inventory"]:
            if isinstance(n_itm, dict):
                items_data.append({
                    "id": n_itm.get("id") or n_itm.get("name"),
                    "name": n_itm.get("name") or "Unnamed Item",
                    "description": n_itm.get("description") or "",
                    "item_type": n_itm.get("item_type") or "PICKABLE",
                    "slot": n_itm.get("slot"),
                    "image_url": n_itm.get("image_url"),
                    "location_type": "npc",
                    "location_id": npc["id"],
                    "location_name": f"{npc['name']} (in {npc['current_scene_name']})",
                    "is_hidden": npc["is_hidden"],
                    "is_portable": True,
                    "is_locked": False,
                    "switch_state": None,
                    "is_open": False,
                    "metadata": n_itm.get("metadata_json") or {},
                })

    # 6. Map nodes structure
    nodes_data = {}
    for s in scene_lookup.values():
        nodes_data[s.id] = {
            "id": s.id,
            "label": s.label or s.id,
            "description": s.description or "",
            "image_url": s.image_url,
            "is_current": s.id == state.current_scene_id,
            "npcs": scene_npcs.get(s.id, []),
        }

    blueprint_data = None
    try:
        from backend.api.routes.adventures.editor import _build_adventure_editor_assets
        blueprint_obj = await _build_adventure_editor_assets(state.template_id, db)
        blueprint_data = blueprint_obj.model_dump()
    except Exception as exc:
        logger.warning("Could not build blueprint assets for debug: %s", exc)

    return {
        "session": {
            "id": state.session_id,
            "template_id": state.template_id,
            "adventure_title": adventure.title if adventure else (state.session.adventure_title if state.session else "Adventure"),
            "current_scene_id": state.current_scene_id,
            "current_scene_name": scene_names.get(state.current_scene_id, state.current_scene_id),
            "in_game_time": state.in_game_time,
            "time_system": state.time_system,
            "is_debug_enabled": state.is_debug_enabled,
            "status": state.session.status if state.session else "active",
            "status_note": state.session.status_note if state.session else None,
        },
        "avatar": {
            "id": avatar.id if avatar else None,
            "name": avatar.name if avatar else "Protagonist",
            "hp": avatar.hp if avatar else 100,
            "max_hp": avatar.max_hp if avatar else 100,
            "stamina": avatar.stamina if avatar else 50,
            "max_stamina": avatar.max_stamina if avatar else 50,
            "mana": avatar.mana if avatar else 50,
            "max_mana": avatar.max_mana if avatar else 50,
            "exp": avatar.exp if avatar else 0,
            "stats": {
                "strength": getattr(avatar, "strength", 10) if avatar else 10,
                "dexterity": getattr(avatar, "dexterity", 10) if avatar else 10,
                "intelligence": getattr(avatar, "intelligence", 10) if avatar else 10,
                "wisdom": getattr(avatar, "wisdom", 10) if avatar else 10,
                "charisma": getattr(avatar, "charisma", 10) if avatar else 10,
                "armor_class": getattr(avatar, "armor_class", 10) if avatar else 10,
            },
        },
        "npcs": npcs_data,
        "scene_npcs": scene_npcs,
        "items": items_data,
        "map": {
            "nodes": nodes_data,
            "exits": exits_data,
            "current_scene_id": state.current_scene_id,
            "scene_npcs": scene_npcs,
        },
        "blueprint": blueprint_data,
        "runtime": {
            "current_scene_id": state.current_scene_id,
            "in_game_time": state.in_game_time,
            "is_debug_enabled": state.is_debug_enabled,
            "entity_overrides": entity_overrides,
            "exit_overrides": exit_overrides,
            "quests": state.quests or [],
            "world_memories": state.world_memories or [],
        },
        "raw": {
            "session_id": state.session_id,
            "template_id": state.template_id,
            "current_scene_id": state.current_scene_id,
            "in_game_time": state.in_game_time,
            "is_debug_enabled": state.is_debug_enabled,
            "entity_states": state.entity_states or {},
            "exit_states": state.exit_states or {},
            "quests": state.quests or [],
            "world_memories": state.world_memories or [],
            "avatar_stats": {
                "hp": avatar.hp if avatar else None,
                "mana": avatar.mana if avatar else None,
                "stamina": avatar.stamina if avatar else None,
                "exp": avatar.exp if avatar else None,
            },
        },
    }


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

    adv_res = await db.execute(select(AdventureTemplate).where(AdventureTemplate.id == state.template_id))
    adventure = adv_res.scalars().first()

    cv_res = await db.execute(select(Avatar).where(Avatar.id == state.avatar_id))
    avatar = cv_res.scalars().first()

    return await _build_session_debug_payload(db, state, adventure, avatar, current_user)


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

    adv_res = await db.execute(select(AdventureTemplate).where(AdventureTemplate.id == state.template_id))
    adventure = adv_res.scalars().first()
    
    cv_res = await db.execute(select(Avatar).where(Avatar.id == state.avatar_id))
    avatar = cv_res.scalars().first()

    chat_res = await db.execute(select(ChatMessage).where(ChatMessage.session_id == state.session_id).order_by(ChatMessage.created_at.asc()))
    history = [{"id": m.id, "role": m.role, "content": m.content} for m in chat_res.scalars().all()]
    
    # Use the canonical template map so all sessions of the same adventure share one topology.
    world_map = await AdventureLogic.get_or_create_map(db, state.template_id)
    map_dict = MapEngine.to_dict(world_map) if world_map else None
    if map_dict is not None:
        map_dict["current_scene_id"] = MapEngine._safe_id(state.current_scene_id)
        # Heal stale image_url values (e.g. from deleted sessions) in the map nodes
        for node in map_dict.get("nodes", {}).values():
            if isinstance(node, dict) and node.get("image_url"):
                node["image_url"] = AdventureLogic.resolve_existing_data_asset_url(node["image_url"])
    
    # Augment with adjacent unvisited scenes
    if world_map:
        exit_query = select(WorldExit).where(
            or_(
                WorldExit.session_id == state.session_id,
                WorldExit.template_id == state.template_id
            )
        )
        exits_res = await db.execute(exit_query)
        exits = list(exits_res.scalars().all())
        map_dict = MapEngine.augment_map_data(map_dict, exits, state.current_scene_id)

    entities = await AdventureLogic.build_session_entities(db, state)
    
    scene_image = await AdventureLogic.resolve_scene_image(db, state, state.current_scene_id)
    pending_terminal_epilogue, input_locked = _terminal_flags_from_state(state)

    full_world_debug = None
    if include_full_world and (settings.TALEWEAVER_DEBUG_ENABLED or state.is_debug_enabled):
        try:
            from backend.api.routes.adventures.editor import _build_adventure_editor_assets
            full_world_debug = await _build_adventure_editor_assets(state.template_id, db)
        except Exception as exc:
            logger.warning("Could not build full_world debug payload: %s", exc)

    return ChatResponse(
        messages=history,
        sheet=await AdventureLogic.build_sheet_snapshot(avatar, state, db),
        combat=AdventureLogic.get_combat_snapshot(state),
        map_data=map_dict,
        nodes=await AdventureLogic.get_all_scene_metadata(db, state.template_id, session_id=state.session_id),
        entities=entities,
        npc_metadata=await AdventureLogic.get_npc_metadata(db, state.template_id, session_id=state.session_id),
        image_url=scene_image,
        adventure_image=AdventureLogic.resolve_session_asset(state, "cover", adventure.image_url if adventure else None),
        quests=state.quests,
        awards=[
            {
                **aw,
                "is_earned": any(
                    ea.get("key") == aw.get("key")
                    and (
                        ea.get("template_id") == (adventure.id if adventure else state.template_id)
                        or ea.get("adventure_id") == (adventure.id if adventure else state.template_id)
                    )
                    for ea in (current_user.earned_awards or [])
                ),
            }
            for aw in ((adventure.awards if adventure else (AdventureLogic.extract_manifest_snapshot(state).get("adventure") or {}).get("awards")) or [])
        ],
        is_completed=state.is_completed,
        game_over=state.session.status == "game_over" if state.session else False,
        game_completed=state.session.status == "completed" if state.session else False,
        status_note=state.session.status_note if state.session else None,
        input_locked=input_locked,
        pending_terminal_epilogue=pending_terminal_epilogue,
        prompt_suggestions=GameTurnManager.extract_prompt_suggestions(state.exit_states or {}),
        world_memories=state.world_memories or [],
        world_rumors=state.world_rumors or [],
        full_world=full_world_debug,
    )

@router.post("/{game_id}/chat")
async def post_chat_message(
    game_id: str,
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Processes a user message and returns a streaming response."""
    # Hard-coded, static error message used for any client-visible failure
    # path. Defined as a module-level constant so static-analysis tools can
    # verify that no exception text is ever forwarded to the response body.
    _CLIENT_ERROR_DETAIL = "Unable to process this turn."

    try:
        manager = GameTurnManager(db, game_id, current_user)
        turn_id = uuid4().hex

        async def _stream_with_turn_id(source: AsyncGenerator[str, None]) -> AsyncGenerator[str, None]:
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
                    f"data: {json.dumps({'detail': _CLIENT_ERROR_DETAIL, 'retryable': True})}\n\n"
                )

        try:
            turn_stream = manager.process_turn(
                payload.content,
                auto_visualize=payload.auto_visualize,
                language=payload.language,
            )
        except Exception:
            logger.exception("Failed to initialize chat stream for session %s", game_id)
            raise HTTPException(status_code=500, detail=_CLIENT_ERROR_DETAIL)

        return StreamingResponse(
            _stream_with_turn_id(turn_stream),
            media_type="text/event-stream",
            headers={"X-Taleweaver-Turn-Id": turn_id},
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to start chat turn for session %s", game_id)
        raise HTTPException(status_code=500, detail="Unable to process this turn.")


@router.post("/{game_id}/agent/turn")
async def run_agent_turn(
    game_id: str,
    current_user: User = Depends(get_current_user),
):
    """Computes an agent decision based on walkthrough & game state, then executes the turn."""
    import json
    import asyncio
    from fastapi.encoders import jsonable_encoder
    from backend.api.routes.adventures.agent_logic import AgentService
    from backend.core.database import AsyncSessionLocal

    # Pre-flight check to raise direct HTTP exceptions if session invalid or agent not active
    async with AsyncSessionLocal() as db:
        manager = GameTurnManager(db, game_id, current_user)
        if not await manager.initialize():
            raise HTTPException(status_code=404, detail="Game session not found.")
        agent_state = AgentService.get_agent_state(manager.state)
        if not agent_state.get("active", False):
            raise HTTPException(status_code=400, detail="Agent is not enabled for this session.")

    turn_id = uuid4().hex

    async def _agent_stream() -> AsyncGenerator[str, None]:
        yield f"event: status\ndata: {json.dumps({'content': 'Agent is thinking...'})}\n\n"
        
        async with AsyncSessionLocal() as db:
            manager = GameTurnManager(db, game_id, current_user)
            await manager.initialize()
            state = manager.state

            try:
                decision_err = False
                try:
                    decision = await AgentService.get_decision(
                        db, game_id, current_user, state, manager.avatar, manager.adventure, manager
                    )
                except asyncio.CancelledError:
                    logger.info("Agent turn stream cancelled during LLM decision call.")
                    await db.rollback()
                    raise
                except Exception as exc:
                    logger.exception("Agent decision failed")
                    decision = None
                    decision_err = True

                if not decision or decision.is_stuck_or_bug:
                    desc = decision.issue_description if decision else (
                        "Agent decision generation failed due to an internal error."
                        if decision_err
                        else "Agent did not return a valid decision."
                    )
                    thoughts = decision.thoughts if decision else "Failed to get decision thoughts."
                    action = decision.action if decision else "None"
                    
                    hist_res = await db.execute(
                        select(ChatMessage)
                        .where(ChatMessage.session_id == game_id)
                        .order_by(ChatMessage.created_at.desc())
                        .limit(5)
                    )
                    recent_msgs = list(reversed(list(hist_res.scalars().all())))
                    history_summary = " | ".join([f"{m.role}: {m.content}" for m in recent_msgs])
                    
                    failures = AgentService.increment_failure(state)
                    AgentService.log_issue(state.session_id, thoughts, action, desc, history_summary)
                    await db.commit()

                    msg = f"Agent issue detected: {desc} (Attempt {failures}/3)"
                    if failures >= 3:
                        msg += " - Agent mode has been deactivated."
                    
                    await manager._save_chat_message("system", msg)
                    yield f"event: system\ndata: {json.dumps({'role': 'system', 'content': msg})}\n\n"
                    
                    final_data = jsonable_encoder({
                        'sheet': await AdventureLogic.build_sheet_snapshot(manager.avatar, state, db),
                        'entities': await AdventureLogic.build_session_entities(db, state),
                        'combat': AdventureLogic.get_combat_snapshot(state),
                        'prompt_suggestions': GameTurnManager.extract_prompt_suggestions(state.exit_states or {}),
                        **manager._build_terminal_flags_payload(),
                        'status': 'success',
                    })
                    yield f"event: final\ndata: {json.dumps(final_data)}\n\n"
                    return

                yield f"event: thought\ndata: {json.dumps({'content': decision.thoughts})}\n\n"
                await asyncio.sleep(0.5)
                
                await manager._save_chat_message("player", decision.action)
                yield f"event: player_action\ndata: {json.dumps({'content': decision.action})}\n\n"
                yield f"event: status\ndata: {json.dumps({'content': f'Agent decides: {decision.action}'})}\n\n"
                
                AgentService.reset_failures(state)
                await db.commit()

                try:
                    async for chunk in manager.process_turn(decision.action):
                        yield chunk
                except asyncio.CancelledError:
                    logger.info("Agent turn stream cancelled during gameplay process_turn.")
                    await db.rollback()
                    raise
            except asyncio.CancelledError:
                logger.info("Agent turn stream cancelled, rolling back db session.")
                await db.rollback()
                raise

    return StreamingResponse(
        _agent_stream(),
        media_type="text/event-stream",
        headers={"X-Taleweaver-Turn-Id": turn_id},
    )


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
        raise HTTPException(status_code=400, detail="Selected translation model is unavailable.") from None

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
    """Returns the walkthrough for the current session if revealed or in debug mode."""
    res = await db.execute(
        select(SessionState)
        .join(GameSession, GameSession.id == SessionState.session_id)
        .where(SessionState.session_id == game_id, GameSession.user_id == current_user.id)
    )
    state = res.scalars().first()
    if not state:
        raise HTTPException(status_code=404, detail="Session state not found.")
    
    # Check if revealed or debug enabled
    from backend.core.config import settings
    if not state.is_walkthrough_revealed and not settings.TALEWEAVER_DEBUG_ENABLED:
        raise HTTPException(status_code=403, detail="The walkthrough is not revealed yet.")

    return {"walkthrough": state.walkthrough or "No walkthrough available for this adventure."}


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

    ent_res = await db.execute(
        select(WorldEntity).where(
            WorldEntity.session_id == state.session_id,
            WorldEntity.id == entity_id,
        )
    )
    entity = ent_res.scalars().first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found in this session.")

    if entity.entity_type != "OBJECT" or str(entity.item_type or "").upper() != "READABLE":
        raise HTTPException(status_code=400, detail="Entity is not a readable text log.")

    entity_states = dict(state.entity_states or {})
    current_entry = entity_states.get(entity.id)
    override_entry = dict(current_entry) if isinstance(current_entry, dict) else {}
    override_entry["is_read"] = True
    entity_states[entity.id] = override_entry

    state.entity_states = entity_states
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
    state = await AdventureLogic.resolve_session_state(db, game_id, user_id=current_user.id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found.")

    ent_res = await db.execute(
        select(WorldEntity).where(
            WorldEntity.session_id == state.session_id,
            WorldEntity.id == entity_id,
        )
    )
    entity = ent_res.scalars().first()
    if not entity or entity.entity_type != "OBJECT" or str(entity.item_type or "").upper() != "CONTAINER":
        raise HTTPException(status_code=404, detail="Container not found.")

    metadata_json = dict(entity.metadata_json or {})
    expected_code = str(metadata_json.get("code_to_unlock") or "").strip()
    if not expected_code:
        raise HTTPException(status_code=400, detail="This container does not require a code.")

    submitted_code = str(payload.code or "").strip()
    if not submitted_code:
        raise HTTPException(status_code=400, detail="Code is required.")
    if submitted_code.lower() != expected_code.lower():
        raise HTTPException(status_code=403, detail=INVALID_CONTAINER_CODE_MESSAGE)

    entity_states = dict(state.entity_states or {})
    entry = dict(entity_states.get(entity.id) or {})
    
    # Check if already unlocked to avoid double XP
    was_locked = entry.get("locked") if "locked" in entry else True

    entry["locked"] = False
    entity_states[entity.id] = entry
    state.entity_states = entity_states
    
    if was_locked:
        cv_res = await db.execute(select(Avatar).where(Avatar.id == state.avatar_id))
        avatar = cv_res.scalars().first()
        if avatar:
            xp_reward = metadata_json.get("exp_reward") or metadata_json.get("xp_reward") or 100
            avatar.exp = (avatar.exp or 0) + xp_reward
            db.add(
                ChatMessage(
                    session_id=state.session_id,
                    role="system",
                    content=f"Unlocked {entity.name} with the correct code!",
                )
            )
            db.add(
                ChatMessage(
                    session_id=state.session_id,
                    role="system",
                    content=f"you gained {xp_reward} XP",
                )
            )
            
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
    state = await AdventureLogic.resolve_session_state(db, game_id, user_id=current_user.id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found.")

    ent_res = await db.execute(
        select(WorldEntity).where(
            WorldEntity.session_id == state.session_id,
            WorldEntity.id == entity_id,
        )
    )
    entity = ent_res.scalars().first()
    if not entity or entity.entity_type != "OBJECT" or str(entity.item_type or "").upper() != "CONTAINER":
        raise HTTPException(status_code=404, detail="Container not found.")

    metadata_json = dict(entity.metadata_json or {})
    expected_item_id = str(metadata_json.get("item_to_unlock") or "").strip().upper()
    if not expected_item_id:
        raise HTTPException(status_code=400, detail="This container does not require an item to unlock.")

    submitted_item_id = str(payload.item_id or "").strip().upper()
    if not submitted_item_id:
        raise HTTPException(status_code=400, detail="Item ID is required.")
    if submitted_item_id != expected_item_id:
        raise HTTPException(status_code=403, detail="This item cannot unlock this container.")

    # Check if the player possesses the item in their inventory
    cv_res = await db.execute(select(Avatar).where(Avatar.id == state.avatar_id))
    avatar = cv_res.scalars().first()
    if not avatar:
        raise HTTPException(status_code=404, detail="Avatar not found.")

    inventory_ids = {
        str(item.get("id") or "").strip().upper() if isinstance(item, dict) else str(item).strip().upper()
        for item in (avatar.inventory or [])
    }

    if submitted_item_id not in inventory_ids:
        raise HTTPException(status_code=403, detail="You do not possess the required key item.")

    entity_states = dict(state.entity_states or {})
    entry = dict(entity_states.get(entity.id) or {})
    
    was_locked = entry.get("locked") if "locked" in entry else True

    entry["locked"] = False
    entity_states[entity.id] = entry
    state.entity_states = entity_states
    
    if was_locked:
        xp_reward = metadata_json.get("exp_reward") or metadata_json.get("xp_reward") or 100
        avatar.exp = (avatar.exp or 0) + xp_reward
        
        # Resolve item name for narration
        item_name = submitted_item_id
        for item in (avatar.inventory or []):
            if isinstance(item, dict) and str(item.get("id") or "").strip().upper() == submitted_item_id:
                item_name = item.get("name") or item_name
                break

        db.add(
            ChatMessage(
                session_id=state.session_id,
                role="system",
                content=f"Unlocked {entity.name} using {item_name}!",
            )
        )
        db.add(
            ChatMessage(
                session_id=state.session_id,
                role="system",
                content=f"you gained {xp_reward} XP",
            )
        )
        
    await db.commit()

    return {"status": "ok", "entity_id": entity.id, "locked": False}


class SwitchFlipCodeRequest(BaseModel):
    target_state: str
    code: str


class SwitchFlipItemRequest(BaseModel):
    target_state: str
    item_id: str


def _get_switch_config(entity: WorldEntity) -> dict:
    """Returns the parsed switch config from metadata_json."""
    raw = entity.metadata_json or {}
    return raw.get("switch") or {}


def _resolve_switch_transition(config: dict, current_state: str, target_state: str) -> dict | None:
    """Finds the matching transition definition for current -> target (or None).

    Matching precedence:
    1. Exact from/to match (both fields specified).
    2. Wildcard match (only ``to`` specified) — applies regardless of current state.
    """
    transitions = config.get("transitions") or []
    if not isinstance(transitions, list):
        return None

    wildcard_match: dict | None = None
    for t in transitions:
        if not isinstance(t, dict):
            continue
        from_s = str(t.get("from") or "").strip().upper()
        to_s = str(t.get("to") or "").strip().upper()
        if not to_s or to_s != target_state:
            continue
        if from_s and from_s == current_state:
            return t
        if not from_s and wildcard_match is None:
            wildcard_match = t
    return wildcard_match


@router.post("/{game_id}/switches/{entity_id}/flip-code")
async def flip_switch_with_code(
    game_id: str,
    entity_id: str,
    payload: SwitchFlipCodeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Deterministically flips a switch when the provided code matches the transition gate code."""
    state = await AdventureLogic.resolve_session_state(db, game_id, user_id=current_user.id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found.")

    ent_res = await db.execute(
        select(WorldEntity).where(
            WorldEntity.session_id == state.session_id,
            WorldEntity.id == entity_id,
        )
    )
    entity = ent_res.scalars().first()
    if not entity or entity.entity_type != "OBJECT" or str(entity.item_type or "").upper() != "SWITCH":
        raise HTTPException(status_code=404, detail="Switch not found.")

    config = _get_switch_config(entity)
    states = config.get("states") or []
    allowed_states = [str(s).strip().upper() for s in states if str(s).strip()]

    target_state = str(payload.target_state or "").strip().upper()
    if target_state not in allowed_states:
        raise HTTPException(status_code=400, detail=f"Invalid target state '{target_state}'.")

    session_states = dict(state.entity_states or {})
    entry = dict(session_states.get(entity.id) or {})
    configured_current = str(config.get("initial_state") or (allowed_states[0] if allowed_states else "")).strip().upper()
    current_state = str(entry.get("switch_state") or configured_current).strip().upper()

    if current_state == target_state:
        raise HTTPException(status_code=400, detail=f"Switch is already in state '{target_state}'.")

    transition = _resolve_switch_transition(config, current_state, target_state)
    if transition is None:
        raise HTTPException(status_code=400, detail="No transition definition found for this state change.")

    gates = transition.get("gates") if isinstance(transition.get("gates"), dict) else {}
    required_code = str(gates.get("code") or "").strip()
    if not required_code:
        raise HTTPException(status_code=400, detail="This transition does not require a code.")

    submitted_code = str(payload.code or "").strip()
    if not submitted_code:
        raise HTTPException(status_code=400, detail="Code is required.")
    if submitted_code.lower() != required_code.lower():
        fail_message = str(transition.get("fail_message") or "").strip()
        raise HTTPException(status_code=403, detail=fail_message or "Incorrect code. The switch does not move.")

    entry["switch_state"] = target_state
    session_states[entity.id] = entry
    state.entity_states = session_states

    db.add(
        ChatMessage(
            session_id=state.session_id,
            role="system",
            content=f"{entity.name} switched to {target_state} using the correct code.",
        )
    )

    await db.commit()
    return {"status": "ok", "entity_id": entity.id, "switch_state": target_state}


@router.post("/{game_id}/switches/{entity_id}/flip-item")
async def flip_switch_with_item(
    game_id: str,
    entity_id: str,
    payload: SwitchFlipItemRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Deterministically flips a switch when the player possesses the required item."""
    state = await AdventureLogic.resolve_session_state(db, game_id, user_id=current_user.id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found.")

    ent_res = await db.execute(
        select(WorldEntity).where(
            WorldEntity.session_id == state.session_id,
            WorldEntity.id == entity_id,
        )
    )
    entity = ent_res.scalars().first()
    if not entity or entity.entity_type != "OBJECT" or str(entity.item_type or "").upper() != "SWITCH":
        raise HTTPException(status_code=404, detail="Switch not found.")

    config = _get_switch_config(entity)
    states = config.get("states") or []
    allowed_states = [str(s).strip().upper() for s in states if str(s).strip()]

    target_state = str(payload.target_state or "").strip().upper()
    if target_state not in allowed_states:
        raise HTTPException(status_code=400, detail=f"Invalid target state '{target_state}'.")

    session_states = dict(state.entity_states or {})
    entry = dict(session_states.get(entity.id) or {})
    configured_current = str(config.get("initial_state") or (allowed_states[0] if allowed_states else "")).strip().upper()
    current_state = str(entry.get("switch_state") or configured_current).strip().upper()

    if current_state == target_state:
        raise HTTPException(status_code=400, detail=f"Switch is already in state '{target_state}'.")

    transition = _resolve_switch_transition(config, current_state, target_state)
    if transition is None:
        raise HTTPException(status_code=400, detail="No transition definition found for this state change.")

    gates = transition.get("gates") if isinstance(transition.get("gates"), dict) else {}
    required_item_id = str(gates.get("item") or "").strip().upper()
    if not required_item_id:
        raise HTTPException(status_code=400, detail="This transition does not require an item.")

    submitted_item_id = str(payload.item_id or "").strip().upper()
    if not submitted_item_id:
        raise HTTPException(status_code=400, detail="Item ID is required.")
    if submitted_item_id != required_item_id:
        fail_message = str(transition.get("fail_message") or "").strip()
        raise HTTPException(status_code=403, detail=fail_message or "This item cannot activate the switch.")

    # Verify the player has the item
    cv_res = await db.execute(select(Avatar).where(Avatar.id == state.avatar_id))
    avatar = cv_res.scalars().first()
    if not avatar:
        raise HTTPException(status_code=404, detail="Avatar not found.")

    inventory_ids = {
        str(item.get("id") or "").strip().upper() if isinstance(item, dict) else str(item).strip().upper()
        for item in (avatar.inventory or [])
    }
    if submitted_item_id not in inventory_ids:
        raise HTTPException(status_code=403, detail="You do not possess the required item.")

    entry["switch_state"] = target_state
    session_states[entity.id] = entry
    state.entity_states = session_states

    # Resolve item name for narration
    item_name = submitted_item_id
    for item in (avatar.inventory or []):
        if isinstance(item, dict) and str(item.get("id") or "").strip().upper() == submitted_item_id:
            item_name = item.get("name") or item_name
            break

    db.add(
        ChatMessage(
            session_id=state.session_id,
            role="system",
            content=f"{entity.name} switched to {target_state} using {item_name}.",
        )
    )

    await db.commit()
    return {"status": "ok", "entity_id": entity.id, "switch_state": target_state}


# ---------------------------------------------------------------------------
# Exit unlock & traversal endpoints
# ---------------------------------------------------------------------------

INVALID_EXIT_CODE_MESSAGE = "That code does not open this way."


async def _resolve_session_exit(db: AsyncSession, state: SessionState, exit_id: str) -> WorldExit | None:
    """Returns the exit used for the current session, preferring the session-scoped row."""
    clean_id = (exit_id or "").strip()
    res = await db.execute(
        select(WorldExit).where(
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
                WorldExit.to_scene_id == resolved.to_scene_id
            )
        )
        session_exit = session_res.scalars().first()
        if session_exit:
            return session_exit

    return resolved


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
    state = await AdventureLogic.resolve_session_state(db, game_id, user_id=current_user.id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found.")

    world_exit = await _resolve_session_exit(db, state, exit_id)
    if not world_exit:
        raise HTTPException(status_code=404, detail="Exit not found.")

    expected = str(world_exit.code_to_unlock or "").strip()
    if not expected:
        raise HTTPException(status_code=400, detail="This exit does not require a code.")

    submitted = str(payload.code or "").strip()
    if not submitted:
        raise HTTPException(status_code=400, detail="Code is required.")
    if submitted.lower() != expected.lower():
        raise HTTPException(status_code=403, detail=INVALID_EXIT_CODE_MESSAGE)

    world_exit.is_locked = False
    db.add(
        ChatMessage(
            session_id=state.session_id,
            role="system",
            content=f"{world_exit.label or 'The exit'} accepts the code and the way is open.",
        )
    )
    await db.commit()
    return {"status": "ok", "exit_id": world_exit.id, "is_locked": False}


@router.post("/{game_id}/exits/{exit_id}/unlock-item")
async def unlock_exit_with_item(
    game_id: str,
    exit_id: str,
    payload: ExitUnlockItemRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Unlocks an exit when the player possesses the required key item."""
    state = await AdventureLogic.resolve_session_state(db, game_id, user_id=current_user.id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found.")

    world_exit = await _resolve_session_exit(db, state, exit_id)
    if not world_exit:
        raise HTTPException(status_code=404, detail="Exit not found.")

    expected_item = str(world_exit.item_to_unlock or "").strip().upper()
    if not expected_item:
        raise HTTPException(status_code=400, detail="This exit does not require an item to unlock.")

    submitted_item = str(payload.item_id or "").strip().upper()
    if not submitted_item:
        raise HTTPException(status_code=400, detail="Item ID is required.")
    if submitted_item != expected_item:
        raise HTTPException(status_code=403, detail="This item cannot unlock this exit.")

    av_res = await db.execute(select(Avatar).where(Avatar.id == state.avatar_id))
    avatar = av_res.scalars().first()
    if not avatar:
        raise HTTPException(status_code=404, detail="Avatar not found.")

    inventory_ids = {
        str(item.get("id") or "").strip().upper() if isinstance(item, dict) else str(item).strip().upper()
        for item in (avatar.inventory or [])
    }
    if submitted_item not in inventory_ids:
        raise HTTPException(status_code=403, detail="You do not possess the required key item.")

    item_name = submitted_item
    for item in (avatar.inventory or []):
        if isinstance(item, dict) and str(item.get("id") or "").strip().upper() == submitted_item:
            item_name = item.get("name") or item_name
            break

    world_exit.is_locked = False
    db.add(
        ChatMessage(
            session_id=state.session_id,
            role="system",
            content=f"{world_exit.label or 'The exit'} yields to {item_name} and the way is open.",
        )
    )
    await db.commit()
    return {"status": "ok", "exit_id": world_exit.id, "is_locked": False}


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
        raise HTTPException(status_code=403, detail=str(world_exit.lock_description or "The way is locked."))

    current_scene_id = str(state.current_scene_id or "").strip().upper()
    if world_exit.from_scene_id == current_scene_id:
        target_scene_id = world_exit.to_scene_id
    elif world_exit.exit_type.lower() == "bidirectional" and world_exit.to_scene_id == current_scene_id:
        target_scene_id = world_exit.from_scene_id
    else:
        raise HTTPException(status_code=400, detail="This exit does not connect to the current scene.")

    scene_res = await db.execute(
        select(WorldScene).where(
            or_(
                WorldScene.session_id == state.session_id,
                and_(
                    WorldScene.template_id == state.template_id,
                    WorldScene.session_id.is_(None),
                ),
            ),
            WorldScene.id == target_scene_id,
        )
    )
    scene = scene_res.scalars().first()
    if not scene:
        raise HTTPException(status_code=400, detail="The target scene is not available.")

    state.current_scene_id = target_scene_id

    db.add(
        ChatMessage(
            session_id=state.session_id,
            role="system",
            content=f"You pass through {world_exit.label or 'the exit'} into {scene.label}.",
        )
    )
    await db.commit()
    return {"status": "ok", "exit_id": world_exit.id, "scene_id": target_scene_id}
