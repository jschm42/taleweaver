"""Resolves scene background music (``WorldScene.music_url``) for sessions and template lists."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.routes.adventures.asset_url_healing import resolve_existing_data_asset_url
from backend.engine.sessions.start_scene import resolve_initial_scene_id
from backend.models.session_state import SessionState
from backend.models.world_entity import WorldScene

SCRIPT_VARS_KEY = "__script_vars__"


def script_music_key(scene_id: str) -> str:
    """Script var under which `tw.scene.music = ...` stores the scene's music override."""
    return f"__scene_attr_{scene_id}_music_url"


def _script_music_override(state: SessionState, scene_id: str) -> tuple[bool, Optional[str]]:
    """(override set, url) from the session's script vars; an empty url means silence."""
    script_vars = (state.entity_states or {}).get(SCRIPT_VARS_KEY) or {}
    key = script_music_key(scene_id)
    if not isinstance(script_vars, dict) or key not in script_vars:
        return False, None
    return True, str(script_vars.get(key) or "").strip() or None


async def resolve_scene_music(
    db: AsyncSession, state: SessionState, scene_id: Optional[str]
) -> Optional[str]:
    """Music URL of a scene: script override, then the session's scene copy, then the template."""
    if not scene_id:
        return None
    has_override, override_url = _script_music_override(state, scene_id)
    if has_override:
        return resolve_existing_data_asset_url(override_url) if override_url else None

    res = await db.execute(
        select(WorldScene.music_url)
        .where(
            WorldScene.id == scene_id,
            or_(
                WorldScene.session_id == state.session_id,
                and_(
                    WorldScene.template_id == state.template_id,
                    WorldScene.session_id.is_(None),
                ),
            ),
        )
        .order_by(WorldScene.session_id.is_(None))
    )
    return resolve_existing_data_asset_url(res.scalars().first())


async def entry_scene_music_urls(db: AsyncSession, template_ids: list[str]) -> dict[str, str]:
    """Maps template id -> music URL of its start scene, for templates whose start scene has one.

    One query loads every template scene with music; the start scene is only resolved for
    templates that have any, so the template list stays cheap for adventures without music.
    """
    if not template_ids:
        return {}
    res = await db.execute(
        select(WorldScene.template_id, WorldScene.id, WorldScene.music_url).where(
            WorldScene.template_id.in_(template_ids),
            WorldScene.session_id.is_(None),
            WorldScene.music_url.is_not(None),
            WorldScene.music_url != "",
        )
    )
    music_by_template: dict[str, dict[str, str]] = {}
    for template_id, scene_id, music_url in res.all():
        music_by_template.setdefault(template_id, {})[scene_id] = music_url

    result: dict[str, str] = {}
    for template_id, scene_music in music_by_template.items():
        start_scene_id = await resolve_initial_scene_id(db, template_id)
        url = resolve_existing_data_asset_url(scene_music.get(start_scene_id))
        if url:
            result[template_id] = url
    return result
