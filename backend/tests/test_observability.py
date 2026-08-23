from services import observability as obs


def test_summary_and_recent():
    with obs.tagged("s1", "triage_agent"):
        obs.record_llm_call("groq", "llama", "ok", 100, 50, 10, 1)
        obs.record_llm_call("groq", "llama", "ok", 300, 50, 10, 0)
        obs.record_llm_call("nvidia_nim", "llama", "error", 20, error="HTTP 500")
    obs.record_run("s1", "agent", "Urgent", False, [], None, 900, 2, 1, "web")
    obs.record_run("s2", "rules", "HomeCare", True, ["x"], "no_llm_provider", 50, 0, 0, "web")
    obs.record_run("e1", "rules", "HomeCare", False, [], None, 10, 0, 0, "eval")

    s = obs.summary()
    assert s["llm"]["calls"] == 3 and s["llm"]["errors"] == 1
    assert s["llm"]["by_provider"]["groq"]["calls"] == 2
    assert s["llm"]["by_purpose"] == {"triage_agent": 3}
    assert s["llm"]["prompt_tokens"] == 100
    assert s["triage"]["runs"] == 2, "eval runs excluded by default"
    assert s["triage"]["fallback_rate"] == 0.5 and s["triage"]["escalations"] == 1
    assert obs.summary(include_eval=True)["triage"]["runs"] == 3

    calls = obs.recent_calls(10)
    assert calls[0]["provider"] == "nvidia_nim" and calls[0]["session_id"] == "s1"
    assert obs.recent_runs(1)[0]["session_id"] == "e1"
    assert sum(p["calls"] for p in obs.timeseries()) == 3


def test_tags_reset_after_block():
    with obs.tagged("x", "p"):
        pass
    assert obs.current_session.get() is None and obs.current_purpose.get() == "unspecified"


def test_empty_store():
    s = obs.summary()
    assert s["llm"]["calls"] == 0 and s["llm"]["error_rate"] is None and s["triage"]["latency_ms_p50"] is None
