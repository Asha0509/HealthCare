import os
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    APP_NAME: str = "AI Healthcare Triage System"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False

    # Security
    SECRET_KEY: str = "supersecret-change-in-production-32chars"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./health_triage.db"  # SQLite for local dev
    # DATABASE_URL: str = "postgresql+asyncpg://healthuser:healthpass123@localhost:5432/healthtriage"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    SESSION_EXPIRE_SECONDS: int = 3600  # 1 hour
    USE_MEMORY_SESSION: bool = True  # Use in-memory sessions instead of Redis

    # External APIs
    GOOGLE_MAPS_API_KEY: str = ""
    GEMINI_API_KEY: str = ""  # Set via environment variable or .env file

    # Data paths - use parent directory since data is at project root
    DATA_DIR: str = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
    MODELS_DIR: str = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "models")

    # NLP
    SPACY_MODEL: str = "en_core_sci_md"
    USE_SCISPACY: bool = True

    # ML Model
    TRIAGE_MODEL_PATH: str = ""  # Set after training

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
