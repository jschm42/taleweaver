import uuid

from sqlalchemy import JSON, Column, ForeignKey, Integer, String

from backend.models.base import Base, TimestampMixin


class Character(Base, TimestampMixin):
    """
    User's character templates.
    """
    __tablename__ = "characters"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    
    name = Column(String(30), nullable=False)
    profile_image = Column(String(255), nullable=True)
    
    # Generic base stats that can be mapped conceptually anywhere.
    # We initialize them statically to 10 as per rules.
    stats = Column(JSON, default=lambda: {
        "strength": 10,
        "intelligence": 10,
        "wisdom": 10,
        "dexterity": 10,
        "charisma": 10,
        "armor_class": 10
    }, nullable=False)
    
    # Core RPG Stats (explicit columns for consistency with Avatar)
    strength = Column(Integer, default=10, nullable=False)
    intelligence = Column(Integer, default=10, nullable=False)
    wisdom = Column(Integer, default=10, nullable=False)
    dexterity = Column(Integer, default=10, nullable=False)
    charisma = Column(Integer, default=10, nullable=False)
    armor_class = Column(Integer, default=10, nullable=False)
    
    # Empty starting gear and stuff
    inventory = Column(JSON, default=list, nullable=False)
    
    equipment = Column(JSON, default=lambda: {
        "Head": None,
        "Chest": None,
        "Arms": None,
        "Legs": None,
        "Hands": None,
        "Feet": None,
        "Ring_1": None,
        "Ring_2": None,
        "Neck": None,
        "MainHand": None,
        "OffHand": None
    }, nullable=False)
    
    status_effects = Column(JSON, default=list, nullable=False)
