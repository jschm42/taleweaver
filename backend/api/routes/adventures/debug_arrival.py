"""Stream side of ``/debug goto``: the scene's arrival hooks and the scene transition event."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import and_, func, or_, select

from backend.api.routes.adventures.audio_snapshot import build_audio_snapshot
from backend.api.routes.adventures.scene_scripts import run_global_scene_scripts
from backend.engine.interaction.trigger_service import TriggerService
from backend.models.world_entity import WorldScene


async def _load_scene(manager: Any, scene_id: str) -> WorldScene | None:
    state = manager.state
    res = await manager.db.execute(
        select(WorldScene)
        .where(
            or_(
                WorldScene.session_id == state.session_id,
                and_(WorldScene.template_id == state.template_id, WorldScene.session_id.is_(None)),
            ),
            func.lower(WorldScene.id) == scene_id.lower(),
        )
        .order_by(WorldScene.session_id.is_(None))
    )
    return res.scalars().first()


async def stream_debug_arrival(manager: Any, scene_id: str) -> AsyncGenerator[str, None]:
    """Fires the scene's and the global ``on_enter_scene`` scripts, without the arrival narration."""
    scene = await _load_scene(manager, scene_id)
    if scene is None:
        return
    await manager.db.commit()

    transition = {
        "scene_id": scene.id,
        "scene_label": scene.label,
        "audio": await build_audio_snapshot(manager.db, manager.state, None, manager.user),
    }
    yield f"event: scene_transition\ndata: {json.dumps(transition)}\n\n"

    if scene.on_enter_scene_script or scene.on_enter_scene_text:
        messages = await TriggerService.execute_trigger(
            manager.db,
            manager.state,
            "on_enter_scene",
            scene.id,
            script_code=scene.on_enter_scene_script,
            narrative_text=scene.on_enter_scene_text,
        )
        for message in messages:
            yield _sse(message)
    for message in await run_global_scene_scripts(manager, "on_enter_scene", scene.id):
        yield _sse(message)


def _sse(message: Any) -> str:
    """One script message as a stream event with its own role (speech stays speech)."""
    role = str(getattr(message, "role", "system"))
    return f"event: {role}\ndata: {json.dumps({'role': role, 'content': str(message)})}\n\n"
