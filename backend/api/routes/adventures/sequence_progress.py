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


async def _execute_script_or_text(
    script: Optional[str],
    text: Optional[str],
    hook_name: str,
    target_id: str,
    script_executor: Optional[Any],
    message_saver: Optional[Any],
) -> list[str]:
    messages: list[str] = []
    if script and script_executor:
        msgs = await script_executor(script, hook_name, target_id)
        messages.extend(msgs)
    if text:
        if message_saver:
            await message_saver("system", text)
        messages.append(text)
    return messages


def _resolve_sequence_index(
    sequences: list[dict[str, Any]], target_id: Optional[str], current_active_id: Optional[str]
) -> int:
    if target_id:
        norm = target_id.strip().upper()
        for i, s in enumerate(sequences):
            if str(s.get("id", "")).strip().upper() == norm:
                return i
    for i, s in enumerate(sequences):
        if s.get("id") == current_active_id or (not current_active_id and i == 0):
            return i
    return -1


async def _advance_and_trigger(
    sequences: list[dict[str, Any]],
    index: int,
    state: SessionState,
    script_executor: Optional[Any],
    message_saver: Optional[Any],
) -> list[str]:
    next_index = index + 1
    if next_index >= len(sequences):
        if hasattr(state, "is_completed"):
            state.is_completed = True
            _flag(state, "is_completed")
        return []

    next_seq = sequences[next_index]
    seq_id = next_seq.get("id")
    state.active_sequence_id = seq_id
    state.active_sequence_order = next_seq.get("order", next_index + 1)
    _flag(state, "active_sequence_id", "active_sequence_order")

    title = next_seq.get("title") or seq_id
    unlock_msg = f"New Sequence unlocked: {title}"
    if message_saver:
        await message_saver("system", unlock_msg)
    messages = [unlock_msg]

    hook_msgs = await _execute_script_or_text(
        next_seq.get("on_start_sequence_script"),
        next_seq.get("on_start_sequence_text"),
        "on_start_sequence",
        str(seq_id or f"seq_{next_index}"),
        script_executor,
        message_saver,
    )
    messages.extend(hook_msgs)
    return messages


async def _handle_sequence_completion(
    sequences: list[dict[str, Any]],
    state: SessionState,
    avatar: Optional[Avatar],
    changeset: Any,
    script_executor: Optional[Any],
    message_saver: Optional[Any],
) -> list[str]:
    target_end_id = getattr(changeset, "sequence_end_id", None)
    idx = _resolve_sequence_index(
        sequences, target_end_id, getattr(state, "active_sequence_id", None)
    )
    if idx < 0:
        return []

    completed_seq = sequences[idx]
    messages: list[str] = []
    seq_id = str(completed_seq.get("id") or f"seq_{idx}")

    hook_msgs = await _execute_script_or_text(
        completed_seq.get("on_end_sequence_script"),
        completed_seq.get("on_end_sequence_text"),
        "on_end_sequence",
        seq_id,
        script_executor,
        message_saver,
    )
    messages.extend(hook_msgs)

    if avatar:
        comp_msg = _award_completion(completed_seq, idx, avatar)
        if message_saver:
            await message_saver("system", comp_msg)
        messages.append(comp_msg)

    advance = getattr(changeset, "sequence_advance", True)
    if not advance:
        state.active_sequence_id = None
        state.active_sequence_order = 0
        _flag(state, "active_sequence_id", "active_sequence_order")
        return messages

    adv_msgs = await _advance_and_trigger(sequences, idx, state, script_executor, message_saver)
    messages.extend(adv_msgs)
    return messages


async def _handle_sequence_start(
    sequences: list[dict[str, Any]],
    state: SessionState,
    target_id: str,
    script_executor: Optional[Any],
    message_saver: Optional[Any],
) -> list[str]:
    norm = target_id.strip().upper()
    matched = next(
        (s for s in sequences if str(s.get("id", "")).strip().upper() == norm),
        None,
    )
    new_id = matched.get("id", target_id) if matched else target_id
    order = matched.get("order", 1) if matched else 1
    state.active_sequence_id = new_id
    state.active_sequence_order = order
    _flag(state, "active_sequence_id", "active_sequence_order")

    title = (matched.get("title") or new_id) if matched else new_id
    start_msg = f"Sequence started: {title}"
    if message_saver:
        await message_saver("system", start_msg)
    messages = [start_msg]

    if not matched:
        return messages

    hook_msgs = await _execute_script_or_text(
        matched.get("on_start_sequence_script"),
        matched.get("on_start_sequence_text"),
        "on_start_sequence",
        new_id,
        script_executor,
        message_saver,
    )
    messages.extend(hook_msgs)
    return messages


async def apply_sequence_changeset(
    adventure: Any,
    state: SessionState,
    avatar: Optional[Avatar],
    changeset: Any,
    script_executor: Optional[Any] = None,
    message_saver: Optional[Any] = None,
) -> list[str]:
    """Applies sequence progression or sequence starts from a script changeset."""
    has_completion = bool(
        getattr(changeset, "sequence_completed", False)
        or getattr(changeset, "sequence_end_id", None)
    )
    has_start = bool(getattr(changeset, "sequence_start_id", None))
    if not has_completion and not has_start:
        return []

    sequences = _ordered_sequences(adventure)
    messages: list[str] = []

    if has_completion:
        end_msgs = await _handle_sequence_completion(
            sequences, state, avatar, changeset, script_executor, message_saver
        )
        messages.extend(end_msgs)

    if has_start:
        start_id = str(changeset.sequence_start_id)
        start_msgs = await _handle_sequence_start(
            sequences, state, start_id, script_executor, message_saver
        )
        messages.extend(start_msgs)

    return messages
