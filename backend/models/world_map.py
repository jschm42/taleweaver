"""
WorldMap model — persists the discovered scene graph for an adventure.

Nodes  = Scenes the player has visited (keyed by scene_id string).
Edges  = Directed exits between scenes.

Stored as two JSON columns so the graph can be traversed and serialised
to Mermaid.js notation in O(V + E) time.
"""
import uuid6

from sqlalchemy import JSON, Column, ForeignKey, String
from sqlalchemy.orm import synonym

from backend.models.base import Base, TimestampMixin


class WorldMap(Base, TimestampMixin):
    __tablename__ = "world_maps"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid6.uuid7()))
    template_id = Column(String(36), ForeignKey("adventure_templates.id"), nullable=False)
    session_id = Column(String(36), ForeignKey("game_sessions.id"), nullable=True, index=True)

    # {"scene_id": {"label": "...", "description": "..."}, ...}
    nodes: dict = Column(JSON, default=dict, nullable=False)

    # [{"from": "scene_id", "to": "scene_id", "label": "..."}, ...]
    edges: list = Column(JSON, default=list, nullable=False)

    # The scene_id that is currently active (highlighted on the map)
    current_scene_id = Column(String(255), nullable=True)

    # Legacy alias for backward compatibility during migration rollout.
    adventure_id = synonym("template_id")
