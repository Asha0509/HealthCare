from conftest import reply, tool_call

from services import observability
from services.agent import Case, assess


def _case(**kw):
    base = dict(complaint="sore throat and mild fever for 2 days", age=25, symptoms=["sore_throat", "fever"],
                duration_hours=48)
    base.update(kw)
    return Case(**base)


def _happy_script(label="HomeCare", cite=("sore_throat#self-care",)):
    return [
        reply(tool_calls=[tool_call("lookup_symptom", {"symptom": "sore_throat"}, "c1")]),
        reply(tool_calls=[tool_call("search_knowledge", {"query": "sore throat self care"}, "c2")]),
        reply(tool_calls=[tool_call("submit_assessment", {
            "triage_label": label,
            "probabilities": {"HomeCare": 7, "Urgent": 2, "Emergency": 1},
            "explanation": "Likely a viral sore throat.",
            "recommended_action": "Rest and fluids.",
            "key_factors": ["short duration", "no warning signs"],
            "conditions_to_consider": ["viral pharyngitis"],
            "self_care": ["warm salt-water gargles"],
            "citations": list(cite) + ["made_up#source"],
        }, "c3")]),
    ]


def test_agent_happy_path_uses_tools_and_filters_citations(fake_llm):
    script = fake_llm(_happy_script())
    r = assess(_case(), session_id="s1")
    assert r["decision_path"] == "agent" and r["triage_label"] == "HomeCare"
    assert r["provider"] == "groq" and r["llm_calls"] == 3 and r["tool_calls"] == 3
    # hallucinated citation dropped, real one kept
    assert [c["chunk_id"] for c in r["citations"]] == ["sore_throat#self-care"]
    # probabilities normalised to sum to 1
    assert abs(sum(r["probabilities"].values()) - 1) < 1e-6 and r["probabilities"]["HomeCare"] == 0.7
    names = [s["name"] for s in r["agent_steps"]]
    assert names[0] == "red_flag_rules" and "lookup_symptom" in names and names[-1] == "safety_merge"
    # tool results were sent back to the model with matching ids
    last_messages = script.requests[-1][1]["messages"]
    assert any(m.get("role") == "tool" and m.get("tool_call_id") == "c2" for m in last_messages)
    assert script.requests[0][1]["tools"]


def test_red_flag_escalates_agent_answer(fake_llm):
    fake_llm(_happy_script(label="HomeCare"))
    r = assess(_case(complaint="sore throat and now I can't breathe"))
    assert r["proposed_label"] == "HomeCare"
    assert r["triage_label"] == "Emergency" and r["escalated"]
    assert any(s["name"] == "safety_merge" and "escalated" in s["summary"] for s in r["agent_steps"])


def test_failover_to_second_provider(fake_llm):
    script = fake_llm(_happy_script(), fail_providers={"groq"})
    r = assess(_case())
    assert r["decision_path"] == "agent" and r["provider"] == "nvidia_nim"
    calls = observability.recent_calls(20)
    assert {c["provider"] for c in calls if c["status"] == "error"} == {"groq"}
    assert sum(1 for c in calls if c["status"] == "ok") == 3


def test_all_providers_down_falls_back_to_rules(fake_llm):
    fake_llm([], fail_providers={"groq", "nvidia_nim"})
    r = assess(_case())
    assert r["decision_path"] == "rules" and r["fallback_reason"] == "agent_failed"
    assert r["citations"], "rules path still retrieves knowledge"
    assert r["probabilities"] is None, "no fake confidence on the rules path"


def test_no_provider_configured(no_llm):
    r = assess(_case())
    assert r["decision_path"] == "rules" and r["fallback_reason"] == "no_llm_provider"


def test_model_answers_in_plain_json_after_nudge(fake_llm):
    fake_llm([
        reply(content="Let me think."),
        reply(content='{"triage_label": "Urgent", "explanation": "Fever for days.", "recommended_action": "See a GP."}'),
    ])
    r = assess(_case())
    assert r["decision_path"] == "agent" and r["triage_label"] == "Urgent"
    assert any(s["name"] == "parsed_json_reply" for s in r["agent_steps"])


def test_agent_gives_up_after_max_turns(fake_llm):
    looping = [reply(tool_calls=[tool_call("lookup_symptom", {"symptom": "fever"}, f"c{i}")]) for i in range(10)]
    fake_llm(looping)
    r = assess(_case())
    assert r["decision_path"] == "rules" and r["fallback_reason"] == "agent_failed"
    assert r["llm_calls"] == 0  # metadata of the failed agent run isn't reported as the decision's


def test_crisis_bypasses_llm(fake_llm):
    script = fake_llm(_happy_script())
    r = assess(_case(complaint="I want to end my life", symptoms=[]))
    assert r["crisis_response"] and r["triage_label"] == "Emergency" and r["decision_path"] == "red_flag"
    assert script.requests == []
    assert "9152987821" in r["recommended_action"]


def test_invalid_label_from_model_is_treated_conservatively(fake_llm):
    fake_llm([reply(tool_calls=[tool_call("submit_assessment", {
        "triage_label": "Maybe", "explanation": "x", "recommended_action": "y"})])])
    r = assess(_case())
    assert r["triage_label"] == "Urgent"


def test_unknown_tool_and_bad_symptom_do_not_crash(fake_llm):
    fake_llm([
        reply(tool_calls=[tool_call("delete_database", {}, "a"), tool_call("lookup_symptom", {"symptom": "zz"}, "b")]),
        reply(tool_calls=[tool_call("submit_assessment", {"triage_label": "HomeCare", "explanation": "ok",
                                                          "recommended_action": "rest"}, "c")]),
    ])
    r = assess(_case())
    assert r["decision_path"] == "agent"
    summaries = " ".join(s.get("summary", "") for s in r["agent_steps"])
    assert "unknown tool" in summaries and "unknown symptom" in summaries


def test_run_is_logged(no_llm):
    assess(_case(), session_id="logged", source="eval")
    runs = observability.recent_runs(5)
    assert runs[0]["session_id"] == "logged" and runs[0]["source"] == "eval"
