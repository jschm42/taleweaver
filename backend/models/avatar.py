import uuid6
from typing import Any, Dict, List, Optional

from sqlalchemy import JSON, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, synonym

from backend.models.base import Base, TimestampMixin


class Avatar(Base, TimestampMixin):
    __tablename__ = "avatars"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid6.uuid7()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    template_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("adventure_templates.id"), nullable=True) # Linked for cleanup
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    profile_image: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Character Sheet values
    hp: Mapped[int] = mapped_column(Integer, default=200, nullable=False)
    max_hp: Mapped[int] = mapped_column(Integer, default=200, nullable=False)
    stamina: Mapped[int] = mapped_column(Integer, default=200, nullable=False)
    max_stamina: Mapped[int] = mapped_column(Integer, default=200, nullable=False)
    mana: Mapped[int] = mapped_column(Integer, default=200, nullable=False)
    max_mana: Mapped[int] = mapped_column(Integer, default=200, nullable=False)
    exp: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    # Core RPG Stats (1-99)
    strength: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    intelligence: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    wisdom: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    dexterity: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    charisma: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    armor_class: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    
    # JSON fields for flexible data structures
    stats: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    inventory: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    
    # Default equipment slots setup
    equipment: Mapped[Dict[str, Any]] = mapped_column(JSON, default=lambda: {
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
    
    status_effects: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)

    # Legacy alias for backward compatibility during migration rollout.
    adventure_id = synonym("template_id")
