import uuid
from sqlalchemy import Column, String, ForeignKey, Text
from backend.models.base import Base, TimestampMixin

class ChatMessage(Base, TimestampMixin):
    """
    Stores conversational history for the sliding-window memory management.
    """
    __tablename__ = "chat_messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    game_state_id = Column(String(36), ForeignKey("game_states.id"), nullable=False)
    
    # "user", "assistant", or "system"
    role = Column(String(20), nullable=False)
    
    # The actual message payload
    content = Column(Text, nullable=False)
