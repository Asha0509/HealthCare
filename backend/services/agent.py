"""
Triage agent.

Pipeline for one case:
  1. Deterministic red-flag rules (always run, no AI).
  2. If a self-harm crisis is detected -> crisis response, no AI involved.
  3. Otherwise an LLM agent works the case with tools:
       lookup_symptom    - symptom graph facts (base urgency, conditions)
       search_knowledge  - RAG over the curated knowledge base
       check_red_flags   - run the deterministic rules on any text
       submit_assessment - structured final answer (ends the loop)
  4. If no LLM is configured or the agent fails, a rule-based assessment
     is used instead and the reason is recorded.
  5. Safety merge: the final level is the HIGHER of the AI/rules level and the
     strongest red flag. The AI can never downgrade a red flag.

Every step is recorded in a trace that the result page shows, and the run is
logged to the observability store.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.config import settings
from core.logging import app_logger

from services import adaptive_engine, decision_model, llm_client, observability, red_flags
from services.rag import retriever

LABELS = ["HomeCare", "Urgent", "Emergency"]
MAX_LLM_TURNS = 6
NO_WARNING_FACTOR = "no warning signs found in your answers"

ACTIONS = {
    "Emergency": "Call emergency services (112) or go to the nearest emergency department now.",
    "Urgent": "See a doctor today or within 24 hours. If things get worse, go to an emergency department.",
    "HomeCare": "You can likely manage this at home. See a doctor if it gets worse or doesn't improve in a few days.",
}


@dataclass
class Case:
    complaint: str
    age: Optional[int] = None
    gender: Optional[str] = None
    symptoms: List[str] = field(default_factory=list)
    answers: Dict[str, str] = field(default_factory=dict)       # question_id -> answer
    questions: Dict[str, str] = field(default_factory=dict)     # question_id -> question text
    severity: Optional[float] = None
    duration_hours: Optional[float] = None

    def summary(self) -> str:
        lines = [f"Chief complaint: {self.complaint}"]
        if self.age is not None:
            lines.append(f"Age: {self.age}")
        if self.gender:
            lines.append(f"Gender: {self.gender}")
        if self.symptoms:
            lines.append("Symptoms identified: " + ", ".join(self.symptoms))
        if self.severity is not None:
            lines.append(f"Self-rated severity: {self.severity:g}/10")
        if self.duration_hours is not None:
            lines.append(f"Duration: about {_human_duration(self.duration_hours)}")
        if self.answers:
            lines.append("Follow-up answers:")
            for qid, ans in self.answers.items():
                lines.append(f"- {self.questions.get(qid, qid)} -> {ans}")
        return "\n".join(lines)


def _human_duration(hours: float) -> str:
    if hours < 24:
        return f"{hours:g} hours"
    if hours < 24 * 14:
        return f"{hours / 24:.0f} days"
    return f"{hours / 168:.0f} weeks"


# ── Tools ────────────────────────────────────────────────────────────────

def _kg() -> Dict:
    return adaptive_engine._get_kg()


def tool_specs() -> List[Dict]:
    symptom_enum = sorted(_kg().keys())
    return [
        {"type": "function", "function": {
            "name": "lookup_symptom",
            "description": "Facts about one symptom from the clinical symptom graph: its baseline urgency, "
                           "whether it is a red-flag symptom, and conditions commonly associated with it.",
            "parameters": {"type": "object", "properties": {
                "symptom": {"type": "string", "enum": symptom_enum}}, "required": ["symptom"]}}},
        {"type": "function", "function": {
            "name": "search_knowledge",
            "description": "Search the curated knowledge base for self-care advice, when to see a doctor, and "
                           "emergency warning signs. Returns passages with chunk_id values you can cite.",
            "parameters": {"type": "object", "properties": {
                "query": {"type": "string", "description": "What to look up, in plain words."}},
                "required": ["query"]}}},
        {"type": "function", "function": {
            "name": "check_red_flags",
            "description": "Run the deterministic emergency red-flag rules on a piece of text. Any level these "
                           "rules return is a floor: your assessment cannot be lower.",
            "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}}},
        {"type": "function", "function": {
            "name": "submit_assessment",
            "description": "Submit the final triage assessment. Call exactly once, at the end.",
            "parameters": {"type": "object", "properties": {
                "triage_label": {"type": "string", "enum": LABELS},
                "probabilities": {"type": "object", "description": "Your probability for each level, summing to 1.",
                                  "properties": {k: {"type": "number"} for k in LABELS}},
                "explanation": {"type": "string", "description": "2-3 plain sentences explaining the level."},
                "recommended_action": {"type": "string"},
                "key_factors": {"type": "array", "items": {"type": "string"}},
                "conditions_to_consider": {"type": "array", "items": {"type": "string"}},
                "self_care": {"type": "array", "items": {"type": "string"}},
                "citations": {"type": "array", "items": {"type": "string"},
                              "description": "chunk_id values from search_knowledge that support your advice."},
            }, "required": ["triage_label", "explanation", "recommended_action"]}}},
    ]


def run_tool(name: str, args: Dict[str, Any], case: Case, retrieved: Dict[str, Dict]) -> Dict:
    if name == "lookup_symptom":
        node = _kg().get(args.get("symptom", ""))
        if not node:
            return {"error": "unknown symptom"}
        return {"symptom": args["symptom"], "base_urgency": node.get("base_urgency"),
                "red_flag_symptom": node.get("red_flag", False),
                "associated_conditions": [d.replace("_", " ") for d in node.get("diseases", [])][:7]}
    if name == "search_knowledge":
        hits = retriever.search(str(args.get("query", "")), k=3, symptoms=case.symptoms)
        for h in hits:
            retrieved[h["chunk_id"]] = h
        return {"results": [{"chunk_id": h["chunk_id"], "title": h["title"], "section": h["section"],
                             "text": h["text"]} for h in hits]}
    if name == "check_red_flags":
        flags = red_flags.scan_text(str(args.get("text", "")))
        return {"red_flags": [f.to_dict() for f in flags],
                "floor_level": red_flags.highest_level(flags) or "none"}
    return {"error": f"unknown tool {name}"}


SYSTEM_PROMPT = """You are a careful clinical triage assistant inside a decision-support demo.
Decide how urgently the person should get care:
- Emergency: possibly life-threatening, needs emergency care now.
- Urgent: should see a doctor within about 24 hours.
- HomeCare: can be managed at home with self-care and monitoring.

