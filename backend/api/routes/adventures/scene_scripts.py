"""Global scene scripts (``on_leave_scene`` / ``on_enter_scene``) for moves outside a GM turn.

A turn in which the Game Master moves the player runs the adventure's top-level and
active-sequence ``on_enter_scene`` scripts in the mechanics pass. Walking through an exit
(``/traverse_exit``) and ``/debug goto`` skip that pass, so they call these helpers next to the
scene's own inline trigger. Scripts without a target run for every scene.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.engine.rules.rule_engine import GameOverError

logger = logging.getLogger(__name__)


async def run_global_scene_scripts(manager: Any, trigger: str, scene_id: str) -> list[Any]:
    """Runs the matching global scripts and applies their changeset; returns its messages.

    A game over raised by a script ends the session and is returned as a message.
    """
    runner = manager._get_script_runner()
    if not runner.scripts:
        return []
    try:
        context = await manager._build_script_context()
        changeset = runner.run_trigger(trigger, context, target_id=scene_id)
        return list(await manager._apply_script_changeset(changeset))
    except GameOverError as goe:
        logger.info("[Scene Scripts] %s on %s ended the game: %s", trigger, scene_id, goe)
        await manager._finalize_session("game_over", str(goe))
        return [str(goe)]
