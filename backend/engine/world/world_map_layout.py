"""The world map as a grid of image tiles (``AdventureTemplate.world_map_layout``).

::

    {"cols": 3, "rows": 2, "tiles": [{"col": 0, "row": 0, "url": "/data/..."}, ...]}

Every tile is a 16:9 image; the grid grows by one column to the right or one row downwards
(at most ``MAX_GRID`` each way), and a tile may be missing (drawn empty). Region positions
(``map_x`` / ``map_y``) stay percent of the whole map: when the grid grows or shrinks, they are
rescaled so every region stays over the same spot of the drawn map.
Spec: docs/specs/world_sections.md (phase 4).
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Optional

from backend.engine.world.sections import normalize_sections

MAX_GRID = 6
_TILE_REGIONS = 12
_DESCRIPTION_LENGTH = 120


def compose_map_prompt(prompt: str, tone: str = "") -> str:
    """The final image prompt: the author's (or default) prompt plus the adventure's tone."""
    text = prompt.strip()
    return f"{text} Mood and atmosphere: {tone.strip()}" if tone.strip() else text


def empty_layout() -> dict[str, Any]:
    return {"cols": 1, "rows": 1, "tiles": []}


def _index(raw: Any, limit: int) -> Optional[int]:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if 0 <= value < limit else None


def normalize_layout(raw: Any) -> dict[str, Any]:
    """The canonical layout: grid size 1-6 each way, one tile per cell inside the grid."""
    if not isinstance(raw, dict):
        return empty_layout()
    cols = _index(raw.get("cols"), MAX_GRID + 1) or 1
    rows = _index(raw.get("rows"), MAX_GRID + 1) or 1
    tiles: dict[tuple[int, int], dict[str, Any]] = {}
    for tile in raw.get("tiles") or []:
        if not isinstance(tile, dict) or not str(tile.get("url") or "").strip():
            continue
        col, row = _index(tile.get("col"), cols), _index(tile.get("row"), rows)
        if col is None or row is None:
            continue
        tiles[(col, row)] = {"col": col, "row": row, "url": str(tile["url"]).strip()}
    return {"cols": cols, "rows": rows, "tiles": [tiles[key] for key in sorted(tiles)]}


def layout_or_none(layout: dict[str, Any]) -> Optional[dict[str, Any]]:
    """None for a layout without any image (so the column stays empty)."""
    return layout if layout["tiles"] else None


def rescale_sections(
    sections: list[dict[str, Any]], before: tuple[int, int], after: tuple[int, int]
) -> list[dict[str, Any]]:
    """Keeps every region over the same spot of the drawn map when the grid size changes."""
    (cols_a, rows_a), (cols_b, rows_b) = before, after
    rescaled = deepcopy(sections)
    for section in rescaled:
        section["map_x"] = round(min(100.0, section["map_x"] * cols_a / cols_b), 1)
        section["map_y"] = round(min(100.0, section["map_y"] * rows_a / rows_b), 1)
    return rescaled


def place_tile(layout: dict[str, Any], col: int, row: int, url: str) -> dict[str, Any]:
    """Puts an image into a cell; a cell right of or below the grid grows it by one."""
    current = normalize_layout(layout)
    if col > current["cols"] or row > current["rows"] or col < 0 or row < 0:
        raise ValueError("A new tile must be next to the map (right of it or below it).")
    cols, rows = max(current["cols"], col + 1), max(current["rows"], row + 1)
    if cols > MAX_GRID or rows > MAX_GRID:
        raise ValueError(f"The world map has at most {MAX_GRID} x {MAX_GRID} tiles.")
    tiles = [t for t in current["tiles"] if (t["col"], t["row"]) != (col, row)]
    return normalize_layout(
        {"cols": cols, "rows": rows, "tiles": [*tiles, {"col": col, "row": row, "url": url}]}
    )


def remove_tile(layout: dict[str, Any], col: int, row: int) -> dict[str, Any]:
    """Removes a tile; empty last columns and rows are dropped (the grid shrinks)."""
    current = normalize_layout(layout)
    tiles = [t for t in current["tiles"] if (t["col"], t["row"]) != (col, row)]
    cols = max([t["col"] + 1 for t in tiles], default=1)
    rows = max([t["row"] + 1 for t in tiles], default=1)
    return normalize_layout({"cols": cols, "rows": rows, "tiles": tiles})


def imported_map_layout(raw: Any, asset_mapping: dict[str, str]) -> Optional[dict[str, Any]]:
    """The layout of an imported bundle: tiles whose file came with it, at their new path."""
    layout = normalize_layout(raw)
    tiles = [
        {**tile, "url": asset_mapping[tile["url"]]}
        for tile in layout["tiles"]
        if tile["url"] in asset_mapping
    ]
    return layout_or_none({**layout, "tiles": tiles})


def grid_size(layout: dict[str, Any]) -> tuple[int, int]:
    current = normalize_layout(layout)
    return current["cols"], current["rows"]


def _direction(x: float, y: float) -> str:
    north_south = "north" if y < 34 else ("south" if y > 66 else "")
    west_east = "west" if x < 34 else ("east" if x > 66 else "")
    if north_south and west_east:
        return f"{north_south}-{west_east}"
    return north_south or west_east or "centre"


def _tile_regions(
    sections: list[dict[str, Any]], cols: int, rows: int, col: int, row: int
) -> list[str]:
    """Regions on one tile, placed by their position inside that tile."""
    lines = []
    for section in sections:
        x, y = section["map_x"] * cols / 100, section["map_y"] * rows / 100
        if int(min(x, cols - 0.001)) != col or int(min(y, rows - 0.001)) != row:
            continue
        local = _direction((x - col) * 100, (y - row) * 100)
        text = (section["description"] or section["brief"])[:_DESCRIPTION_LENGTH]
        lines.append(f"{section['label']} in the {local}: {text}")
    return lines[:_TILE_REGIONS]


def tile_prompt(adventure: Any, layout: dict[str, Any], col: int, row: int) -> str:
    """The default image prompt of one tile (the grid as it is after placing that tile)."""
    current = normalize_layout(layout)
    cols, rows = max(current["cols"], col + 1), max(current["rows"], row + 1)
    sections = normalize_sections(getattr(adventure, "world_sections", None))
    regions = _tile_regions(sections, cols, rows, col, row)
    setting = str(getattr(adventure, "plot", "") or getattr(adventure, "teaser", "") or "")[:300]
    part = (
        ""
        if cols == rows == 1
        else f"This image is one part of a larger map: column {col + 1} of {cols}, row {row + 1} of "
        f"{rows}; its landscape continues over the edges into the neighbouring parts. "
    )
    places = (
        f"Regions on this part: {'; '.join(regions)}. "
        if regions
        else "Open land between regions. "
    )
    return (
        "A hand-drawn world map seen from straight above, wide landscape format, for a text "
        f"adventure. Setting: {setting} {part}{places}"
        "Show the landscape (coast, forests, mountains, towns) and roads. No text, no letters, no "
        "labels, no legend, no compass rose with letters, no frame or border."
    )
