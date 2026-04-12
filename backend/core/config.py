from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "TaleWeaver"
    DATABASE_URL: str = "sqlite+aiosqlite:///./taleweaver.db"
    
    class Config:
        env_file = ".env"

settings = Settings()
