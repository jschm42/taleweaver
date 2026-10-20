"""Play-agent session settings: activation defaults, partial updates and snapshots."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel

from backend.api.routes.adventures.agent_logic import AgentService
from backend.models.session_state import SessionState

PERSONALITY_LABELS: dict[str, str] = {
    "casual": "Casual",
    "buerokrat": "Bürokrat",
    "powerplayer": "Powerplayer",
    "custom": "Custom",
}

PERSONALITY_ALIASES: dict[str, str] = {
    "casual": "casual",
    "buerokrat": "buerokrat",
    "bürokrat": "buerokrat",
    "bureaucrat": "buerokrat",
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
    AgentService.set_monkey_mode(state, bool(defaults.get("play_agent_monkey_mode", False)))
    AgentService.set_walkthrough_allowed(
        state, bool(defaults.get("play_agent_allow_walkthrough", True))
    )
    AgentService.set_step_by_step(state, bool(defaults.get("play_agent_step_by_step", False)))
    if personality:
        AgentService.set_personality(state, personality)
    else:
        AgentService.set_personality(
            state,
            defaults.get("play_agent_personality", "casual"),
            defaults.get("play_agent_custom_personality", ""),
        )
    return AgentService.get_agent_state(state)


def apply_settings_update(
    state: SessionState, update: AgentSettingsUpdate, llm_settings: dict[str, Any] | None
) -> None:
    """Applies a partial settings update; raises ValueError on an unknown personality."""
    if update.active is True and not AgentService.get_agent_state(state).get("active"):
        activate_with_defaults(state, llm_settings)
    if update.active is False:
        AgentService.set_agent_active(state, False)
    if update.step_by_step is not None:
        AgentService.set_step_by_step(state, update.step_by_step)
    if update.allow_walkthrough is not None:
        AgentService.set_walkthrough_allowed(state, update.allow_walkthrough)
    if update.monkey_mode is not None:
        AgentService.set_monkey_mode(state, update.monkey_mode)
    if update.personality is None and update.custom_personality is None:
        return

    current = AgentService.get_agent_state(state).get("personality", "casual")
    personality = normalize_personality(update.personality or current)
    if not personality:
        raise ValueError(f"Unknown personality: {update.personality}")
    AgentService.set_personality(state, personality, update.custom_personality)


def build_agent_snapshot(state: SessionState) -> dict[str, Any]:
    """Returns the agent fields in the same shape as the character sheet snapshot."""
    agent_state = AgentService.get_agent_state(state)
    return {
        "agent_active": bool(agent_state.get("active", False)),
        "agent_monkey_mode": bool(agent_state.get("monkey_mode", False)),
        "agent_allow_walkthrough": bool(agent_state.get("allow_walkthrough", True)),
        "agent_step_by_step": bool(agent_state.get("step_by_step", False)),
        "agent_personality": str(agent_state.get("personality", "casual")),
        "agent_custom_personality": str(agent_state.get("custom_personality", "")),
    }
