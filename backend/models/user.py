from datetime import datetime
from typing import Any, Optional

import uuid6
from sqlalchemy import JSON, Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid6.uuid7())
    )
    username: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, default="user"
    )  # "admin" or "user"

    profile_image_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    bio: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    default_language: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    has_imported_defaults: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Bumped on every password change/reset; JWTs carrying an older version are rejected.
    token_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    # SHA-256 hashes of unused one-time recovery codes (plaintext is shown to the user once).
    recovery_code_hashes: Mapped[Optional[list[str]]] = mapped_column(JSON, nullable=True)
    # Admin-issued one-time password reset link (SHA-256 of the token + expiry).
    password_reset_token_hash: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, index=True
    )
    password_reset_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Store encrypted keys mapping, e.g., {"openai": "gAAAAAB...", "anthropic": "..."}
    encrypted_api_keys: Mapped[Optional[dict[str, str]]] = mapped_column(JSON, nullable=True)

    # Store LLM preferences: {"small_model": "...", "complex_model": "..."}
    llm_settings: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Store T2I preferences: {"simple_model": "...", "advanced_model": "...", "provider": "..."}
    t2i_settings: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    tts_settings: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Admin-managed catalogs for adventure generation selectors.
    image_styles_catalog: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(
        JSON, nullable=True
    )
    tone_catalog: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(JSON, nullable=True)
    # Narrator voices adventures can pick (see core/narrator_voices.py).
    narrator_voice_catalog: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(
        JSON, nullable=True
    )

    # General game preferences: {"clock_24h": false}
    game_settings: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Setup wizard progress, per user (not broadcast): {"state": "pending", "visuals_opt_out": false}
    setup_wizard: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Award System: stores earned awards as a list of objects
    # [{"key": "...", "tier": "gold", "adventure_title": "...", "session_id": "...", "earned_at": "..."}]
    earned_awards: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(JSON, nullable=True)

    # Game Log: stores history of completed or game-over sessions
    # [{"session_id": "...", "adventure_title": "...", "status": "completed|game_over", "note": "...", "ended_at": "..."}]
    game_log: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(JSON, nullable=True)

    @property
    def recovery_codes_remaining(self) -> int:
        return len(self.recovery_code_hashes or [])
