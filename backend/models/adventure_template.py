import uuid
from sqlalchemy import Column, String, Integer, Boolean, JSON, ForeignKey
from backend.models.base import Base, TimestampMixin

class GenerationCancelled(Exception):
    """Raised when the user cancels a background generation task."""
    pass

class AdventureTemplate(Base, TimestampMixin):
    __tablename__ = "adventure_templates"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    title = Column(String(50), nullable=False)
    teaser = Column(String(300), nullable=True)
    
    image_url = Column(String(255), nullable=True)
    # context is now replaced by original_prompt below
    
    # Configuration / Rules (Back to top-level for easier querying/migration)
    strict_rules = Column(Boolean, default=True, nullable=False)
    rule_enforcement_mode = Column(String(16), default="strict", nullable=False)
    time_per_turn = Column(Integer, default=5, nullable=False)
    pacing_minutes = Column(Integer, default=5, nullable=False)
    clock_enabled = Column(Boolean, default=False, nullable=False)
    time_system = Column(String(20), default="calendar", nullable=False)
    time_config = Column(JSON, nullable=True)
    
    generate_scene_images = Column(Boolean, default=False, nullable=False)
    generate_npc_images = Column(Boolean, default=False, nullable=False)
    generate_item_images = Column(Boolean, default=False, nullable=False)
    selected_image_styles = Column(JSON, nullable=True)
    selected_tone = Column(String(100), nullable=True)

    game_over_rules = Column(JSON, nullable=True)
    quests = Column(JSON, nullable=True)
    is_completed = Column(Boolean, default=False, nullable=False)
    
    # Status
    is_ready = Column(Boolean, default=False)
    creation_status = Column(String(100), nullable=True)
    creation_error = Column(String(500), nullable=True)

    # Metadata
    original_manifest = Column(JSON, nullable=True)
    
    # Generation Constraints
    min_scenes = Column(Integer, default=1, nullable=False)
    max_scenes = Column(Integer, default=5, nullable=False)

    # New Concept Fields
    plot = Column(String(5000), nullable=True)
    rules = Column(String(5000), nullable=True)
    walkthrough = Column(String(10000), nullable=True)
    completed_condition = Column(String(1000), nullable=True)
    gameover_condition = Column(String(1000), nullable=True)
    original_prompt = Column(String(5000), nullable=True)
    starting_timestamp = Column(Integer, default=0, nullable=False) # Minutes from Day 1, 00:00

    # Award System
    awards = Column(JSON, nullable=True)
    award_generation_enabled = Column(Boolean, default=False, nullable=False)
    min_awards = Column(Integer, default=3, nullable=False)
    max_awards = Column(Integer, default=8, nullable=False)
