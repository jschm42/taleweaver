"""
MapEngine — manages the scene graph and converts it to Mermaid.js notation.

Responsibilities:
  * register_visit  — Upsert the current scene node (idempotent).
  * register_exit   — Add a directed edge between two scenes (deduplicates).
  * to_mermaid      — Serialise the graph in Mermaid flowchart syntax O(V+E).
"""
from __future__ import annotations

from typing import Optional
from sqlalchemy.orm.attributes import flag_modified
import logging

logger = logging.getLogger(__name__)


class MapEngine:
    @staticmethod
    def _safe_id(raw: str) -> str:
        """
        Convert an arbitrary scene_id string to a Mermaid-safe node identifier.
        Replaces spaces and hyphens with underscores; strips other specials.
        """
        return "".join(c if (c.isalnum() or c == "_") else "_" for c in raw.replace("-", "_")).upper()

    @staticmethod
    def register_visit(
        world_map,
        scene_id: str,
        label: Optional[str] = None,
        description: Optional[str] = None,
        image_url: Optional[str] = None,
    ) -> None:
        """
        Upsert a scene node. If the node already exists only missing fields
        are filled in, so richer data from later visits is preserved.

        Args:
            world_map:   WorldMap ORM instance (mutated in-place).
            scene_id:    Unique identifier of the scene.
            label:       Short human-readable name for display on the map.
            description: Optional one-line flavour text stored alongside the node.
            image_url:   Optional URL to the scene image for the tooltip.
        """
        # Reassign to a new dict so SQLAlchemy detects the mutation.
        nodes: dict = dict(world_map.nodes or {})
        
        # Use safe ID for keys to ensure consistency with Mermaid diagram IDs
        sid = MapEngine._safe_id(scene_id)

        if sid not in nodes:
            nodes[sid] = {
                "id": scene_id, # Preserve original ID in metadata
                "label": label or scene_id, 
                "description": description or "",
                "image_url": image_url
            }
        else:
            # Update data if missing or if the new data is more detailed.
            if label and (not nodes[sid].get("label") or len(label) > len(nodes[sid]["label"])):
                nodes[sid]["label"] = label
            
            # If current description is empty, always fill it.
            curr_desc = nodes[sid].get("description", "")
            if description and (not curr_desc or len(description) > len(curr_desc)):
                nodes[sid]["description"] = description
                
            if image_url and not nodes[sid].get("image_url"):
                nodes[sid]["image_url"] = image_url

        world_map.nodes = nodes
        world_map.current_scene_id = sid # Also store safe ID as current location

    @staticmethod
    def register_exit(
        world_map, 
        from_scene: str, 
        to_scene: str, 
        exit_label: str = "", 
        is_locked: bool = False
    ) -> None:
        """
        Adds a directed edge between two scenes. 
        Normalizes IDs and prevents self-loops.
        """
        if not (from_scene and to_scene):
            return

        # Normalize IDs
        src_id = MapEngine._safe_id(from_scene)
        dst_id = MapEngine._safe_id(to_scene)

        # Prevent self-loops
        if src_id == dst_id:
            logger.debug(f"MapEngine: Ignoring self-loop registration for {src_id}")
            return

        edges = list(world_map.edges or [])

        # Check for existing
        for idx, e in enumerate(edges):
            # Compare normalized IDs
            if MapEngine._safe_id(e["from"]) == src_id and MapEngine._safe_id(e["to"]) == dst_id:
                # Update existing edge (e.g. label or lock status)
                edges[idx]["label"] = exit_label
                edges[idx]["is_locked"] = is_locked
                world_map.edges = edges
                flag_modified(world_map, "edges")
                return

        # Add new edge
        edges.append({
            "from": from_scene, 
            "to": to_scene, 
            "label": exit_label,
            "is_locked": is_locked
        })
        world_map.edges = edges
        flag_modified(world_map, "edges")

    @staticmethod
    def to_mermaid(world_map, direction: str = "LR") -> str:
        """
        Serializes the WorldMap into a Mermaid.js flowchart string.
        """
        if not world_map or not world_map.nodes:
            return ""

        nodes = world_map.nodes
        edges = world_map.edges or []
        current = world_map.current_scene_id

        lines: list[str] = [f"flowchart {direction}"]
        
        # Track IDs to ensure they are added to the graph even if they have no edges
        all_scene_ids = set(nodes.keys())
        for edge in edges:
            all_scene_ids.add(MapEngine._safe_id(edge["from"]))
            all_scene_ids.add(MapEngine._safe_id(edge["to"]))

        # 1. Add Nodes with styles
        for scene_id in sorted(all_scene_ids):
            node_data = nodes.get(scene_id, {})
            label = node_data.get("label", scene_id)
            safe_id = MapEngine._safe_id(scene_id)
            
            if scene_id == current:
                lines.append(f'  {safe_id}["{label} 📍"]:::current')
            else:
                lines.append(f'  {safe_id}["{label}"]:::visited')

        # 2. Add Edges (Connections)
        locked_indices = []
        for idx, edge in enumerate(edges):
            src_raw = edge["from"]
            dst_raw = edge["to"]
            src = MapEngine._safe_id(src_raw)
            dst = MapEngine._safe_id(dst_raw)
            
            # Skip self-loops in rendering
            if src == dst:
                continue

            is_locked = edge.get("is_locked", False)
            
            lbl = edge.get("label", "").replace('"', "'")
            if is_locked:
                lbl = f"🔒 {lbl}".strip()
                locked_indices.append(idx)
                # Dotted line for locked passages
                connection = "-.->"
            else:
                connection = "-->"

            if lbl:
                lines.append(f'  {src} {connection}|"{lbl}"| {dst}')
            else:
                lines.append(f"  {src} {connection} {dst}")

        # Mermaid classDef tags to be styled in the frontend/themeCSS.
        lines.append("  classDef current stroke-width:4px;")
        lines.append("  classDef visited opacity:1.0;")
        lines.append("  classDef unvisited stroke-dasharray: 2 2;")

        return "\n".join(lines)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _safe_id(raw: str) -> str:
    """
    Convert an arbitrary scene_id string to a Mermaid-safe node identifier.
    Replaces spaces and hyphens with underscores; strips other specials.
    """
    return "".join(c if (c.isalnum() or c == "_") else "_" for c in raw.replace("-", "_"))
