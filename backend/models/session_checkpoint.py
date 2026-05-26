import uuid6

from sqlalchemy import Column, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import relationship

from backend.models.base import Base, TimestampMixin


class SessionCheckpoint(Base, TimestampMixin):
    __tablename__ = "session_checkpoints"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid6.uuid7()))
    session_id = Column(String(36), ForeignKey("game_sessions.id", ondelete="CASCADE"), nullable=False)
    message_index = Column(Integer, nullable=False)
    state_snapshot = Column(JSON, nullable=False)
    trigger_reason = Column(String(64), nullable=False)

    session = relationship("GameSession", back_populates="checkpoints")