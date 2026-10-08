#!/usr/bin/env bash
# One-command validation: lint -> tests -> safety eval gate -> (agent eval if a key is set) -> frontend build.
# Usage: scripts/validate.sh [--skip-frontend]
set -uo pipefail
cd "$(dirname "$0")/.."

STAGES=(); FAILED=0
stage() { # name, command...
  local name="$1"; shift
  local t0=$SECONDS
  echo; echo "==> $name"
  if "$@"; then STAGES+=("PASS  $name ($((SECONDS - t0))s)"); else STAGES+=("FAIL  $name ($((SECONDS - t0))s)"); FAILED=1; fi
}
finish() { echo; echo "---- validation summary ----"; printf "%s\n" "${STAGES[@]}"; exit $FAILED; }

stage "lint (ruff)" ruff check .
cd backend
stage "unit + API tests" python -m pytest -q
stage "safety eval, rules pipeline (gated)" python ../evals/run_eval.py --pipeline rules --gate --out /tmp/rules-eval.json
if [[ -n "${GROQ_API_KEY:-}" ]]; then
  stage "safety eval, agent pipeline (gated)" python ../evals/run_eval.py --pipeline agent --gate --delay 2 --out /tmp/agent-eval.json
else
  echo "(agent eval skipped: GROQ_API_KEY not set)"
fi
cd ..
if [[ "${1:-}" != "--skip-frontend" && -d frontend/node_modules ]]; then
  stage "frontend build" bash -c "cd frontend && npm run build"
fi
finish
