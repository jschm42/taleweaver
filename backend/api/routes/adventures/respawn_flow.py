"""Defeat handling: a fallen protagonist respawns when the adventure allows it, else game over.

Every place that catches a ``GameOverError`` calls :func:`end_or_respawn`. Only a
``ProtagonistDownError`` (HP fell to 0) can respawn; deliberate defeats (``tw.game.game_over()``,
the defeat condition, a GM ``game_over``) always end the session.

The respawn itself (:func:`respawn_protagonist`): HP set to the revival share, all status effects
cleared, the protagonist moved to the revival point (the last one reached, else the start scene),
the following companion brought along, then the revival scene's ``on_enter_scene`` scripts and
the global ``on_respawn`` scripts (penalties are up to the author). A sequence with
``respawn_allowed: false`` keeps 0 HP deadly. A normal turn writes its scene-change checkpoint
afterwards as usual.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy import and_, or_, select
from sqlalchemy.orm.attributes import flag_modified

from backend.api.routes.adventures.logic import AdventureLogic
from backend.api.routes.adventures.scene_scripts import run_global_scene_scripts
from backend.api.routes.adventures.section_triggers import run_section_change_scripts
from backend.engine.interaction.trigger_service import TriggerService
from backend.engine.rules.respawn import (
    read_respawn,
    respawn_settings,
    revival_hp,
    store_respawn,
)
from backend.engine.rules.rule_engine import GameEvent, GameOverError, ProtagonistDownError
from backend.engine.sessions.scene_entry import enter_scene
from backend.engine.sessions.start_scene import resolve_initial_scene_id
from backend.models.world_entity import WorldScene

logger = logging.getLogger(__name__)


async def end_or_respawn(manager: Any, error: GameOverError, game_event: Any = None) -> bool:
    """Handles a defeat raised during a turn. Returns True when the adventure ended.

    After a respawn the turn's draft narration is replaced, so Pass 2 tells of the knockout and
    the awakening instead of the protagonist's death.
    """
    if isinstance(error, ProtagonistDownError):
        note = await respawn_protagonist(manager)
        if note is not None:
            if isinstance(game_event, GameEvent):
                game_event.narrative_description = note
            return False
    await manager._finalize_session("game_over", str(error))
    if isinstance(game_event, GameEvent):
        game_event.game_over = True
        game_event.status_note = str(error)
    return True


def can_respawn(manager: Any) -> bool:
    """Whether a protagonist at 0 HP would respawn now.

    Needs the adventure's respawn mode, an active sequence that does not forbid it
    (``respawn_allowed: false``), and no respawn already running.
    """
    if getattr(manager, "_respawning", False):
        return False
    adventure = manager.adventure
    if not respawn_settings(getattr(adventure, "game_over_rules", None)).enabled:
        return False
    sequence = AdventureLogic.resolve_active_sequence(adventure, manager.state)
    return not (isinstance(sequence, dict) and sequence.get("respawn_allowed") is False)


async def respawn_protagonist(manager: Any) -> Optional[str]:
    """Revives the fallen protagonist at their revival point and returns the respawn note.

    None when the adventure does not respawn. A defeat inside the respawn itself (e.g. a deadly
    ``on_enter_scene`` script) is final.
    """
    if not can_respawn(manager):
        return None
    manager._respawning = True
    try:
        return await _revive(manager)
    finally:
        manager._respawning = False


async def _scene(manager: Any, scene_id: str) -> Optional[WorldScene]:
    state = manager.state
    res = await manager.db.execute(
        select(WorldScene)
        .where(
            WorldScene.id == scene_id,
            or_(
                WorldScene.session_id == state.session_id,
                and_(WorldScene.template_id == state.template_id, WorldScene.session_id.is_(None)),
            ),
        )
        .order_by(WorldScene.session_id.is_(None))
    )
    return res.scalars().first()


async def revival_scene(manager: Any) -> Optional[WorldScene]:
    """The scene the protagonist wakes up in: the last revival point reached, else the start."""
    point = read_respawn(manager.state.entity_states)["point"]
    scene = await _scene(manager, point) if point else None
    if scene is not None:
        return scene
    start_id = await resolve_initial_scene_id(manager.db, manager.state.template_id)
    return await _scene(manager, start_id)


async def _revive(manager: Any) -> Optional[str]:
    state, avatar = manager.state, manager.avatar
    settings = respawn_settings(manager.adventure.game_over_rules)
    scene = await revival_scene(manager)
    fallen_in = state.current_scene_id
    target_id = scene.id if scene is not None else fallen_in

    avatar.hp = revival_hp(avatar.max_hp, settings.hp_percent)
    avatar.status_effects = []
    flag_modified(avatar, "status_effects")
    record = read_respawn(state.entity_states)
    record["count"] += 1
    state.entity_states = store_respawn(state.entity_states, record)
    state.current_scene_id = target_id
    flag_modified(state, "entity_states")

    label = scene.label if scene is not None else target_id
    logger.info("[Respawn %s] %s revived in %s", state.session_id, avatar.name, target_id)
    note = f"{avatar.name} was knocked out and wakes up in {label} with {avatar.hp} HP."
    await manager._save_chat_message("system", note)
    for msg in await enter_scene(manager.db, state, fallen_in, adventure=manager.adventure):
        await manager._save_chat_message("system", msg)
    if scene is not None and target_id != fallen_in:
        await _enter(manager, scene)
        await run_section_change_scripts(manager, fallen_in, target_id)
    if not await _run_on_respawn(manager):
        return None
    return note


async def _run_on_respawn(manager: Any) -> bool:
    """Global ``on_respawn`` scripts; False when one of them ended the adventure."""
    runner = manager._get_script_runner()
    if not runner.scripts:
        return True
    try:
        context = await manager._build_script_context()
        changeset = runner.run_trigger("on_respawn", context)
        if changeset.has_changes:
            await manager._apply_script_changeset(changeset)
    except GameOverError as goe:
        logger.info("[Respawn %s] on_respawn ended the game: %s", manager.state.session_id, goe)
        await manager._finalize_session("game_over", str(goe))
        return False
    return True


async def _enter(manager: Any, scene: WorldScene) -> None:
    """The revival scene's own and global ``on_enter_scene`` scripts (messages are stored)."""
    if scene.on_enter_scene_script or scene.on_enter_scene_text:
        await TriggerService.execute_trigger(
            manager.db,
            manager.state,
            "on_enter_scene",
            scene.id,
            script_code=scene.on_enter_scene_script,
            narrative_text=scene.on_enter_scene_text,
        )
    await run_global_scene_scripts(manager, "on_enter_scene", scene.id)
