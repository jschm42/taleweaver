import uuid6

from sqlalchemy import Column, ForeignKey, String
from sqlalchemy.orm import relationship

from backend.models.base import Base, TimestampMixin


class GameSession(Base, TimestampMixin):
    __tablename__ = "game_sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid6.uuid7()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    avatar_id = Column(String(36), ForeignKey("avatars.id"), nullable=False)
    template_id = Column(String(36), ForeignKey("adventure_templates.id", ondelete="SET NULL"), nullable=True)
    
    # Denormalized fields to preserve history if template is deleted
    adventure_title = Column(String(100), nullable=True)
    adventure_image_url = Column(String(255), nullable=True)
    
    status = Column(String(20), default="active", nullable=False) # active, archived, completed, game_over
    status_note = Column(String(500), nullable=True)
    copied_from_id = Column(String(36), ForeignKey("game_sessions.id", ondelete="SET NULL"), nullable=True)

    # Relationships
    state = relationship("SessionState", back_populates="session", uselist=False, cascade="all, delete-orphan")
    checkpoints = relationship("SessionCheckpoint", back_populates="session", cascade="all, delete-orphan")

