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
    ) -> None:
        """
        Add a directed edge (exit) between two scenes, deduplicating by
        (from, to) pair so repeated visits don't bloat the graph.

        Args:
            world_map:   WorldMap ORM instance (mutated in-place).
            from_scene:  Source scene_id.
            to_scene:    Destination scene_id.
            exit_label:  Optional direction / action label (e.g. "north", "open door").
        """
        edges: list = list(world_map.edges or [])

        already_exists = any(
            e["from"] == from_scene and e["to"] == to_scene
            for e in edges
        )
        if not already_exists:
            edges.append({"from": from_scene, "to": to_scene, "label": exit_label})
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

        # Emit node definitions — sanitise labels for Mermaid compatibility.
        for scene_id, meta in nodes.items():
            safe_id = _safe_id(scene_id)
            label = meta.get("label", scene_id).replace('"', "'")
            if scene_id == current:
                # Highlight the current location with a distinctive shape.
                lines.append(f'  {safe_id}["{label} ★"]:::current')
            else:
                lines.append(f'  {safe_id}["{label}"]')

        # Emit edges.
        for edge in edges:
            src = _safe_id(edge["from"])
            dst = _safe_id(edge["to"])
            lbl = edge.get("label", "").replace('"', "'")
            if lbl:
                lines.append(f'  {src} -->|"{lbl}"| {dst}')
            else:
                lines.append(f"  {src} --> {dst}")

        # Mermaid classDef for the current-location highlight.
        lines.append("  classDef current fill:#10b981,stroke:#059669,color:#fff,font-weight:bold")

        return "\n".join(lines)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _safe_id(raw: str) -> str:
    """
    Convert an arbitrary scene_id string to a Mermaid-safe node identifier.
    Replaces spaces and hyphens with underscores; strips other specials.
    """
    return "".join(c if (c.isalnum() or c == "_") else "_" for c in raw.replace("-", "_"))
