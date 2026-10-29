"""Resolves the scene a fresh session of an adventure template starts in.

Shared by session start (API layer) and the adventure exporter, which writes the result into
the manifest so an imported copy starts in the same scene.
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.adventure_template import AdventureTemplate
from backend.models.world_entity import WorldExit, WorldScene

_FALLBACK_SCENE_ID = "START"
_EXPLICIT_START_KEYS = ("start_scene_id", "scene_id", "current_scene_id")


def _manifest_start_scene(manifest: Any, scene_set: set[str]) -> Optional[str]:
    """Explicit start scene from the manifest, else the first manifest scene that exists."""
    if not isinstance(manifest, dict):
        return None
    explicit = next((manifest.get(key) for key in _EXPLICIT_START_KEYS if manifest.get(key)), None)
    if isinstance(explicit, str) and explicit.strip() in scene_set:
        return explicit.strip()
    scenes = manifest.get("scenes")
    if not isinstance(scenes, list):
        return None
    ids = (entry.get("id") for entry in scenes if isinstance(entry, dict))
    return next(
        (sid.strip() for sid in ids if isinstance(sid, str) and sid.strip() in scene_set), None
    )


async def _entry_scene(db: AsyncSession, template_id: str, scene_set: set[str]) -> str:
    """First scene (sorted) without incoming exits, else the first scene id overall."""
    exit_res = await db.execute(
        select(WorldExit.from_scene_id, WorldExit.to_scene_id).where(
            WorldExit.template_id == template_id,
            WorldExit.session_id.is_(None),
        )
    )
    reachable = {
        to_scene_id
        for from_scene_id, to_scene_id in exit_res.all()
        if from_scene_id in scene_set and to_scene_id in scene_set
    }
    entry_scenes = sorted(scene_set - reachable)
    return entry_scenes[0] if entry_scenes else sorted(scene_set)[0]


async def resolve_initial_scene_id(db: AsyncSession, template_id: Optional[str]) -> str:
    """Resolve a stable initial scene for a fresh session.

    Priority:
    1) Explicit scene from template manifest (`start_scene_id`, `scene_id`, `current_scene_id`).
    2) First scene in template manifest order.
    3) Scene with id "START" when present.
    4) Entry scene(s) with no incoming exits (template baseline only).
    5) Lexicographically first available scene id.
    6) Fallback "START" when no scenes exist.
    """
    if not template_id:
        return _FALLBACK_SCENE_ID

    scene_res = await db.execute(
        select(WorldScene.id).where(
            WorldScene.template_id == template_id,
            WorldScene.session_id.is_(None),
        )
    )
    scene_set = {sid for sid in scene_res.scalars().all() if isinstance(sid, str) and sid}
    if not scene_set:
        return _FALLBACK_SCENE_ID

    adv_res = await db.execute(
        select(AdventureTemplate.original_manifest).where(AdventureTemplate.id == template_id)
    )
    from_manifest = _manifest_start_scene(adv_res.scalar_one_or_none(), scene_set)
    if from_manifest:
        return from_manifest
    if _FALLBACK_SCENE_ID in scene_set:
        return _FALLBACK_SCENE_ID
    return await _entry_scene(db, template_id, scene_set)
