"""Blueprint converters for world sections (regions).

``position: 20, 65`` places a section on the world map (percent, 0-100 each).
``links: HARBOR_TOWN 8h, GLOOM_PEAKS 2d`` lists planned routes of a planned section with an
optional travel time (``90``, ``2h 30m``, ``1d``).
"""

from __future__ import annotations

import re
from typing import Any

from backend.engine.blueprint.converters import normalize_id
from backend.engine.rules.game_clock import to_minutes

_SEPARATORS = re.compile(r"[;,]")


def _coordinate(raw: str) -> float:
    try:
        value = float(raw.strip().rstrip("%"))
    except ValueError as exc:
        raise ValueError(f"expected a number from 0 to 100, got '{raw.strip()}'") from exc
    if not 0 <= value <= 100:
        raise ValueError(f"expected a number from 0 to 100, got '{raw.strip()}'")
    return value


def section_position(raw: str) -> dict[str, float]:
    """``20, 65`` / ``20 65`` -> ``{"map_x": 20.0, "map_y": 65.0}``."""
    parts = [part for part in re.split(r"[\s,;/]+", raw.strip()) if part]
    if len(parts) != 2:
        raise ValueError(f"expected two numbers 'x, y', got '{raw.strip()}'")
    return {"map_x": _coordinate(parts[0]), "map_y": _coordinate(parts[1])}


def _link(part: str) -> dict[str, Any] | None:
    target, _, duration = part.strip().partition(" ")
    section_id = normalize_id(target)
    if not section_id:
        return None
    minutes = to_minutes(duration.strip()) if duration.strip() else None
    if duration.strip() and minutes is None:
        raise ValueError(f"expected a travel time like '8h' after {section_id}, got '{duration}'")
    return {"to_section_id": section_id, "travel_minutes": minutes}


def section_links(raw: str) -> list[dict[str, Any]]:
    """``HARBOR_TOWN 8h, GLOOM_PEAKS`` -> planned links with optional travel minutes."""
    links = [_link(part) for part in _SEPARATORS.split(raw) if part.strip()]
    return [link for link in links if link]
