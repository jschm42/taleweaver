import uuid6

from sqlalchemy import Column, ForeignKey, String, Text

from backend.models.base import Base, TimestampMixin


class ChatMessage(Base, TimestampMixin):
    """
    Stores conversational history for the sliding-window memory management.
    """
    __tablename__ = "chat_messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid6.uuid7()))
    session_id = Column(String(36), ForeignKey("game_sessions.id"), nullable=False)
    
    # "user", "assistant", or "system"
    role = Column(String(20), nullable=False)
    
    # The actual message payload
    content = Column(Text, nullable=False)
