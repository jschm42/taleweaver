from __future__ import annotations
from typing import Optional, Union
"""
MapEngine — manages the scene graph.

Responsibilities:
  * register_visit  — Upsert the current scene node (idempotent).
  * register_exit   — Add a directed edge between two scenes (deduplicates).
  * augment_map_data — Add adjacent unvisited scenes as placeholders.
"""

import logging

from sqlalchemy.orm.attributes import flag_modified

logger = logging.getLogger(__name__)


class MapEngine:
    @staticmethod
    def _safe_id(raw: str) -> str:
        """
        Convert an arbitrary scene_id string to a safe node identifier.
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
        
        # Use safe ID for keys to ensure consistency
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
        is_locked: bool = False,
        exit_type: str = "one_way"
    ) -> None:
        """
        Adds a directed or bidirectional edge between two scenes. 
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
            existing_from = MapEngine._safe_id(e["from"])
            existing_to = MapEngine._safe_id(e["to"])
            
            # Match A -> B or (if bidirectional) B -> A
            is_match = (existing_from == src_id and existing_to == dst_id) or (
                (exit_type == "bidirectional" or e.get("exit_type") == "bidirectional")
                and existing_from == dst_id and existing_to == src_id
            )
            
            if is_match:
                # Update existing edge (e.g. label or lock status)
                edges[idx]["label"] = exit_label
                edges[idx]["is_locked"] = is_locked
                edges[idx]["exit_type"] = exit_type
                world_map.edges = edges
                flag_modified(world_map, "edges")
                return

        # Add new edge
        edges.append({
            "from": from_scene, 
            "to": to_scene, 
            "label": exit_label,
            "is_locked": is_locked,
            "exit_type": exit_type
        })
        world_map.edges = edges
        flag_modified(world_map, "edges")

    @staticmethod
    def augment_map_data(map_dict: dict, exits: list, current_scene_id: str) -> dict:
        """
        Adds adjacent unvisited scenes as placeholder nodes to the map dictionary.
        
        Args:
            map_dict: The serialized map dictionary (nodes, edges, current_scene_id).
            exits: List of WorldExit objects for the current session/template.
            current_scene_id: The raw ID of the current scene.
        """
        if not current_scene_id:
            return map_dict

        nodes = map_dict.get("nodes", {})
        edges = map_dict.get("edges", [])
        
        # Find all exits starting from or ending at the current scene (if bidirectional)
        current_safe_id = MapEngine._safe_id(current_scene_id)
        
        for ex in exits:
            is_from_current = (ex.from_scene_id == current_scene_id)
            is_to_current = (ex.to_scene_id == current_scene_id and ex.exit_type == "bidirectional")
            
            if not (is_from_current or is_to_current):
                continue
                
            target_raw_id = ex.to_scene_id if is_from_current else ex.from_scene_id
            target_safe_id = MapEngine._safe_id(target_raw_id)
            
            # If the target node is not yet in our visited nodes, add it as unknown
            if target_safe_id not in nodes:
                nodes[target_safe_id] = {
                    "id": target_raw_id,
                    "label": "?",
                    "description": "An unexplored area...",
                    "is_unknown": True
                }

            # Check if this edge already exists
            edge_exists = any(
                (MapEngine._safe_id(e["from"]) == current_safe_id and MapEngine._safe_id(e["to"]) == target_safe_id) or
                (ex.exit_type == "bidirectional" and MapEngine._safe_id(e["from"]) == target_safe_id and MapEngine._safe_id(e["to"]) == current_safe_id)
                for e in edges
            )

            if not edge_exists:
                edges.append({
                    "from": current_scene_id if is_from_current else target_raw_id,
                    "to": target_raw_id if is_from_current else current_scene_id,
                    "label": ex.label or "",
                    "is_locked": ex.is_locked,
                    "exit_type": ex.exit_type
                })

        map_dict["nodes"] = nodes
        map_dict["edges"] = edges
        return map_dict

    @staticmethod
    def to_dict(world_map) -> dict:
        """
        Serializes the WorldMap into a raw dictionary for frontend rendering (e.g. Rough.js).
        """
        if not world_map:
            return {"nodes": {}, "edges": [], "current_scene_id": None}
            
        return {
            "nodes": world_map.nodes or {},
            "edges": world_map.edges or [],
            "current_scene_id": world_map.current_scene_id
        }
