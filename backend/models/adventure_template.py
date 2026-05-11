import uuid6
from typing import Any, Dict, List, Optional

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, TimestampMixin


class GenerationCancelled(Exception):
    """Raised when the user cancels a background generation task."""
    pass

class AdventureTemplate(Base, TimestampMixin):
    __tablename__ = "adventure_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid6.uuid7()))
    owner_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(50), nullable=False)
    teaser: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    version: Mapped[Optional[str]] = mapped_column(String(15), nullable=True)
    language: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    origin_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True) # Stable ID for default/sample templates

    image_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Configuration / Rules
    strict_rules: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    rule_enforcement_mode: Mapped[str] = mapped_column(String(16), default="strict", nullable=False)
    time_per_turn: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    pacing_minutes: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    clock_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    time_system: Mapped[str] = mapped_column(String(20), default="calendar", nullable=False)
    time_config: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    
    generate_scene_images: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    generate_npc_images: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    generate_item_images: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    selected_image_styles: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True)
    selected_tone: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    game_over_rules: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    quests: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Status
    is_ready: Mapped[bool] = mapped_column(Boolean, default=False)
    creation_status: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    creation_error: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Metadata
    original_manifest: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    
    # Generation Constraints
    min_scenes: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    max_scenes: Mapped[int] = mapped_column(Integer, default=5, nullable=False)

    # New Concept Fields
    plot: Mapped[Optional[str]] = mapped_column(String(5000), nullable=True)
    rules: Mapped[Optional[str]] = mapped_column(String(5000), nullable=True)
    intro_text: Mapped[Optional[str]] = mapped_column(String(20000), nullable=True)
    walkthrough: Mapped[Optional[str]] = mapped_column(String(20000), nullable=True)
    completed_condition: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    gameover_condition: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    tts_director_notes: Mapped[Optional[str]] = mapped_column(String(5000), nullable=True)
    original_prompt: Mapped[Optional[str]] = mapped_column(String(20000), nullable=True)
    starting_timestamp: Mapped[int] = mapped_column(Integer, default=0, nullable=False) # Minutes from Day 1, 00:00
    allow_dynamic_items: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Award System
    awards: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True)
    award_generation_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    min_awards: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    max_awards: Mapped[int] = mapped_column(Integer, default=8, nullable=False)
    
    # Adventure Generator Mode
    is_adventure_generator: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
