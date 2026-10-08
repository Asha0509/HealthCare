# Project Issues and What Needs To Be Done

## Current Status
- Backend now supports provider fallback for LLM calls (Groq primary, NVIDIA NIM fallback).
- Emergency hard-stop logic is implemented for severe cardiac wording.
- Triage result now supports richer outputs including medications.
- Frontend displays medication guidance.

## Open Issues (Priority Order)

### 1) API Key and Secret Management (High)
- API keys are currently present in local env files and were manually shared during development.
- Risk: accidental secret exposure if env files are committed or copied.
- What needs to be done:
  - Rotate all exposed keys immediately.
  - Verify `.env` and `backend/.env` are ignored by git.
  - Add `.env.example` files with placeholders only.
  - Use environment-level secret management for deployment.

### 2) LLM Rate Limiting and Reliability (High)
- External LLM provider requests can fail with 429/5xx and malformed JSON.
- Current fallback exists, but retry strategy is basic.
- What needs to be done:
  - Add exponential backoff with jitter for retryable status codes.
  - Add stricter JSON schema validation and automatic repair prompt on parse failure.
  - Add per-provider timeout and circuit-breaker style temporary disable after repeated failures.

### 3) Provider Observability (High)
- It is hard to know which provider (Groq/NVIDIA/heuristic) generated each response in production.
- What needs to be done:
  - Persist provider name in triage result and audit logs.
  - Add lightweight `/api/system/llm-status` health endpoint.
  - Surface provider badge in UI for debugging mode.

### 4) Clinical Safety for Medication Guidance (High)
- Medication output is guidance-level text but can still be interpreted as prescription.
- What needs to be done:
  - Add stronger medication disclaimers for all triage labels.
  - For Urgent/Emergency, enforce wording: evaluation by clinician before medication.
  - Add red-flag blocklist for unsafe medication suggestions.

### 5) Database Migration Hygiene (Medium)
- Runtime column patching was added for backward compatibility.
- What needs to be done:
  - Add formal Alembic migration for `triage_results.medications`.
  - Remove runtime schema mutation once migration process is in place.

### 6) Startup Lifecycle Deprecation (Medium)
- FastAPI warns that `@app.on_event("startup")` is deprecated.
- What needs to be done:
  - Move startup logic to lifespan handlers.

### 7) Test Coverage Gaps (Medium)
- Existing tests validate core paths but not all new fallback/provider scenarios.
- What needs to be done:
  - Add tests for Groq failure -> NVIDIA success.
  - Add tests for malformed JSON from provider.
  - Add tests for medication field persistence and frontend rendering.

### 8) Hospital Recommendation Quality Controls (Medium)
- Location-aware recommendations can still return uneven quality in edge regions.
- What needs to be done:
  - Add validation checks (phone/address/maps_url quality).
  - Add robust deterministic fallback catalog per city/state if LLM response is weak.

## Immediate Next Sprint Plan
1. Security hardening: rotate keys, confirm `.env` ignore, add `.env.example`.
2. Reliability: implement retry/backoff + parse-repair flow.
3. Observability: persist provider metadata and add LLM status endpoint.
4. Safety: medication safety filter and explicit emergency wording enforcement.
5. Migration: create Alembic migration for medications column.
6. QA: add provider fallback and malformed-output tests.

## Definition of Done for Stabilization
- No secrets in repository history.
- Triage remains functional under provider rate limits/outages.
- Provider path is visible in logs and result metadata.
- Safety checks pass for all emergency and medication scenarios.
- All new fallback paths covered by automated tests.
