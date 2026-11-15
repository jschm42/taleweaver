"""Cluster Blueprint schema, LLM generator, fallback builder, and prompt formatter."""

from __future__ import annotations

import logging
import re
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from backend.api.routes.adventures.turn_context_helpers import resolve_model_settings
from backend.core.api_keys import has_api_key
from backend.core.llm_router import GameMasterLLM
from backend.engine.world.dynamic_scene_schemas import (
    build_dynamic_placeholder_scene_id,
    normalize_generation_model,
)

logger = logging.getLogger(__name__)

_LOCAL_LLM_PROVIDERS = {"ollama", "lmstudio"}
_NODE_COORDS_RX = re.compile(r"^D(\d+)_(\d+)$", re.IGNORECASE)
_DYNAMIC_MODEL_CATEGORY_MAP: dict[str, tuple[str, str, str]] = {
    "mechanics": ("small_model_provider", "small_model", "small"),
    "narration": ("complex_model_provider", "complex_model", "complex"),
    "world_builder": ("generator_model_provider", "generator_model", "generator"),
}
NodeRole = Literal["entry", "obstacle", "branch", "climax"]


def resolve_dynamic_llm_model(
    user: Any,
    zone: Optional[dict[str, Any]] = None,
    generation_config: Optional[dict[str, Any]] = None,
) -> tuple[str, str, str]:
    """Resolve (provider, model, category) for dynamic cluster and scene generation."""
    llm_settings = dict(getattr(user, "llm_settings", None) or {})
    resolved = resolve_model_settings(llm_settings)
    raw_choice = (zone or {}).get("generation_model") or (generation_config or {}).get(
        "generation_model"
    )
    tier = normalize_generation_model(raw_choice) or "mechanics"
    prov_key, model_key, category = _DYNAMIC_MODEL_CATEGORY_MAP[tier]
    return str(resolved[prov_key]), str(resolved[model_key]), category


class DynamicClusterNodeSpec(BaseModel):
    """Single room node in a pre-planned dynamic cluster mini-adventure."""

    node_id: str = Field(min_length=1, max_length=24)
    depth: int = Field(default=1, ge=1, le=6)
    role: NodeRole = "entry"
    label: str = Field(min_length=1, max_length=100)
    theme_hint: str = Field(default="", max_length=300)
    story_beat: str = Field(default="", max_length=600)
    npc_hint: str = Field(default="", max_length=300)
    object_hint: str = Field(default="", max_length=300)


class DynamicClusterEdgeSpec(BaseModel):
    """Directed passage between two nodes in a dynamic cluster graph."""

    from_node_id: str = Field(min_length=1, max_length=24)
    to_node_id: str = Field(min_length=1, max_length=24)
    exit_label: str = Field(min_length=1, max_length=100)
    theme_hint: str = Field(default="", max_length=300)


class DynamicClusterBlueprint(BaseModel):
    """Cohesive mini-adventure blueprint and topology for a dynamic cluster."""

    cluster_title: str = Field(min_length=1, max_length=120)
    story_arc: str = Field(min_length=1, max_length=1000)
    climax_goal: str = Field(min_length=1, max_length=500)
    key_item_concept: str = Field(default="", max_length=300)
    nodes: list[DynamicClusterNodeSpec] = Field(default_factory=list, max_length=8)
    edges: list[DynamicClusterEdgeSpec] = Field(default_factory=list, max_length=12)


