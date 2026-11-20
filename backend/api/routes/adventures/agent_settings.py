"""Play-agent session settings: activation defaults, partial updates and snapshots."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Optional

from pydantic import BaseModel, Field
from sqlalchemy.orm.attributes import flag_modified

from backend.api.routes.adventures.agent_access import access_fields, is_debug_session
from backend.api.routes.adventures.agent_dialogue import (
    DEFAULT_DIALOGUE_LEVEL,
    normalize_dialogue_level,
)
from backend.api.routes.adventures.agent_logic import MAX_STEP_DELAY_SECONDS, AgentService
from backend.models.session_state import SessionState

PERSONALITY_LABELS: dict[str, str] = {
    "casual": "Casual",
    "bureaucrat": "Bureaucrat",
    "powerplayer": "Powerplayer",
    "custom": "Custom",
}

PERSONALITY_ALIASES: dict[str, str] = {
    "casual": "casual",
    "bureaucrat": "bureaucrat",
    # Legacy German keys from earlier versions.
    "buerokrat": "bureaucrat",
    "bürokrat": "bureaucrat",
    "powerplayer": "powerplayer",
    "custom": "custom",
}


class AgentSettingsUpdate(BaseModel):
    active: Optional[bool] = None
    step_by_step: Optional[bool] = None
    personality: Optional[str] = None
    custom_personality: Optional[str] = None
    allow_walkthrough: Optional[bool] = None
    monkey_mode: Optional[bool] = None
    step_delay: Optional[int] = Field(default=None, ge=0, le=MAX_STEP_DELAY_SECONDS)
    wait_for_tts: Optional[bool] = None
    dialogue_level: Optional[str] = None
    # Player's instruction for the next steps; "" clears it.
    instruction: Optional[str] = Field(default=None, max_length=2000)


def normalize_personality(value: str | None) -> str | None:
    """Maps user input to a known personality key, or None when unknown."""
    return PERSONALITY_ALIASES.get((value or "").strip().lower())


def personality_label(value: str | None) -> str:
    key = normalize_personality(value) or "casual"
    return PERSONALITY_LABELS[key]


def activate_with_defaults(
    state: SessionState, llm_settings: dict[str, Any] | None, personality: str | None = None
) -> dict[str, Any]:
    """Activates the agent, seeding its options from the user's persisted defaults."""
    defaults = llm_settings or {}
    AgentService.set_agent_active(state, True)
    monkey_default = bool(defaults.get("play_agent_monkey_mode", False))
    AgentService.set_monkey_mode(state, monkey_default and is_debug_session(state))
    AgentService.set_walkthrough_allowed(
        state, bool(defaults.get("play_agent_allow_walkthrough", True))
    )
    AgentService.set_step_by_step(state, bool(defaults.get("play_agent_step_by_step", False)))
    _default_wait_for_tts(state)
    if personality:
        AgentService.set_personality(state, personality)
    else:
        AgentService.set_personality(
            state,
            defaults.get("play_agent_personality", "casual"),
            defaults.get("play_agent_custom_personality", ""),
        )
    return AgentService.get_agent_state(state)


def _default_wait_for_tts(state: SessionState) -> None:
    """Waiting for speech is on by default; a choice the player made in this session stays."""
    agent_state = AgentService.get_agent_state(state)
    if not agent_state.get("wait_for_tts_chosen"):
        agent_state["wait_for_tts"] = True
        flag_modified(state, "entity_states")


def _set_monkey_mode(state: SessionState, enabled: bool) -> None:
    # Monkey mode is a debug tool; regular players cannot switch it on.
    AgentService.set_monkey_mode(state, enabled and is_debug_session(state))


def _set_dialogue_level(state: SessionState, value: str) -> None:
    level = normalize_dialogue_level(value)
    if not level:
        raise ValueError(f"Unknown dialogue level: {value}")
    AgentService.set_dialogue_level(state, level)


def _set_instruction(state: SessionState, text: str) -> None:
    AgentService.set_instruction(state, text)


# Update field -> setter, applied when the field is present in the patch.
_SIMPLE_SETTERS: dict[str, Callable[[SessionState, Any], None]] = {
    "step_by_step": AgentService.set_step_by_step,
    "allow_walkthrough": AgentService.set_walkthrough_allowed,
    "monkey_mode": _set_monkey_mode,
    "step_delay": AgentService.set_step_delay,
    "wait_for_tts": AgentService.set_wait_for_tts,
    "dialogue_level": _set_dialogue_level,
    "instruction": _set_instruction,
}


def apply_settings_update(
    state: SessionState, update: AgentSettingsUpdate, llm_settings: dict[str, Any] | None
) -> None:
    """Applies a partial settings update; raises ValueError on an unknown personality or level."""
    if update.active is True and not AgentService.get_agent_state(state).get("active"):
        activate_with_defaults(state, llm_settings)
    if update.active is False:
        AgentService.set_agent_active(state, False)
    for field_name, setter in _SIMPLE_SETTERS.items():
        value = getattr(update, field_name)
        if value is not None:
            setter(state, value)
    if update.personality is None and update.custom_personality is None:
        return

    current = AgentService.get_agent_state(state).get("personality", "casual")
    personality = normalize_personality(update.personality or current)
    if not personality:
        raise ValueError(f"Unknown play-agent personality: {update.personality}")
    AgentService.set_personality(state, personality, update.custom_personality)


def build_agent_snapshot(state: SessionState, adventure: Any = None) -> dict[str, Any]:
    """Returns the agent fields in the same shape as the character sheet snapshot."""
    agent_state = AgentService.get_agent_state(state)
    return {
        **access_fields(adventure, state),
        "agent_active": bool(agent_state.get("active", False)),
        "agent_monkey_mode": bool(agent_state.get("monkey_mode", False)),
        "agent_allow_walkthrough": bool(agent_state.get("allow_walkthrough", True)),
        "agent_step_by_step": bool(agent_state.get("step_by_step", False)),
        "agent_personality": str(agent_state.get("personality", "casual")),
        "agent_custom_personality": str(agent_state.get("custom_personality", "")),
        "agent_step_delay": int(agent_state.get("step_delay", 0) or 0),
        "agent_wait_for_tts": bool(agent_state.get("wait_for_tts", True)),
        "agent_dialogue_level": str(agent_state.get("dialogue_level") or DEFAULT_DIALOGUE_LEVEL),
        "agent_instruction": str(agent_state.get("instruction") or ""),
    }
