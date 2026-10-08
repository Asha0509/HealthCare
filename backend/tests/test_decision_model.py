"""Conformal sets, escalate-only behaviour and the model client (no network)."""
import json

import pytest
from core.config import settings
from services import agent
from services import decision_model as dm
from services.agent import Case


def _p(home=0.0, urgent=0.0, emergency=0.0):
    return {"HomeCare": home, "Urgent": urgent, "Emergency": emergency}


def test_calibrate_uses_finite_sample_quantile():
    probs = [_p(home=0.9, urgent=0.1)] * 9 + [_p(home=0.4, urgent=0.6)]
    cal = dm.calibrate(probs, ["HomeCare"] * 10, alpha=0.1)
    # scores: nine of 0.1 and one of 0.6; rank = ceil(11 * 0.9) = 10 -> the largest score
    assert cal.quantile == pytest.approx(0.6)
    assert cal.n == 10


def test_calibrate_returns_one_when_too_few_cases_for_alpha():
    cal = dm.calibrate([_p(home=1.0)] * 3, ["HomeCare"] * 3, alpha=0.05)
    assert cal.quantile == 1.0  # ceil(4 * 0.95) = 4 > n


@pytest.mark.parametrize("alpha", [0, 1, -0.1, 1.5])
def test_calibrate_rejects_bad_alpha(alpha):
    with pytest.raises(ValueError):
        dm.calibrate([_p(home=1.0)], ["HomeCare"], alpha)


def test_calibrate_rejects_mismatched_inputs():
    with pytest.raises(ValueError):
        dm.calibrate([_p(home=1.0)], [], 0.1)


def test_prediction_set_edges_and_never_empty():
    p = _p(home=0.7, urgent=0.2, emergency=0.1)
    assert dm.prediction_set(p, 0.3) == ["HomeCare"]
    assert dm.prediction_set(p, 0.8) == ["HomeCare", "Urgent"]  # 1 - 0.2 = 0.8 is inside
    assert dm.prediction_set(p, 0.95) == ["HomeCare", "Urgent", "Emergency"]
    assert dm.prediction_set(p, 0.0) == ["HomeCare"]  # nothing qualifies: fall back to the top label


@pytest.mark.parametrize(
    ("label", "chosen", "expected"),
    [
        ("HomeCare", ["HomeCare"], "HomeCare"),
        ("HomeCare", ["HomeCare", "Urgent"], "Urgent"),
        ("Urgent", ["HomeCare"], "Urgent"),  # never lowers
        ("Urgent", ["Urgent", "Emergency"], "Emergency"),
        ("Emergency", ["HomeCare", "Urgent"], "Emergency"),
    ],
)
def test_escalate_with_set_only_raises(label, chosen, expected):
    assert dm.escalate_with_set(label, chosen) == expected


def test_leave_one_out_coverage_is_reported():
    probs = [_p(home=0.8, urgent=0.2)] * 10 + [_p(urgent=0.8, home=0.2)] * 10
    truths = ["HomeCare"] * 10 + ["Urgent"] * 10
    result = dm.evaluate_leave_one_out(probs, truths, alpha=0.1)
    assert result["coverage"] == 1.0
    assert result["n"] == 20
    assert 1.0 <= result["mean_set_size"] <= 3.0


def test_parse_probabilities_normalises_and_accepts_wrapper():
    assert dm._parse_probabilities({"probabilities": {"HomeCare": 2, "Urgent": 2}}) == {
        "HomeCare": 0.5, "Urgent": 0.5, "Emergency": 0.0}
    assert dm._parse_probabilities({"output": {"probabilities": {"Emergency": 1}}})["Emergency"] == 1.0
    assert dm._parse_probabilities({"probabilities": {"HomeCare": 0}}) is None
    assert dm._parse_probabilities({"probabilities": "nope"}) is None
    assert dm._parse_probabilities({"probabilities": {"HomeCare": "x"}}) is None
    assert dm._parse_probabilities({}) is None


