"""World sections (regions) on the player's map.

The map nodes are the scenes the player knows; this module tags each with its section and
derives the world map from them: the regions the player discovered and the links between
them (known exits whose two scenes lie in different regions). Unexplored placeholder nodes
get no section, so the map never tells which region lies behind an unexplored exit.
"""

from __future__ import annotations

from typing import Any, Optional

from backend.engine.interaction.map_engine import MapEngine
from backend.engine.world.sections import player_sections

VISITED = "visited"
REVEALED = "revealed"


def _node_discovery(node: dict[str, Any]) -> Optional[str]:
    if node.get("is_unknown"):
        return None
    return REVEALED if node.get("is_revealed") else VISITED


def _tag_nodes(nodes: dict[str, Any], scene_sections: dict[str, Optional[str]]) -> None:
    by_safe_id = {MapEngine._safe_id(sid): section for sid, section in scene_sections.items()}
    for safe_id, node in nodes.items():
        known = _node_discovery(node) is not None
        node["section_id"] = by_safe_id.get(safe_id) if known else None


def _discovered(nodes: dict[str, Any], section_ids: set[str]) -> dict[str, str]:
    """section id -> ``visited`` (a scene was entered) or ``revealed`` (only seen)."""
    found: dict[str, str] = {}
    for node in nodes.values():
        section_id, discovery = node.get("section_id"), _node_discovery(node)
        if section_id not in section_ids or discovery is None:
            continue
        if found.get(section_id) != VISITED:
            found[section_id] = discovery
    return found


def _section_links(
    edges: list[dict[str, Any]], nodes: dict[str, Any], shown: set[str]
) -> list[dict[str, Any]]:
    """One link per pair of shown regions joined by a known exit; open when any exit is open."""
    links: dict[tuple[str, str], dict[str, Any]] = {}
    for edge in edges:
        a = (nodes.get(MapEngine._safe_id(str(edge.get("from") or ""))) or {}).get("section_id")
        b = (nodes.get(MapEngine._safe_id(str(edge.get("to") or ""))) or {}).get("section_id")
        if not a or not b or a == b or not {a, b} <= shown:
            continue
        key = (min(a, b), max(a, b))
        link = links.setdefault(key, {"from": key[0], "to": key[1], "is_locked": True})
        link["is_locked"] = link["is_locked"] and bool(edge.get("is_locked"))
    return list(links.values())


def attach_sections(
    map_dict: dict[str, Any],
    scene_sections: dict[str, Optional[str]],
    raw_sections: Any,
) -> dict[str, Any]:
    """Adds ``section_id`` to the nodes plus ``sections``, ``section_links`` and the current one."""
    nodes = map_dict.get("nodes") or {}
    edges = map_dict.get("edges") or []
    _tag_nodes(nodes, scene_sections)
    sections = player_sections(raw_sections)
    discovered = _discovered(nodes, {s["id"] for s in sections})
    map_dict["sections"] = [
        {**section, "discovery": discovered[section["id"]]}
        for section in sections
        if section["id"] in discovered
    ]
    map_dict["section_links"] = _section_links(edges, nodes, set(discovered))
    current = nodes.get(str(map_dict.get("current_scene_id") or "")) or {}
    map_dict["current_section_id"] = current.get("section_id")
    return map_dict