def build_canonical_cluster_skeleton(
    max_depth: int,
    cul_de_sac: bool = True,
) -> tuple[list[tuple[str, int, NodeRole]], list[tuple[str, str, int]]]:
    """Return canonical ``(nodes, edges)`` skeleton matching ``max_depth``."""
    clamped = max(1, min(6, int(max_depth or 3)))
    if clamped == 1:
        return [("D1_1", 1, "climax" if cul_de_sac else "entry")], []
    if clamped == 2:
        final_role: NodeRole = "climax" if cul_de_sac else "obstacle"
        return [("D1_1", 1, "entry"), ("D2_1", 2, final_role)], [("D1_1", "D2_1", 1)]

    depth3_role: NodeRole = "climax" if (clamped == 3 and cul_de_sac) else "obstacle"
    nodes: list[tuple[str, int, NodeRole]] = [
        ("D1_1", 1, "entry"),
        ("D2_1", 2, "obstacle"),
        ("D2_2", 2, "branch"),
        ("D3_1", 3, depth3_role),
    ]
    edges: list[tuple[str, str, int]] = [
        ("D1_1", "D2_1", 1),
        ("D1_1", "D2_2", 2),
        ("D2_1", "D3_1", 1),
        ("D2_2", "D3_1", 1),
    ]
    for depth in range(4, clamped + 1):
        role: NodeRole = "climax" if (depth == clamped and cul_de_sac) else "obstacle"
        node_id = f"D{depth}_1"
        nodes.append((node_id, depth, role))
        edges.append((f"D{depth - 1}_1", node_id, 1))
    return nodes, edges


def _fallback_node_details(
    node_id: str,
    depth: int,
    role: NodeRole,
    clean_zone: str,
    theme: str,
    exit_label: str,
) -> DynamicClusterNodeSpec:
    if role == "entry":
        return DynamicClusterNodeSpec(
            node_id=node_id,
            depth=depth,
            role=role,
            label=f"{clean_zone} Threshold"[:100],
            theme_hint=theme[:300],
            story_beat=f"Step beyond {exit_label or 'the passage'} into {theme} and discover clues pointing deeper inside.",
            npc_hint="A wary lookout or traveler who hints at the danger ahead.",
            object_hint="Clues or light supplies near the threshold.",
        )
    if role == "branch":
        return DynamicClusterNodeSpec(
            node_id=node_id,
            depth=depth,
            role=role,
            label=f"{clean_zone} Side Chamber"[:100],
            theme_hint=f"{theme} — secluded alcove or workshop"[:300],
            story_beat=f"A quieter side route in {theme} hiding preparation gear or lore about the inner sanctum.",
            npc_hint="Optional neutral wanderer or creature.",
            object_hint="Helpful consumable, weapon, or lore note.",
        )
    if role == "climax":
        return DynamicClusterNodeSpec(
            node_id=node_id,
            depth=depth,
            role=role,
            label=f"{clean_zone} Inner Sanctum"[:100],
            theme_hint=f"{theme} — heart of the zone"[:300],
            story_beat=f"Confront the main guardian or mystery at the heart of {theme} and claim the final reward.",
            npc_hint="The primary guardian or boss defending the sanctum.",
            object_hint="Sealed reward container and centerpiece treasure.",
        )
    suffix = f" ({depth})" if depth > 2 else ""
    return DynamicClusterNodeSpec(
        node_id=node_id,
        depth=depth,
        role=role,
        label=f"{clean_zone} Guarded Watch{suffix}"[:100],
        theme_hint=f"{theme} — defended choke point"[:300],
        story_beat=f"Overcome hostile resistance blocking the main route through {theme}.",
        npc_hint="Hostile sentry carrying a key item for deeper access.",
        object_hint="Zone key item or tactical supply.",
    )


