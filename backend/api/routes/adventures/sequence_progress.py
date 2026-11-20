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


def _active_index(
    sequences: list[dict[str, Any]],
    active_seq_id: Optional[str],
    progression_mode: str = "linear",
) -> int:
    clean = str(active_seq_id or "").strip()
    if not clean:
        return 0 if (progression_mode == "linear" and sequences) else -1
    norm = clean.upper()
    for index, seq in enumerate(sequences):
        if str(seq.get("id") or "").strip().upper() == norm:
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


def _progression_mode(adventure: Any) -> str:
    """Returns 'linear' or 'dynamic'."""
    mode = getattr(adventure, "sequence_progression_mode", None)
    if not mode and isinstance(adventure, dict):
        mode = adventure.get("sequence_progression_mode") or adventure.get("sequence_progression")
    if not mode:
        manifest = getattr(adventure, "original_manifest", None)
        if isinstance(manifest, dict):
            mode = manifest.get("sequence_progression_mode") or manifest.get("sequence_progression")
    cleaned = str(mode or "linear").strip().lower()
    return cleaned if cleaned in {"linear", "dynamic"} else "linear"


def _is_sequence_completed_in_state(state: SessionState, sequence_id: str) -> bool:
    clean = str(sequence_id or "").strip().upper()
    if not clean:
        return False
    ent_states = getattr(state, "entity_states", None) or {}
    script_vars = ent_states.get("__script_vars__", {}) if isinstance(ent_states, dict) else {}
    return bool(script_vars.get(f"__seq_completed_{clean}__", False))


def _record_sequence_completed(state: SessionState, seq: dict[str, Any]) -> None:
    seq_id = str(seq.get("id") or "").strip().upper()
    if not seq_id:
        return
    if state.entity_states is None:
        state.entity_states = {}
    ent_states = dict(state.entity_states)
    script_vars = dict(ent_states.get("__script_vars__", {}))
    script_vars[f"__seq_completed_{seq_id}__"] = True
    ent_states["__script_vars__"] = script_vars
    state.entity_states = ent_states
    _flag(state, "entity_states")


def _advance(
    sequences: list[dict[str, Any]],
    index: int,
    state: SessionState,
    progression_mode: str = "linear",
    target_scene_id: Optional[str] = None,
) -> list[str]:
    if progression_mode == "dynamic":
        target = (
            str(target_scene_id or getattr(state, "current_scene_id", "") or "").strip().upper()
        )
        if target:
            for s in sequences:
                act_scene = str(s.get("activation_scene_id") or "").strip().upper()
                if act_scene and act_scene == target:
                    s_id = str(s.get("id") or "")
                    if not _is_sequence_completed_in_state(state, s_id):
                        state.active_sequence_id = s.get("id")
                        state.active_sequence_order = s.get("order", 1)
                        _flag(state, "active_sequence_id", "active_sequence_order")
                        return [f"New Sequence unlocked: {s.get('title') or s.get('id')}"]
        state.active_sequence_id = None
        state.active_sequence_order = 0
        _flag(state, "active_sequence_id", "active_sequence_order")
        return []

    next_index = index + 1
    if next_index < len(sequences):
        next_seq = sequences[next_index]
        state.active_sequence_id = next_seq.get("id")
        state.active_sequence_order = next_seq.get("order", next_index + 1)
        _flag(state, "active_sequence_id", "active_sequence_order")
        return [f"New Sequence unlocked: {next_seq.get('title') or next_seq.get('id')}"]
    state.active_sequence_id = None
    state.active_sequence_order = 0
    _flag(state, "active_sequence_id", "active_sequence_order")
    return []


def _try_activate_scene_sequence(
    sequences: list[dict[str, Any]],
    state: SessionState,
    target_scene_id: Optional[str],
) -> list[str]:
    target = str(target_scene_id or getattr(state, "current_scene_id", "") or "").strip().upper()
    if not target:
        return []
    for s in sequences:
        act_scene = str(s.get("activation_scene_id") or "").strip().upper()
        if act_scene and act_scene == target:
            s_id = str(s.get("id") or "")
            if not _is_sequence_completed_in_state(state, s_id):
                state.active_sequence_id = s.get("id")
                state.active_sequence_order = s.get("order", 1)
                _flag(state, "active_sequence_id", "active_sequence_order")
                return [f"New Sequence unlocked: {s.get('title') or s.get('id')}"]
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
    prog_mode = _progression_mode(adventure)
    active_id = getattr(state, "active_sequence_id", None)
    index = _active_index(sequences, active_id, progression_mode=prog_mode)

    if index < 0:
        if prog_mode == "dynamic":
            return _try_activate_scene_sequence(sequences, state, new_scene_id)
        return []

    current = sequences[index]
    if _is_sequence_completed_in_state(state, current.get("id")):
        return []
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

    _record_sequence_completed(state, current)
    award_msg = _award_completion(current, index, avatar)
    adv_msgs = _advance(
        sequences,
        index,
        state,
        progression_mode=prog_mode,
        target_scene_id=new_scene_id,
    )
    return [award_msg, *adv_msgs]


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
    sequences: list[dict[str, Any]],
    target_id: Optional[str],
    current_active_id: Optional[str],
    progression_mode: str = "linear",
) -> int:
    if target_id:
        norm = target_id.strip().upper()
        for i, s in enumerate(sequences):
            if str(s.get("id", "")).strip().upper() == norm:
                return i
    if not current_active_id and progression_mode == "dynamic":
        return -1
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
        state.active_sequence_id = None
        state.active_sequence_order = 0
        _flag(state, "active_sequence_id", "active_sequence_order")
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
    progression_mode: str = "linear",
) -> list[str]:
    target_end_id = getattr(changeset, "sequence_end_id", None)
    idx = _resolve_sequence_index(
        sequences,
        target_end_id,
        getattr(state, "active_sequence_id", None),
        progression_mode=progression_mode,
    )
    if idx < 0:
        return []

    completed_seq = sequences[idx]
    messages: list[str] = []
    seq_id = str(completed_seq.get("id") or f"seq_{idx}")

    norm_id = seq_id.strip().upper()
    if state.entity_states is None:
        state.entity_states = {}
    ent_states = dict(state.entity_states)
    script_vars = dict(ent_states.get("__script_vars__", {}))
    script_vars[f"__seq_completed_{norm_id}__"] = True
    ent_states["__script_vars__"] = script_vars
    state.entity_states = ent_states
    _flag(state, "entity_states")

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

    advance = getattr(changeset, "sequence_advance", True) and (progression_mode != "dynamic")
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
    prog_mode = _progression_mode(adventure)
    messages: list[str] = []

    if has_completion:
        end_msgs = await _handle_sequence_completion(
            sequences,
            state,
            avatar,
            changeset,
            script_executor,
            message_saver,
            progression_mode=prog_mode,
        )
        messages.extend(end_msgs)

    if has_start:
        start_id = str(changeset.sequence_start_id)
        start_msgs = await _handle_sequence_start(
            sequences, state, start_id, script_executor, message_saver
        )
        messages.extend(start_msgs)

    return messages
