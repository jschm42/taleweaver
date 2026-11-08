"""``tw.story.skip_narration()``: no automatic Game Master narration in the next Pass 2.

Use case: a script starts an audio track (music, a recorded speech) that the narration and its
TTS must not talk over. The script records ``changeset.skip_narration``; every changeset applier
stores it in ``entity_states``; the next Pass 2 takes it (once) and produces no narration, while
script messages, system events, ``on_narration_done`` and the clock tick still happen.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.orm.attributes import flag_modified

SKIP_NARRATION_KEY = "__skip_narration__"


def store_skip_narration(entity_states: dict[str, Any], requested: bool) -> None:
    """Remember the request until the next narration (a later request changes nothing)."""
    if requested:
        entity_states[SKIP_NARRATION_KEY] = True


def take_skip_narration(state: Any) -> bool:
    """True (once) when a script asked to skip the coming narration."""
    if not (state.entity_states or {}).get(SKIP_NARRATION_KEY):
        return False
    entity_states = dict(state.entity_states)
    entity_states.pop(SKIP_NARRATION_KEY, None)
    state.entity_states = entity_states
    flag_modified(state, "entity_states")
    return True


async def no_narration() -> AsyncIterator[Any]:
    """Stands in for the narration stream when it is skipped (yields nothing)."""
    for _ in ():
        yield _
