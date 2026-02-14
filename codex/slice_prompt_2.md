# SLICE PROMPT  The Longevity Alchemist (Slice #2)

You are implementing a small vertical slice for The Longevity Alchemist.

Follow AGENTS.md and this slice prompt strictly.
Work only within the defined scope.
Do not refactor unrelated code.
Keep changes minimal and testable.

---

# Slice Goal

Implement metric logging (time-series) and basic scoring (domain + composite) with a dashboard summary endpoint.

This slice must allow an authenticated user to:
1) add metrics (time-stamped),
2) retrieve metrics (range),
3) compute/store latest domain scores + composite score,
4) retrieve a dashboard summary containing latest scores and recent metric trends.

NO AI integration yet.
NO multi-agent council yet.
NO experiments yet.
NO photo/voice yet.

---

# What This Slice Must Include

## A) Metrics (Time-Series)

### Endpoints (authenticated)
- POST /metrics
- GET  /metrics?metric_type=...&from=...&to=...

### Metric Types (minimum set)
Support at least these metric types:

Objective
- weight_kg (float)
- waist_cm (float)
- bp_systolic (int)
- bp_diastolic (int)
- resting_hr_bpm (int)
- sleep_hours (float)
- steps (int) (optional but recommended)
- active_minutes (int) (optional)

Subjective
- energy_1_10 (int)
- mood_1_10 (int)
- stress_1_10 (int)
- sleep_quality_1_10 (int)
- motivation_1_10 (int)

Validation required:
- metric_type must be one of allowed enums
- value must match expected type and reasonable range
- timestamp defaults to "now" if omitted (server time)
- user can only write/read their own metrics

Storage:
- Store as a normalized table: metrics(user_id, metric_type, value_num, value_text?, taken_at)

(You may implement all as numeric for MVP and skip text values for now.)

---

## B) Scoring (MVP, Transparent, Simple)

### Domain Scores (required)
Compute a score in range 0100 for:
- sleep_score
- metabolic_score
- recovery_score
- behavioral_score
- fitness_score (can be simple placeholder based on steps/active minutes if available)

### Composite Score (required)
- longevity_score = weighted average of domain scores
- Must be explainable and deterministic (no AI)

### Storage
- Store score snapshots with timestamp:
  domain_scores(user_id, sleep, metabolic, recovery, behavioral, fitness, computed_at)
  composite_scores(user_id, longevity_score, computed_at)

### Scoring Logic (MVP)
Use clear rules (simple and adjustable), e.g.:

Sleep Score:
- based on sleep_hours and sleep_quality_1_10 average over last 7 days

Metabolic Score:
- based on BP and waist and weight trend (last 30 days) if present

Recovery Score:
- based on stress + sleep + resting HR trend (last 714 days)

Behavioral Score:
- based on logging consistency (days with at least N metrics logged in last 7 days)

Fitness Score:
- based on steps or active minutes (last 7 days average)

Keep it minimal and documented in code comments.

---

## C) Dashboard Summary

### Endpoint (authenticated)
- GET /dashboard/summary

Response must include:
- latest domain scores + timestamp
- latest composite score + timestamp
- last 7 days trends for key metrics (at least: sleep_hours, weight_kg, bp_systolic/bp_diastolic if present, energy_1_10)

The endpoint should compute scores on demand if missing or stale.

---

# Out of Scope (Critical)

You MUST NOT:

- Implement LLM calls or coaching endpoints
- Implement multi-agent council
- Implement experiment engine
- Implement guided question engine
- Implement meal photo or voice endpoints
- Implement PubMed ingestion
- Add a front-end UI (API only this slice)
- Refactor auth/base code beyond what is needed

---

# Files Allowed to Change

You may only modify or create:

- app/api/metrics.py
- app/api/dashboard.py
- app/db/models.py
- app/db/session.py
- app/core/scoring.py
- app/main.py
- requirements.txt
- (optional) app/core/time.py (only if needed)

If additional files are required:
STOP and explain why before proceeding.

---

# Database Constraints

- SQLite only
- DB path: /var/data/longevity.db
- SQLAlchemy ORM

Add tables:
- metrics
- domain_scores
- composite_scores

Constraints:
- all rows keyed by user_id
- indexes for (user_id, metric_type, taken_at)

---

# Tests (Minimum)

Add minimal tests that verify:
- unauthorized cannot POST/GET metrics
- authenticated user can POST metrics
- metric validation rejects invalid types/ranges
- dashboard summary returns expected structure
- scoring returns values 0100 and composite is computed

Use the repos existing test framework (pytest recommended).
If no test framework exists yet, add pytest minimally and include 24 key tests.

---

# Acceptance Criteria

This slice is complete when:

- [ ] Authenticated user can add metrics
- [ ] Authenticated user can query metrics by type and date range
- [ ] Domain scores computed and stored
- [ ] Composite score computed and stored
- [ ] Dashboard summary returns latest scores and basic trends
- [ ] Unauthorized requests are rejected
- [ ] Server runs without errors
- [ ] Minimal tests pass

---

# Verification Steps

After implementation provide:

1) Run server:
   uvicorn app.main:app --reload

2) Add metric example:
   curl -X POST http://localhost:8000/metrics \
     -H "Authorization: Bearer <token>" \
     -H "Content-Type: application/json" \
     -d '{"metric_type":"sleep_hours","value":7.5,"taken_at":"2026-02-13T07:00:00"}'

3) Get metrics example:
   curl -X GET "http://localhost:8000/metrics?metric_type=sleep_hours&from=2026-02-01T00:00:00&to=2026-02-14T00:00:00" \
     -H "Authorization: Bearer <token>"

4) Get dashboard summary:
   curl -X GET http://localhost:8000/dashboard/summary \
     -H "Authorization: Bearer <token>"

5) Run tests (if pytest added):
   pytest -q

---

# Implementation Requirements

- Production-grade code
- Pydantic models for requests/responses
- Clear error handling and HTTP codes
- Deterministic scoring logic
- No excessive abstraction
- Keep diffs minimal

---

# Deliverables Format

You must respond with:

1. PLAN
2. FILE CHANGES
3. FULL CODE FOR EACH CHANGED FILE
4. HOW TO VERIFY
5. NOTES

---

# Reminder

Small vertical slice.
No AI.
No UI.
No experiments.
Just metrics + scoring + dashboard summary API.


----------------------------------------------------------------------------------------------------------------------




