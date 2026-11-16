"""What the play-agent may use outside debug mode.

The play-agent is a regular player feature. A few of its options only make sense for
testing, or would hand the player content they have not earned:

* **Walkthrough**: the agent only reads the current chapter's walkthrough when the player
  unlocked that chapter with XP (``/walkthrough reveal``). In debug mode it is always free.
* **Monkey mode** (robustness test) and the AGENTS.md issue log are debug tools.

The stored preferences in ``entity_states["__agent__"]`` stay untouched; these helpers
compute what is effectively in force, so unlocking a chapter later switches the walkthrough on
without the player having to toggle it again.
"""

from __future__ import annotations

from typing import Any

from backend.core.config import settings
from backend.engine.rules.walkthrough_unlocks import walkthrough_status

# Commands the agent never plays: they would switch itself off or spend the player's XP.
BLOCKED_AGENT_COMMANDS = ("/playagent", "/play-agent", "/walkthrough")


def is_debug_session(state: Any) -> bool:
    """Debug mode is on for the server or for this session."""
    return bool(settings.TALEWEAVER_DEBUG_ENABLED or getattr(state, "is_debug_enabled", False))


def walkthrough_unlocked(adventure: Any, state: Any) -> bool:
    """The agent may read the current chapter's walkthrough (unlocked with XP, or debug)."""
    if adventure is None or state is None:
        return False
    status = walkthrough_status(adventure, state, free=is_debug_session(state))
    return bool(status.get("current_revealed"))


def uses_walkthrough(adventure: Any, state: Any, agent_state: dict[str, Any]) -> bool:
    """Walkthrough guidance in force: wanted by the player and unlocked."""
    if not agent_state.get("allow_walkthrough", True):
        return False
    return walkthrough_unlocked(adventure, state)


def uses_monkey_mode(state: Any, agent_state: dict[str, Any]) -> bool:
    """Monkey mode only runs in debug mode."""
    return bool(agent_state.get("monkey_mode", False)) and is_debug_session(state)


def is_blocked_command(action: str) -> bool:
    """True for agent actions that must not be played (see ``BLOCKED_AGENT_COMMANDS``)."""
    head = (action or "").strip().split(None, 1)
    return bool(head) and head[0].lower() in BLOCKED_AGENT_COMMANDS


def access_fields(adventure: Any, state: Any) -> dict[str, Any]:
    """Sheet fields telling the control panel which options are available right now."""
    return {
        "agent_walkthrough_unlocked": walkthrough_unlocked(adventure, state),
        "agent_debug_tools": is_debug_session(state),
    }
