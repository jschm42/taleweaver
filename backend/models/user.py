import uuid
from sqlalchemy import Column, String, JSON, Boolean
from backend.models.base import Base, TimestampMixin

class User(Base, TimestampMixin):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(50), nullable=False, unique=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="user") # "admin" or "user"
    
    profile_image_url = Column(String(255), nullable=True)
    bio = Column(String(1000), nullable=True)
    default_language = Column(String(20), nullable=True)
    has_imported_defaults = Column(Boolean, nullable=False, default=False)

    # Store encrypted keys mapping, e.g., {"openai": "gAAAAAB...", "anthropic": "..."}
    encrypted_api_keys = Column(JSON, nullable=True)

    # Store LLM preferences: {"small_model": "...", "complex_model": "..."}
    llm_settings = Column(JSON, nullable=True)

    # Store T2I preferences: {"simple_model": "...", "advanced_model": "...", "provider": "..."}
    t2i_settings = Column(JSON, nullable=True)

    # Admin-managed catalogs for adventure generation selectors.
    image_styles_catalog = Column(JSON, nullable=True)
    tone_catalog = Column(JSON, nullable=True)

    # General game preferences: {"clock_24h": false}
    game_settings = Column(JSON, nullable=True)

    # Award System: stores earned awards as a list of objects
    # [{"key": "...", "tier": "gold", "adventure_title": "...", "session_id": "...", "earned_at": "..."}]
    earned_awards = Column(JSON, nullable=True)

    # Game Log: stores history of completed or game-over sessions
    # [{"session_id": "...", "adventure_title": "...", "status": "completed|game_over", "note": "...", "ended_at": "..."}]
    game_log = Column(JSON, nullable=True)

