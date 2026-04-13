"""
MapEngine — manages the scene graph and converts it to Mermaid.js notation.

Responsibilities:
  * register_visit  — Upsert the current scene node (idempotent).
  * register_exit   — Add a directed edge between two scenes (deduplicates).
  * to_mermaid      — Serialise the graph in Mermaid flowchart syntax O(V+E).
"""
from __future__ import annotations

from typing import Optional


class MapEngine:

    @staticmethod
    def register_visit(
        world_map,
        scene_id: str,
        label: Optional[str] = None,
        description: Optional[str] = None,
    ) -> None:
        """
        Upsert a scene node. If the node already exists only missing fields
        are filled in, so richer data from later visits is preserved.

        Args:
            world_map:   WorldMap ORM instance (mutated in-place).
            scene_id:    Unique identifier of the scene (e.g. "START", "TAVERN").
            label:       Short human-readable name for display on the map.
            description: Optional one-line flavour text stored alongside the node.
        """
        # Reassign to a new dict so SQLAlchemy detects the mutation.
        nodes: dict = dict(world_map.nodes or {})

        if scene_id not in nodes:
            nodes[scene_id] = {"label": label or scene_id, "description": description or ""}
        else:
            # Preserve existing data; only fill gaps.
            if label and not nodes[scene_id].get("label"):
                nodes[scene_id]["label"] = label
            if description and not nodes[scene_id].get("description"):
                nodes[scene_id]["description"] = description

        world_map.nodes = nodes
        world_map.current_scene_id = scene_id

    @staticmethod
    def register_exit(
        world_map,
        from_scene: str,
        to_scene: str,
        exit_label: str = "",
        is_locked: bool = False,
    ) -> None:
        """
        Add a directed edge (exit) between two scenes, deduplicating by
        (from, to) pair so repeated visits don't bloat the graph.

        Args:
            world_map:   WorldMap ORM instance (mutated in-place).
            from_scene:  Source scene_id.
            to_scene:    Destination scene_id.
            exit_label:  Optional direction / action label (e.g. "north", "open door").
            is_locked:   Whether the path is currently blocked.
        """
        edges: list = list(world_map.edges or [])

        # Find existing edge to update or add new
        existing_idx = -1
        for idx, e in enumerate(edges):
            if e["from"] == from_scene and e["to"] == to_scene:
                existing_idx = idx
                break

        if existing_idx != -1:
            edges[existing_idx]["is_locked"] = is_locked
            if exit_label: edges[existing_idx]["label"] = exit_label
        else:
            edges.append({
                "from": from_scene, 
                "to": to_scene, 
                "label": exit_label,
                "is_locked": is_locked
            })
            
        world_map.edges = edges

    @staticmethod
    def to_mermaid(world_map, direction: str = "LR") -> str:
        """
        Serialise the scene graph to Mermaid.js flowchart notation.

        Complexity: O(V + E) — one pass over nodes, one pass over edges.

        Args:
            world_map: WorldMap ORM instance.
            direction: Mermaid graph direction — "LR", "TD", "RL", "BT".

        Returns:
            A Mermaid diagram string ready to be rendered by the frontend.
        """
        nodes: dict = world_map.nodes or {}
        edges: list = world_map.edges or []
        current: Optional[str] = world_map.current_scene_id

        lines: list[str] = [f"flowchart {direction}"]

        # Emit node definitions.
        # Collect all unique scene IDs from both the visited nodes and the discovered edges.
        all_scene_ids = set(nodes.keys())
        for edge in edges:
            all_scene_ids.add(edge["from"])
            all_scene_ids.add(edge["to"])

        for scene_id in all_scene_ids:
            safe_id = _safe_id(scene_id)
            is_visited = scene_id in nodes
            meta = nodes.get(scene_id, {})
            
            if is_visited:
                label = meta.get("label", scene_id).replace('"', "'")
                if scene_id == current:
                    lines.append(f'  {safe_id}["{label} ★"]:::current')
                else:
                    lines.append(f'  {safe_id}["{label}"]')
            else:
                # Discovered but not yet visited (Fog of War)
                lines.append(f'  {safe_id}["?"]:::unvisited')

        # Emit edges.
        locked_indices = []
        for idx, edge in enumerate(edges):
            src = _safe_id(edge["from"])
            dst = _safe_id(edge["to"])
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

        # Mermaid classDef for the current-location highlight.
        lines.append("  classDef current fill:#10b981,stroke:#059669,color:#fff,font-weight:bold")
        lines.append("  classDef unvisited fill:#1e293b,stroke:#475569,color:#94a3b8,stroke-dasharray: 2 2")
        
        # Style locked links (dotted red)
        for idx in locked_indices:
            lines.append(f"  linkStyle {idx} stroke:#ef4444,stroke-width:2px,stroke-dasharray: 5 5")

        return "\n".join(lines)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _safe_id(raw: str) -> str:
    """
    Convert an arbitrary scene_id string to a Mermaid-safe node identifier.
    Replaces spaces and hyphens with underscores; strips other specials.
    """
    return "".join(c if (c.isalnum() or c == "_") else "_" for c in raw.replace("-", "_"))
