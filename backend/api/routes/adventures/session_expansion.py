"""Session expansion: add regions that were built after a session started.

Sessions own a full copy of the world and a frozen adventure snapshot, so a region the author
generates later never reaches them. ``pending_sections`` lists the built regions of the
template that the session does not know yet; ``expand_session`` copies them in: their scenes,
every exit that touches one of them (the gateway exits on the old side included), the
characters and items placed there, and the quests, awards, chapters and scripts the snapshot
does not know yet. It only adds: no existing row, no ``entity_states`` entry and no avatar
field changes. That is safe because region generation is additive and never touches the
init script. Spec: docs/specs/world_sections.md (9.7).
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from backend.api.routes.adventures.session_adventure import (
    SESSION_MANIFEST_SNAPSHOT_KEY,
    extract_snapshot,
)
from backend.api.routes.adventures.session_assets import copy_data_asset_to_session
from backend.api.routes.adventures.session_cloning import clone_entity, clone_exit, clone_scene
from backend.engine.world.sections import player_sections
from backend.models.adventure_template import AdventureTemplate
from backend.models.session_state import SessionState
from backend.models.world_entity import WorldEntity, WorldExit, WorldScene


async def _rows(
    db: AsyncSession, model: Any, *, template_id: str | None = None, session_id: str | None = None
) -> list[Any]:
    query = select(model)
    if session_id:
        query = query.where(model.session_id == session_id)
    else:
        query = query.where(model.template_id == template_id, model.session_id.is_(None))
    return list((await db.execute(query)).scalars().all())


def _snapshot_section_ids(state: SessionState) -> set[str]:
    adventure = extract_snapshot(state).get("adventure") or {}
    return {s["id"] for s in player_sections(adventure.get("world_sections"))}


async def pending_sections(db: AsyncSession, state: SessionState) -> list[dict[str, Any]]:
    """Built regions of the template with scenes that this session does not have yet."""
    template = await db.get(AdventureTemplate, state.template_id) if state.template_id else None
    if template is None:
        return []
    known = _snapshot_section_ids(state)
    session_scenes = {s.id for s in await _rows(db, WorldScene, session_id=state.session_id)}
    template_scenes = await _rows(db, WorldScene, template_id=template.id)
    pending = []
    for section in player_sections(template.world_sections):
        new_scenes = [
            s
            for s in template_scenes
            if s.section_id == section["id"] and s.id not in session_scenes
        ]
        if section["id"] not in known and new_scenes:
            pending.append(section)
    return pending


def _held_by(entities: list[WorldEntity], holders: set[str]) -> set[str]:
    """Ids of entities placed in ``holders`` or carried by them (inventories, containers)."""
    chosen = {e.id for e in entities if e.current_scene_id in holders}
    for entity in entities:
        if entity.id in chosen:
            chosen.update(
                str(i.get("id"))
                for i in entity.inventory or []
                if isinstance(i, dict) and i.get("id")
            )
    return chosen


def _merge_by_id(current: Any, extra: Any, key: str = "id") -> list[dict[str, Any]]:
    current = list(current) if isinstance(current, list) else []
    known = {str(item.get(key)) for item in current if isinstance(item, dict)}
    added = [
        deepcopy(i) for i in extra or [] if isinstance(i, dict) and str(i.get(key)) not in known
    ]
    return [*current, *added]


def _extend_snapshot(
    state: SessionState,
    template: AdventureTemplate,
    sections: list[dict[str, Any]],
    scene_ids: set[str],
) -> None:
    snapshot = deepcopy(extract_snapshot(state))
    adventure = snapshot.setdefault("adventure", {})
    adventure["world_sections"] = _merge_by_id(adventure.get("world_sections"), sections)
    source = template.original_manifest if isinstance(template.original_manifest, dict) else {}
    manifest = snapshot.setdefault("original_manifest", {})
    manifest["scenes"] = _merge_by_id(
        manifest.get("scenes"), [s for s in source.get("scenes") or [] if s.get("id") in scene_ids]
    )
    manifest["sections"] = adventure["world_sections"]
    manifest["scripts"] = _merge_by_id(manifest.get("scripts"), source.get("scripts"))
    for key, id_key in (("quests", "id"), ("awards", "key"), ("sequences", "id")):
        merged = _merge_by_id(adventure.get(key), getattr(template, key, None), id_key)
        adventure[key] = merged
        manifest[key] = merged
    states = dict(state.entity_states or {})
    states[SESSION_MANIFEST_SNAPSHOT_KEY] = snapshot
    state.entity_states = states
    flag_modified(state, "entity_states")
    state.quests = _merge_by_id(
        state.quests, [{**q, "status": "open"} for q in template.quests or []]
    )


async def expand_session(db: AsyncSession, state: SessionState) -> list[dict[str, Any]]:
    """Copies every pending region into the session; returns the added regions (commits)."""
    sections = await pending_sections(db, state)
    if not sections:
        return []
    template = await db.get(AdventureTemplate, state.template_id)
    wanted = {s["id"] for s in sections}
    session_id, cache = state.session_id, {}
    session_scene_ids = {s.id for s in await _rows(db, WorldScene, session_id=session_id)}
    new_scenes = [
        s
        for s in await _rows(db, WorldScene, template_id=template.id)
        if s.section_id in wanted and s.id not in session_scene_ids
    ]
    scene_ids = {s.id for s in new_scenes}
    for scene in new_scenes:
        db.add(
            clone_scene(
                scene,
                session_id,
                copy_data_asset_to_session(session_id, "scenes", scene.image_url, cache),
            )
        )
    session_routes = {
        (e.from_scene_id, e.to_scene_id) for e in await _rows(db, WorldExit, session_id=session_id)
    }
    for exit_row in await _rows(db, WorldExit, template_id=template.id):
        touches = {exit_row.from_scene_id, exit_row.to_scene_id} & scene_ids
        if touches and (exit_row.from_scene_id, exit_row.to_scene_id) not in session_routes:
            db.add(clone_exit(exit_row, session_id))
    session_entities = {e.id for e in await _rows(db, WorldEntity, session_id=session_id)}
    entities = await _rows(db, WorldEntity, template_id=template.id)
    for entity in (e for e in entities if e.id in _held_by(entities, scene_ids) - session_entities):
        image = copy_data_asset_to_session(session_id, "entities", entity.image_url, cache)
        db.add(
            clone_entity(
                entity,
                session_id,
                image,
                is_in_inventory=entity.is_in_inventory,
                unlock_rule=entity.unlock_rule,
            )
        )
    _extend_snapshot(state, template, sections, scene_ids)
    await db.commit()
    return sections
