"""Session persistence for Dynamic Cluster Blueprints and pre-built scene graphs."""

from __future__ import annotations

from collections import deque
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from backend.engine.blueprint.parser import has_blueprint_tags
from backend.engine.world.dynamic_cluster_blueprint import (
    build_fallback_cluster_blueprint,
    build_node_zone_context,
    generate_dynamic_cluster_blueprint,
    normalize_cluster_blueprint,
)
from backend.engine.world.dynamic_scene_schemas import (
    DynamicGeneratedScenePayload,
    build_dynamic_placeholder_scene_id,
    normalize_instructions_scope,
)
from backend.models.session_state import SessionState
from backend.models.world_entity import WorldExit, WorldScene

DYNAMIC_CLUSTER_BP_KEY = "__dynamic_clusters__"


def _cluster_key(zone_id: str) -> str:
    return str(zone_id or "").strip().lower()


def get_cluster_blueprint(state: SessionState, zone_id: str) -> Optional[dict[str, Any]]:
    """Return persisted cluster blueprint dictionary for ``zone_id`` if present."""
    key = _cluster_key(zone_id)
    entity_states = state.entity_states if isinstance(state.entity_states, dict) else {}
    clusters = entity_states.get(DYNAMIC_CLUSTER_BP_KEY)
    if not key or not isinstance(clusters, dict):
        return None
    entry = clusters.get(key)
    return dict(entry) if isinstance(entry, dict) else None


def _store_cluster_blueprint(
    state: SessionState,
    zone_id: str,
    cluster_bp: dict[str, Any],
) -> None:
    key = _cluster_key(zone_id)
    if not key:
        return
    entity_states = dict(state.entity_states or {})
    clusters = dict(entity_states.get(DYNAMIC_CLUSTER_BP_KEY) or {})
    clusters[key] = cluster_bp
    entity_states[DYNAMIC_CLUSTER_BP_KEY] = clusters
    state.entity_states = entity_states
    flag_modified(state, "entity_states")


