"""Player instructions for the play-agent ("look for the key in the library").

The player tells the agent what to do next, from the instruction field of the control panel
(``PATCH /agent/settings`` with ``instruction``) or with ``/instruct <text>`` in the chat
(alias ``/playagent do <text>``). The instruction is stored in
``entity_states["__agent__"]["instruction"]`` and shown to the agent with top priority in every
decision until the agent reports it done (``AgentDecision.instruction_done``) or the player
clears it (``/instruct clear``).
"""

from __future__ import annotations

from typing import Any

INSTRUCT_COMMAND = "/instruct"
MAX_INSTRUCTION_LENGTH = 500
CLEAR_WORDS = ("clear", "none", "stop", "reset", "-")

NO_INSTRUCTION_TEXT = "None. Decide on your own what to do next."


def normalize_instruction(text: str | None) -> str:
    """Single-spaced text, capped at ``MAX_INSTRUCTION_LENGTH``; clear words give ""."""
    cleaned = " ".join(str(text or "").split())[:MAX_INSTRUCTION_LENGTH]
    return "" if cleaned.lower() in CLEAR_WORDS else cleaned


def current_instruction(agent_state: dict[str, Any]) -> str:
    return str(agent_state.get("instruction") or "")


def instruction_prompt(agent_state: dict[str, Any]) -> str:
    """The PLAYER'S INSTRUCTION block of the agent prompt."""
    instruction = current_instruction(agent_state)
    if not instruction:
        return NO_INSTRUCTION_TEXT
    return (
        f'"{instruction}"\n'
        "The player who controls you asked for this. It has priority over your own plans and "
        "the walkthrough: work towards it step by step, staying in character. Set "
        "`instruction_done` to true in the decision whose action completes it, or when it "
        "clearly cannot be done here (then explain why in `thoughts`)."
    )


def instruction_message(instruction: str, agent_active: bool) -> str:
    """Chat feedback after the player set or cleared an instruction."""
    if not instruction:
        return "Play-Agent instruction cleared. The agent decides on its own again."
    suffix = "" if agent_active else " Start the Play-Agent (Auto-Play) to let it act on it."
    return f'Play-Agent instruction: "{instruction}"{suffix}'
