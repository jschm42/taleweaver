"""Lets a scene go on by itself after a dialog choice (``/continue_story``).

A choice handler can end its fixed lines with ``tw.story.direct(..., after="handler")``: the
next beat (e.g. a character bursting in) should happen right after, without the player typing
anything. The choice endpoint then reports ``continue_story`` and the client sends this command.
It runs a narration-only turn: no mechanics pass (the GM cannot move NPCs or unlock exits), no
interaction triggers, no clock tick and no player message in the chat. The narration uses the
pending directions, then their ``after=`` callbacks run.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from backend.engine.scripting.dialog import pending_dialog
from backend.engine.scripting.gm_directions import pending_after_narration

CONTINUE_STORY_COMMAND = "/continue_story"
CONTINUE_STORY_PROMPT = (
    "[CONTINUE] The player does nothing: the scene goes on by itself. Narrate only the next short "
    "moment of the current scene in one paragraph, following the author's directions. The player "
    "character neither acts nor speaks in it: describe only what the others do and what can be "
    "heard or seen. Do not repeat what was already narrated and do not change any state."
)


def continuation_due(entity_states: Any) -> bool:
    """A callback waits for a narration and no dialog waits for the player."""
    return bool(pending_after_narration(entity_states)) and not pending_dialog(entity_states)


async def continue_story(manager: Any, language: str | None) -> AsyncGenerator[str, None]:
    """Narration-only turn that runs the waiting ``after=`` callbacks; a no-op otherwise."""
    if not continuation_due(manager.state.entity_states):
        yield await manager._command_final_event()
        return
    manager.clock_tick_pending = False
    # Like an arrival narration: the GM only tells the scene, the player touched nothing.
    manager.arrival_narration = True
    try:
        async for chunk in manager._run_llm_cycle(
            CONTINUE_STORY_PROMPT, False, language=language, narration_only=True
        ):
            yield chunk
    finally:
        manager.arrival_narration = False
