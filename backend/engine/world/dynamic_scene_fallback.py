"""Deterministic fallback room of a dynamic zone and the forward exits of a cluster node.

Used when no LLM is configured or the generation failed: the room still gets the author's
instructions (optional backfill) and always the author-placed zone entities.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from backend.engine.world.dynamic_instructions_helper import apply_instructions_backfill
from backend.engine.world.dynamic_required_entities import (
    merge_required_entities,
    required_blocks,
)
from backend.engine.world.dynamic_scene_schemas import (
    DynamicGeneratedChildExit,
    DynamicGeneratedScenePayload,
)


def _build_fallback_scene_payload(
    exit_label: str,
    zone: dict[str, Any],
) -> DynamicGeneratedScenePayload:
    """Deterministic atmospheric fallback when no LLM is configured or generation fails."""
    depth = int(zone.get("depth") or 1)
    max_depth = int(zone.get("max_depth") or 3)
    cul_de_sac = bool(zone.get("cul_de_sac_on_max_depth", True))
    clean_zone = re.sub(r"[_-]+", " ", str(zone.get("zone_id") or "uncharted")).title()
    passage_hint = exit_label.strip() or "a weathered passage"
    forward = (
        []
        if depth >= max_depth and cul_de_sac
        else [
            {
                "label": f"A deeper trail into {clean_zone}",
                "theme_hint": str(zone.get("theme") or clean_zone),
            }
        ]
    )
    return DynamicGeneratedScenePayload.model_validate(
        {
            "name": f"{clean_zone} (Depth {depth})",
            "description": (
                f"Beyond {passage_hint}, the air shifts as you enter an uncharted reach shaped by {zone['theme']}. "
                "Shadows cling to weathered surfaces, and every footstep echoes into the unknown."
            ),
            "visual_description": f"{zone['theme']}, moody atmospheric lighting, detailed environment",
            "music_prompt": f"Atmospheric ambient underscore for {zone['theme']}, subtle tension, seamless loop",
            "npcs": [],
            "objects": [],
            "forward_exits": forward,
        }
    )


def sync_forward_exits_with_blueprint(
    payload: DynamicGeneratedScenePayload,
    zone: dict[str, Any],
    existing_scene_hint: Optional[dict[str, Any]],
) -> None:
    """Align entry scene forward exits with planned outgoing edges on its cluster node."""
    if existing_scene_hint or int(zone.get("depth") or 1) >= int(zone.get("max_depth") or 3):
        return
    cluster_node = zone.get("cluster_node")
    if not isinstance(cluster_node, dict):
        return
    outgoing = list(cluster_node.get("outgoing_exits") or [])
    if not outgoing:
        return
    current = list(payload.forward_exits or [])
    synced: list[DynamicGeneratedChildExit] = []
    for idx, edge in enumerate(outgoing[:2]):
        cand = current[idx] if idx < len(current) else None
        label = str(getattr(cand, "label", "") or edge.get("label") or "Passage")[:100]
        hint = str(getattr(cand, "theme_hint", "") or edge.get("theme_hint") or "")[:300]
        synced.append(DynamicGeneratedChildExit(label=label, theme_hint=hint))
    payload.forward_exits = synced


def finalize_fallback_scene(
    exit_label: str,
    zone: dict[str, Any],
    existing_scene_hint: Optional[dict[str, Any]],
    cluster_context: Optional[list[dict[str, Any]]] = None,
    *,
    backfill: bool = False,
) -> DynamicGeneratedScenePayload:
    """Build fallback payload, clearing exits on pre-mapped scenes and optionally backfilling."""
    fallback = _build_fallback_scene_payload(exit_label, zone)
    if existing_scene_hint:
        fallback.forward_exits = []
        fallback.name = str(existing_scene_hint.get("label") or fallback.name)[:100]
    else:
        sync_forward_exits_with_blueprint(fallback, zone, existing_scene_hint)
    if backfill:
        apply_instructions_backfill(fallback, zone, {}, cluster_context)
    # Author-placed zone entities appear even when the generation failed.
    merge_required_entities(fallback, required_blocks(zone, cluster_context))
    return fallback
