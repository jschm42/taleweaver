"""Turn-pass building blocks shared by the strict and chat-mode LLM cycles.

- Guardrail chain (Pass 1.5): validates/reverts Pass 1 state changes, then applies the event.
- In-game turn clock: base time (`time_per_turn`), status-effect ticks, and the
  `on_turn_end` / `on_turn_start` scripts only advance when the player's scene or the
  active sequence changed. Plain chat messages inside one scene stay within the same
  in-game turn (LLM-requested `extra_time_minutes` still applies on any message).
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

from backend.api.routes.adventures.logic import AdventureLogic
from backend.engine.rules.rule_engine import GameEvent, GameOverException, RuleEngine

logger = logging.getLogger(__name__)

# (manager method, whether it receives the player's message)
_GUARDRAIL_STEPS: tuple[tuple[str, bool], ...] = (
    ("_enforce_constructable_combination", True),
    ("_enforce_no_dynamic_item_generation", False),
    ("_enforce_container_unlock_guardrails", True),
    ("_enforce_exit_unlock_guardrails", True),
    ("_enforce_switch_transition_guardrails", True),
    ("_enforce_npc_movement_guardrails", False),
    ("_enforce_hidden_entity_reveal", True),
)


def sse_system(content: str) -> str:
    return f"event: system\ndata: {json.dumps({'role': 'system', 'content': content})}\n\n"


def sse_role_message(message: Any) -> str:
    role = getattr(message, "role", "system")
    payload: dict[str, Any] = {"role": role, "content": str(message)}
    if getattr(message, "raw", False):
        payload["raw"] = True
    return f"event: {role}\ndata: {json.dumps(payload)}\n\n"


async def run_guardrail_chain(
    manager: Any,
    game_event: GameEvent,
    user_msg: str,
    rule_violations: list[str],
    script_ctx: Any = None,
) -> AsyncGenerator[str, None]:
    """Runs Pass 1.5 (deterministic rule enforcement) and applies the validated event.

    Violations are appended to `rule_violations` so Pass 2 narrates the failure.
    Soft rules run first, against the sequence active when the message started; their
    outcomes are regular events, not violations.
    """
    active_sequence = AdventureLogic.resolve_active_sequence(manager.adventure, manager.state)
    for message in await manager.guardrails._enforce_soft_rules(game_event, active_sequence):
        yield sse_system(message)

    for method_name, takes_user_msg in _GUARDRAIL_STEPS:
        enforce = getattr(manager, method_name)
        args = (game_event, user_msg) if takes_user_msg else (game_event,)
        messages = await enforce(*args)
        rule_violations.extend(messages)
        for message in messages:
            await manager._save_chat_message("system", message)
            yield sse_system(message)

    await manager._enforce_quest_and_award_guardrails(game_event)
    rule_violations.extend(
        await manager._enforce_win_and_loss_guardrails(game_event, script_context=script_ctx)
    )
    for system_message in await manager._apply_game_event(game_event):
        yield sse_role_message(system_message)


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def extract_usage_tokens(usage: Any) -> dict[str, int]:
    """Normalizes provider usage (litellm stream usage) into prompt/completion/cached tokens."""
    if usage is None:
        return {}
    prompt_tokens = _int_or_none(getattr(usage, "prompt_tokens", None))
    completion_tokens = _int_or_none(getattr(usage, "completion_tokens", None))
    if prompt_tokens is None or completion_tokens is None:
        return {}
    details = getattr(usage, "prompt_tokens_details", None)
    cached = _int_or_none(getattr(details, "cached_tokens", None)) or _int_or_none(
        getattr(usage, "cache_read_input_tokens", None)
    )
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "cached_prompt_tokens": cached or 0,
    }


def turn_anchor(state: Any) -> tuple[Any, Any]:
    """Snapshot of what defines an in-game turn: the scene and the active sequence."""
    return (state.current_scene_id, state.active_sequence_id)


def crossed_turn_boundary(state: Any, anchor: tuple[Any, Any] | None) -> bool:
    if anchor is None:
        return False
    return turn_anchor(state) != anchor


async def _run_turn_script(
    manager: Any, script_runner: Any, trigger: str
) -> AsyncGenerator[str, None]:
    script_ctx = await manager._build_script_context()
    changeset = script_runner.run_trigger(trigger, script_ctx)
    if not changeset.has_changes:
        return
    for system_message in await manager._apply_script_changeset(changeset):
        yield sse_role_message(system_message)


async def advance_in_game_turn(
    manager: Any, script_runner: Any, game_event: Any = None
) -> AsyncGenerator[str, None]:
    """Closes the current in-game turn and opens the next one.

    Order: `on_turn_end` (old turn) -> base time + status ticks -> `on_turn_start` (new turn).
    """
    try:
        if script_runner.scripts:
            async for event in _run_turn_script(manager, script_runner, "on_turn_end"):
                yield event

        time_per_turn = manager.adventure.time_per_turn
        manager.state.in_game_time += int(time_per_turn if time_per_turn is not None else 5)
        for tick_message in RuleEngine.apply_ticks(manager.avatar):
            yield sse_system(tick_message)

        if script_runner.scripts:
            async for event in _run_turn_script(manager, script_runner, "on_turn_start"):
                yield event
    except GameOverException as goe:
        await manager._finalize_session("game_over", str(goe))
        if isinstance(game_event, GameEvent):
            game_event.game_over = True
            game_event.status_note = str(goe)
