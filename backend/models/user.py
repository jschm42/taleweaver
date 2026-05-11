import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import JSON, Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="user") # "admin" or "user"
    
    profile_image_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    bio: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    default_language: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    has_imported_defaults: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Store encrypted keys mapping, e.g., {"openai": "gAAAAAB...", "anthropic": "..."}
    encrypted_api_keys: Mapped[Optional[Dict[str, str]]] = mapped_column(JSON, nullable=True)

    # Store LLM preferences: {"small_model": "...", "complex_model": "..."}
    llm_settings: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Store T2I preferences: {"simple_model": "...", "advanced_model": "...", "provider": "..."}
    t2i_settings: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    tts_settings: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Admin-managed catalogs for adventure generation selectors.
    image_styles_catalog: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True)
    tone_catalog: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True)

    # General game preferences: {"clock_24h": false}
    game_settings: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Award System: stores earned awards as a list of objects
    # [{"key": "...", "tier": "gold", "adventure_title": "...", "session_id": "...", "earned_at": "..."}]
    earned_awards: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True)

    # Game Log: stores history of completed or game-over sessions
    # [{"session_id": "...", "adventure_title": "...", "status": "completed|game_over", "note": "...", "ended_at": "..."}]
    game_log: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True)
