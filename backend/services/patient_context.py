"""
Patient Context Engine
-----------------------
Manages patient context across the session lifecycle:
- Aggregates all extracted data into a unified patient profile
- Tracks symptom progression
- Maintains session state in Redis or in-memory (for local dev)
"""

import json
import uuid
from typing import Dict, List, Optional
from core.config import settings
from core.logging import app_logger

# In-memory session store (for local dev without Redis)
_memory_sessions: Dict[str, str] = {}

_redis_client = None


async def get_redis():
    global _redis_client
    if settings.USE_MEMORY_SESSION:
        return None  # Use in-memory store
    if _redis_client is None:
        import redis.asyncio as aioredis
        _redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


def make_session_key(session_id: str) -> str:
    return f"triage:session:{session_id}"


async def create_session_context(
    session_id: str,
    chief_complaint: str,
    nlp_result: Dict,
    patient_age: Optional[int] = None,
    patient_gender: Optional[str] = None,
    language: str = "en",
    user_id: Optional[str] = None,
) -> Dict:
    """Initialize session context in Redis or in-memory."""
    context = {
        "session_id": session_id,
        "user_id": user_id or "",
        "chief_complaint": chief_complaint,
        "language": language,
        "patient_age": patient_age,
        "patient_gender": patient_gender,
        "symptoms": nlp_result.get("symptoms", []),
        "severity_score": nlp_result.get("severity_score"),
        "duration_hours": nlp_result.get("duration_hours"),
        "duration_text": nlp_result.get("duration_text"),
        "intent": nlp_result.get("intent", "symptom_report"),
        "answered": {},          # {question_id: answer}
        "question_index": 0,
        "status": "active",
        "comorbidities": [],
    }
    key = make_session_key(session_id)
    if settings.USE_MEMORY_SESSION:
        _memory_sessions[key] = json.dumps(context)
    else:
        redis = await get_redis()
        await redis.setex(key, settings.SESSION_EXPIRE_SECONDS, json.dumps(context))
    app_logger.info(f"Session {session_id} created with symptoms: {context['symptoms']}")
    return context


async def get_session_context(session_id: str) -> Optional[Dict]:
    """Load session context from Redis or in-memory."""
    key = make_session_key(session_id)
    if settings.USE_MEMORY_SESSION:
        data = _memory_sessions.get(key)
    else:
        redis = await get_redis()
        data = await redis.get(key)
    if not data:
        return None
    return json.loads(data)


async def update_session_context(session_id: str, updates: Dict) -> Optional[Dict]:
    """Merge updates into session context."""
    context = await get_session_context(session_id)
    if context is None:
        return None
    context.update(updates)
    key = make_session_key(session_id)
    if settings.USE_MEMORY_SESSION:
        _memory_sessions[key] = json.dumps(context)
    else:
        redis = await get_redis()
        await redis.setex(key, settings.SESSION_EXPIRE_SECONDS, json.dumps(context))
    return context


async def record_answer(session_id: str, question_id: str, answer: str) -> Optional[Dict]:
    """Store a Q&A answer and advance question index."""
    context = await get_session_context(session_id)
    if context is None:
        return None
    context["answered"][question_id] = answer
    context["question_index"] += 1
    return await update_session_context(session_id, context)


async def close_session(session_id: str) -> None:
    """Mark session as completed."""
    await update_session_context(session_id, {"status": "completed"})


async def delete_session(session_id: str) -> None:
    """Clean up session from Redis or in-memory."""
    key = make_session_key(session_id)
    if settings.USE_MEMORY_SESSION:
        _memory_sessions.pop(key, None)
    else:
        redis = await get_redis()
        await redis.delete(key)
