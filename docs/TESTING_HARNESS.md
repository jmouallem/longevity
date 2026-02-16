# Testing Harness Pattern for AI-Heavy Builds
## The Longevity Alchemist

This document defines a repeatable testing approach for AI-integrated systems where:
- AI outputs can be non-deterministic
- External calls are expensive and flaky
- Safety and correctness matter

Goal: **Fast, deterministic tests** that validate the systems *contracts* and *guardrails* without making real network calls.

---

# 1) Core Testing Strategy

## 1.1 Test the System Around the AI (Not the AI)
We do NOT test whether the LLM is smart.
We test that our software:
- builds correct context,
- enforces safety rules,
- validates and parses structured output,
- handles failures gracefully,
- stores correct state,
- returns correct response shape.

## 1.2 Shift Uncertainty into Contracts
All LLM calls must produce **structured JSON** with a strict schema.
Tests enforce:
- schema validity,
- required fields,
- allowed ranges,
- fallback behavior when schema is violated.

## 1.3 Use Three Test Layers
1) **Unit tests** (pure functions)
2) **Component tests** (LLM mocked)
3) **Contract tests** (golden fixtures; optional live test in CI nightly)

---

# 2) Architectural Hook for Testing

## 2.1 Dependency Injection for LLM Client
Your coaching orchestration must call an interface (or protocol), not a concrete SDK call:

- `LLMClient.generate_json(prompt, schema, timeout) -> dict`
- In production: calls OpenAI/Gemini
- In tests: returns fixtures or error modes

### Why?
So tests can simulate:
- good JSON
- malformed JSON
- tool timeout
- refusal / safety block
- partial fields

---

# 3) The LLM Stub Matrix Pattern

Create a stub that can return deterministic outputs by scenario.

### Scenario examples
- `OK_LUNCH_PLAN`
- `OK_TIRED_ANALYSIS`
- `MALFORMED_JSON`
- `MISSING_FIELDS`
- `TIMEOUT`
- `REFUSAL`
- `HALLUCINATED_FIELDS`

This makes tests explicit and reusable.

---

# 4) Recommended Test Tooling (Python)

- pytest
- httpx TestClient (FastAPI)
- freezegun (optional) for deterministic timestamps
- sqlite in-memory or temp file DB per test

Principle:
- **No network calls in unit/component tests**
- **No persistent state leakage between tests**

---

# 5) Database Harness Pattern (SQLite)

## 5.1 Use a Test Database per Test Session
Use either:
- in-memory SQLite: `sqlite:///:memory:` (fast but sometimes tricky with threads)
- temp file SQLite: `sqlite:////tmp/test_longevity.db` (more realistic)

Recommended: **temp file** for reliability.

## 5.2 Seed Data via Fixtures
Create pytest fixtures:
- `user_factory`
- `baseline_factory`
- `metrics_factory`
- `scores_factory`

Keep seeds minimal and targeted.

---

# 6) Context Builder Tests (High ROI)

The context builder is the most important AI-facing module.

### Test Cases
- baseline missing ? context includes missing baseline marker
- metrics missing ? context reflects missing data
- lots of metrics ? context summarizes trends, not raw dump
- date range filtering correct
- contains only allowed fields (no secrets)

These should be **unit tests**: no FastAPI client required.

---

# 7) Safety Harness Tests (Non-negotiable)

Create a pure function:
- `detect_red_flags(user_text) -> list[str]`
- `build_safety_response(flags) -> response_model`

### Test Cases
- chest pain ? triggers escalation response
- stroke-like symptoms ? triggers escalation
- suicidal ideation (if supported) ? escalation
- supplement contraindication mention (basic rules) ? adds caution flags

These must be deterministic unit tests.

---

# 8) JSON Parsing & Fallback Tests (Critical)

Create a parser function:
- `parse_agent_json(raw_text) -> dict | ParseError`
- `fallback_response(question, reason) -> response_model`

### Test Cases
- valid JSON passes
- invalid JSON triggers fallback
- missing fields triggers fallback or defaults
- wrong types triggers fallback
- confidence out of range clamps or rejects

---

