"""
Triage API.

  POST /api/triage/start               complaint -> red-flag check -> first question (or result)
  POST /api/triage/answer              validated answer -> next question (or result)
  GET  /api/triage/result/{session_id} completed result with agent trace and citations
  POST /api/triage/assess              one-shot assessment (sample cases, evals, API clients)
  GET  /api/triage/history             recent sessions (server side)
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from core.logging import anonymize, app_logger
from db.database import AuditLog, Session as SessionModel, TriageResultModel, get_db
from schemas.models import (AnswerRequest, AnswerType, AssessRequest, QuestionResponse, TriageResult,
                            TriageSessionState, TriageStartRequest)
from services import adaptive_engine, answers as answer_rules, nlp_engine, observability, red_flags
from services.agent import Case, assess
from services.patient_context import (close_session, create_session_context, get_session_context,
                                      update_session_context)

router = APIRouter(prefix="/api/triage", tags=["Triage"])

MAX_QUESTIONS = 6  # keep sessions short; red-flag questions are asked first


def _question_index() -> Dict[str, Dict]:
    return {q["id"]: q for node in adaptive_engine._get_kg().values() for q in node["follow_up_questions"]}


def _question_out(q: Dict) -> QuestionResponse:
    qtype, options = answer_rules.presentation(q)
    return QuestionResponse(question_id=q["id"], question_text=q["text"], answer_type=AnswerType(qtype),
                            options=options)


def _case_from_context(ctx: Dict) -> Case:
    qindex = _question_index()
    return Case(
        complaint=ctx.get("chief_complaint", ""),
        age=ctx.get("patient_age"),
        gender=ctx.get("patient_gender"),
        symptoms=ctx.get("symptoms", []),
        answers=ctx.get("answered", {}),
        questions={qid: qindex[qid]["text"] for qid in ctx.get("answered", {}) if qid in qindex},
        severity=ctx.get("severity_score"),
        duration_hours=ctx.get("duration_hours"),
    )


async def _next_question(ctx: Dict) -> Optional[Dict]:
    if len(ctx.get("answered", {})) >= MAX_QUESTIONS:
        return None
    return await adaptive_engine.get_next_question_async(
        ctx["symptoms"], ctx["answered"], ctx.get("question_index", 0), ctx.get("chief_complaint", ""))


def _progress(ctx: Dict) -> int:
    total = min(MAX_QUESTIONS, max(1, len(adaptive_engine.get_questions_for_symptoms(
        ctx["symptoms"], ctx.get("chief_complaint", "")))))
    return min(99, int(100 * len(ctx.get("answered", {})) / total))


async def _finalise(session_id: str, ctx: Dict, db: AsyncSession) -> Dict:
    """Run the assessment pipeline (agent + safety rules) and persist the result."""
    case = _case_from_context(ctx)
    result = await run_in_threadpool(assess, case, session_id, "web")
    await close_session(session_id)
    db.add(TriageResultModel(
        id=str(uuid.uuid4()),
        session_id=session_id,
        triage_label=result["triage_label"],
        confidence=None,
        probabilities=result["probabilities"],
        red_flag_triggered=result["red_flag_triggered"],
        red_flag_reason="; ".join(f["reason"] for f in result["red_flags"]) or None,
        explanation_text=result["explanation_text"],
        recommended_action=result["recommended_action"],
        diseases_considered=result["conditions_to_consider"],
        remedies=result["self_care"],
        nutrition_tips=result["nutrition_tips"],
        medications=[],
        crisis_response=result["crisis_response"],
        details={k: result[k] for k in ("proposed_label", "escalated", "red_flags", "key_factors", "citations",
                                        "decision_path", "fallback_reason", "provider", "model", "llm_calls",
                                        "tool_calls", "latency_ms", "agent_steps", "symptoms")},
    ))
    sess = await db.get(SessionModel, session_id)
    if sess:
        sess.status = "completed"
        sess.completed_at = datetime.utcnow()
    return result


def _completed(session_id: str, ctx: Dict, message: Optional[str] = None) -> TriageSessionState:
    return TriageSessionState(session_id=session_id, status="completed", progress_percent=100,
                              extracted_symptoms=ctx.get("symptoms", []), message=message)


@router.post("/start", response_model=TriageSessionState)
async def start_triage(data: TriageStartRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """Begin a session: extract symptoms, check red flags, return the first question or a result."""
    session_id = str(uuid.uuid4())
    gender = data.patient_gender.value if data.patient_gender else None
    with observability.tagged(session_id, "symptom_extraction"):
        nlp = await run_in_threadpool(nlp_engine.process_text, data.chief_complaint, data.patient_age, gender)

    db.add(SessionModel(id=session_id, session_token=session_id, status="active",
                        chief_complaint=data.chief_complaint, patient_age=data.patient_age, patient_gender=gender))
    ip = request.client.host if request.client else "unknown"
    db.add(AuditLog(session_id=session_id, event_type="triage_started",
                    event_data={"symptom_count": len(nlp["symptoms"]), "intent": nlp["intent"]},
                    ip_hash=anonymize(ip)))

    ctx = await create_session_context(session_id=session_id, chief_complaint=data.chief_complaint,
                                       nlp_result=nlp, patient_age=data.patient_age, patient_gender=gender,
                                       language=nlp.get("language_detected", data.language))

    flags = red_flags.scan_case(data.chief_complaint, {}, data.patient_age, nlp["symptoms"])
    if red_flags.highest_level(flags) == "Emergency":
        await _finalise(session_id, ctx, db)
        return _completed(session_id, ctx, flags[0].reason)

    if not nlp["symptoms"]:
        return TriageSessionState(
            session_id=session_id, status="active", progress_percent=0, extracted_symptoms=[],
            current_question=QuestionResponse(
                question_id="clarify_symptoms", answer_type=AnswerType.text,
                question_text="I couldn't pick out specific symptoms. Could you describe what you're feeling, "
                              "for example 'headache and fever since yesterday'?"))

    next_q = await _next_question(ctx)
    if not next_q:
        await _finalise(session_id, ctx, db)
        return _completed(session_id, ctx)
    return TriageSessionState(session_id=session_id, status="active", current_question=_question_out(next_q),
                              progress_percent=_progress(ctx), extracted_symptoms=nlp["symptoms"])


@router.post("/answer", response_model=TriageSessionState)
async def submit_answer(data: AnswerRequest, db: AsyncSession = Depends(get_db)):
    """Record a validated answer; return the next question or finish the assessment."""
    ctx = await get_session_context(data.session_id)
    if not ctx:
        raise HTTPException(status_code=404, detail="Session not found or expired. Please start again.")
    if ctx["status"] == "completed":
        raise HTTPException(status_code=400, detail="This assessment is already complete.")

    if data.question_id == "clarify_symptoms":
        text = data.answer.strip()
        if len(text) < 3:
            raise HTTPException(status_code=422, detail="Please describe your symptoms in a few words.")
        with observability.tagged(data.session_id, "symptom_extraction"):
            nlp = await run_in_threadpool(nlp_engine.process_text, text, ctx.get("patient_age"),
                                          ctx.get("patient_gender"))
        ctx["chief_complaint"] = f"{ctx['chief_complaint']}. {text}"
        ctx["symptoms"] = list(dict.fromkeys(ctx["symptoms"] + nlp["symptoms"]))
        for key in ("severity_score", "duration_hours"):
            if nlp.get(key) is not None:
                ctx[key] = nlp[key]
    else:
        question = _question_index().get(data.question_id)
        if question is None:
            raise HTTPException(status_code=422, detail="Unknown question.")
        try:
            value = answer_rules.normalise(question, data.answer)
        except answer_rules.AnswerError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        ctx["answered"][data.question_id] = value
        ctx["question_index"] = ctx.get("question_index", 0) + 1
        ctx.update(answer_rules.case_updates(question, value))
    ctx = await update_session_context(data.session_id, ctx)

    flags = red_flags.scan_case(ctx["chief_complaint"], ctx["answered"], ctx.get("patient_age"), ctx["symptoms"])
    if red_flags.highest_level(flags) == "Emergency":
        await _finalise(data.session_id, ctx, db)
        return _completed(data.session_id, ctx, flags[0].reason)

    if not ctx["symptoms"]:
        return TriageSessionState(
            session_id=data.session_id, status="active", progress_percent=0, extracted_symptoms=[],
            current_question=QuestionResponse(
                question_id="clarify_symptoms", answer_type=AnswerType.text,
                question_text="I still couldn't match that to symptoms I know. Try simple words like "
                              "'cough', 'stomach pain', 'dizzy' or 'rash'."))

    next_q = await _next_question(ctx)
    if not next_q:
        await _finalise(data.session_id, ctx, db)
        return _completed(data.session_id, ctx)
    return TriageSessionState(session_id=data.session_id, status="active", current_question=_question_out(next_q),
                              progress_percent=_progress(ctx), extracted_symptoms=ctx["symptoms"])


@router.get("/result/{session_id}", response_model=TriageResult)
async def get_result(session_id: str, db: AsyncSession = Depends(get_db)):
    row = (await db.execute(select(TriageResultModel).where(TriageResultModel.session_id == session_id))
           ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Result not found. The assessment may still be in progress.")
    sess = await db.get(SessionModel, session_id)
    d = row.details or {}
    return TriageResult(
        session_id=session_id,
        triage_label=row.triage_label,
        proposed_label=d.get("proposed_label"),
        escalated=d.get("escalated", False),
        probabilities=row.probabilities,
        red_flag_triggered=row.red_flag_triggered,
        red_flags=d.get("red_flags", []),
        explanation_text=row.explanation_text or "",
        recommended_action=row.recommended_action or "",
        key_factors=d.get("key_factors", []),
        conditions_to_consider=row.diseases_considered or [],
        self_care=row.remedies or [],
        nutrition_tips=row.nutrition_tips or [],
        citations=d.get("citations", []),
        crisis_response=row.crisis_response,
        decision_path=d.get("decision_path", "rules"),
        fallback_reason=d.get("fallback_reason"),
        provider=d.get("provider"),
        model=d.get("model"),
        llm_calls=d.get("llm_calls", 0),
        tool_calls=d.get("tool_calls", 0),
        latency_ms=d.get("latency_ms"),
        agent_steps=d.get("agent_steps", []),
        symptoms=d.get("symptoms", []),
        chief_complaint=sess.chief_complaint if sess else None,
        created_at=row.created_at.isoformat() + "Z" if row.created_at else None,
    )


@router.post("/assess", response_model=TriageResult)
async def assess_once(data: AssessRequest):
    """Assess a case in one call: no follow-up questions, answers optional."""
    session_id = f"{data.source}-{uuid.uuid4()}"
    gender = data.patient_gender.value if data.patient_gender else None
    with observability.tagged(session_id, "symptom_extraction"):
        nlp = await run_in_threadpool(nlp_engine.process_text, data.chief_complaint, data.patient_age, gender)
    qindex = _question_index()
    clean: Dict[str, str] = {}
    severity, duration = nlp.get("severity_score"), nlp.get("duration_hours")
    for qid, raw in (data.answers or {}).items():
        q = qindex.get(qid)
        if not q:
            raise HTTPException(status_code=422, detail=f"Unknown question id: {qid}")
        try:
            clean[qid] = answer_rules.normalise(q, str(raw))
        except answer_rules.AnswerError as exc:
            raise HTTPException(status_code=422, detail=f"{qid}: {exc}")
        upd = answer_rules.case_updates(q, clean[qid])
        severity = upd.get("severity_score", severity)
        duration = upd.get("duration_hours", duration)
    case = Case(complaint=data.chief_complaint, age=data.patient_age, gender=gender, symptoms=nlp["symptoms"],
                answers=clean, questions={k: qindex[k]["text"] for k in clean}, severity=severity,
                duration_hours=duration)
    result = await run_in_threadpool(assess, case, session_id, data.source, data.use_llm)
    return TriageResult(session_id=session_id, chief_complaint=data.chief_complaint,
                        created_at=datetime.utcnow().isoformat() + "Z", **result)


@router.get("/history")
async def get_history(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(SessionModel, TriageResultModel)
        .outerjoin(TriageResultModel, SessionModel.id == TriageResultModel.session_id)
        .order_by(SessionModel.started_at.desc()).limit(20))).all()
    return {"sessions": [{
        "session_id": str(s.id), "started_at": s.started_at.isoformat(), "status": s.status,
        "chief_complaint": s.chief_complaint, "triage_label": r.triage_label if r else None,
    } for s, r in rows]}
