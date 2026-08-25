
import httpx
import pytest
import pytest_asyncio
from conftest import reply, tool_call
from db.database import init_db
from main import app
from services import facilities, observability


@pytest_asyncio.fixture
async def client():
    await init_db()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def _start(client, complaint, age=30, gender="female"):
    r = await client.post("/api/triage/start", json={"chief_complaint": complaint, "patient_age": age,
                                                     "patient_gender": gender})
    assert r.status_code == 200, r.text
    return r.json()


def _answer_for(q):
    t = q["answer_type"]
    return {"yesno": "No", "scale": "4", "duration": "1-3 days", "text": "not sure"}.get(
        t, (q.get("options") or ["x"])[0])


async def _run_to_completion(client, state):
    for _ in range(12):
        if state["status"] == "completed":
            return state
        q = state["current_question"]
        r = await client.post("/api/triage/answer", json={"session_id": state["session_id"],
                                                          "question_id": q["question_id"], "answer": _answer_for(q)})
        assert r.status_code == 200, r.text
        state = r.json()
    raise AssertionError("never completed")


@pytest.mark.asyncio
async def test_full_flow_typed_questions_and_result(client, no_llm):
    state = await _start(client, "I have a headache and fever since yesterday")
    assert set(state["extracted_symptoms"]) >= {"headache", "fever"}
    q = state["current_question"]
    assert q["answer_type"] in {"yesno", "scale", "duration", "choice", "text"}
    if q["answer_type"] == "yesno":
        assert q["options"] == ["Yes", "No", "Not sure"]
    done = await _run_to_completion(client, state)
    r = await client.get(f"/api/triage/result/{done['session_id']}")
    assert r.status_code == 200
    res = r.json()
    assert res["triage_label"] in {"HomeCare", "Urgent", "Emergency"}
    assert res["decision_path"] in {"rules", "red_flag"} and res["fallback_reason"] == "no_llm_provider"
    assert res["citations"] and res["agent_steps"] and res["chief_complaint"].startswith("I have a headache")
    assert "confidence" not in res, "the random confidence number is gone"


@pytest.mark.asyncio
async def test_question_cap(client, no_llm):
    state = await _start(client, "headache")  # headache has 8 questions in the graph
    asked = 0
    while state["status"] == "active":
        asked += 1
        q = state["current_question"]
        state = (await client.post("/api/triage/answer", json={
            "session_id": state["session_id"], "question_id": q["question_id"], "answer": _answer_for(q)})).json()
    assert asked <= 6


@pytest.mark.asyncio
async def test_invalid_answer_rejected_with_helpful_message(client, no_llm):
    state = await _start(client, "chest pain when I cough")
    yesno = state["current_question"]
    while yesno["answer_type"] != "yesno":
        state = (await client.post("/api/triage/answer", json={
            "session_id": state["session_id"], "question_id": yesno["question_id"], "answer": _answer_for(yesno)})).json()
        yesno = state["current_question"]
    r = await client.post("/api/triage/answer", json={"session_id": state["session_id"],
                                                      "question_id": yesno["question_id"], "answer": "5"})
    assert r.status_code == 422 and "Yes or No" in r.json()["detail"]


@pytest.mark.asyncio
async def test_emergency_complaint_short_circuits(client, no_llm):
    state = await _start(client, "I have intense heart ache since this morning", age=49, gender="male")
    assert state["status"] == "completed"
    res = (await client.get(f"/api/triage/result/{state['session_id']}")).json()
    assert res["triage_label"] == "Emergency" and res["red_flag_triggered"]
    assert res["red_flags"][0]["rule_id"] == "cardiac_chest_pain_severe"


@pytest.mark.asyncio
async def test_yes_to_red_flag_question_finishes_as_emergency(client, no_llm):
    state = await _start(client, "chest pain", age=50, gender="male")
    for _ in range(8):
        q = state["current_question"]
        ans = "Yes" if q["question_id"] == "cp_sweating" else _answer_for(q)
        state = (await client.post("/api/triage/answer", json={
            "session_id": state["session_id"], "question_id": q["question_id"], "answer": ans})).json()
        if state["status"] == "completed":
            break
    res = (await client.get(f"/api/triage/result/{state['session_id']}")).json()
    assert res["triage_label"] == "Emergency"


@pytest.mark.asyncio
async def test_clarify_when_no_symptoms(client, no_llm):
    state = await _start(client, "I just feel off today")
    assert state["current_question"]["question_id"] == "clarify_symptoms"
    r = await client.post("/api/triage/answer", json={"session_id": state["session_id"],
                                                      "question_id": "clarify_symptoms", "answer": "a bad cough"})
    assert r.status_code == 200 and "cough" in r.json()["extracted_symptoms"]