@pytest.fixture
def enabled(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "DECISION_MODEL", "systemone")
    monkeypatch.setattr(settings, "SYSTEMONE_URL", "http://model.test")
    monkeypatch.setattr(settings, "SYSTEMONE_API_KEY", "k")
    monkeypatch.setattr(settings, "CONFORMAL_PATH", str(tmp_path / "conformal.json"))
    return tmp_path / "conformal.json"


def test_query_model_off_or_without_url_makes_no_call(monkeypatch):
    def boom(*_a):
        raise AssertionError("must not be called")

    assert dm.query_model("x", boom) is None
    monkeypatch.setattr(settings, "DECISION_MODEL", "systemone")
    assert dm.query_model("x", boom) is None


def test_query_model_sends_typed_request_and_auth(enabled):
    seen = {}

    def transport(url, payload, headers, timeout):
        seen.update(url=url, payload=payload, headers=headers, timeout=timeout)
        return {"probabilities": {"Urgent": 1}}

    assert dm.query_model("Chief complaint: cough", transport) == _p(urgent=1.0)
    assert seen["url"] == "http://model.test/v1/systemone"
    assert seen["headers"] == {"Authorization": "Bearer k"}
    assert seen["payload"]["input"] == "Chief complaint: cough"
    assert seen["payload"]["output_schema"]["required"] == ["probabilities"]


def test_query_model_swallows_transport_errors(enabled):
    def transport(*_a):
        raise TimeoutError

    assert dm.query_model("x", transport) is None


def test_second_opinion_uncalibrated_has_no_set(enabled, monkeypatch):
    monkeypatch.setattr(dm, "query_model", lambda *_a, **_k: _p(home=0.9, urgent=0.1))
    op = dm.second_opinion("x")
    assert op and op.prediction_set is None and op.calibrated is False


def test_second_opinion_calibrated_has_set(enabled, monkeypatch):
    enabled.write_text(json.dumps({"alpha": 0.1, "quantile": 0.7, "n": 60}))
    monkeypatch.setattr(dm, "query_model", lambda *_a, **_k: _p(home=0.5, urgent=0.4, emergency=0.1))
    op = dm.second_opinion("x")
    assert op.prediction_set == ["HomeCare", "Urgent"] and op.alpha == 0.1 and op.calibrated


def test_load_calibration_handles_missing_and_corrupt(tmp_path):
    assert dm.load_calibration(tmp_path / "missing.json") is None
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    assert dm.load_calibration(bad) is None


# ── integration with assess() ───────────────────────────────────────────────


def _case():
    return Case(complaint="mild sore throat since yesterday", age=24, gender="female", symptoms=["sore_throat"])


def test_assess_is_unchanged_when_model_is_off(no_llm):
    assert agent.assess(_case(), use_llm=False)["second_opinion"] is None


def test_assess_raises_level_when_set_contains_more_urgent_level(enabled, no_llm, monkeypatch):
    enabled.write_text(json.dumps({"alpha": 0.1, "quantile": 0.95, "n": 60}))
    monkeypatch.setattr(dm, "query_model", lambda *_a, **_k: _p(home=0.6, urgent=0.3, emergency=0.1))
    baseline = agent.rules_assessment(_case())["triage_label"]
    result = agent.assess(_case(), use_llm=False)
    assert result["triage_label"] == "Emergency" and baseline != "Emergency"
    assert result["escalated"] is True
    assert any(step["name"] == "decision_model_escalation" for step in result["agent_steps"])


def test_assess_never_lowers_level_and_ignores_uncalibrated_opinion(enabled, no_llm, monkeypatch):
    monkeypatch.setattr(dm, "query_model", lambda *_a, **_k: _p(home=1.0))
    result = agent.assess(_case(), use_llm=False)  # no calibration file
    assert result["second_opinion"]["calibrated"] is False
    assert result["triage_label"] == agent.rules_assessment(_case())["triage_label"]


def test_assess_skips_model_during_self_harm_crisis(enabled, no_llm, monkeypatch):
    def boom(*_a, **_k):
        raise AssertionError("crisis must not wait on a model")

    monkeypatch.setattr(dm, "query_model", boom)
    crisis = Case(complaint="I want to end my life", age=30, gender="male", symptoms=[])
    assert agent.assess(crisis, use_llm=False)["crisis_response"] is True
