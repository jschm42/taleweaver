import uuid
from sqlalchemy import Column, String, Integer, JSON, ForeignKey
from backend.models.base import Base, TimestampMixin

class Avatar(Base, TimestampMixin):
    __tablename__ = "avatars"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    adventure_id = Column(String(36), ForeignKey("adventures.id"), nullable=True) # Linked for cleanup
    name = Column(String(100), nullable=False)
    
    # Character Sheet values
    hp = Column(Integer, default=200, nullable=False)
    stamina = Column(Integer, default=200, nullable=False)
    mana = Column(Integer, default=200, nullable=False)
    
    # JSON fields for flexible data structures
    stats = Column(JSON, default=dict, nullable=False)
    inventory = Column(JSON, default=list, nullable=False)
    
    # Default equipment slots setup
    equipment = Column(JSON, default=lambda: {
        "Head": None,
        "Chest": None,
        "Arms": None,
        "Legs": None,
        "Hands": None,
        "Feet": None,
        "Ring_1": None,
        "Ring_2": None,
        "Amulet": None
    }, nullable=False)
    
    status_effects = Column(JSON, default=list, nullable=False)
