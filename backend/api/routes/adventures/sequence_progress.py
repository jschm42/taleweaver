"""Completes the active sequence (chapter): XP reward, next sequence or adventure completion."""

from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy.orm.attributes import flag_modified

from backend.models.avatar import Avatar
from backend.models.session_state import SessionState

logger = logging.getLogger(__name__)


def _flag(obj: Any, *attributes: str) -> None:
    """flag_modified for ORM rows; plain test doubles have no instance state."""
    for attribute in attributes:
        try:
            flag_modified(obj, attribute)
        except Exception:
            logger.debug("Could not flag %s as modified on %r", attribute, type(obj).__name__)


def _ordered_sequences(adventure: Any) -> list[dict[str, Any]]:
    raw = getattr(adventure, "sequences", None) if adventure else None
    if not isinstance(raw, list):
        return []
    return sorted((s for s in raw if isinstance(s, dict)), key=lambda s: s.get("order", 1))


def _active_index(sequences: list[dict[str, Any]], active_seq_id: Optional[str]) -> int:
    for index, seq in enumerate(sequences):
        if seq.get("id") == active_seq_id or (not active_seq_id and index == 0):
            return index
    return -1


def _sequence_completed(
    seq: dict[str, Any],
    avatar: Avatar,
    state: SessionState,
    force_complete: bool,
    **evaluation_inputs: Any,
) -> bool:
    from backend.engine.rules.hard_rule_evaluator import HardRuleEvaluator

    if not HardRuleEvaluator.has_hard_rules(seq):
        return force_complete
    is_met, _ = HardRuleEvaluator.evaluate_hard_rules(seq, avatar, state, **evaluation_inputs)
    return is_met


def _award_completion(seq: dict[str, Any], index: int, avatar: Avatar) -> str:
    title = seq.get("title") or seq.get("id") or f"Chapter {index + 1}"
    xp_reward = int(seq.get("exp_reward") or 0)
    if xp_reward <= 0:
        return f"Sequence completed: {title}"
    avatar.exp = (getattr(avatar, "exp", 0) or 0) + xp_reward
    _flag(avatar, "exp")
    return f"Sequence completed: {title} (+{xp_reward} XP)"


def _advance(sequences: list[dict[str, Any]], index: int, state: SessionState) -> list[str]:
    next_index = index + 1
    if next_index < len(sequences):
        next_seq = sequences[next_index]
        state.active_sequence_id = next_seq.get("id")
        state.active_sequence_order = next_seq.get("order", next_index + 1)
        _flag(state, "active_sequence_id", "active_sequence_order")
        return [f"New Sequence unlocked: {next_seq.get('title') or next_seq.get('id')}"]
    if hasattr(state, "is_completed"):
        state.is_completed = True
        _flag(state, "is_completed")
    return []


def evaluate_sequence_progress(
    adventure: Any,
    state: SessionState,
    avatar: Avatar,
    new_inventory_items: Optional[list[Any]] = None,
    new_scene_id: Optional[str] = None,
    updated_entities: Optional[list[Any]] = None,
    force_complete: bool = False,
    script_context: Optional[Any] = None,
) -> list[str]:
    """Evaluates whether current active sequence hard rules (or forced completion) are met.

    If conditions are met, awards XP to the avatar, advances state.active_sequence_id,
    and returns descriptive system messages.
    """
    # The final sequence stays active after it completed; evaluating it again would repeat its
    # completion message and XP on every snapshot load.
    if getattr(state, "is_completed", False) is True:
        return []
    sequences = _ordered_sequences(adventure)
    index = _active_index(sequences, getattr(state, "active_sequence_id", None))
    if index < 0:
        return []
    current = sequences[index]
    completed = _sequence_completed(
        current,
        avatar,
        state,
        force_complete,
        new_inventory_items=new_inventory_items,
        new_scene_id=new_scene_id,
        updated_entities=updated_entities,
        script_context=script_context,
    )
    if not completed:
        return []
    return [_award_completion(current, index, avatar), *_advance(sequences, index, state)]