@pytest.mark.asyncio
async def test_unknown_session_and_result(client):
    r = await client.post("/api/triage/answer", json={"session_id": "nope", "question_id": "x", "answer": "y"})
    assert r.status_code == 404
    assert (await client.get("/api/triage/result/nope")).status_code == 404


@pytest.mark.asyncio
async def test_assess_one_shot_with_answers(client, no_llm):
    r = await client.post("/api/triage/assess", json={
        "chief_complaint": "sore throat", "patient_age": 22, "answers": {"st_breathe": "yes"}, "source": "eval"})
    assert r.status_code == 200
    assert r.json()["triage_label"] == "Emergency"
    bad = await client.post("/api/triage/assess", json={"chief_complaint": "sore throat",
                                                        "answers": {"st_breathe": "7"}})
    assert bad.status_code == 422


@pytest.mark.asyncio
async def test_assess_with_agent(client, fake_llm):
    fake_llm([
        reply(content='["cough"]'),  # symptom extraction
        reply(tool_calls=[tool_call("search_knowledge", {"query": "cough self care"}, "k")]),
        reply(tool_calls=[tool_call("submit_assessment", {"triage_label": "HomeCare", "explanation": "Mild cough.",
                                                          "recommended_action": "Rest.", "citations": ["cough#self-care"]},
                                    "s")]),
    ])
    res = (await client.post("/api/triage/assess", json={"chief_complaint": "dry cough for 2 days"})).json()
    assert res["decision_path"] == "agent" and res["provider"] == "groq"
    assert res["citations"][0]["chunk_id"] == "cough#self-care"
    purposes = {c["purpose"] for c in observability.recent_calls(10)}
    assert purposes == {"symptom_extraction", "triage_agent"}


@pytest.mark.asyncio
async def test_system_metrics_knowledge_endpoints(client, no_llm):
    s = (await client.get("/api/system/status")).json()
    assert s["agent_enabled"] is False and s["knowledge_base"]["chunks"] > 50
    await client.post("/api/triage/assess", json={"chief_complaint": "mild headache"})
    m = (await client.get("/api/metrics/summary")).json()
    assert m["triage"]["runs"] >= 1
    assert "runs" in (await client.get("/api/metrics/runs")).json()
    assert "points" in (await client.get("/api/metrics/timeseries")).json()
    kb = (await client.get("/api/knowledge")).json()
    assert len(kb["chunks"]) == kb["status"]["chunks"]


@pytest.mark.asyncio
async def test_evals_endpoints(client, tmp_path, monkeypatch):
    from api import system
    (tmp_path / "rules.json").write_text('{"pipeline": "rules", "run_at": "t", "metrics": {"accuracy": 0.5}}')
    monkeypatch.setattr(system, "EVAL_DIR", str(tmp_path))
    idx = (await client.get("/api/evals")).json()
    assert idx["reports"][0]["name"] == "rules"
    assert (await client.get("/api/evals/rules")).json()["metrics"]["accuracy"] == 0.5
    assert (await client.get("/api/evals/../../etc/passwd")).status_code == 404


@pytest.mark.asyncio
async def test_facilities_endpoint(client, monkeypatch):
    async def fake_nearby(lat, lon, urgency, limit=6):
        return {"facilities": [{"name": "A", "distance_km": 1.0}], "radius_km": 3, "amenities": ["hospital"],
                "source": "osm"}

    async def fake_geocode(q):
        return {"lat": 1.0, "lon": 2.0, "label": "Somewhere"} if q != "Atlantis" else None

    monkeypatch.setattr(facilities, "nearby", fake_nearby)
    monkeypatch.setattr(facilities, "geocode", fake_geocode)
    r = await client.get("/api/facilities/nearby", params={"urgency": "Urgent", "lat": 17.4, "lon": 78.5})
    assert r.status_code == 200 and r.json()["facilities"][0]["name"] == "A"
    r = await client.get("/api/facilities/nearby", params={"urgency": "Urgent", "place": "Hyderabad"})
    assert r.json()["center"]["label"] == "Somewhere"
    assert (await client.get("/api/facilities/nearby", params={"urgency": "Urgent", "place": "Atlantis"})).status_code == 404
    assert (await client.get("/api/facilities/nearby", params={"urgency": "Urgent"})).status_code == 422
