import os
from functools import lru_cache

from pydantic_settings import BaseSettings


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
    GEMINI_API_KEY: str = ""  # Backward compatibility for existing env files
    GROQ_API_KEY: str = ""  # Primary LLM provider key (Groq)
    GROQ_MODEL: str = "openai/gpt-oss-120b"
    NVIDIA_NIM_API_KEY: str = ""  # Optional fallback LLM provider
    NVIDIA_NIM_MODEL: str = "openai/gpt-oss-20b"

    # Optional decision model (second opinion with conformal prediction sets); off by default.
    # Any server exposing POST {SYSTEMONE_URL}/v1/systemone works (hosted, or an open-weights model served locally).
    DECISION_MODEL: str = "off"  # off | systemone
    SYSTEMONE_URL: str = ""
    SYSTEMONE_API_KEY: str = ""
    SYSTEMONE_MODEL: str = "typed-decisions"
    SYSTEMONE_TIMEOUT: float = 20.0
    CONFORMAL_PATH: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models", "conformal.json")

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


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
