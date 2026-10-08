"""Optional second opinion from a decision model, with conformal prediction sets.

A decision model (a hosted one, or an open-weights one served locally behind an
OpenAI-style `/v1/systemone` endpoint) returns a probability for each triage
level for the same case. Those probabilities are turned into a *prediction set*
with split conformal prediction: the set of levels the model cannot rule out at
a stated error rate. If that set contains a more urgent level than the current
answer, the case is raised to it.

Safety rules this module keeps:
* It can only raise a level, never lower one (same rule as the red-flag rules).
* Without a calibration file there is no coverage guarantee, so no set is
  produced and nothing is escalated; the opinion is shown for information only.
* Any failure (no endpoint, timeout, malformed answer) returns None and triage
  carries on without it.

The module is off by default (`DECISION_MODEL=off`).
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from core.config import settings
from loguru import logger

LABELS = ("HomeCare", "Urgent", "Emergency")
LEVEL = {label: i for i, label in enumerate(LABELS)}

Transport = Callable[[str, dict[str, Any], dict[str, str], float], dict[str, Any]]


@dataclass(frozen=True)
class Calibration:
    """Output of `calibrate`: the nonconformity quantile and how it was obtained."""

    alpha: float
    quantile: float
    n: int


@dataclass(frozen=True)
class SecondOpinion:
    probabilities: dict[str, float]
    prediction_set: list[str] | None  # None when no calibration is available
    alpha: float | None
    model: str
    calibrated: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "probabilities": self.probabilities,
            "prediction_set": self.prediction_set,
            "alpha": self.alpha,
            "model": self.model,
            "calibrated": self.calibrated,
        }


# ── conformal prediction ────────────────────────────────────────────────────


def calibrate(probs: Sequence[dict[str, float]], truths: Sequence[str], alpha: float = 0.1) -> Calibration:
    """Split conformal calibration with nonconformity = 1 - p(true label).

    The quantile uses the finite-sample correction ceil((n + 1)(1 - alpha)) / n,
    which is what gives the marginal coverage guarantee P(true in set) >= 1 - alpha
    (assuming calibration and live cases are exchangeable).
    """
    if len(probs) != len(truths) or not probs:
        raise ValueError("calibration needs one true label per probability vector, and at least one case")
    if not 0 < alpha < 1:
        raise ValueError("alpha must be between 0 and 1")
    scores = sorted(1.0 - p.get(t, 0.0) for p, t in zip(probs, truths, strict=True))
    n = len(scores)
    rank = math.ceil((n + 1) * (1 - alpha))
    quantile = 1.0 if rank > n else scores[rank - 1]
    return Calibration(alpha=alpha, quantile=quantile, n=n)


def prediction_set(probabilities: dict[str, float], quantile: float) -> list[str]:
    """Levels whose nonconformity 1 - p is within the calibrated quantile (never empty)."""
    kept = [label for label in LABELS if 1.0 - probabilities.get(label, 0.0) <= quantile]
    return kept or [max(LABELS, key=lambda label: probabilities.get(label, 0.0))]


def escalate_with_set(label: str, labels_in_set: Sequence[str]) -> str:
    """Raise `label` to the most urgent level in the set; never lower it."""
    most_urgent = max(labels_in_set, key=lambda lab: LEVEL[lab])
    return most_urgent if LEVEL[most_urgent] > LEVEL[label] else label


def evaluate_leave_one_out(probs: Sequence[dict[str, float]], truths: Sequence[str], alpha: float = 0.1) -> dict[str, float]:
    """Empirical coverage and mean set size when each case is held out of its own calibration."""
    covered = 0
    sizes = []
    for i, (p, truth) in enumerate(zip(probs, truths, strict=True)):
        rest_p = [q for j, q in enumerate(probs) if j != i]
        rest_t = [t for j, t in enumerate(truths) if j != i]
        chosen = prediction_set(p, calibrate(rest_p, rest_t, alpha).quantile)
        covered += truth in chosen
        sizes.append(len(chosen))
    return {"coverage": covered / len(probs), "mean_set_size": sum(sizes) / len(sizes), "n": len(probs)}


def load_calibration(path: str | Path | None = None) -> Calibration | None:
    target = Path(path or settings.CONFORMAL_PATH)
    try:
        raw = json.loads(target.read_text())
        return Calibration(alpha=float(raw["alpha"]), quantile=float(raw["quantile"]), n=int(raw["n"]))
    except (OSError, ValueError, KeyError):
        return None


# ── model client ────────────────────────────────────────────────────────────


def _http_transport(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: float) -> dict[str, Any]:
    response = httpx.post(url, json=payload, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response.json()


def _parse_probabilities(body: dict[str, Any]) -> dict[str, float] | None:
    """Accept {"probabilities": {...}} or {"output": {"probabilities": {...}}}; normalise to the 3 levels."""
    node = body.get("output", body) if isinstance(body, dict) else {}
    raw = node.get("probabilities") if isinstance(node, dict) else None
    if not isinstance(raw, dict):
        return None
    try:
        values = {label: max(0.0, float(raw.get(label, 0.0))) for label in LABELS}
    except (TypeError, ValueError):
        return None
    total = sum(values.values())
    return {label: v / total for label, v in values.items()} if total > 0 else None


def query_model(case_summary: str, transport: Transport | None = None) -> dict[str, float] | None:
    """Ask the configured decision model for level probabilities; None on any failure."""
    if settings.DECISION_MODEL == "off" or not settings.SYSTEMONE_URL:
        return None
    payload = {
        "model": settings.SYSTEMONE_MODEL,
        "input": case_summary,
        "output_schema": {
            "type": "object",
            "properties": {"probabilities": {"type": "object", "properties": {label: {"type": "number"} for label in LABELS}}},
            "required": ["probabilities"],
        },
    }
    headers = {"Authorization": f"Bearer {settings.SYSTEMONE_API_KEY}"} if settings.SYSTEMONE_API_KEY else {}
    url = settings.SYSTEMONE_URL.rstrip("/") + "/v1/systemone"
    try:
        body = (transport or _http_transport)(url, payload, headers, settings.SYSTEMONE_TIMEOUT)
    except Exception as exc:  # network, HTTP status, bad JSON: all mean "no second opinion"
        logger.warning(f"decision model unavailable: {type(exc).__name__}")
        return None
    return _parse_probabilities(body)


def second_opinion(case_summary: str, transport: Transport | None = None) -> SecondOpinion | None:
    """Query the model and attach a conformal prediction set when a calibration exists."""
    probabilities = query_model(case_summary, transport)
    if probabilities is None:
        return None
    calibration = load_calibration()
    chosen = prediction_set(probabilities, calibration.quantile) if calibration else None
    return SecondOpinion(
        probabilities=probabilities,
        prediction_set=chosen,
        alpha=calibration.alpha if calibration else None,
        model=settings.SYSTEMONE_MODEL,
        calibrated=calibration is not None,
    )
