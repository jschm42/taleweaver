"""Message layout for the turn passes.

System prompts only carry static content (persona, adventure frame, rules, formatting),
so providers can serve them from the prompt cache across turns. Everything that changes
per turn (live state, quests, outcome, violations, reminders) goes into the latest user
message instead.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.chat import ChatMessage

RECENT_NARRATION_MAX_CHARS = 400
DEFAULT_MAX_MEMORY_TURNS = 10

# Planning/request fields whose information is already contained in the backend results.
_OUTCOME_EXCLUDED_FIELDS = {
    "narrative_description",
    "requested_skill_checks",
    "requested_attacks",
    "combination_intent",
}


def _is_debug_message(content: str) -> bool:
    return (content or "").lstrip().startswith("[DEBUG")


def format_recent_narration(history: list[dict[str, str]]) -> str:
    """Tail of the last GM reply, so Pass 1 can resolve references like 'open it'."""
    for message in reversed(history or []):
        content = (message.get("content") or "").strip()
        if message.get("role") != "assistant" or not content:
            continue
        if len(content) > RECENT_NARRATION_MAX_CHARS:
            content = "..." + content[-RECENT_NARRATION_MAX_CHARS:]
        return f"PREVIOUS GM NARRATION (only for resolving references):\n{content}"
    return ""


def build_pass1_user_prompt(
    state_block: str,
    user_msg: str,
    history: list[dict[str, str]] | None = None,
    extra_blocks: tuple[str, ...] = (),
) -> str:
    """Per-turn user message for Pass 1: live state, extra data, recent context, action."""
    parts = [state_block.strip()]
    parts.extend(block.strip() for block in extra_blocks if block and block.strip())
    recent = format_recent_narration(history or [])
    if recent:
        parts.append(recent)
    parts.append(f"PLAYER ACTION:\n{user_msg}")
    return "\n\n".join(part for part in parts if part)


def build_outcome_json(game_event: Any) -> tuple[str, str]:
    """Returns (draft_narration, pruned outcome JSON) for the narration pass."""
    if not game_event:
        return "", "{}"
    outcome = game_event.model_dump()
    draft = outcome.get("narrative_description") or ""
    pruned = {
        key: value
        for key, value in outcome.items()
        if key not in _OUTCOME_EXCLUDED_FIELDS
        and value is not None
        and value is not False
        and value not in (0, "", [], {})
    }
    return draft, json.dumps(pruned, ensure_ascii=False, separators=(",", ":"))


def build_exit_description_task(exits_json: str) -> str:
    """Instruction to close the narration with a compact paragraph about visible exits."""
    try:
        parsed_exits = json.loads(exits_json)
    except (TypeError, ValueError):
        parsed_exits = []
    exit_count = len(parsed_exits) if isinstance(parsed_exits, list) else 0
    sentence_instruction = (
        "Use exactly 1 sentence for the exit paragraph, and do not use contrast/addition connectors like 'on the other side' or 'additionally'."
        if exit_count == 1
        else "Keep it short (max 2 sentences)."
    )
    return (
        "EXIT DESCRIPTION TASK (MANDATORY): "
        "If exits are available, add exactly one compact paragraph at the end that narratively describes visible exits and where they lead. "
        f"Do not use headers, labels, lists, or bullet points. {sentence_instruction} "
        "If an exit is locked, mention it naturally. Use the same language and tone as the rest of your narration."
        f"\nCURRENT SCENE EXITS: {exits_json}"
    )


def build_narration_turn_block(
    state_block: str,
    draft_narration: str,
    outcome_json: str,
    rule_violations: list[str],
    exits_task: str = "",
    reminders: tuple[str, ...] = (),
) -> str:
    """CURRENT STATE + TURN RESOLUTION block prepended to the player's message in Pass 2."""
    lines = [
        state_block.strip(),
        "TURN RESOLUTION:",
        f"DRAFT NARRATION (narrative direction — keep focused and concise, do not bloat): {draft_narration}",
        f"TECHNICAL OUTCOME TO NARRATE: {outcome_json}",
    ]
    if rule_violations:
        lines.append(
            "CRITICAL RULE VIOLATIONS / REVERTS: The following actions/state updates were REVERTED because they "
            "violated game rules or preconditions. You MUST narrate that these actions FAILED in this turn and "
            "explain the reason to the player:\n" + "\n".join(f"- {v}" for v in rule_violations)
        )
    if exits_task:
        lines.append(exits_task)
    if reminders:
        lines.append("REMINDERS: " + " ".join(reminders))
    return "\n".join(line for line in lines if line)


def _resolve_max_turns(state: Any, adventure: Any) -> int:
    max_turns = getattr(state, "max_memory_turns", None)
    if max_turns is None and adventure:
        max_turns = getattr(adventure, "max_memory_turns", DEFAULT_MAX_MEMORY_TURNS)
    if max_turns is None:
        max_turns = DEFAULT_MAX_MEMORY_TURNS
    return max(0, int(max_turns))


async def _load_memory_window(
    db: AsyncSession, session_id: str, max_turns: int
) -> list[ChatMessage]:
    """Loads only the messages of the last `max_turns` turns plus the current one."""
    marker_res = await db.execute(
        select(ChatMessage.id, ChatMessage.created_at)
        .where(ChatMessage.session_id == session_id, ChatMessage.role == "user")
        .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
        .limit(max_turns + 1)
    )
    markers = list(marker_res.all())
    if not markers:
        return []

    start_id, start_created_at = markers[-1]
    msg_res = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id, ChatMessage.created_at >= start_created_at)
        .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
    )
    window = list(msg_res.scalars().all())
    start_idx = next((i for i, m in enumerate(window) if m.id == start_id), 0)
    return window[start_idx:]


def _append_message(messages: list[dict[str, str]], role: str, content: str) -> None:
    # Anthropic/Gemini require alternating roles: merge consecutive same-role entries.
    if messages and messages[-1]["role"] == role and len(messages) > 1:
        messages[-1]["content"] += f"\n\n{content}"
        return
    messages.append({"role": role, "content": content})


async def build_narration_messages(
    db: AsyncSession,
    state: Any,
    adventure: Any,
    narration_prompt: str,
    user_msg: str,
    turn_context: str = "",
) -> tuple[list[dict[str, str]], int]:
    """Builds the multi-turn message list for Pass 2 (narration).

    - Previous turns contribute only player/GM messages; their system events (dice rolls,
      stat changes, debug lines) were already narrated and would only cost tokens.
    - The current turn keeps its system events as `[Game Event: ...]` annotations.
    - `turn_context` (CURRENT STATE + TURN RESOLUTION) is prepended to the final user message.
    Returns (messages, max_turns_configured).
    """
    max_turns = _resolve_max_turns(state, adventure)
    window = await _load_memory_window(db, state.session_id, max_turns)
    current_turn_idx = max((i for i, m in enumerate(window) if m.role == "user"), default=-1)

    messages: list[dict[str, str]] = [{"role": "system", "content": narration_prompt}]
    for idx, message in enumerate(window):
        content = message.content or ""
        if message.role in ("user", "assistant"):
            _append_message(messages, message.role, content)
            continue
        if message.role != "system" or idx < current_turn_idx or _is_debug_message(content):
            continue
        _append_message(messages, "user", f"[Game Event: {content}]")

    # Ensure the last message is role="user" so the LLM responds as assistant.
    if len(messages) == 1 or messages[-1]["role"] != "user":
        messages.append({"role": "user", "content": user_msg})

    if turn_context:
        messages[-1]["content"] = f"{turn_context}\n\nPLAYER ACTION:\n{messages[-1]['content']}"
    return messages, max_turns
