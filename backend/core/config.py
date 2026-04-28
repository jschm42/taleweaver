import base64
import logging
import os
import json
from typing import Optional
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings

def get_app_version() -> str:
    try:
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "version.json")
        with open(path, "r") as f:
            data = json.load(f)
            v = data.get("version", "0.1.0")
            s = data.get("suffix", "")
            return f"{v}-{s}" if s else v
    except Exception:
        return "0.1.0"

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
    APP_VERSION: str = Field(default_factory=get_app_version)
    DATABASE_URL: str = ""
    BACKEND_PORT: int = 8000
    FRONTEND_PORT: int = 5173
    
    # Storage configuration
    DATA_DIR: str = "data"
    
    @model_validator(mode="after")
    def assemble_db_url(self) -> "Settings":
        if not self.DATABASE_URL:
            # Construct default path in data dir
            self.DATABASE_URL = f"sqlite+aiosqlite:///./{self.DATA_DIR}/taleweaver.db"
        return self
    IMAGE_GENERATION_TIMEOUT_SECONDS: int = 120
    
    # Use existing key from environment or generate a temporary one
    ENCRYPTION_KEY: str = Field(default_factory=generate_temp_key)

    # API Keys from Environment (Optional)
    # These take precedence over database-stored keys
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    GOOGLE_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    OPENROUTER_API_KEY: Optional[str] = None
    MISTRAL_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None
    BLACK_FOREST_LABS_API_KEY: Optional[str] = None
    MIDJOURNEY_API_KEY: Optional[str] = None
    
    def get_env_api_key(self, provider: str) -> Optional[str]:
        """Returns the API key for a provider if set in environment variables."""
        p = provider.lower()
        if p == "openai": return self.OPENAI_API_KEY
        if p == "anthropic": return self.ANTHROPIC_API_KEY
        if p in ["google", "gemini"]: return self.GOOGLE_API_KEY or self.GEMINI_API_KEY
        if p == "openrouter": return self.OPENROUTER_API_KEY
        if p == "mistral": return self.MISTRAL_API_KEY
        if p == "groq": return self.GROQ_API_KEY
        if p == "black_forest_labs": return self.BLACK_FOREST_LABS_API_KEY
        if p == "midjourney": return self.MIDJOURNEY_API_KEY
        return None
    
    model_config = {"env_file": ".env", "extra": "ignore"}

settings = Settings()
