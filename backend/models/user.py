import uuid
from sqlalchemy import Column, String, JSON
from backend.models.base import Base, TimestampMixin

class User(Base, TimestampMixin):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(50), nullable=False, unique=True, default="local_default_user")

    # Store encrypted keys mapping, e.g., {"openai": "gAAAAAB...", "anthropic": "..."}
    encrypted_api_keys = Column(JSON, nullable=True)

    # Store LLM preferences: {"small_model": "...", "complex_model": "..."}
    llm_settings = Column(JSON, nullable=True)

    # Store T2I preferences: {"simple_model": "...", "advanced_model": "...", "provider": "..."}
    t2i_settings = Column(JSON, nullable=True)
