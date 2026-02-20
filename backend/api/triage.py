"""
Triage API Router — The core clinical pipeline endpoint.

Flow:
  POST /api/triage/start    → NLP + create session → first question
  POST /api/triage/answer   → record answer → next question or result
  GET  /api/triage/result/{session_id} → fetch completed result
  GET  /api/triage/history  → user's past sessions
"""

import uuid
from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from db.database import get_db, Session as SessionModel, TriageResultModel, AuditLog
from schemas.models import (
    TriageStartRequest, AnswerRequest, TriageSessionState,
    TriageResult, QuestionResponse, AnswerType
)
from services import nlp_engine, safety_guardrails, adaptive_engine, risk_classifier
from services.patient_context import (
    create_session_context, get_session_context,
    record_answer, close_session, update_session_context
)
from core.logging import app_logger, anonymize
from datetime import datetime

router = APIRouter(prefix="/api/triage", tags=["Triage"])


@router.post("/start", response_model=TriageSessionState)
async def start_triage(
    data: TriageStartRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Step 1: Begin a triage session.
    Runs NLP on chief complaint, checks safety guardrails,
    initializes session, returns first follow-up question.
    """
    session_id = str(uuid.uuid4())

    # ── NLP Processing ──
    nlp_result = nlp_engine.process_text(
        data.chief_complaint,
        patient_age=data.patient_age,
        patient_gender=data.patient_gender.value if data.patient_gender else None,
    )

    symptoms = nlp_result["symptoms"]
    intent = nlp_result["intent"]
    language = nlp_result.get("language_detected", data.language)

    # ── Safety Guardrails (crisis check only) ──
    guardrail, reason = safety_guardrails.apply_guardrails(
        symptoms=symptoms,
        intent=intent,
        severity=nlp_result.get("severity_score"),
        age=data.patient_age,
        language=language,
        chief_complaint=data.chief_complaint,
    )

    # ── Create DB session record ──
    db_session = SessionModel(
        id=session_id,
        session_token=session_id,
        status="active",
        chief_complaint=data.chief_complaint,
        patient_age=data.patient_age,
        patient_gender=data.patient_gender.value if data.patient_gender else None,
    )
    db.add(db_session)

    # ── Audit log ──
    ip = request.client.host if request.client else "unknown"
    db.add(AuditLog(
        session_id=session_id,
        event_type="triage_started",
        event_data={"symptom_count": len(symptoms), "intent": intent, "language": language},
        ip_hash=anonymize(ip),
    ))

    # ── If immediate guardrail triggered → skip Q&A, return result ──
    if guardrail:
        await _save_guardrail_result(session_id, guardrail, symptoms, db, language)
        return TriageSessionState(
            session_id=session_id,
            status="completed",
            progress_percent=100,
            extracted_symptoms=symptoms,
            message=guardrail.get("reason", ""),
        )

    # ── Create Redis context ──
    context = await create_session_context(
        session_id=session_id,
        chief_complaint=data.chief_complaint,
        nlp_result=nlp_result,
        patient_age=data.patient_age,
        patient_gender=data.patient_gender.value if data.patient_gender else None,
        language=language,
    )

    # ── Get first question ──
    if not symptoms:
        # No symptoms found — ask clarifying question
        return TriageSessionState(
            session_id=session_id,
            status="active",
            current_question=QuestionResponse(
                question_id="clarify_symptoms",
                question_text="I didn't catch specific symptoms. Could you describe what you're feeling in more detail? (e.g., 'I have a headache and fever')",
                answer_type=AnswerType.text,
            ),
            progress_percent=0,
            extracted_symptoms=[],
        )

    next_q = await adaptive_engine.get_next_question_async(symptoms, {}, 0, data.chief_complaint)
    progress = adaptive_engine.compute_progress(symptoms, {}, data.chief_complaint)

    current_question = None
    if next_q:
        current_question = QuestionResponse(
            question_id=next_q["id"],
            question_text=next_q["text"],
            answer_type=AnswerType(next_q["type"]),
            options=next_q.get("options"),
        )

    return TriageSessionState(
        session_id=session_id,
        status="active",
        current_question=current_question,
        progress_percent=progress,
        extracted_symptoms=symptoms,
    )


@router.post("/answer", response_model=TriageSessionState)
async def submit_answer(
    data: AnswerRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Step 2: Submit an answer to a follow-up question.
    Returns the next question, or the completed result if done.
    """
    context = await get_session_context(data.session_id)
    if not context:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    if context["status"] == "completed":
        raise HTTPException(status_code=400, detail="Session already completed")

    # Record answer
    context = await record_answer(data.session_id, data.question_id, data.answer)
    symptoms = context["symptoms"]
    answered = context["answered"]

    # Re-check guardrails with new answer info (crisis check only)
    guardrail, reason = safety_guardrails.apply_guardrails(
        symptoms=symptoms,
        intent=context.get("intent", "symptom_report"),
        severity=context.get("severity_score"),
        age=context.get("patient_age"),
        answers=answered,
        language=context.get("language", "en"),
        chief_complaint=context.get("chief_complaint", ""),
    )

    if guardrail:
        await close_session(data.session_id)
        await _save_guardrail_result(data.session_id, guardrail, symptoms, db, context.get("language", "en"))
        return TriageSessionState(
            session_id=data.session_id,
            status="completed",
            progress_percent=100,
            extracted_symptoms=symptoms,
            message=guardrail.get("reason", ""),
        )

    # Get next question
    chief_complaint = context.get("chief_complaint", "")
    next_q = await adaptive_engine.get_next_question_async(symptoms, answered, context["question_index"], chief_complaint)
    progress = adaptive_engine.compute_progress(symptoms, answered, chief_complaint)

    if not next_q or progress >= 100:
        # ── All questions answered → run classification ──
        result = await _run_classification(data.session_id, context, db)
        await close_session(data.session_id)
        return TriageSessionState(
            session_id=data.session_id,
            status="completed",
            progress_percent=100,
            extracted_symptoms=symptoms,
        )

    current_question = QuestionResponse(
        question_id=next_q["id"],
        question_text=next_q["text"],
        answer_type=AnswerType(next_q["type"]),
        options=next_q.get("options"),
    )

    return TriageSessionState(
        session_id=data.session_id,
        status="active",
        current_question=current_question,
        progress_percent=progress,
        extracted_symptoms=symptoms,
    )


@router.get("/result/{session_id}", response_model=TriageResult)
async def get_result(session_id: str, db: AsyncSession = Depends(get_db)):
    """Fetch the final triage result for a completed session."""
    result_record = await db.execute(
        select(TriageResultModel).where(TriageResultModel.session_id == session_id)
    )
    result = result_record.scalar_one_or_none()
    if not result:
        raise HTTPException(status_code=404, detail="Result not found. Session may still be active.")

    shap_feats = result.shap_values or []
    return TriageResult(
        session_id=session_id,
        triage_label=result.triage_label,
        confidence=result.confidence or 0.7,
        probabilities=result.probabilities or {},
        red_flag_triggered=result.red_flag_triggered,
        red_flag_reason=result.red_flag_reason,
        explanation_text=result.explanation_text or "",
        recommended_action=result.recommended_action or "",
        diseases_considered=result.diseases_considered or [],
        shap_features=shap_feats,
        remedies=result.remedies or [],
        nutrition_tips=result.nutrition_tips or [],
        crisis_response=result.crisis_response,
    )


@router.get("/history")
async def get_history(
    db: AsyncSession = Depends(get_db),
):
    """Get recent triage sessions."""
    sessions_result = await db.execute(
        select(SessionModel, TriageResultModel)
        .outerjoin(TriageResultModel, SessionModel.id == TriageResultModel.session_id)
        .order_by(SessionModel.started_at.desc())
        .limit(20)
    )
    rows = sessions_result.all()
    history = []
    for session, result in rows:
        history.append({
            "session_id": str(session.id),
            "started_at": session.started_at.isoformat(),
            "status": session.status,
            "chief_complaint": session.chief_complaint,
            "triage_label": result.triage_label if result else None,
            "confidence": result.confidence if result else None,
        })
    return {"sessions": history}


# ── Internal helpers ──

async def _save_guardrail_result(session_id, guardrail, symptoms, db, language):
    """Persist a guardrail-triggered result to DB."""
    rn = adaptive_engine.get_remedies_nutrition(symptoms)
    is_crisis = guardrail.get("is_crisis", False)
    crisis_info = guardrail.get("crisis_info", {})

    action = guardrail.get("action", "Seek emergency care immediately.")
    if is_crisis:
        resources = crisis_info.get("resources", [])
        if resources:
            action += " | " + " | ".join(f"{r['name']}: {r['number']}" for r in resources)

    db.add(TriageResultModel(
        id=str(uuid.uuid4()),
        session_id=session_id,
        triage_label="Emergency",
        confidence=1.0,
        probabilities={"HomeCare": 0.0, "Urgent": 0.0, "Emergency": 1.0},
        red_flag_triggered=True,
        red_flag_reason=guardrail.get("reason"),
        explanation_text=guardrail.get("reason", "High-risk presentation detected."),
        recommended_action=action,
        diseases_considered=[],
        remedies=rn.get("remedies", []),
        nutrition_tips=rn.get("nutrition_tips", []),
        crisis_response=is_crisis,
    ))


async def _run_classification(session_id, context, db):
    """Run Gemini-powered classification and save result to DB."""
    symptoms = context["symptoms"]
    answered = context["answered"]

    bayesian_urgency = adaptive_engine.bayesian_urgency_update("HomeCare", answered, symptoms)
    diseases = adaptive_engine.get_diseases_for_symptoms(symptoms)
    rn = adaptive_engine.get_remedies_nutrition(symptoms)

    clf_result = risk_classifier.classify_triage(
        symptoms=symptoms,
        severity=context.get("severity_score"),
        duration_hours=context.get("duration_hours"),
        age=context.get("patient_age"),
        comorbidities=context.get("comorbidities", []),
        bayesian_urgency=bayesian_urgency,
        answers=answered,
        chief_complaint=context.get("chief_complaint", ""),
        gender=context.get("patient_gender"),
    )

    db.add(TriageResultModel(
        id=str(uuid.uuid4()),
        session_id=session_id,
        triage_label=clf_result["triage_label"],
        confidence=clf_result["confidence"],
        probabilities=clf_result["probabilities"],
        red_flag_triggered=False,
        shap_values=clf_result.get("shap_features", []),
        explanation_text=clf_result["explanation_text"],
        recommended_action=clf_result["recommended_action"],
        diseases_considered=diseases,
        remedies=rn.get("remedies", []),
        nutrition_tips=rn.get("nutrition_tips", []),
        crisis_response=False,
    ))
    return clf_result