Work the case with your tools before deciding:
1. lookup_symptom for the main symptoms.
2. search_knowledge for self-care and warning signs relevant to this person.
3. check_red_flags on anything in the answers that sounds worrying.
Then call submit_assessment exactly once.

Rules:
- The deterministic red flags already found are listed in the case. Your level must not be lower than them.
- Be conservative with chest pain, breathing problems, neurological symptoms, pregnancy, infants and older adults.
- Most common, mild, short-lived symptoms without warning signs are HomeCare.
- Cite only chunk_id values returned by search_knowledge. Do not invent sources.
- Do not recommend prescription medicines or doses. Plain language, no jargon.
"""


def _assistant_message(result: llm_client.ChatResult) -> Dict:
    msg: Dict[str, Any] = {"role": "assistant", "content": result.content or ""}
    if result.tool_calls:
        msg["tool_calls"] = [{"id": tc["id"], "type": "function",
                              "function": {"name": tc["name"], "arguments": json.dumps(tc["arguments"])}}
                             for tc in result.tool_calls]
    return msg


def _short(obj: Any, n: int = 220) -> str:
    s = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False)
    return s if len(s) <= n else s[: n - 1] + "…"


def run_agent(case: Case, flags: List[red_flags.RedFlag], trace: List[Dict]) -> Optional[Dict]:
    """Run the tool-calling loop. Returns the submitted assessment plus metadata, or None on failure."""
    flag_text = "\n".join(f"- [{f.level}] {f.reason}" for f in flags) or "- none"
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"{case.summary()}\n\nDeterministic red flags already found:\n{flag_text}"},
    ]
    tools = tool_specs()
    retrieved: Dict[str, Dict] = {}
    llm_calls = tool_calls = 0
    nudged = False
    last: Optional[llm_client.ChatResult] = None

    for _turn in range(MAX_LLM_TURNS):
        result = llm_client.chat(messages, tools=tools, temperature=0.1, max_tokens=900)
        llm_calls += 1
        if result is None:
            trace.append({"kind": "llm", "name": "chat", "ok": False, "summary": "all providers failed"})
            return None
        last = result
        trace.append({"kind": "llm", "name": "chat", "ok": True, "provider": result.provider,
                      "model": result.model, "ms": round(result.latency_ms),
                      "summary": (f"requested {', '.join(tc['name'] for tc in result.tool_calls)}"
                                  if result.tool_calls else _short(result.content or "(empty)")),
                      "failovers": result.errors})
        messages.append(_assistant_message(result))

        if not result.tool_calls:
            if nudged:
                break
            nudged = True
            messages.append({"role": "user", "content": "Call submit_assessment now with your final assessment."})
            continue

        for tc in result.tool_calls:
            tool_calls += 1
            if tc["name"] == "submit_assessment":
                shown = {k: v for k, v in tc["arguments"].items() if k != "recommended_action"}  # ignored; fixed table is used
                trace.append({"kind": "tool", "name": "submit_assessment", "args": shown,
                              "summary": f"label={tc['arguments'].get('triage_label')}"})
                return {"submission": tc["arguments"], "retrieved": retrieved, "llm_calls": llm_calls,
                        "tool_calls": tool_calls, "provider": result.provider, "model": result.model}
            started = time.perf_counter()
            output = run_tool(tc["name"], tc["arguments"], case, retrieved)
            trace.append({"kind": "tool", "name": tc["name"], "args": tc["arguments"],
                          "ms": round((time.perf_counter() - started) * 1000, 1), "summary": _short(output)})
            messages.append({"role": "tool", "tool_call_id": tc["id"], "content": json.dumps(output)})

    # No tool submission: accept a JSON answer in plain content as a last resort.
    if last and last.content:
        try:
            sub = llm_client.extract_json(last.content)
            if isinstance(sub, dict) and sub.get("triage_label") in LABELS:
                trace.append({"kind": "note", "name": "parsed_json_reply",
                              "summary": "model answered in text; parsed as assessment"})
                return {"submission": sub, "retrieved": retrieved, "llm_calls": llm_calls,
                        "tool_calls": tool_calls, "provider": last.provider, "model": last.model}
        except Exception:
            pass
    trace.append({"kind": "note", "name": "no_submission", "summary": f"no assessment after {llm_calls} turns"})
    return None


# ── Rules fallback ──────────────────────────────────────────────────────

def rules_assessment(case: Case) -> Dict:
    """Deterministic assessment from the symptom graph, severity, duration and answer boosts."""
    label = adaptive_engine.bayesian_urgency_update("HomeCare", case.answers, case.symptoms)
    factors = []
    kg = _kg()
    for s in case.symptoms:
        base = kg.get(s, {}).get("base_urgency", "home_care")
        if base != "home_care":
            factors.append(f"{s.replace('_', ' ')} is treated as {base.replace('_', ' ')} by default")
    if case.severity is not None and case.severity >= 8:
        label = red_flags.escalate(label, [red_flags.RedFlag("sev", "Urgent", "", "")])
        factors.append(f"high self-rated severity ({case.severity:g}/10)")
    if case.duration_hours is not None and case.duration_hours > 24 * 14:
        label = red_flags.escalate(label, [red_flags.RedFlag("dur", "Urgent", "", "")])
        factors.append(f"symptoms for about {_human_duration(case.duration_hours)}")
    if "fever" in case.symptoms and case.duration_hours is not None and case.duration_hours > 72:
        label = red_flags.escalate(label, [red_flags.RedFlag("fev", "Urgent", "", "")])
        factors.append("fever lasting more than three days")
    if not factors:
        factors.append(NO_WARNING_FACTOR)
    names = ", ".join(s.replace("_", " ") for s in case.symptoms[:3]) or "the symptoms you described"
    explanation = {
        "Emergency": f"Your answers about {names} include signs that need emergency assessment.",
        "Urgent": f"Based on {names} and your answers, a doctor should see you soon.",
        "HomeCare": f"Based on {names} and your answers, this can likely be managed at home with self-care.",
    }[label]
    return {"triage_label": label, "explanation": explanation, "recommended_action": ACTIONS[label],
            "key_factors": factors, "conditions_to_consider": adaptive_engine.get_diseases_for_symptoms(case.symptoms)}


# ── Orchestration ───────────────────────────────────────────────────────

def _normalise_probs(p: Any) -> Optional[Dict[str, float]]:
    if not isinstance(p, dict):
        return None
    vals = {k: max(0.0, float(p.get(k, 0) or 0)) for k in LABELS}
    total = sum(vals.values())
    if total <= 0:
        return None
    return {k: round(v / total, 3) for k, v in vals.items()}


def _clean_list(x: Any, limit: int = 6) -> List[str]:
    if not isinstance(x, list):
        return []
    return [str(i).strip() for i in x if str(i).strip()][:limit]


def assess(case: Case, session_id: Optional[str] = None, source: str = "web", use_llm: bool = True) -> Dict:
    """Assess a case end to end. Always returns a complete result; never raises for model failures."""
    started = time.perf_counter()
    trace: List[Dict] = []
    flags = red_flags.scan_case(case.complaint, case.answers, case.age, case.symptoms)
    trace.append({"kind": "rule", "name": "red_flag_rules",
                  "summary": ", ".join(f"{f.rule_id} ({f.level})" for f in flags) or "no red flags"})

    decision_path = "agent"
    fallback_reason: Optional[str] = None
    provider = model = None
    llm_calls = tool_calls = 0
    probabilities: Optional[Dict[str, float]] = None
    citations: List[Dict] = []
    crisis = red_flags.is_crisis(flags)

    if crisis:
        decision_path = "red_flag"
        base = {"triage_label": "Emergency",
                "explanation": "You mentioned thoughts of ending your life or harming yourself. "
                               "You deserve support right now, and talking to someone can help.",
                "recommended_action": "Call a crisis line now: iCall 9152987821 or Vandrevala Foundation "
                                      "1860-2662-345 (24/7), or emergency services on 112.",
                "key_factors": [f.reason for f in flags], "conditions_to_consider": []}
        citations = retriever.search("thoughts of suicide or self-harm support", k=2)
    else:
        agent_out = None
        if use_llm and llm_client.has_any_provider():
            with observability.tagged(session_id, "triage_agent"):
                try:
                    agent_out = run_agent(case, flags, trace)
                except Exception as exc:  # never let an agent bug break triage
                    app_logger.exception(f"agent crashed: {exc}")
                    trace.append({"kind": "note", "name": "agent_error", "summary": type(exc).__name__})
            if agent_out is None:
                fallback_reason = "agent_failed"
        else:
            fallback_reason = "llm_disabled" if not use_llm else "no_llm_provider"

        if agent_out:
            sub = agent_out["submission"]
            label = sub.get("triage_label") if sub.get("triage_label") in LABELS else "Urgent"
            base = {"triage_label": label,
                    "explanation": str(sub.get("explanation") or "").strip(),
                    "recommended_action": ACTIONS[label],
                    "key_factors": _clean_list(sub.get("key_factors")),
                    "conditions_to_consider": _clean_list(sub.get("conditions_to_consider")),
                    "self_care": _clean_list(sub.get("self_care"))}
            probabilities = _normalise_probs(sub.get("probabilities"))
            provider, model = agent_out["provider"], agent_out["model"]
            llm_calls, tool_calls = agent_out["llm_calls"], agent_out["tool_calls"]
            # Only keep citations the agent actually retrieved in this run.
            cited = [c for c in _clean_list(sub.get("citations"), 10) if c in agent_out["retrieved"]]
            citations = [agent_out["retrieved"][c] for c in cited]
            if not citations and agent_out["retrieved"]:
                citations = list(agent_out["retrieved"].values())[:2]
        else:
            decision_path = "rules"
            base = rules_assessment(case)
            trace.append({"kind": "rule", "name": "rules_assessment",
                          "summary": f"label={base['triage_label']} ({fallback_reason})"})

        if not citations:
            query = f"{case.complaint}. {' '.join(s.replace('_', ' ') for s in case.symptoms)}"
            citations = retriever.search(query, k=3, symptoms=case.symptoms)
            trace.append({"kind": "tool", "name": "search_knowledge", "args": {"query": _short(query, 80)},
                          "summary": ", ".join(c["chunk_id"] for c in citations) or "no matches"})

    # ── Optional decision-model second opinion (escalate-only, needs a calibration) ──
    opinion = None
    if not crisis and settings.DECISION_MODEL != "off":
        opinion = decision_model.second_opinion(case.summary())
        if opinion:
            trace.append({"kind": "model", "name": "decision_model",
                          "summary": (f"set={opinion.prediction_set} at alpha={opinion.alpha}" if opinion.calibrated
                                      else "uncalibrated, shown for information only")})

    # ── Safety merge (escalate-only) ──
    proposed = base["triage_label"]
    final = red_flags.escalate(proposed, flags)
    if opinion and opinion.prediction_set:
        raised = decision_model.escalate_with_set(final, opinion.prediction_set)
        if raised != final:
            trace.append({"kind": "model", "name": "decision_model_escalation",
                          "summary": f"prediction set {opinion.prediction_set} raised {final} -> {raised}"})
            base["recommended_action"] = ACTIONS[raised]
            base["explanation"] = (f"A second model could not rule out {raised} for this case, so the level is {raised}. "
                                   + (base["explanation"] or ""))
            final = raised
    escalated = final != proposed
    if escalated and flags and final == red_flags.escalate(proposed, flags):
        top = max(flags, key=lambda f: red_flags.LEVELS[f.level])
        base["recommended_action"] = ACTIONS[final]
        source = "AI agent" if decision_path == "agent" else "rule-based assessment"
        base["explanation"] = (f"{top.reason} That warning sign sets the level to {final}. "
                               f"On its own, the {source} would have said {proposed}"
                               + (f": {base['explanation']}" if base["explanation"] else "."))
        base["key_factors"] = [k for k in base.get("key_factors", []) if k != NO_WARNING_FACTOR]
        trace.append({"kind": "rule", "name": "safety_merge",
                      "summary": f"escalated {proposed} -> {final} by {top.rule_id}"})
        if decision_path == "rules":
            decision_path = "red_flag"
    else:
        trace.append({"kind": "rule", "name": "safety_merge", "summary": f"kept {final}"})

    latency = (time.perf_counter() - started) * 1000
    observability.record_run(session_id, decision_path, final, escalated, [f.rule_id for f in flags],
                             fallback_reason, latency, llm_calls, tool_calls, source)

    tips = adaptive_engine.get_remedies_nutrition(case.symptoms)
    return {
        "triage_label": final,
        "proposed_label": proposed,
        "escalated": escalated,
        "explanation_text": base["explanation"],
        "recommended_action": base["recommended_action"],
        "key_factors": base.get("key_factors", []),
        "conditions_to_consider": [c.replace("_", " ") for c in base.get("conditions_to_consider", [])][:6],
        "self_care": base.get("self_care") or tips.get("remedies", []),
        "nutrition_tips": tips.get("nutrition_tips", []),
        "probabilities": probabilities,
        "red_flags": [f.to_dict() for f in flags],
        "red_flag_triggered": bool(flags) and red_flags.highest_level(flags) == "Emergency",
        "crisis_response": crisis,
        "citations": citations,
        "decision_path": decision_path,
        "fallback_reason": fallback_reason,
        "provider": provider,
        "model": model,
        "llm_calls": llm_calls,
        "tool_calls": tool_calls,
        "latency_ms": round(latency),
        "agent_steps": trace,
        "symptoms": case.symptoms,
        "second_opinion": opinion.to_dict() if opinion else None,
    }
