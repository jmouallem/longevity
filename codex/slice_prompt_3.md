# SLICE PROMPT  The Longevity Alchemist (Slice #3)

You are implementing a small vertical slice for The Longevity Alchemist.

Follow AGENTS.md and this slice prompt strictly.
Work only within the defined scope.
Do not refactor unrelated code.
Keep changes minimal and testable.

---

# Slice Goal

Implement the **first coaching endpoint** using a **single LLM call** (no multi-agent council yet).

This slice must allow an authenticated user to:
1) ask a coaching question (e.g., what next?, what should I eat for lunch?, Im tired),
2) receive a contextual answer based on stored baseline + recent metrics + latest scores,
3) receive suggested next best questions (guided prompts),
4) store a compact conversation summary in SQLite.

No meal photo handling.
No voice handling.
No research ingestion.
No multi-agent council.
No experiments engine.

---

# What This Slice Must Include

## A) Coaching Q&A Endpoint (Authenticated)

### Endpoint
- POST /coach/question

### Request Body (Pydantic)
- question: string (required)
- mode: enum ["quick","deep"] (optional, default "quick")
- context_hint: string (optional) (user may specify lunch, sleep, training, etc.)

### Response Body
- answer: string
- rationale_bullets: string[] (37 bullets, plain language)
- recommended_actions: { title: string, steps: string[] }[] (13 items)
- suggested_questions: string[] (38 items)
- safety_flags: string[] (0+ items)
- disclaimer: string (always present, short)

---

## B) Context Builder (Deterministic, DB-first)

When answering, the backend must load:
- user baseline (if exists)
- last 7 days metrics (relevant types only)
- latest domain scores + composite score (from Slice #2)
- user goals (if goals table exists; otherwise omit with TODO note)

Then build a compact context object to send to the LLM.

Rules:
- Keep context concise (summarize trends; do not dump raw rows)
- Include only relevant metrics (sleep, BP, weight, energy/mood/stress, activity)
- If baseline is missing: ask user to complete baseline before detailed advice

---

## C) LLM Service (Server-Side Only)

- Add an LLM client module (if not present) in `app/services/llm.py`
- Must read provider/model/key from authenticated user's saved AI config when available
- Must never expose key to client
- Must handle timeouts and failures gracefully

Provider support (minimum):
- OpenAI (ChatGPT models)
- Gemini

Fallback behavior:
- If per-user key is missing/invalid, return actionable setup guidance
- Env-level fallback keys may be supported for controlled dev/admin use only

**LLM Call Style**
- Single call per request
- Must request structured JSON output
- Must validate/parse JSON
- If invalid JSON: fallback to a safe minimal response with suggested next steps and prompt user to retry

---

## D) The Longevity Alchemist Voice (Wrapper Only)

Persona requirements:
- warm, witty (lightly; adaptive)
- clear, practical, science-informed
- never shame-based
- gentle coaching when user choices are risky

Persona must be applied in a **single wrapper** function so internal logic remains structured.

---

## E) Safety Guardrails (MVP)

Implement a minimal safety layer that:
- scans user question for urgent symptoms (e.g., chest pain, fainting, stroke signs)
- if detected:
  - return a seek professional care / emergency services response
  - do NOT attempt to diagnose

Also ensure supplement-related guidance includes:
- short caution statement
- check with clinician if on meds / conditions style warning

---

## F) Conversation Summary Persistence

Add a table to store compact conversation summaries:

- conversation_summaries:
  - id
  - user_id
  - created_at
  - question (short)
  - answer_summary (short)
  - tags (optional string)
  - safety_flags (optional string/json)

Store only summaries (not full transcripts).

---

## G) Suggested Question Hints (Mandatory)

The response MUST include suggested_questions even if the user asked something narrow.

Suggested questions should be derived from:
- missing data (e.g., no BP data)
- recent negative trends
- goal alignment
- common next steps (Want lunch options?, Want a sleep optimization plan?)

This can be produced by the LLM output contract, but must exist even on fallback.

---

# Out of Scope (Critical)

You MUST NOT:

- Implement multi-agent AI council
- Implement experiments engine
- Implement guided question engine UI (API only)
- Implement meal photo endpoints
- Implement voice endpoints
- Implement research ingestion / PubMed
- Refactor metrics/scoring logic beyond whats required to build context
- Add a front-end UI

---

# Files Allowed to Change

You may only modify or create:

- app/api/coach.py
- app/services/llm.py
- app/core/safety.py
- app/core/persona.py
- app/core/context_builder.py
- app/db/models.py
- app/db/session.py
- app/main.py
- requirements.txt
- tests/test_coach.py (or similar)

If additional files are required:
STOP and explain why before proceeding.

---

# Database Constraints

- SQLite only
- DB path: /var/data/longevity.db
- SQLAlchemy ORM

Add table:
- conversation_summaries (as specified)

Index:
- (user_id, created_at)

---

# Tests (Minimum)

Add minimal tests to verify:
- unauthorized cannot call POST /coach/question
- authorized can call POST /coach/question
- if baseline missing, response asks user to complete baseline
- safety trigger returns emergency guidance response (for a test phrase)
- JSON parse failure triggers fallback response structure

Mock LLM call in tests (do not call external network).

---

# Acceptance Criteria

This slice is complete when:

- [ ] Authenticated user can ask /coach/question
- [ ] Response includes: answer, rationale_bullets, recommended_actions, suggested_questions, safety_flags, disclaimer
- [ ] Backend loads baseline + recent metrics + latest scores to build context
- [ ] Safety guardrails trigger appropriate escalation response
- [ ] Conversation summary is stored in SQLite
- [ ] LLM failures return safe fallback response
- [ ] Tests pass
- [ ] Server runs without errors

---

# Verification Steps

After implementation provide:

1) Run server:
   uvicorn app.main:app --reload

2) Ask coaching question:
   curl -X POST http://localhost:8000/coach/question \
     -H "Authorization: Bearer <token>" \
     -H "Content-Type: application/json" \
     -d '{"question":"What should I eat for lunch today?","mode":"quick"}'

3) Safety test:
   curl -X POST http://localhost:8000/coach/question \
     -H "Authorization: Bearer <token>" \
     -H "Content-Type: application/json" \
     -d '{"question":"I have chest pain and feel faint.","mode":"quick"}'

4) Run tests:
   pytest -q

---

# Implementation Requirements

- Production-grade code
- Pydantic request/response models
- Deterministic context builder
- Robust JSON parsing + fallback response
- Strict server-side secret handling
- Minimal diffs, no scope creep

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

This slice is single-call coaching only.
No multi-agent council.
No photo/voice.
No experiments.
No research ingestion.
Keep it tight and deployable.

----------------------------------------------------------------------------------------




