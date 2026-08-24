"""System status, observability metrics, eval results and the knowledge base."""

import json
import os

from fastapi import APIRouter, HTTPException, Query

from core.config import settings
from services import llm_client, observability
from services.rag import retriever

router = APIRouter(prefix="/api", tags=["System"])

EVAL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                        "evals", "results")


@router.get("/system/status")
async def status():
    """What's actually running: which LLM providers are configured, retrieval mode, versions."""
    retriever.ensure_loaded()
    return {
        "version": settings.VERSION,
        "llm_providers": llm_client.configured_providers(),
        "llm_models": {p.name: p.model() for p in llm_client.PROVIDERS if p.key()},
        "agent_enabled": llm_client.has_any_provider(),
        "knowledge_base": retriever.status(),
    }


@router.get("/metrics/summary")
async def metrics_summary(hours: float = Query(168, gt=0, le=24 * 90), include_eval: bool = False):
    return observability.summary(hours, include_eval)


@router.get("/metrics/calls")
async def metrics_calls(limit: int = Query(50, ge=1, le=500)):
    return {"calls": observability.recent_calls(limit)}


@router.get("/metrics/runs")
async def metrics_runs(limit: int = Query(50, ge=1, le=500)):
    return {"runs": observability.recent_runs(limit)}


@router.get("/metrics/timeseries")
async def metrics_timeseries(hours: float = Query(24, gt=0, le=24 * 30), bucket_minutes: int = Query(60, ge=5)):
    return {"points": observability.timeseries(hours, bucket_minutes)}


@router.get("/evals")
async def evals_index():
    """Available eval reports (one per pipeline)."""
    if not os.path.isdir(EVAL_DIR):
        return {"reports": []}
    reports = []
    for name in sorted(os.listdir(EVAL_DIR)):
        if name.endswith(".json"):
            with open(os.path.join(EVAL_DIR, name)) as f:
                data = json.load(f)
            reports.append({"name": name[:-5], "pipeline": data.get("pipeline"), "run_at": data.get("run_at"),
                            "metrics": data.get("metrics")})
    return {"reports": reports}


@router.get("/evals/{name}")
async def eval_report(name: str):
    path = os.path.join(EVAL_DIR, f"{os.path.basename(name)}.json")
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="No such eval report.")
    with open(path) as f:
        return json.load(f)


@router.get("/knowledge")
async def knowledge():
    """Every knowledge-base chunk the retriever can cite."""
    retriever.ensure_loaded()
    return {"status": retriever.status(),
            "chunks": [c.citation() for c in retriever.chunks]}
