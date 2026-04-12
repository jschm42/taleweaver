import base64
import logging
import os
from pydantic import Field
from pydantic_settings import BaseSettings
from typing import Optional

logger = logging.getLogger(__name__)

def generate_temp_key() -> str:
    logger.warning(
        "No ENCRYPTION_KEY found in environment! "
        "Generating a random ephemeral key for this session. "
        "WARNING: Any API keys saved during this session will become unreadable upon server restart. "
        "Please generate a persistent key using 'python scripts/generate_fernet_key.py' and add it to your .env file."
    )
    return base64.urlsafe_b64encode(os.urandom(32)).decode()

class Settings(BaseSettings):
    PROJECT_NAME: str = "TaleWeaver"
    DATABASE_URL: str = "sqlite+aiosqlite:///./taleweaver.db"
    
    # Use existing key from environment or generate a temporary one
    ENCRYPTION_KEY: str = Field(default_factory=generate_temp_key)
    
    class Config:
        env_file = ".env"

settings = Settings()
