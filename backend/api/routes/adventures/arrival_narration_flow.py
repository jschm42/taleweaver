"""The arrival narration after the protagonist reached a new scene through exits.

Shared by the exit traversal (``/traverse_exit``) and fast travel (``/fast_travel``): the
client clears the old scene (``scene_transition`` event, with the new scene's audio), then a
full LLM cycle narrates the place with ``manager.arrival_narration`` set, so the Game Master
only describes it and does not move the player on.
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import Any

from backend.api.routes.adventures.audio_snapshot import build_audio_snapshot
from backend.api.routes.adventures.dynamic_scene_media import drain_pending_dynamic_visuals


def _user_safe_error(exc: Exception) -> str:
    # Lazy import: gameplay_logic imports the turn managers that call this module.
    from backend.api.routes.adventures.gameplay_logic import (
        _friendly_llm_error_message,
        _friendly_llm_unexpected_error_message,
    )

    return _friendly_llm_error_message(exc) or _friendly_llm_unexpected_error_message()


async def narrate_arrival(
    interactions: Any, scene: Any, narration_prompt: str, language: str | None
) -> AsyncGenerator[str, None]:
    """Streams the scene transition event and the arrival narration of ``scene``."""
    manager = interactions.manager
    transition = {
        "scene_id": scene.id,
        "scene_label": scene.label,
        "audio": await build_audio_snapshot(
            interactions.db, interactions.state, None, interactions.user
        ),
    }
    yield f"event: scene_transition\ndata: {json.dumps(transition)}\n\n"
    status = {"content": f"Entering {scene.label or scene.id}..."}
    yield f"event: status\ndata: {json.dumps(status)}\n\n"

    manager.arrival_narration = True
    try:
        async for chunk in interactions._run_llm_cycle(narration_prompt, False, language=language):
            yield chunk
    except Exception as exc:
        yield f"event: error\ndata: {json.dumps({'detail': _user_safe_error(exc)})}\n\n"
    finally:
        manager.arrival_narration = False
        pending_visuals = getattr(manager, "pending_dynamic_visuals", None)
        if pending_visuals:
            await drain_pending_dynamic_visuals(
                interactions.db, interactions.state, pending_visuals
            )
            await interactions.db.commit()
