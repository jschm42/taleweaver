"""Gateway scenes of a new region: the existing scenes it connects to (always in the prompt).

Per linked, built neighbour the scenes the author picked come first (the link's
``gateway_scene_ids``), then the scenes at its border (an exit already leads out of that
region), then its fast travel points, then the rest. A region without a built
neighbour gets fallback candidates (start scene, fast travel points, scenes without a
region), so it can be connected even when the author left the scene list out of the prompt.
Spec: docs/specs/region_builder.md (5.2, 5.2a).
"""

from __future__ import annotations

from typing import Any

from backend.engine.world.section_context import ContextBlock, ContextSource
from backend.engine.world.section_context_world import scene_line
from backend.engine.world.sections import is_stub

GATEWAY_SCENES = 8


def built_neighbours(
    section: dict[str, Any], sections: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """The section's planned links that lead to a built region."""
    built = {s["id"] for s in sections if not is_stub(s)}
    return [link for link in section["planned_links"] if link["to_section_id"] in built]


def _border_scene_ids(src: ContextSource, region_id: str) -> set[str]:
    inside = {s.id for s in src.rows.scenes if s.section_id == region_id}
    border = set()
    for ex in src.rows.exits:
        ends = {ex.from_scene_id, ex.to_scene_id}
        if len(ends & inside) == 1:
            border |= ends & inside
    return border


def _neighbour_scenes(src: ContextSource, link: dict[str, Any]) -> list[Any]:
    """The author's picks first (in their order), then border scenes, fast travel points, rest."""
    region_id = link["to_section_id"]
    picked = [str(i) for i in link.get("gateway_scene_ids") or []]
    border = _border_scene_ids(src, region_id)
    scenes = [s for s in src.rows.scenes if s.section_id == region_id]

    def rank(scene: Any) -> tuple[int, int, str]:
        if scene.id in picked:
            return (0, picked.index(scene.id), scene.id)
        if scene.id in border:
            return (1, 0, scene.id)
        return (2 if scene.is_fast_travel_point else 3, 0, scene.id)

    return sorted(scenes, key=rank)[:GATEWAY_SCENES]


def _fallback_scenes(src: ContextSource) -> list[Any]:
    def rank(scene: Any) -> tuple[int, str]:
        if scene.id == src.start_scene_id:
            return (0, scene.id)
        if scene.is_fast_travel_point:
            return (1, scene.id)
        return (2 if not scene.section_id else 3, scene.id)

    return sorted(src.rows.scenes, key=rank)[:GATEWAY_SCENES]


def _neighbour_lines(src: ContextSource, link: dict[str, Any]) -> list[str]:
    minutes = link.get("travel_minutes")
    travel = f", travel_minutes {minutes}" if minutes else ""
    scenes = _neighbour_scenes(src, link)
    return [f"Region {link['to_section_id']}{travel}:", *(scene_line(s) for s in scenes)]


def gateway_block(src: ContextSource, neighbours: list[dict[str, Any]]) -> ContextBlock:
    """The GATEWAY SCENES block; never switched off."""
    if neighbours:
        lines = ["GATEWAY SCENES (connect the new region to some of these, one per region):"]
        for link in neighbours:
            lines.extend(_neighbour_lines(src, link))
        return ContextBlock("gateway", "\n".join(lines), len(lines) - 1 - len(neighbours), True)
    scenes = _fallback_scenes(src)
    if not scenes:
        return ContextBlock(
            "gateway", "GATEWAY SCENES: none; the adventure has no scenes.", 0, True
        )
    lines = [
        "GATEWAY SCENES (the region has no built neighbour yet; connect it to at least one of "
        "these existing scenes):",
        *(scene_line(s) for s in scenes),
    ]
    return ContextBlock("gateway", "\n".join(lines), len(scenes), True)
