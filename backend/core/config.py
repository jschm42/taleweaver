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
    # Default restricted to loopback + common local-dev / test hostnames;
    # explicitly set "*" for Docker-behind-nginx, or set a comma-separated list
    # (e.g. "taleweaver.example.com,www.example.com") for a public deployment
    # behind a reverse proxy that performs TLS termination.
    ALLOWED_HOSTS: str = "localhost,127.0.0.1,0.0.0.0,taleweaver,test,testserver"

    @property
    def allowed_hosts_list(self) -> list[str]:
        """Return ALLOWED_HOSTS as a list, splitting on commas."""
        return [h.strip() for h in self.ALLOWED_HOSTS.split(",") if h.strip()]


    DATA_DIR: str = "data"
    # When set, LLM debug logs are written here (recommended: outside DATA_DIR).
    # When unset (default), logs are written to DATA_DIR/logs — in that case
    # the SafeStaticFiles mount blocks access to .jsonl files via HTTP.
    LLM_LOG_DIR: Optional[str] = None
    # Master switch for the JSONL LLM telemetry log. Persists every LLM
    # round-trip (system_prompt, user_prompt, raw response, token usage) to
    # disk — must be opted in explicitly. Default off.
    LLM_TELEMETRY_ENABLED: bool = False
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

    # SSRF: allow private/loopback hosts in user-supplied URLs (Ollama, Automatic1111, etc.)
    # Default False rejects calls to 127.0.0.1, ::1, RFC1918 ranges, link-local, etc.
    ALLOW_PRIVATE_NETWORK_MODELS: bool = True

    # setup-root hardening: allow the bootstrap endpoint to be reached from
    # non-loopback addresses. Must be explicitly enabled; defaults to False.
    ALLOW_REMOTE_SETUP: bool = False

    # Toggle Strict-Transport-Security header (production deployments should
    # leave this on; development behind plain HTTP may want to disable it to
    # avoid browsers caching the HSTS directive locally).
    ENABLE_HSTS: bool = True

    # Hard upper bound on number of scenes before AI validation is skipped.
    # Larger adventures overflow typical LLM context windows and incur
    # disproportionate cost. Structural validation always runs regardless.
    # Only relevant for the manual "Run full validation" button in the
    # editor's Validation tab; structural-only saves are never affected.
    MAX_AI_VALIDATION_SCENES: int = 50

    # Validation panel limits.
    # Hard upper bound on number of scenes before AI validation is skipped.
    # Larger adventures overflow typical LLM context windows and incur
    # disproportionate cost. Structural validation always runs regardless.
    MAX_AI_VALIDATION_SCENES: int = 50

    # Per-user rate limit on POST /editor/validate (covers both modes).
    VALIDATION_RATE_LIMIT_MAX: int = 5
    VALIDATION_RATE_LIMIT_WINDOW_SECONDS: int = 60

    # Hard wall-clock cap on a single AI fix-suggestion round. Even if the
    # upstream provider hangs past its own request_timeout, this watchdog
    # returns control to the client so we can show a clean inline retry.
    AI_FIX_SUGGEST_TIMEOUT_SECONDS: float = 30.0

    # Provider/model used as a fallback when the user's configured
    # complex_model_provider times out or errors. Empty string disables
    # the fallback and surfaces the original error to the caller.
    AI_FIX_FALLBACK_PROVIDER: str = "openai"
    AI_FIX_FALLBACK_MODEL: str = "gpt-4o-mini"

    # Maximum number of HTTPS scheme bytes accepted in user-supplied URLs.
    MAX_PROVIDER_URL_LENGTH: int = 512

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

    # ENCRYPTION_KEY MUST be set; we no longer silently fall back to an
    # ephemeral key. Generate one with `python scripts/generate_fernet_key.py`.
    ENCRYPTION_KEY: Optional[str] = None
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
    MINIMAX_API_KEY: Optional[str] = None
    MINIMAX_API_BASE: str = "https://api.minimax.io/v1"

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
        if p == "minimax": return self.MINIMAX_API_KEY
        return None
    
    model_config = {"env_file": ".env", "extra": "ignore"}

settings = Settings()
print(f"DEBUG: TaleWeaver Debug Mode: {'ENABLED' if settings.TALEWEAVER_DEBUG_ENABLED else 'DISABLED'}")
logger.info(f"TaleWeaver Debug Mode: {'ENABLED' if settings.TALEWEAVER_DEBUG_ENABLED else 'DISABLED'}")
