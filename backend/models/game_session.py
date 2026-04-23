import uuid
from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.orm import relationship
from backend.models.base import Base, TimestampMixin

class GameSession(Base, TimestampMixin):
    __tablename__ = "game_sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    avatar_id = Column(String(36), ForeignKey("avatars.id"), nullable=False)
    template_id = Column(String(36), ForeignKey("adventure_templates.id"), nullable=False)
    
    status = Column(String(20), default="active", nullable=False) # active, archived, completed

    # Relationships
    state = relationship("SessionState", back_populates="session", uselist=False, cascade="all, delete-orphan")
