import uuid
from sqlalchemy import Column, String, Integer, ForeignKey
from backend.models.base import Base, TimestampMixin

class GameState(Base, TimestampMixin):
    __tablename__ = "game_states"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    avatar_id = Column(String(36), ForeignKey("avatars.id"), nullable=False)
    adventure_id = Column(String(36), ForeignKey("adventures.id"), nullable=False)
    
    scene_id = Column(String(255), nullable=False) # Reference to graph node
    in_game_time = Column(Integer, default=0, nullable=False) # e.g. minutes passed