def build_fallback_cluster_blueprint(
    exit_label: str,
    zone: dict[str, Any],
) -> DynamicClusterBlueprint:
    """Build a deterministic mini-adventure blueprint when no LLM runs."""
    theme = str(zone.get("root_theme") or zone.get("theme") or "uncharted reach").strip()
    clean_zone = re.sub(r"[_-]+", " ", str(zone.get("zone_id") or "uncharted")).title()
    max_depth = int(zone.get("max_depth") or 3)
    cul_de_sac = bool(zone.get("cul_de_sac_on_max_depth", True))
    skel_nodes, skel_edges = build_canonical_cluster_skeleton(max_depth, cul_de_sac)

    nodes = [
        _fallback_node_details(node_id, depth, role, clean_zone, theme, exit_label)
        for node_id, depth, role in skel_nodes
    ]
    edge_labels = {
        ("D1_1", "D2_1"): f"Main Passage into {clean_zone}",
        ("D1_1", "D2_2"): f"Narrow Side Gallery of {clean_zone}",
        ("D2_1", "D3_1"): f"Descend toward {clean_zone} Sanctum",
        ("D2_2", "D3_1"): f"Hidden Conduit to {clean_zone} Sanctum",
    }
    edges = [
        DynamicClusterEdgeSpec(
            from_node_id=src,
            to_node_id=dst,
            exit_label=edge_labels.get((src, dst), f"Passage to {dst}")[:100],
            theme_hint=theme[:300],
        )
        for src, dst, _ in skel_edges
    ]
    return DynamicClusterBlueprint(
        cluster_title=f"Mystery of {clean_zone}"[:120],
        story_arc=f"Venture past {exit_label or 'the threshold'} into {theme}, uncover what threatens it, and reach its heart.",
        climax_goal=f"Overcome the guardian of {clean_zone} and unlock its final cache.",
        key_item_concept=f"An emblem or passkey tied to {clean_zone}",
        nodes=nodes,
        edges=edges,
    )


def _node_scene_id(node_id: str, depth: int, zone_id: str, entry_scene_id: str) -> str:
    if node_id == "D1_1":
        return entry_scene_id
    match = _NODE_COORDS_RX.match(node_id)
    branch_idx = int(match.group(2)) if match else 1
    return build_dynamic_placeholder_scene_id(
        zone_id,
        depth,
        branch_idx,
        suffix=entry_scene_id[-4:],
    )


def _match_node_spec(
    raw_nodes: list[DynamicClusterNodeSpec],
    used_indices: set[int],
    node_id: str,
    depth: int,
    role: NodeRole,
    fb_node: DynamicClusterNodeSpec,
) -> DynamicClusterNodeSpec:
    target = node_id.upper()
    for idx, candidate in enumerate(raw_nodes):
        if idx not in used_indices and candidate.node_id.strip().upper() == target:
            used_indices.add(idx)
            return candidate
    for idx, candidate in enumerate(raw_nodes):
        if idx not in used_indices and candidate.depth == depth and candidate.role == role:
            used_indices.add(idx)
            return candidate
    for idx, candidate in enumerate(raw_nodes):
        if idx not in used_indices:
            used_indices.add(idx)
            return candidate
    return fb_node


def _match_edge_spec(
    raw_edges: list[DynamicClusterEdgeSpec],
    used_edges: set[int],
    src: str,
    dst: str,
    fb_edge: DynamicClusterEdgeSpec,
) -> DynamicClusterEdgeSpec:
    pair = (src.upper(), dst.upper())
    for idx, edge in enumerate(raw_edges):
        cand_pair = (edge.from_node_id.strip().upper(), edge.to_node_id.strip().upper())
        if idx not in used_edges and cand_pair == pair:
            used_edges.add(idx)
            return edge
    for idx, edge in enumerate(raw_edges):
        if idx not in used_edges:
            used_edges.add(idx)
            return edge
    return fb_edge


