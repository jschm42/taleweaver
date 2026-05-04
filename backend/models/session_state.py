import uuid
from sqlalchemy import Column, String, Integer, Boolean, JSON, ForeignKey
from sqlalchemy.orm import relationship, synonym
from backend.models.base import Base, TimestampMixin

class SessionState(Base, TimestampMixin):
    __tablename__ = "session_states"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("game_sessions.id"), nullable=False)
    
    # Denormalized fields for easier querying
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    template_id = Column(String(36), ForeignKey("adventure_templates.id", ondelete="SET NULL"), nullable=True)
    avatar_id = Column(String(36), ForeignKey("avatars.id"), nullable=True)
    
    # Current Runtime State
    current_scene_id = Column(String(100), nullable=False, default="START")
    in_game_time = Column(Integer, default=0, nullable=False)
    time_system = Column(String(20), default="calendar", nullable=False)
    time_config = Column(JSON, nullable=True)
    inventory = Column(JSON, nullable=True, default=[])
    
    # Progress trackers
    entity_states = Column(JSON, nullable=True, default={})
    exit_states = Column(JSON, nullable=True, default={})
    discovered_scenes = Column(JSON, nullable=True, default=[])
    quests = Column(JSON, nullable=True, default=[])
    start_datetime = Column(String(36), nullable=True)
    
    # Session-specific overrides/copies from template
    plot = Column(String(5000), nullable=True)
    rules = Column(String(5000), nullable=True)
    walkthrough = Column(String(10000), nullable=True)
    completed_condition = Column(String(1000), nullable=True)
    gameover_condition = Column(String(1000), nullable=True)
    selected_image_styles = Column(JSON, nullable=True)
    selected_tone = Column(JSON, nullable=True)
    
    # Runtime flags
    is_completed = Column(Boolean, default=False)
    is_debug_enabled = Column(Boolean, default=False)

    # Relationships
    session = relationship("GameSession", back_populates="state")

    # Legacy aliases for backward compatibility during migration rollout.
    adventure_id = synonym("template_id")
    scene_id = synonym("current_scene_id")