async def ensure_cluster_blueprint(
    *,
    state: SessionState,
    target_id: str,
    zone: dict[str, Any],
    adventure_title: str,
    adventure_setting: str,
    adventure_tone: str,
    origin_scene_name: str,
    origin_scene_description: str,
    exit_label: str,
    user: Any,
    adventure_id: Optional[str] = None,
    game_id: Optional[str] = None,
    language: str = "English",
    generation_config: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Ensure a cluster blueprint exists on ``state`` and attach entry ``cluster_node``."""
    existing = get_cluster_blueprint(state, zone["zone_id"])
    if existing is not None:
        zone["cluster_node"] = build_node_zone_context(existing, "D1_1")
        return existing

    raw_bp = await generate_dynamic_cluster_blueprint(
        adventure_title=adventure_title,
        adventure_setting=adventure_setting,
        adventure_tone=adventure_tone,
        origin_scene_name=origin_scene_name,
        origin_scene_description=origin_scene_description,
        exit_label=exit_label,
        zone=zone,
        user=user,
        adventure_id=adventure_id,
        game_id=game_id,
        language=language,
        generation_config=generation_config,
    )
    cluster_bp = normalize_cluster_blueprint(raw_bp, zone, entry_scene_id=target_id)
    _store_cluster_blueprint(state, zone["zone_id"], cluster_bp)
    zone["cluster_node"] = build_node_zone_context(cluster_bp, "D1_1")
    return cluster_bp


def _build_child_base_zone(zone: dict[str, Any]) -> dict[str, Any]:
    child_scope = normalize_instructions_scope(zone.get("instructions_scope"))
    child_consumed = bool(zone.get("instructions_consumed")) or (
        child_scope in {"once", "first_scene"}
        and not has_blueprint_tags(str(zone.get("instructions") or ""))
    )
    base = {
        **zone,
        "root_theme": zone.get("root_theme") or zone["theme"],
        "instructions_consumed": child_consumed,
    }
    base.pop("cluster_node", None)
    base.pop("materialized", None)
    return base


def _persist_fallback_forward_exits(
    *,
    db: AsyncSession,
    state: SessionState,
    target_id: str,
    zone: dict[str, Any],
    payload: DynamicGeneratedScenePayload,
) -> list[dict[str, str]]:
    spawned: list[dict[str, str]] = []
    child_base = _build_child_base_zone(zone)
    for idx, child_exit in enumerate(payload.forward_exits[:2], start=1):
        child_target = build_dynamic_placeholder_scene_id(
            zone["zone_id"],
            int(zone["depth"]) + 1,
            idx,
            suffix=target_id[-4:],
        )
        child_zone = {
            **child_base,
            "depth": int(zone["depth"]) + 1,
            "theme": child_exit.theme_hint or zone["theme"],
        }
        db.add(
            WorldExit(
                template_id=None,
                session_id=state.session_id,
                from_scene_id=target_id,
                to_scene_id=child_target,
                label=child_exit.label[:100],
                exit_type="bidirectional",
                is_locked=False,
                is_revealed=False,
                dynamic_zone=child_zone,
            )
        )
        spawned.append(
            {
                "to_scene_id": child_target,
                "label": child_exit.label[:100],
                "theme_hint": child_exit.theme_hint,
            }
        )
    return spawned


def _collect_reachable_subgraph(
    cluster_bp: dict[str, Any],
    active_entry_edges: list[dict[str, Any]],
) -> tuple[set[str], list[dict[str, Any]]]:
    """Return reachable ``node_id`` set and directed edges starting from ``active_entry_edges``."""
    reachable: set[str] = {"D1_1"}
    active_edges: list[dict[str, Any]] = list(active_entry_edges)
    queue: deque[str] = deque()
    for edge in active_entry_edges:
        dst = str(edge.get("to_node_id") or "")
        if dst and dst not in reachable:
            reachable.add(dst)
            queue.append(dst)

    all_edges = list(cluster_bp.get("edges") or [])
    while queue:
        cur = queue.popleft()
        for edge in all_edges:
            if edge.get("from_node_id") != cur:
                continue
            active_edges.append(edge)
            dst = str(edge.get("to_node_id") or "")
            if dst and dst not in reachable:
                reachable.add(dst)
                queue.append(dst)
    return reachable, active_edges


def _sync_entry_edges_from_payload(
    entry_edges: list[dict[str, Any]],
    forward_exits: list[Any],
) -> list[dict[str, Any]]:
    active: list[dict[str, Any]] = []
    for edge, child_exit in zip(entry_edges, forward_exits, strict=False):
        if str(getattr(child_exit, "label", "") or "").strip():
            edge["exit_label"] = str(child_exit.label)[:100]
        if str(getattr(child_exit, "theme_hint", "") or "").strip():
            edge["theme_hint"] = str(child_exit.theme_hint)[:300]
        active.append(edge)
    return active


async def persist_cluster_graph_from_entry(
    *,
    db: AsyncSession,
    state: SessionState,
    target_id: str,
    zone: dict[str, Any],
    payload: DynamicGeneratedScenePayload,
) -> list[dict[str, str]]:
    """Persist unmaterialized cluster ``WorldScene`` nodes and ``WorldExit`` graph."""
    if int(zone.get("depth") or 1) >= int(zone.get("max_depth") or 3) or not payload.forward_exits:
        return []

    cluster_bp = get_cluster_blueprint(state, zone["zone_id"])
    if cluster_bp is None:
        fb = build_fallback_cluster_blueprint(payload.name or zone["theme"], zone)
        cluster_bp = normalize_cluster_blueprint(fb, zone, entry_scene_id=target_id)

    entry_edges = [
        edge for edge in (cluster_bp.get("edges") or []) if edge.get("from_scene_id") == target_id
    ]
    if not entry_edges:
        return _persist_fallback_forward_exits(
            db=db,
            state=state,
            target_id=target_id,
            zone=zone,
            payload=payload,
        )

    active_entry = _sync_entry_edges_from_payload(entry_edges, list(payload.forward_exits))
    _store_cluster_blueprint(state, zone["zone_id"], cluster_bp)
    reachable_ids, active_edges = _collect_reachable_subgraph(cluster_bp, active_entry)

    existing_scene_ids = set(
        (
            await db.execute(select(WorldScene.id).where(WorldScene.session_id == state.session_id))
        ).scalars()
    )
    existing_exit_pairs = {
        (str(row.from_scene_id), str(row.to_scene_id))
        for row in (
            await db.execute(select(WorldExit).where(WorldExit.session_id == state.session_id))
        ).scalars()
    }

    child_base = _build_child_base_zone(zone)
    node_zone_by_id: dict[str, dict[str, Any]] = {}
    for node in cluster_bp.get("nodes") or []:
        node_id = str(node.get("node_id") or "")
        scene_id = str(node.get("scene_id") or "")
        if node_id not in reachable_ids or int(node.get("depth") or 1) < 2:
            continue
        node_zone = {
            **child_base,
            "depth": int(node["depth"]),
            "theme": str(node.get("theme_hint") or zone["theme"]),
            "materialized": False,
            "cluster_node": build_node_zone_context(cluster_bp, node_id),
        }
        node_zone_by_id[node_id] = node_zone
        if scene_id and scene_id not in existing_scene_ids:
            existing_scene_ids.add(scene_id)
            db.add(
                WorldScene(
                    id=scene_id,
                    template_id=None,
                    session_id=state.session_id,
                    label=str(node.get("label") or zone["theme"])[:100],
                    description=str(node.get("story_beat") or zone["theme"])[:2000],
                    dynamic_zone=node_zone,
                )
            )

    for edge in active_edges:
        src_sid = str(edge.get("from_scene_id") or "")
        dst_sid = str(edge.get("to_scene_id") or "")
        pair = (src_sid, dst_sid)
        if not src_sid or not dst_sid or pair in existing_exit_pairs:
            continue
        existing_exit_pairs.add(pair)
        target_zone = node_zone_by_id.get(str(edge.get("to_node_id") or ""))
        db.add(
            WorldExit(
                template_id=None,
                session_id=state.session_id,
                from_scene_id=src_sid,
                to_scene_id=dst_sid,
                label=str(edge.get("exit_label") or "Passage")[:100],
                exit_type="bidirectional",
                is_locked=False,
                is_revealed=False,
                dynamic_zone=target_zone,
            )
        )

    return [
        {
            "to_scene_id": str(edge["to_scene_id"]),
            "label": str(edge["exit_label"])[:100],
            "theme_hint": str(edge.get("theme_hint") or ""),
        }
        for edge in active_entry
    ]