def normalize_cluster_blueprint(
    blueprint: DynamicClusterBlueprint,
    zone: dict[str, Any],
    *,
    entry_scene_id: str,
) -> dict[str, Any]:
    """Snap LLM blueprint output onto the canonical skeleton and assign DB scene IDs."""
    max_depth = int(zone.get("max_depth") or 3)
    cul_de_sac = bool(zone.get("cul_de_sac_on_max_depth", True))
    zone_id = str(zone.get("zone_id") or "dynamic_zone")
    skel_nodes, skel_edges = build_canonical_cluster_skeleton(max_depth, cul_de_sac)
    fallback = build_fallback_cluster_blueprint(str(zone.get("theme") or "Passage"), zone)

    fb_nodes = {n.node_id: n for n in fallback.nodes}
    fb_edges = {(e.from_node_id, e.to_node_id): e for e in fallback.edges}
    raw_nodes = list(blueprint.nodes or [])
    raw_edges = list(blueprint.edges or [])
    used_node_idx: set[int] = set()
    used_edge_idx: set[int] = set()

    norm_nodes: list[dict[str, Any]] = []
    scene_by_node: dict[str, str] = {}
    for node_id, depth, role in skel_nodes:
        spec = _match_node_spec(raw_nodes, used_node_idx, node_id, depth, role, fb_nodes[node_id])
        scene_id = _node_scene_id(node_id, depth, zone_id, entry_scene_id)
        scene_by_node[node_id] = scene_id
        norm_nodes.append(
            {
                "node_id": node_id,
                "scene_id": scene_id,
                "depth": depth,
                "role": role,
                "label": (spec.label or fb_nodes[node_id].label)[:100],
                "theme_hint": (spec.theme_hint or fb_nodes[node_id].theme_hint)[:300],
                "story_beat": (spec.story_beat or fb_nodes[node_id].story_beat)[:600],
                "npc_hint": (spec.npc_hint or fb_nodes[node_id].npc_hint)[:300],
                "object_hint": (spec.object_hint or fb_nodes[node_id].object_hint)[:300],
            }
        )

    norm_edges: list[dict[str, Any]] = []
    for src, dst, _ in skel_edges:
        edge = _match_edge_spec(raw_edges, used_edge_idx, src, dst, fb_edges[(src, dst)])
        norm_edges.append(
            {
                "from_node_id": src,
                "to_node_id": dst,
                "from_scene_id": scene_by_node[src],
                "to_scene_id": scene_by_node[dst],
                "exit_label": (edge.exit_label or fb_edges[(src, dst)].exit_label)[:100],
                "theme_hint": (edge.theme_hint or fb_edges[(src, dst)].theme_hint)[:300],
            }
        )

    return {
        "cluster_title": (blueprint.cluster_title or fallback.cluster_title)[:120],
        "story_arc": (blueprint.story_arc or fallback.story_arc)[:1000],
        "climax_goal": (blueprint.climax_goal or fallback.climax_goal)[:500],
        "key_item_concept": (blueprint.key_item_concept or fallback.key_item_concept)[:300],
        "nodes": norm_nodes,
        "edges": norm_edges,
    }


def build_node_zone_context(cluster_bp: dict[str, Any], node_id: str) -> dict[str, Any]:
    """Extract per-node blueprint context to embed in ``zone['cluster_node']``."""
    nodes = list(cluster_bp.get("nodes") or [])
    node = next((n for n in nodes if n.get("node_id") == node_id), None)
    if node is None:
        return {}
    return {
        "node_id": node["node_id"],
        "scene_id": node["scene_id"],
        "role": node["role"],
        "label": node["label"],
        "theme_hint": node["theme_hint"],
        "story_beat": node["story_beat"],
        "npc_hint": node["npc_hint"],
        "object_hint": node["object_hint"],
        "cluster_title": cluster_bp.get("cluster_title") or "",
        "story_arc": cluster_bp.get("story_arc") or "",
        "climax_goal": cluster_bp.get("climax_goal") or "",
        "key_item_concept": cluster_bp.get("key_item_concept") or "",
        "outgoing_exits": [
            {
                "to_node_id": edge["to_node_id"],
                "to_scene_id": edge["to_scene_id"],
                "label": edge["exit_label"],
                "theme_hint": edge["theme_hint"],
            }
            for edge in cluster_bp.get("edges") or []
            if edge.get("from_node_id") == node_id
        ],
    }


