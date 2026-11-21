"""The world map image: a drawn map of the adventure's regions as background of the world map.

The prompt places every region by its map position (compass directions) and asks for a map
without lettering, because image models garble text; the region names are drawn by the
client on top. Stored in ``AdventureTemplate.world_map_image_url``.
Spec: docs/specs/world_sections.md (phase 4).
"""

from __future__ import annotations

from typing import Any

from backend.engine.world.sections import normalize_sections

_MAX_REGIONS = 16
_DESCRIPTION_LENGTH = 120


def _direction(x: float, y: float) -> str:
    """Compass words for a map position in percent (0/0 = north-west)."""
    north_south = "north" if y < 34 else ("south" if y > 66 else "")
    west_east = "west" if x < 34 else ("east" if x > 66 else "")
    if north_south and west_east:
        return f"{north_south}-{west_east}"
    return north_south or west_east or "centre"


def world_map_prompt(adventure: Any) -> str:
    """The image prompt for the adventure's world map."""
    regions = normalize_sections(getattr(adventure, "world_sections", None))[:_MAX_REGIONS]
    lines = [
        f"{r['label']} in the {_direction(r['map_x'], r['map_y'])}: "
        f"{(r['description'] or r['brief'])[:_DESCRIPTION_LENGTH]}"
        for r in regions
    ]
    setting = str(getattr(adventure, "plot", "") or getattr(adventure, "teaser", "") or "")[:300]
    return (
        "A hand-drawn world map seen from straight above, wide landscape format, for a text "
        f"adventure. Setting: {setting} "
        f"Regions: {'; '.join(lines)}. "
        "Show each region's landscape (coast, forests, mountains, towns) at its place and roads "
        "between neighbouring regions. No text, no letters, no labels, no legend, no compass "
        "rose with letters."
    )
