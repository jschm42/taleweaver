"""Progress checks for state changes made outside the logic pass (dialog choices, scripts).

A regular turn evaluates side-quests, awards, sequence completion and the adventure's win/loss
guards when it applies the logic pass. State changed after that point would otherwise skip
them: a dialog that sets ``bomb_disarmed`` must still complete the chapter and win the
adventure, and an ``on_interact`` script that sets a quest variable must complete the quest
in the same turn, not one message later.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from backend.api.routes.adventures.logic import AdventureLogic
from backend.api.routes.adventures.quest_completion import (
    announce_completed_quests,
    hard_rule_quest_ids,
    mark_quests_completed,
)
from backend.api.routes.adventures.sequence_hooks import run_sequence_transition_hooks
from backend.api.routes.adventures.turn_state_applier import TurnStateApplier
from backend.engine.rules.hard_rule_evaluator import HardRuleEvaluator
from backend.engine.rules.rule_engine import GameEvent

if TYPE_CHECKING:
    from backend.api.routes.adventures.gameplay_logic import GameTurnManager

TERMINAL_STATUSES = frozenset({"completed", "game_over"})

# (guard field, condition field, resulting session status, fallback note); loss is checked first.
_END_GUARDS = (
    ("gameover_guard_expression", "gameover_condition", "game_over", "Defeat condition triggered."),
    ("completed_guard_expression", "completed_condition", "completed", "Victory achieved!"),
)


def session_ended(manager: GameTurnManager) -> bool:
    session = getattr(manager.state, "session", None)
    return bool(session and session.status in TERMINAL_STATUSES)


def _field(manager: GameTurnManager, name: str) -> str:
    raw = getattr(manager.state, name, None) or getattr(manager.adventure, name, None)
    return raw.strip() if isinstance(raw, str) else ""


async def _quests_and_awards(manager: GameTurnManager, script_context: Any) -> list[Any]:
    """Completes side-quests and grants awards whose hard rules hold now."""
    applier = getattr(manager, "state_applier", None) or TurnStateApplier(manager)
    messages: list[Any] = await applier._evaluate_deterministic_awards(GameEvent(), script_context)
    completed = mark_quests_completed(
        manager.state,
        hard_rule_quest_ids(manager.avatar, manager.state, script_context),
        game_id=manager.game_id,
    )
    messages.extend(announce_completed_quests(manager, completed))
    return messages


async def _advance_sequences(manager: GameTurnManager, script_context: Any) -> list[Any]:
    old_seq_id = manager.state.active_sequence_id
    messages: list[Any] = AdventureLogic.evaluate_sequence_progress(
        adventure=manager.adventure,
        state=manager.state,
        avatar=manager.avatar,
        script_context=script_context,
    )
    if not messages:
        return []
    for message in messages:
        await manager._save_chat_message("system", message)
    messages.extend(
        await run_sequence_transition_hooks(
            manager,
            manager._save_chat_message,
            manager.adventure,
            old_seq_id,
            manager.state.active_sequence_id,
        )
    )
    return messages


def _ending(manager: GameTurnManager, script_context: Any) -> Optional[tuple[str, str]]:
    """(status, note) when a win/loss guard holds."""
    for guard_field, condition_field, status, fallback in _END_GUARDS:
        guard = _field(manager, guard_field)
        if not guard:
            continue
        met, _detail = HardRuleEvaluator.check_guard_expression(
            guard, manager.avatar, manager.state, script_context=script_context
        )
        if met:
            return status, _field(manager, condition_field) or fallback
    return None


async def apply_out_of_turn_progress(manager: GameTurnManager) -> tuple[list[Any], Optional[str]]:
    """Completes quests and awards, advances sequences and ends the adventure if a guard holds.

    Returns (messages to show, the terminal status the session reached or None).
    """
    if session_ended(manager):
        return [], None
    context = await manager._build_script_context()
    messages = await _quests_and_awards(manager, context)
    messages.extend(await _advance_sequences(manager, context))
    ending = _ending(manager, await manager._build_script_context())
    if ending is None:
        return messages, None
    status, note = ending
    await manager._finalize_session(status, note)
    return messages, status
