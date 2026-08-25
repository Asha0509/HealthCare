"""
HealthAI triage eval harness.

Runs every case in cases.jsonl through the real /api/triage/assess endpoint
(in-process by default, or against a deployed URL) and scores it.

The metric that matters most for triage is UNDER-triage: telling someone with
an emergency they can stay home. Accuracy is reported, but the gate is on
missed emergencies.

Usage:
  python evals/run_eval.py --pipeline rules                 # deterministic, no API key needed
  python evals/run_eval.py --pipeline agent                 # needs GROQ_API_KEY / NVIDIA_NIM_API_KEY
  python evals/run_eval.py --pipeline agent --base-url https://healthai-triage-api.onrender.com
  python evals/run_eval.py --pipeline rules --gate          # exit 1 if a gate fails (CI)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Dict, List

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LABELS = ["HomeCare", "Urgent", "Emergency"]
RANK = {k: i for i, k in enumerate(LABELS)}

# Gates (CI fails if violated). Strict on safety, silent on accuracy.
# The rules pipeline is only expected to catch textbook red flags (cases tagged
# red_flag_*); cases tagged "judgement" are worded to need reasoning and are
# where the agent has to earn its place, so they gate the agent only.
GATES = {
    "rules": {"scope": "red_flag cases", "critical_misses": 0, "emergency_recall_min": 1.0},
    "agent": {"scope": "all cases", "critical_misses": 0, "emergency_recall_min": 0.9},
}


def load_cases(path: str) -> List[Dict]:
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def pct(values: List[float], p: float):
    if not values:
        return None
    s = sorted(values)
    return round(s[max(0, min(len(s) - 1, int(round(p / 100 * (len(s) - 1)))))], 1)


def score(rows: List[Dict]) -> Dict:
    n = len(rows)
    ok_rows = [r for r in rows if r.get("predicted")]
    confusion = {e: {p: 0 for p in LABELS} for e in LABELS}
    for r in ok_rows:
        confusion[r["expected"]][r["predicted"]] += 1
    per_class = {}
    for k in LABELS:
        tp = confusion[k][k]
        fp = sum(confusion[e][k] for e in LABELS if e != k)
        fn = sum(confusion[k][p] for p in LABELS if p != k)
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        per_class[k] = {"precision": round(prec, 3), "recall": round(rec, 3), "f1": round(f1, 3),
                        "support": tp + fn}
    rf_rows = [r for r in ok_rows if r["tag"].startswith("red_flag")]
    rf_emerg = [r for r in rf_rows if r["expected"] == "Emergency"]
    under = [r for r in ok_rows if RANK[r["predicted"]] < RANK[r["expected"]]]
    over = [r for r in ok_rows if RANK[r["predicted"]] > RANK[r["expected"]]]
    critical = [r for r in ok_rows if r["expected"] == "Emergency" and r["predicted"] == "HomeCare"]
    latencies = [r["latency_ms"] for r in ok_rows if r.get("latency_ms") is not None]
    return {
        "cases": n,
        "errors": n - len(ok_rows),
        "accuracy": round(sum(r["predicted"] == r["expected"] for r in ok_rows) / n, 3) if n else None,
        "macro_f1": round(sum(c["f1"] for c in per_class.values()) / 3, 3),
        "emergency_recall": per_class["Emergency"]["recall"],
        "under_triage_rate": round(len(under) / n, 3) if n else None,
        "over_triage_rate": round(len(over) / n, 3) if n else None,
        "critical_misses": len(critical),
        "critical_miss_ids": [r["id"] for r in critical],
        "red_flag_cases": {
            "cases": len(rf_rows),
            "critical_misses": sum(1 for r in rf_emerg if r["predicted"] == "HomeCare"),
            "emergency_recall": round(sum(r["predicted"] == "Emergency" for r in rf_emerg) / len(rf_emerg), 3)
            if rf_emerg else None,
        },
        "escalated_by_safety_rules": sum(1 for r in ok_rows if r.get("escalated")),
        "fallback_rate": round(sum(1 for r in ok_rows if r.get("fallback_reason")) / n, 3) if n else None,
        "latency_ms_p50": pct(latencies, 50),
        "latency_ms_p95": pct(latencies, 95),
        "avg_llm_calls": round(sum(r.get("llm_calls", 0) for r in ok_rows) / n, 2) if n else None,
        "avg_tool_calls": round(sum(r.get("tool_calls", 0) for r in ok_rows) / n, 2) if n else None,
        "per_class": per_class,
        "confusion": confusion,
        "by_tag": {t: {"cases": len(g), "accuracy": round(sum(r.get("predicted") == r["expected"] for r in g) / len(g), 3)}
                   for t in sorted({r["tag"] for r in rows}) for g in [[r for r in rows if r["tag"] == t]]},
    }


def check_gates(pipeline: str, m: Dict) -> List[str]:
    g = GATES[pipeline]
    scoped = m["red_flag_cases"] if pipeline == "rules" else m
    failures = []
    if scoped["critical_misses"] > g["critical_misses"]:
        failures.append(f"critical_misses ({g['scope']}) {scoped['critical_misses']} > {g['critical_misses']}")
    if (scoped["emergency_recall"] or 0) < g["emergency_recall_min"]:
        failures.append(f"emergency_recall ({g['scope']}) {scoped['emergency_recall']} < {g['emergency_recall_min']}")
    if m["errors"]:
        failures.append(f"{m['errors']} cases errored")
    return failures


async def run(cases: List[Dict], pipeline: str, base_url: str | None, delay: float) -> List[Dict]:
    import httpx

    if base_url:
        client = httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=120)
    else:
        sys.path.insert(0, os.path.join(ROOT, "backend"))
        os.chdir(os.path.join(ROOT, "backend"))
        if pipeline == "rules":
            os.environ.setdefault("OBS_DB_PATH", os.path.join(HERE, ".eval-obs.db"))
        from db.database import init_db
        from main import app
        await init_db()
        client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://eval", timeout=120)

    rows = []
    async with client:
        for i, c in enumerate(cases, 1):
            body = {"chief_complaint": c["complaint"], "patient_age": c["age"], "patient_gender": c["gender"],
                    "answers": c["answers"], "use_llm": pipeline == "agent", "source": "eval"}
            started = time.perf_counter()
            row = {"id": c["id"], "complaint": c["complaint"], "expected": c["expected"], "tag": c["tag"],
                   "rationale": c["rationale"]}
            try:
                resp = await client.post("/api/triage/assess", json=body)
                resp.raise_for_status()
                d = resp.json()
                row.update({
                    "predicted": d["triage_label"], "proposed": d.get("proposed_label"),
                    "escalated": d.get("escalated"), "decision_path": d.get("decision_path"),
                    "fallback_reason": d.get("fallback_reason"), "provider": d.get("provider"),
                    "latency_ms": d.get("latency_ms"), "wall_ms": round((time.perf_counter() - started) * 1000),
                    "llm_calls": d.get("llm_calls", 0), "tool_calls": d.get("tool_calls", 0),
                    "red_flags": [f["rule_id"] for f in d.get("red_flags", [])],
                    "citations": [x["chunk_id"] for x in d.get("citations", [])],
                    "explanation": d.get("explanation_text"),
                })
            except Exception as exc:
                row["error"] = f"{type(exc).__name__}: {exc}"[:300]
            mark = "ok " if row.get("predicted") == c["expected"] else "XX "
            print(f"{mark}{i:2d}/{len(cases)} {c['id']} expected={c['expected']:<9} got={row.get('predicted', 'ERROR')}"
                  f" path={row.get('decision_path')}", flush=True)
            rows.append(row)
            if delay:
                await asyncio.sleep(delay)
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pipeline", choices=["rules", "agent"], default="rules")
    ap.add_argument("--base-url", help="Run against a deployed API instead of in-process")
    ap.add_argument("--cases", default=os.path.join(HERE, "cases.jsonl"))
    ap.add_argument("--delay", type=float, default=0.0, help="Seconds between cases (rate limits)")
    ap.add_argument("--out", help="Output file (default evals/results/<pipeline>.json)")
    ap.add_argument("--gate", action="store_true", help="Exit non-zero if a safety gate fails")
    args = ap.parse_args()

    cases = load_cases(args.cases)
    rows = asyncio.run(run(cases, args.pipeline, args.base_url, args.delay))
    metrics = score(rows)
    providers = sorted({r["provider"] for r in rows if r.get("provider")})
    report = {
        "pipeline": args.pipeline,
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "target": args.base_url or "in-process",
        "providers": providers,
        "label_note": "Expected labels were written by the project author from public triage guidance; "
                      "they are not clinically validated.",
        "metrics": metrics,
        "gates": GATES[args.pipeline],
        "gate_failures": check_gates(args.pipeline, metrics),
        "results": rows,
    }
    out = args.out or os.path.join(HERE, "results", f"{args.pipeline}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump(report, f, indent=2)

    m = metrics
    print(f"\n{args.pipeline}: accuracy {m['accuracy']}  macro-F1 {m['macro_f1']}  emergency recall "
          f"{m['emergency_recall']}  under-triage {m['under_triage_rate']}  over-triage {m['over_triage_rate']}  "
          f"critical misses {m['critical_misses']}  p50 {m['latency_ms_p50']} ms")
    print(f"wrote {out}")
    if report["gate_failures"]:
        print("GATE FAILURES: " + "; ".join(report["gate_failures"]))
        return 1 if args.gate else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
