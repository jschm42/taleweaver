"""What the play-agent should work towards: the player's quest log and the clock.

The agent sees the same as the player in the quest log and the header: the current chapter
(title and description), the quests with their status, and, when the adventure has a clock,
the in-game time and how long one action takes. Without this block the agent only knew the
current room and could play past the adventure's deadline without ever pursuing its goals.
Walkthrough steps stay separate (``agent_access``: only for chapters unlocked with XP).
"""

from __future__ import annotations

from typing import Any

from backend.api.routes.adventures.logic import AdventureLogic
from backend.engine.rules.game_clock import clock_view, default_minutes_per_tick, read_clock
from backend.engine.sessions.memory_manager import MemoryManager
from backend.engine.world.sections import player_sections

_MAX_TEXT = 300


def _short(value: Any) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= _MAX_TEXT else text[: _MAX_TEXT - 1] + "…"


def _chapter_line(adventure: Any, state: Any) -> str:
    sequence = AdventureLogic.resolve_active_sequence(adventure, state)
    if not sequence:
        return ""
    title = sequence.get("title") or sequence.get("name") or sequence.get("id")
    description = _short(sequence.get("description"))
    return f"CURRENT CHAPTER: {title}" + (f" - {description}" if description else "")


def _quest_lines(state: Any, adventure: Any = None) -> list[str]:
    regions = {
        s["id"]: s["label"] for s in player_sections(getattr(adventure, "world_sections", None))
    }
    lines = []
    for quest in state.quests or []:
        if not isinstance(quest, dict):
            continue
        status = "DONE" if quest.get("status") == "completed" else "OPEN"
        text = _short(quest.get("description") or quest.get("goal"))
        region = regions.get(str(quest.get("section_id") or ""))
        where = f" (continues in {region})" if region and status == "OPEN" else ""
        lines.append(
            f"- [{status}] {quest.get('title') or quest.get('id')}{where}"
            + (f": {text}" if text else "")
        )
    return lines


def _clock_lines(adventure: Any, state: Any) -> list[str]:
    if not getattr(adventure, "clock_enabled", False):
        return []
    view = clock_view(state, adventure)
    now = MemoryManager.format_game_time(
        view["minutes"], time_system=view["time_system"], time_config=view["time_config"]
    )
    per_action = read_clock(state.entity_states or {}).get("minutes_per_tick")
    if per_action is None:
        per_action = default_minutes_per_tick(adventure)
    return [
        f"CURRENT TIME: {now}",
        f"Every action you take costs about {per_action} in-game minutes. The story may have "
        "deadlines: do not waste actions on chatter or on places you already searched.",
    ]


def format_objectives(adventure: Any, state: Any) -> str:
    """The OBJECTIVES block of the agent prompt."""
    lines = [line for line in (_chapter_line(adventure, state),) if line]
    quests = _quest_lines(state, adventure)
    if quests:
        lines.append("QUESTS (from your quest log):")
        lines.extend(quests)
    lines.extend(_clock_lines(adventure, state))
    if not lines:
        return "No chapter goal or quests are known yet. Explore and talk to characters."
    lines.append(
        "Always work towards the CURRENT CHAPTER goal first, then the OPEN quests. Pick the "
        "action that gets you closest to them."
    )
    return "\n".join(lines)
