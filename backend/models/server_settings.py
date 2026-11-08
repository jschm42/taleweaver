from typing import Any, Optional

from sqlalchemy import JSON, Integer
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, TimestampMixin

SERVER_SETTINGS_ID = 1


class ServerSettings(Base, TimestampMixin):
    """Server-wide configuration, managed by admins. The table holds exactly one row.

    Field names match the legacy ``User`` columns so the runtime overlay
    (``backend.core.global_settings``) can lay them over every user unchanged.
    """

    __tablename__ = "server_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=SERVER_SETTINGS_ID)

    # Encrypted provider API keys ({provider: ciphertext}).
    encrypted_api_keys: Mapped[Optional[dict[str, str]]] = mapped_column(JSON, nullable=True)
    llm_settings: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    t2i_settings: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    tts_settings: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    image_styles_catalog: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(
        JSON, nullable=True
    )
    tone_catalog: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(JSON, nullable=True)
    narrator_voice_catalog: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(
        JSON, nullable=True
    )
    # Who pays per provider: {provider: "user_optional" | "user_required" | "disabled"};
    # providers not listed use the server key (see backend/core/api_keys.py).
    api_key_policy: Mapped[Optional[dict[str, str]]] = mapped_column(JSON, nullable=True)
    # Shared game settings; player-owned keys stay in ``User.game_settings``.
    game_settings: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    # Audio generation (experimental ComfyUI workflow); see backend/core/audio_settings.py.
    audio_settings: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
