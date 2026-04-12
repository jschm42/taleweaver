import uuid
from sqlalchemy import Column, String, Integer, Boolean, JSON
from backend.models.base import Base, TimestampMixin

class Adventure(Base, TimestampMixin):
    __tablename__ = "adventures"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(255), nullable=False)
    
    strict_rules = Column(Boolean, default=True, nullable=False)
    heartbeat_enabled = Column(Boolean, default=False, nullable=False)
    heartbeat_interval = Column(Integer, default=10, nullable=False) # Configurable interval
    
    game_over_rules = Column(JSON, nullable=True)