# 9) API Component Tests (LLM Mocked)

Use FastAPI TestClient.

### Example tests for `/coach/question`
- unauthorized returns 401
- baseline missing returns please complete baseline
- LLM OK returns response with required fields
- LLM malformed JSON returns fallback response (still valid shape)
- LLM returns partial/mixed JSON inside `answer` -> response normalizer returns clean readable text
- GPT-5 empty-output or incomplete-output behavior still returns usable fallback/salvaged text
- safety flags override LLM (escalation path)
- model catalog endpoint returns provider models or fallback list deterministically
- best default model is selected from available model list
- task router selects utility model for summarization/routing/extraction tasks
- auto mode resolves to quick mode for cost guardrails
- duplicate identical questions within cache TTL return stable cached response shape

---

# 10) Golden Fixture Pattern

For stable behavior validation:
- Store expected LLM JSON outputs in fixtures:
  - `tests/fixtures/llm/OK_LUNCH_PLAN.json`
  - `tests/fixtures/llm/MALFORMED_JSON.txt`

Tests load these and assert outputs.

This prevents prompt drift from silently breaking your parsing.

---

# 11) Optional Live Tests (Controlled)

Live tests should be:
- opt-in
- separate mark (pytest marker)
- not run on every commit
- run nightly or manually

Example:
- `pytest -m live_llm`

Purpose:
- detect upstream model behavior changes
- validate prompt still yields valid JSON

Never block normal CI on these.

---

# 12) Minimal Reference Implementation Pattern (Pseudo)

## 12.1 Interface
- `LLMClient` has a single method that returns structured dict or raises.

## 12.2 Orchestrator uses interface
- Orchestrator receives `llm_client` via DI (FastAPI dependency or simple parameter).

## 12.3 Tests replace it
- Provide `FakeLLMClient(mode="MALFORMED_JSON")`.

---

# 13) What to Measure in Tests

Assert these, not quality:
- Response schema shape always valid
- Safety overrides work
- Context includes correct facts
- DB writes occur as expected (summaries stored)
- Score calculation deterministic
- No PII leakage beyond intended fields
- Utility task class uses utility model profile by default
- Deep-think task class uses deep thinker model profile by default
- Reasoning task class uses reasoning model profile by default
- Intake status endpoint correctly reflects baseline completion
- Workspace settings endpoints (password change) enforce auth and validation
- Intake coach asks one question at a time and advances deterministically
- Risk/concern flags trigger deeper follow-up questions in intake flow
- Coach follow-up questions are framed as user-response prompts
- Token and mode routing behavior remain deterministic and testable

---

# 14) Recommended Test Folder Layout

tests/
  conftest.py
  fixtures/
    llm/
      OK_LUNCH_PLAN.json
      OK_TIRED_ANALYSIS.json
      MALFORMED_JSON.txt
  unit/
    test_context_builder.py
    test_safety.py
    test_json_parser.py
    test_scoring.py
  api/
    test_auth.py
    test_metrics.py
    test_dashboard.py
    test_coach.py

---

# 15) Definition of Done for AI Features

An AI-backed feature is complete when:

- [ ] Context builder covered by unit tests
- [ ] Safety rules covered by unit tests
- [ ] JSON parsing + fallback covered by unit tests
- [ ] API endpoint covered with mocked LLM component tests
- [ ] No-network test suite runs under ~1020 seconds locally
- [ ] Optional live tests exist but are not required for normal CI

---

# 16) Why This Works

This harness ensures:
- fast iteration (vibe coding friendly)
- predictable outputs
- guardrails against unsafe behavior
- resilience to model variance
- confidence that system logic is correct

The LLM can change  your system should not break.

************************************************************************************

If Codex asks how do I inject the fake?, the clean pattern is:
In app/services/llm.py:


define def get_llm_client() -> LLMClient: ...


In your endpoint:


llm: LLMClient = Depends(get_llm_client)


In tests:


app.dependency_overrides[get_llm_client] = lambda: FakeLLMClient("OK_LUNCH_PLAN")


Same idea applies to DB sessions if your repo uses Depends(get_db).
