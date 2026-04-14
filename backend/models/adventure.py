import uuid
from sqlalchemy import Column, String, Integer, Boolean, JSON
from backend.models.base import Base, TimestampMixin

class Adventure(Base, TimestampMixin):
    __tablename__ = "adventures"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(50), nullable=False)
    
    image_url = Column(String(255), nullable=True) # Max 512x512
    context = Column(String(2000), nullable=True) # Story idea
    
    strict_rules = Column(Boolean, default=True, nullable=False)
    time_per_turn = Column(Integer, default=5, nullable=False) # Minutes advanced per action
    heartbeat_enabled = Column(Boolean, default=False, nullable=False) # Deprecated but kept for safety
    heartbeat_interval = Column(Integer, default=10, nullable=False)
    
    game_over_rules = Column(JSON, nullable=True)
    original_manifest = Column(JSON, nullable=True) # Full blueprint for reset
    
    # Async Generation Status
    is_ready = Column(Boolean, default=True) # New ones start False, old ones remain ready
    creation_status = Column(String(100), nullable=True) # e.g., "Generating Plot..."
    creation_error = Column(String(500), nullable=True) # For failure reporting
