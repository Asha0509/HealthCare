"""Calibrate and evaluate the optional decision-model second opinion.

Sends every case in cases.jsonl to a decision-model endpoint (POST
{url}/v1/systemone), then reports:
  * top-1 accuracy of the model on its own,
  * under-triage (an emergency or urgent case ranked lower by the model),
  * leave-one-out conformal coverage and mean prediction-set size at the chosen
    alpha: each case is scored with a quantile calibrated on the *other* cases,
  * (with --write-calibration) the calibration file the API loads at runtime.

With only 60 written cases the quantile is coarse; the numbers say what the
procedure does on this set, not how it would do on real patients.

Usage:
  python evals/decision_eval.py --url http://127.0.0.1:8090 --model typed-decisions
  python evals/decision_eval.py --url ... --write-calibration
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "backend"))

from core.config import settings
from services import decision_model

CASES = os.path.join(HERE, "cases.jsonl")
OUT = os.path.join(HERE, "results", "decision.json")


def case_text(case: dict) -> str:
    parts = [f"Chief complaint: {case['complaint']}"]
    if case.get("age") is not None:
        parts.append(f"Age: {case['age']}")
    if case.get("gender"):
        parts.append(f"Gender: {case['gender']}")
    return "\n".join(parts)


def collect(cases: list[dict], query=decision_model.query_model) -> tuple[list[dict], list[str], int]:
    """Query the model for each case; returns (probabilities, truths, number of failed queries)."""
    probs, truths, failed = [], [], 0
    for case in cases:
        p = query(case_text(case))
        if p is None:
            failed += 1
            continue
        probs.append(p)
        truths.append(case["expected"])
    return probs, truths, failed


def summarise(probs: list[dict], truths: list[str], alpha: float) -> dict:
    top = [max(decision_model.LABELS, key=lambda lab: p[lab]) for p in probs]
    level = decision_model.LEVEL
    under = sum(level[t] > level[a] for t, a in zip(truths, top, strict=True))
    missed_emergency = sum(t == "Emergency" and level[a] < level["Emergency"] for t, a in zip(truths, top, strict=True))
    loo = decision_model.evaluate_leave_one_out(probs, truths, alpha)
    # Emergencies the set would still have flagged even though the top label missed them.
    rescued = 0
    for i, (p, t, a) in enumerate(zip(probs, truths, top, strict=True)):
        if t == "Emergency" and a != "Emergency":
            rest_p = [q for j, q in enumerate(probs) if j != i]
            rest_t = [x for j, x in enumerate(truths) if j != i]
            cal = decision_model.calibrate(rest_p, rest_t, alpha)
            rescued += "Emergency" in decision_model.prediction_set(p, cal.quantile)
    return {
        "n": len(probs),
        "top1_accuracy": sum(a == t for a, t in zip(top, truths, strict=True)) / len(probs),
        "under_triage": under / len(probs),
        "missed_emergencies_top1": missed_emergency,
        "missed_emergencies_rescued_by_set": rescued,
        "loo_coverage": loo["coverage"],
        "loo_mean_set_size": loo["mean_set_size"],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--url", default=settings.SYSTEMONE_URL)
    ap.add_argument("--model", default=settings.SYSTEMONE_MODEL)
    ap.add_argument("--alpha", type=float, default=0.1)
    ap.add_argument("--write-calibration", action="store_true")
    args = ap.parse_args()
    if not args.url:
        print("no endpoint: pass --url or set SYSTEMONE_URL", file=sys.stderr)
        return 2
    settings.DECISION_MODEL, settings.SYSTEMONE_URL, settings.SYSTEMONE_MODEL = "systemone", args.url, args.model

    with open(CASES) as handle:
        cases = [json.loads(line) for line in handle if line.strip()]
    probs, truths, failed = collect(cases)
    if not probs:
        print("the model returned nothing usable", file=sys.stderr)
        return 1
    result = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "model": args.model,
        "alpha": args.alpha,
        "failed_queries": failed,
        **summarise(probs, truths, args.alpha),
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as handle:
        json.dump(result, handle, indent=2)
    print(json.dumps(result, indent=2))
    if args.write_calibration:
        cal = decision_model.calibrate(probs, truths, args.alpha)
        with open(settings.CONFORMAL_PATH, "w") as handle:
            json.dump({"alpha": cal.alpha, "quantile": cal.quantile, "n": cal.n, "model": args.model}, handle, indent=2)
        print(f"wrote {settings.CONFORMAL_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
