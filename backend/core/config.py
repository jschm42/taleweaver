import base64
import json
import logging
import os
from typing import Optional

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings


def get_app_version() -> str:
    try:
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "version.json")
        with open(path) as f:
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

class TTSSettings(BaseModel):
    enabled: bool = True
    provider: str = "google"  # google, elevenlabs
    selected_model: str = "gemini-2.5-flash-preview-tts"
    selected_voice: str = "Puck"
    elevenlabs_voice_id: str = ""
    use_vocal_tags: bool = True
    voice_list: list[str] = [
        "Zephyr", "Puck", "Charon", "Kore", "Fenrir", "Leda", "Orus", "Aoede", "Callirrhoe",
        "Autonoe", "Enceladus", "Iapetus", "Umbriel", "Algieba", "Despina", "Erinome",
        "Algenib", "Rasalgethi", "Laomedeia", "Achernar", "Alnilam", "Schedar", "Gacrux",
        "Pulcherrima", "Achird", "Zubenelgenubi", "Vindemiatrix", "Sadachbia", "Sadaltager"
    ]
    voice_catalog: list[dict] = []
    sample_context: str = ""
    speech_rate: float = 1.0

class Settings(BaseSettings):
    PROJECT_NAME: str = "TaleWeaver"
    APP_VERSION: str = Field(default_factory=get_app_version)
    DATABASE_URL: str = ""
    BACKEND_PORT: int = 8000
    FRONTEND_PORT: int = 5173
    LOG_LEVEL: str = "INFO"
    
    # Comma-separated list of allowed host headers.
    # Default "*" works for local dev and Docker-behind-nginx deployments.
    # In a public non-proxied deployment set this to your actual domain,
    # e.g. ALLOWED_HOSTS=myserver.example.com
    ALLOWED_HOSTS: str = "*"

    @property
    def allowed_hosts_list(self) -> list[str]:
        """Return ALLOWED_HOSTS as a list, splitting on commas."""
        return [h.strip() for h in self.ALLOWED_HOSTS.split(",") if h.strip()]


    DATA_DIR: str = "data"
    SESSION_EMPTY_DIR_CLEANUP_DAYS: int = 7
    
    VISUAL_TIMEOUT: int = 300
    INTELLIGENCE_TIMEOUT: int = 60
    WORLDBUILDING_TIMEOUT: int = 600
    TTS_TIMEOUT_SECONDS: int = 120
    TTS_TIMEOUT_PER_1K_CHARS: int = 20
    TTS_TIMEOUT_MAX_SECONDS: int = 300
    TTS_REQUEST_MIN_INTERVAL_MS: int = 650
    TTS_RATE_LIMIT_MAX_RETRIES: int = 5
    TTS_RATE_LIMIT_BASE_DELAY_SECONDS: float = 2.0
    TTS_RATE_LIMIT_MAX_DELAY_SECONDS: float = 30.0
    TTS_RATE_LIMIT_JITTER_MIN: float = 0.9
    TTS_RATE_LIMIT_JITTER_MAX: float = 1.15

    @model_validator(mode="before")
    @classmethod
    def normalize_data_dir(cls, values):
        if isinstance(values, dict):
            data_dir = values.get("DATA_DIR")
            if not isinstance(data_dir, str) or not data_dir.strip():
                values["DATA_DIR"] = "data"
        return values
    
    @model_validator(mode="after")
    def assemble_db_url(self) -> "Settings":
        if not self.DATABASE_URL:
            # Construct default path in data dir
            self.DATABASE_URL = f"sqlite+aiosqlite:///./{self.DATA_DIR}/taleweaver.db"
        return self
    
    # Use existing key from environment or generate a temporary one
    ENCRYPTION_KEY: str = Field(default_factory=generate_temp_key)
    SECRET_KEY: Optional[str] = None

    # API Keys from Environment (Optional)
    # These take precedence over database-stored keys
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    GOOGLE_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    OPENROUTER_API_KEY: Optional[str] = None
    DEEPSEEK_API_KEY: Optional[str] = None
    KIMI_API_KEY: Optional[str] = None
    KIMI_API_BASE: str = "https://api.moonshot.ai/v1"
    MISTRAL_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None
    BLACK_FOREST_LABS_API_KEY: Optional[str] = None
    
    # Debug / Development
    TALEWEAVER_DEBUG_ENABLED: bool = False
    
    def get_env_api_key(self, provider: str) -> Optional[str]:
        """Returns the API key for a provider if set in environment variables."""
        p = provider.lower()
        if p == "openai": return self.OPENAI_API_KEY
        if p == "anthropic": return self.ANTHROPIC_API_KEY
        if p in ["google", "gemini"]: return self.GOOGLE_API_KEY or self.GEMINI_API_KEY
        if p == "deepseek": return self.DEEPSEEK_API_KEY
        if p == "kimi": return self.KIMI_API_KEY
        if p == "openrouter": return self.OPENROUTER_API_KEY
        if p == "mistral": return self.MISTRAL_API_KEY
        if p == "groq": return self.GROQ_API_KEY
        if p == "black_forest_labs": return self.BLACK_FOREST_LABS_API_KEY
        return None
    
    model_config = {"env_file": ".env", "extra": "ignore"}

settings = Settings()
print(f"DEBUG: TaleWeaver Debug Mode: {'ENABLED' if settings.TALEWEAVER_DEBUG_ENABLED else 'DISABLED'}")
logger.info(f"TaleWeaver Debug Mode: {'ENABLED' if settings.TALEWEAVER_DEBUG_ENABLED else 'DISABLED'}")
