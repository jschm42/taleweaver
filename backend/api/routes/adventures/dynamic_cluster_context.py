"""Cluster context loader and container inventory linker for procedural Dynamic Scenes."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.engine.world.dynamic_scene_schemas import DynamicGeneratedObject
from backend.models.session_state import SessionState
from backend.models.world_entity import WorldEntity, WorldScene


def normalize_match_token(raw: object) -> str:
    """Normalize an entity ID or display name into an uppercase matching key."""
    return re.sub(r"[^A-Z0-9]+", "_", str(raw or "").strip().upper()).strip("_")


def _extract_container_parent_map(entities: list[WorldEntity]) -> dict[str, str]:
    child_to_container: dict[str, str] = {}
    for ent in entities:
        if ent.entity_type != "OBJECT" or ent.item_type != "CONTAINER":
            continue
        for item in ent.inventory or []:
            child_id = item.get("id") if isinstance(item, dict) else item
            if child_id:
                child_to_container[str(child_id)] = ent.name
    return child_to_container


def _format_entity_summary(
    entities: list[WorldEntity],
    child_to_container: dict[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    npcs: list[dict[str, Any]] = []
    objects: list[dict[str, Any]] = []
    for ent in entities:
        if ent.entity_type == "NPC":
            npcs.append(
                {
                    "id": ent.id,
                    "name": ent.name,
                    "npc_type": str(ent.npc_type or "HUMANOID"),
                    "role": str(ent.goal or ""),
                    "description": str(ent.description or "")[:180],
                }
            )
            continue
        meta = ent.metadata_json if isinstance(ent.metadata_json, dict) else {}
        objects.append(
            {
                "id": ent.id,
                "name": ent.name,
                "item_type": str(ent.item_type or "STANDARD"),
                "damage_dice": str(meta.get("damage_dice") or ""),
                "in_container": child_to_container.get(ent.id, ""),
            }
        )
    return npcs, objects


def _matching_cluster_entries(
    state: SessionState,
    zone_id: str,
    exclude_scene_id: str,
) -> list[tuple[str, dict[str, Any]]]:
    target_zone = str(zone_id or "").strip().lower()
    entity_states = state.entity_states if isinstance(state.entity_states, dict) else {}
    zones_meta = entity_states.get("__dynamic_zones__")
    if not target_zone or not isinstance(zones_meta, dict):
        return []

    excluded = str(exclude_scene_id or "").strip().lower()
    matching: list[tuple[str, dict[str, Any]]] = []
    for scene_id, meta in zones_meta.items():
        if not isinstance(meta, dict):
            continue
        meta_zone = str(meta.get("zone_id") or "").strip().lower()
        if meta_zone != target_zone or (excluded and str(scene_id).strip().lower() == excluded):
            continue
        matching.append((str(scene_id), meta))
    return matching


def _group_entities_by_scene(entity_rows: list[WorldEntity]) -> dict[str, list[WorldEntity]]:
    grouped: dict[str, list[WorldEntity]] = {}
    for ent in entity_rows:
        if ent.current_scene_id:
            grouped.setdefault(ent.current_scene_id, []).append(ent)
    return grouped


async def collect_cluster_context(
    db: AsyncSession,
    state: SessionState,
    zone_id: str,
    exclude_scene_id: str = "",
) -> list[dict[str, Any]]:
    """Load existing scenes, NPCs, and items belonging to the same dynamic exit cluster."""
    matching = _matching_cluster_entries(state, zone_id, exclude_scene_id)
    if not matching:
        return []

    recent_entries = matching[-10:]
    scene_ids = [sid for sid, _ in recent_entries]
    meta_by_id = dict(recent_entries)

    scene_rows = (
        (
            await db.execute(
                select(WorldScene).where(
                    WorldScene.session_id == state.session_id,
                    WorldScene.id.in_(scene_ids),
                )
            )
        )
        .scalars()
        .all()
    )
    entity_rows = (
        (
            await db.execute(
                select(WorldEntity).where(
                    WorldEntity.session_id == state.session_id,
                    WorldEntity.current_scene_id.in_(scene_ids),
                )
            )
        )
        .scalars()
        .all()
    )

    entities_by_scene = _group_entities_by_scene(list(entity_rows))
    scene_by_id = {sc.id: sc for sc in scene_rows}
    cluster: list[dict[str, Any]] = []
    for sid in scene_ids:
        scene = scene_by_id.get(sid)
        if not scene:
            continue
        scene_entities = entities_by_scene.get(sid, [])
        child_to_container = _extract_container_parent_map(scene_entities)
        npcs, objects = _format_entity_summary(scene_entities, child_to_container)
        cluster.append(
            {
                "scene_id": scene.id,
                "name": scene.label,
                "depth": int((meta_by_id.get(sid) or {}).get("depth") or 1),
                "description": str(scene.description or "")[:240],
                "npcs": npcs,
                "objects": objects,
            }
        )
    return cluster


def link_generated_container_inventories(
    objects: list[DynamicGeneratedObject],
    raw_id_to_entity: dict[str, WorldEntity],
) -> None:
    """Resolve generated container inventory references onto persisted WorldEntity IDs."""
    for obj in objects:
        if obj.item_type != "CONTAINER" or not obj.inventory:
            continue
        container_entity = raw_id_to_entity.get(normalize_match_token(obj.id))
        if container_entity is None:
            continue
        resolved_ids: list[str] = []
        for child_token in obj.inventory:
            child_entity = raw_id_to_entity.get(normalize_match_token(child_token))
            if child_entity is None or child_entity.id == container_entity.id:
                continue
            if child_entity.id not in resolved_ids:
                resolved_ids.append(child_entity.id)
        container_entity.inventory = resolved_ids
