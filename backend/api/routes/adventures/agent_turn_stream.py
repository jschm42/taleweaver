"""Autonomous play-agent turn: decide an action from walkthrough & state, then play it."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select

from backend.api.routes.adventures.agent_actions import execute_agent_action
from backend.api.routes.adventures.agent_combat import decide_combat_turn
from backend.api.routes.adventures.agent_logic import AgentService
from backend.api.routes.adventures.agent_settings import build_agent_snapshot
from backend.api.routes.adventures.gameplay_logic import GameTurnManager
from backend.api.routes.adventures.logic import AdventureLogic
from backend.core import database as core_database
from backend.models.chat import ChatMessage
from backend.models.user import User

logger = logging.getLogger(__name__)

MAX_AGENT_FAILURES = 3


def _sse(event: str, payload: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


async def ensure_agent_active(game_id: str, current_user: User) -> None:
    """Pre-flight check raising direct HTTP errors before the stream starts."""
    # Resolved at call time: tests swap the session factory on the database module.
    async with core_database.AsyncSessionLocal() as db:
        manager = GameTurnManager(db, game_id, current_user)
        if not await manager.initialize():
            raise HTTPException(status_code=404, detail="Game session not found.")
        agent_state = AgentService.get_agent_state(manager.state)
        if not agent_state.get("active", False):
            raise HTTPException(status_code=400, detail="Agent is not enabled for this session.")


async def _decide(db, game_id: str, current_user: User, manager: GameTurnManager):
    """Returns (decision or None, whether the decision call failed).

    Fights and loot phases are played by the deterministic combat tactician.
    """
    try:
        if manager._has_combat_phase():
            return await decide_combat_turn(manager), False
        decision = await AgentService.get_decision(
            db, game_id, current_user, manager.state, manager.avatar, manager.adventure, manager
        )
    except asyncio.CancelledError:
        logger.info("Agent turn stream cancelled during LLM decision call.")
        await db.rollback()
        raise
    except Exception:
        logger.exception("Agent decision failed")
        return None, True
    return decision, False


def _issue_description(decision: Any, decision_failed: bool) -> str:
    if decision:
        return decision.issue_description
    if decision_failed:
        return "Agent decision generation failed due to an internal error."
    return "Agent did not return a valid decision."


async def _recent_history_summary(db, game_id: str) -> str:
    hist_res = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == game_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(5)
    )
    recent_msgs = list(reversed(list(hist_res.scalars().all())))
    return " | ".join(f"{m.role}: {m.content}" for m in recent_msgs)


async def _agent_issue_events(
    db, game_id: str, manager: GameTurnManager, decision: Any, decision_failed: bool
) -> AsyncGenerator[str, None]:
    """Logs a stuck/failed agent turn, counts the failure, and ends the turn."""
    state = manager.state
    description = _issue_description(decision, decision_failed)
    thoughts = decision.thoughts if decision else "Failed to get decision thoughts."
    action = decision.action if decision else "None"
    history_summary = await _recent_history_summary(db, game_id)

    failures = AgentService.increment_failure(state)
    AgentService.log_issue(state.session_id, thoughts, action, description, history_summary)
    await db.commit()

    msg = f"Agent issue detected: {description} (Attempt {failures}/{MAX_AGENT_FAILURES})"
    if failures >= MAX_AGENT_FAILURES:
        msg += " - Agent mode has been deactivated."
    await manager._save_chat_message("system", msg)
    yield _sse("system", {"role": "system", "content": msg})
    yield await _final_event(db, manager)


async def _final_event(db, manager: GameTurnManager) -> str:
    state = manager.state
    final_data = jsonable_encoder(
        {
            "sheet": await AdventureLogic.build_sheet_snapshot(manager.avatar, state, db),
            "entities": await AdventureLogic.build_session_entities(db, state),
            "combat": AdventureLogic.get_combat_snapshot(state),
            "prompt_suggestions": GameTurnManager.extract_prompt_suggestions(
                state.exit_states or {}
            ),
            **manager._build_terminal_flags_payload(),
            "status": "success",
        }
    )
    return _sse("final", final_data)


async def _agent_action_events(
    db, manager: GameTurnManager, decision: Any
) -> AsyncGenerator[str, None]:
    """Announces the agent's decision and plays it as a regular turn."""
    yield _sse("thought", {"content": decision.thoughts})
    await asyncio.sleep(0.5)

    await manager._save_chat_message("player", decision.action)
    yield _sse("player_action", {"content": decision.action})
    yield _sse("status", {"content": f"Agent decides: {decision.action}"})

    AgentService.reset_failures(manager.state)
    await db.commit()

    outcome = await execute_agent_action(manager, decision.action)
    if outcome.turn_command is None:
        # Movement/unlock attempts resolved without a narration turn.
        await db.commit()
        await manager._save_chat_message("system", outcome.message or "")
        yield _sse("system", {"role": "system", "content": outcome.message or ""})
        yield await _final_event(db, manager)
        return

    try:
        async for chunk in manager.process_turn(outcome.turn_command):
            yield chunk
    except asyncio.CancelledError:
        logger.info("Agent turn stream cancelled during gameplay process_turn.")
        await db.rollback()
        raise

    async for event in _agent_finish_events(db, manager):
        yield event


async def _agent_finish_events(db, manager: GameTurnManager) -> AsyncGenerator[str, None]:
    """Deactivates the agent once the adventure has been won or lost."""
    flags = manager._build_terminal_flags_payload()
    if not (flags.get("game_over") or flags.get("game_completed")):
        return

    AgentService.set_agent_active(manager.state, False)
    await db.commit()
    outcome = "lost" if flags.get("game_over") else "won"
    msg = f"Play-Agent finished: the adventure was {outcome}. You are back in control."
    await manager._save_chat_message("system", msg)
    yield _sse("system", {"role": "system", "content": msg})
    yield _sse("agent_state", build_agent_snapshot(manager.state))


async def stream_agent_turn(game_id: str, current_user: User) -> AsyncGenerator[str, None]:
    yield _sse("status", {"content": "Agent is thinking..."})

    async with core_database.AsyncSessionLocal() as db:
        manager = GameTurnManager(db, game_id, current_user)
        await manager.initialize()
        try:
            decision, decision_failed = await _decide(db, game_id, current_user, manager)
            if not decision or decision.is_stuck_or_bug:
                events = _agent_issue_events(db, game_id, manager, decision, decision_failed)
            else:
                events = _agent_action_events(db, manager, decision)
            async for event in events:
                yield event
        except asyncio.CancelledError:
            logger.info("Agent turn stream cancelled, rolling back db session.")
            await db.rollback()
            raise