def build_cluster_blueprint_prompt_section(zone: dict[str, Any]) -> str:
    """Format the current node's mini-adventure beat for scene materialization prompts."""
    node = zone.get("cluster_node")
    if not isinstance(node, dict) or not zone.get("cluster_consistency", True):
        return ""
    lines = [
        f"CLUSTER MINI-ADVENTURE BLUEPRINT ({node.get('cluster_title') or 'Uncharted Cluster'}):",
        f"- Mini-Story Arc: {node.get('story_arc') or ''}",
        f"- Climax Goal: {node.get('climax_goal') or ''}",
    ]
    if node.get("key_item_concept"):
        lines.append(f"- Key Item Concept: {node['key_item_concept']}")
    lines.append(
        f"- Current Room ({node.get('node_id')}, role={node.get('role')}): {node.get('label')}"
    )
    if node.get("story_beat"):
        lines.append(f"- Room Story Beat: {node['story_beat']}")
    if node.get("npc_hint"):
        lines.append(f"- Planned NPCs Hint: {node['npc_hint']}")
    if node.get("object_hint"):
        lines.append(f"- Planned Objects Hint: {node['object_hint']}")
    outgoing = list(node.get("outgoing_exits") or [])
    if outgoing:
        ex_text = "; ".join(f"{ex.get('label')} -> {ex.get('to_node_id')}" for ex in outgoing)
        lines.append(f"- Planned Outgoing Exits: {ex_text}")
    return "\n".join(lines)


async def generate_dynamic_cluster_blueprint(
    *,
    adventure_title: str,
    adventure_setting: str,
    adventure_tone: str,
    origin_scene_name: str,
    origin_scene_description: str,
    exit_label: str,
    zone: dict[str, Any],
    user: Any,
    adventure_id: Optional[str] = None,
    game_id: Optional[str] = None,
    language: str = "English",
    generation_config: Optional[dict[str, Any]] = None,
) -> DynamicClusterBlueprint:
    """Generate a cohesive mini-adventure blueprint for a dynamic cluster via LLM or fallback."""
    provider, model, model_category = resolve_dynamic_llm_model(user, zone, generation_config)

    has_creds = provider in _LOCAL_LLM_PROVIDERS or has_api_key(
        getattr(user, "encrypted_api_keys", None) or {},
        provider,
    )
    if not has_creds:
        return build_fallback_cluster_blueprint(exit_label, zone)

    max_depth = int(zone.get("max_depth") or 3)
    cul_de_sac = bool(zone.get("cul_de_sac_on_max_depth", True))
    skel_nodes, skel_edges = build_canonical_cluster_skeleton(max_depth, cul_de_sac)
    nodes_spec = ", ".join(f"{nid} (depth={d}, role={r})" for nid, d, r in skel_nodes)
    edges_spec = ", ".join(f"{src}->{dst}" for src, dst, _ in skel_edges) or "none"

    system_prompt = (
        "You are TaleWeaver's mini-adventure cluster architect.\n"
        f"Design a cohesive, self-contained side-cluster mini-story written strictly in {language}.\n"
        "- NEVER reference or alter main-quest core story items or major main-plot NPCs.\n"
        f"- Populate EXACTLY these skeleton nodes using the exact node_id values: {nodes_spec}.\n"
        f"- Populate EXACTLY these edges (from_node_id -> to_node_id): {edges_spec}.\n"
        "- Ensure the story_arc connects entry clues, obstacles/branches, a key_item_concept, and the climax_goal."
    )
    instructions = str(zone.get("instructions") or "").strip()[:1200]
    user_prompt = (
        f"Adventure Title: {adventure_title}\n"
        f"Adventure Tone: {adventure_tone or 'Atmospheric'}\n"
        f"Setting Context: {adventure_setting[:450]}\n"
        f"Origin Scene: {origin_scene_name} — {origin_scene_description[:240]}\n"
        f"Entry Exit Label: {exit_label}\n"
        f"Zone Theme: {zone.get('root_theme') or zone.get('theme')}\n"
        f"Danger Level: {zone.get('danger_level') or 'medium'}\n"
        f"Max NPCs Per Scene: {zone.get('max_npcs', 2)}"
        + (f"\nAuthor Instructions: {instructions}" if instructions else "")
    )
    try:
        llm = GameMasterLLM(user, provider=provider, model_category=model_category)
        return await llm.aexecute_complex_task(
            system_prompt,
            user_prompt,
            DynamicClusterBlueprint,
            model,
            adventure_id=adventure_id,
            game_id=game_id,
            operation="dynamic_cluster.blueprint",
            phase="expansion",
        )
    except Exception as exc:
        logger.warning("Cluster blueprint generation failed (%s); using fallback.", exc)
        return build_fallback_cluster_blueprint(exit_label, zone)
