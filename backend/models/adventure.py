import uuid
from sqlalchemy import Column, String, Integer, Boolean, JSON, ForeignKey
from backend.models.base import Base, TimestampMixin

class Adventure(Base, TimestampMixin):
    __tablename__ = "adventures"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_id = Column(String(36), ForeignKey("users.id"), nullable=True) # Linked to User
    title = Column(String(50), nullable=False)
    
    image_url = Column(String(255), nullable=True) # Max 512x512
    context = Column(String(2000), nullable=True) # Story idea
    
    strict_rules = Column(Boolean, default=True, nullable=False)
    rule_enforcement_mode = Column(String(16), default="strict", nullable=False)
    time_per_turn = Column(Integer, default=5, nullable=False) # Minutes advanced per action
    pacing_minutes = Column(Integer, default=5, nullable=False)
    clock_enabled = Column(Boolean, default=False, nullable=False)
    heartbeat_enabled = Column(Boolean, default=False, nullable=False) # Deprecated but kept for safety
    heartbeat_interval = Column(Integer, default=10, nullable=False)
    
    generate_scene_images = Column(Boolean, default=False, nullable=False)
    generate_npc_images = Column(Boolean, default=False, nullable=False)
    generate_item_images = Column(Boolean, default=False, nullable=False)
    selected_image_styles = Column(JSON, nullable=True)
    selected_tone = Column(String(100), nullable=True)

    game_over_rules = Column(JSON, nullable=True)
    original_manifest = Column(JSON, nullable=True) # Full blueprint for reset
    
    # Generation Constraints
    min_scenes = Column(Integer, default=1, nullable=False)
    max_scenes = Column(Integer, default=5, nullable=False)
    
    # Async Generation Status
    is_ready = Column(Boolean, default=True) # New ones start False, old ones remain ready
    creation_status = Column(String(100), nullable=True) # e.g., "Generating Plot..."
    creation_error = Column(String(500), nullable=True) # For failure reporting

    # Quest System
    quests = Column(JSON, nullable=True) # List of quest objects
    is_completed = Column(Boolean, default=False, nullable=False)
