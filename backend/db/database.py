from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, JSON
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
import uuid
from core.config import settings

# Use JSON for both SQLite and PostgreSQL compatibility
# UUID stored as String for SQLite compatibility
Base = declarative_base()
engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG, pool_pre_ping=True)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    """Create all tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


class User(Base):
    __tablename__ = "users"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255))
    age = Column(Integer)
    gender = Column(String(20))
    comorbidities = Column(JSON, default=[])  # JSON instead of ARRAY
    language_preference = Column(String(10), default="en")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)


class Session(Base):
    __tablename__ = "sessions"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), nullable=True)
    session_token = Column(String(255), unique=True, nullable=False)
    status = Column(String(20), default="active")
    chief_complaint = Column(Text)
    patient_age = Column(Integer)
    patient_gender = Column(String(20))
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    question_index = Column(Integer, default=0)
    total_questions = Column(Integer, default=0)


class TriageResultModel(Base):
    __tablename__ = "triage_results"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), nullable=False)
    triage_label = Column(String(30), nullable=False)
    confidence = Column(Float)
    probabilities = Column(JSON)  # JSON instead of JSONB
    red_flag_triggered = Column(Boolean, default=False)
    red_flag_reason = Column(Text)
    shap_values = Column(JSON)  # JSON instead of JSONB
    explanation_text = Column(Text)
    recommended_action = Column(Text)
    diseases_considered = Column(JSON, default=[])  # JSON instead of ARRAY
    remedies = Column(JSON, default=[])  # JSON instead of ARRAY
    nutrition_tips = Column(JSON, default=[])  # JSON instead of ARRAY
    crisis_response = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36))
    event_type = Column(String(100), nullable=False)
    event_data = Column(JSON)  # JSON instead of JSONB
    ip_hash = Column(String(64))
    created_at = Column(DateTime, default=datetime.utcnow)
