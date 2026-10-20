"""In-game console command `/playagent` for configuring the autonomous play-agent."""

from __future__ import annotations

import json
import os
from collections.abc import AsyncGenerator, Callable
from typing import Any

from backend.api.routes.adventures.agent_logic import AgentService
from backend.api.routes.adventures.agent_settings import (
    activate_with_defaults,
    normalize_personality,
    personality_label,
)
from backend.core.config import settings
from backend.utils.path_security import ensure_within_data_dir, sanitize_path_component

PLAYAGENT_COMMANDS = ("/playagent", "/play-agent")

USAGE_TEXT = (
    "Usage: /playagent [on/off] | /playagent [casual|buerokrat|powerplayer] | "
    "/playagent personality <casual|buerokrat|powerplayer|custom <text>> | "
    "/playagent walkthrough on/off | /playagent step on/off | /playagent monkey on/off"
)


def _activate(manager: Any, personality: str | None = None) -> str:
    agent_state = activate_with_defaults(manager.state, manager.user.llm_settings, personality)
    msg = (
        "Play-Agent enabled. The AI will now play the game on your behalf "
        f"(Personality: {personality_label(agent_state.get('personality'))}). "
        "Use the Play-Agent panel to control it."
    )
    if agent_state.get("monkey_mode"):
        msg += " Monkey Mode is active by default from settings."
    if not agent_state.get("allow_walkthrough", True):
        msg += " Sequence Walkthrough guidance is disabled (normal player mode)."
    if agent_state.get("step_by_step"):
        msg += " Step mode is enabled."
    return msg


def _issue_log_hint(manager: Any) -> str:
    session_id = manager.state.session_id if manager.state else manager.game_id
    safe_session_id = sanitize_path_component(session_id)
    if not safe_session_id:
        return "Agent issues log file is unavailable due to an invalid session path."

    agents_md_path = ensure_within_data_dir(
        os.path.join(settings.DATA_DIR, "adventures", "sessions", safe_session_id, "AGENTS.md")
    )
    link_path = agents_md_path.replace("\\", "/")
    if not link_path.startswith("/"):
        link_path = "/" + link_path
    return f"Agent issues log file: [AGENTS.md](file://{link_path}) (Path: `{agents_md_path}`)"


def _deactivate(manager: Any) -> str:
    AgentService.set_agent_active(manager.state, False)
    return f"Play-Agent disabled. You are now back in control.\n\n{_issue_log_hint(manager)}"


def _set_personality(manager: Any, args: str) -> str:
    if not args:
        current = AgentService.get_agent_state(manager.state).get("personality", "casual")
        return (
            f"Current Play-Agent personality: {personality_label(current)}. "
            "Usage: /playagent personality <casual | buerokrat | powerplayer | custom <instructions>>"
        )

    parts = args.split(None, 1)
    chosen = normalize_personality(parts[0])
    custom_text = parts[1].strip() if len(parts) > 1 else ""
    if chosen and chosen != "custom":
        AgentService.set_personality(manager.state, chosen)
        return f"Play-Agent personality set to {personality_label(chosen)}."

    # "custom <text>" or free text without keyword both define custom instructions.
    instructions = custom_text if chosen == "custom" else args
    if not instructions:
        return (
            "Please provide custom personality instructions. "
            "Usage: /playagent personality custom <your instructions>"
        )
    AgentService.set_personality(manager.state, "custom", instructions)
    return f'Play-Agent custom personality updated: "{instructions}"'


def _toggle(setter: Callable[[Any, bool], None], enabled: bool, msg: str) -> Callable[[Any], str]:
    def handler(manager: Any) -> str:
        setter(manager.state, enabled)
        return msg

    return handler


_FIXED_HANDLERS: dict[str, Callable[[Any], str]] = {
    "": _activate,
    "on": _activate,
    "start": _activate,
    "enable": _activate,
    "off": _deactivate,
    "stop": _deactivate,
    "walkthrough on": _toggle(
        AgentService.set_walkthrough_allowed,
        True,
        "Play-Agent Sequence Walkthrough guidance enabled. "
        "The agent may consult the current sequence walkthrough for strategic guidance.",
    ),
    "walkthrough off": _toggle(
        AgentService.set_walkthrough_allowed,
        False,
        "Play-Agent Sequence Walkthrough guidance disabled. "
        "The agent will play strictly as a regular player without walkthrough or spoiler information.",
    ),
    "step on": _toggle(
        AgentService.set_step_by_step,
        True,
        "Play-Agent Step mode enabled. Use the Next Step button in the Play-Agent panel.",
    ),
    "step off": _toggle(
        AgentService.set_step_by_step,
        False,
        "Play-Agent Auto mode enabled. The agent will play until the adventure is won or lost.",
    ),
    "monkey on": _toggle(
        AgentService.set_monkey_mode,
        True,
        "Play-Agent Monkey Mode enabled. The agent will now deliberately try invalid, chaotic, "
        "or context-inappropriate actions to stress-test engine robustness.",
    ),
    "monkey off": _toggle(
        AgentService.set_monkey_mode,
        False,
        "Play-Agent Monkey Mode disabled. The agent will return to normal behavior.",
    ),
}


def resolve_playagent_message(manager: Any, cmd_args: str) -> tuple[str, bool]:
    """Applies the sub-command and returns (message, whether state changed)."""
    args_lower = cmd_args.lower()
    handler = _FIXED_HANDLERS.get(args_lower)
    if handler:
        return handler(manager), True

    if args_lower.startswith("personality"):
        return _set_personality(manager, cmd_args[len("personality") :].strip()), True

    personality = normalize_personality(args_lower)
    if personality and personality != "custom":
        return _activate(manager, personality), True

    return USAGE_TEXT, False


async def handle_playagent_command(manager: Any, cmd_args: str) -> AsyncGenerator[str, None]:
    """Runs a `/playagent` sub-command and streams the resulting system message."""
    msg, changed = resolve_playagent_message(manager, cmd_args)
    if changed:
        await manager.db.commit()
        await manager._save_chat_message("system", msg)
    payload = {"role": "system", "content": msg}
    yield f"event: system\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
