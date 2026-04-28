import uuid
from sqlalchemy import Column, String, Integer, JSON, ForeignKey
from sqlalchemy.orm import synonym
from backend.models.base import Base, TimestampMixin

class Avatar(Base, TimestampMixin):
    __tablename__ = "avatars"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    template_id = Column(String(36), ForeignKey("adventure_templates.id"), nullable=True) # Linked for cleanup
    name = Column(String(100), nullable=False)
    role = Column(String(100), nullable=True)
    description = Column(String(1000), nullable=True)
    profile_image = Column(String(255), nullable=True)
    
    # Character Sheet values
    hp = Column(Integer, default=200, nullable=False)
    max_hp = Column(Integer, default=200, nullable=False)
    stamina = Column(Integer, default=200, nullable=False)
    max_stamina = Column(Integer, default=200, nullable=False)
    mana = Column(Integer, default=200, nullable=False)
    max_mana = Column(Integer, default=200, nullable=False)
    exp = Column(Integer, default=0, nullable=False)
    
    # Core RPG Stats (1-99)
    strength = Column(Integer, default=10, nullable=False)
    intelligence = Column(Integer, default=10, nullable=False)
    wisdom = Column(Integer, default=10, nullable=False)
    dexterity = Column(Integer, default=10, nullable=False)
    charisma = Column(Integer, default=10, nullable=False)
    armor_class = Column(Integer, default=10, nullable=False)
    
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

    # Legacy alias for backward compatibility during migration rollout.
    adventure_id = synonym("template_id")
