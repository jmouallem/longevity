# SLICE PROMPT  The Longevity Alchemist (Slice 4: AI Testing Harness)

You are implementing a testing harness pattern for AI-heavy builds.

Follow AGENTS.md and this slice prompt strictly.
Work only within the defined scope.
Do not refactor unrelated code.
Keep changes minimal and testable.

---

# Slice Goal

Add a deterministic, offline testing harness for AI-backed endpoints (starting with Slice #3 `/coach/question`).

This slice must:
1) introduce a FakeLLMClient with scenario modes (fixture-driven),
2) ensure tests never call external networks,
3) provide unit tests for safety + JSON parsing + context builder,
4) provide API tests for `/coach/question` using FastAPI dependency overrides,
5) run fast locally (`pytest -q`) and pass reliably.

No new runtime features beyond enabling dependency injection hooks needed for tests.

---

# What This Slice Must Include

## A) Test Tooling
- Add pytest if not present
- Add httpx (if not present) for TestClient support
- Optionally add freezegun (only if needed for time stability)

## B) LLM Client Interface + Fake
- Ensure production code calls the LLM through a single interface (e.g., `LLMClient.generate_json(...)`)
- Implement `FakeLLMClient` in tests with scenario modes:
  - OK_LUNCH_PLAN
  - OK_TIRED_ANALYSIS
  - MALFORMED_JSON
  - MISSING_FIELDS
  - TIMEOUT
  - REFUSAL

Fake must load JSON fixtures from `tests/fixtures/llm/*.json` where applicable.

## C) Golden Fixtures
Create:
- tests/fixtures/llm/OK_LUNCH_PLAN.json
- tests/fixtures/llm/OK_TIRED_ANALYSIS.json
- tests/fixtures/llm/MISSING_FIELDS.json
- tests/fixtures/llm/MALFORMED_JSON.txt

These fixtures must conform to the response contract used by `/coach/question`
(or to the internal LLM JSON contract if you parse it into response models).

## D) Database Test Harness (SQLite)
- Use a temporary SQLite database file per test session (pytest tmp_path)
- Ensure tables are created for tests (SQLAlchemy metadata create_all)
- Provide factories/fixtures:
  - create_user
  - auth_token (or login helper)
  - seed_baseline
  - seed_metrics
  - seed_scores (optional)

## E) FastAPI Dependency Overrides
- Add an override mechanism so tests can inject FakeLLMClient:
  - e.g., `get_llm_client()` dependency in app/services/llm.py
  - In tests: override dependency to return FakeLLMClient

If no dependency injection exists yet, implement minimal DI without refactors.

## F) Unit Tests (High ROI)
Add unit tests for:
1) safety red flag detection:
   - chest pain triggers escalation flag(s)
2) JSON parsing:
   - valid JSON passes
   - malformed JSON triggers ParseError / fallback path
3) context builder:
   - baseline missing produces context noting missing baseline
   - metrics summarized (not raw dump)

## G) API Tests (Mocked LLM)
Add API tests for `/coach/question`:
- unauthorized ? 401
- baseline missing ? asks for baseline / returns safe shape
- OK fixture ? returns response with required fields
- MALFORMED_JSON fixture ? returns fallback response shape
- safety phrase ? returns escalation response (LLM not used or overridden by safety)

---

# Out of Scope (Critical)

You MUST NOT:
- Add multi-agent council
- Add experiments
- Add UI
- Add photo/voice endpoints
- Add research ingestion
- Change scoring logic
- Refactor unrelated modules

Only add minimal DI hooks required to mock LLM client and DB if necessary.

---

# Files Allowed to Change

You may only modify or create:

Production (minimal DI hooks if needed):
- app/services/llm.py
- app/main.py (only if needed to register dependencies cleanly)
- app/db/session.py (only if needed to support test DB injection)

Tests:
- tests/conftest.py
- tests/api/test_coach.py
- tests/unit/test_safety.py
- tests/unit/test_json_parser.py
- tests/unit/test_context_builder.py
- tests/fixtures/llm/*
- requirements.txt (or pyproject.toml) for test deps

If additional files are required:
STOP and explain why before proceeding.

---

# Acceptance Criteria

This slice is complete when:

- [ ] `pytest -q` runs fully offline and passes
- [ ] No tests call external network (LLM calls mocked)
- [ ] FakeLLMClient supports scenario modes + fixtures
- [ ] Dependency overrides cleanly inject FakeLLMClient
- [ ] Temporary SQLite DB is used for tests
- [ ] Unit tests cover safety + parsing + context builder
- [ ] API tests cover main success + fallback + safety paths

---

# Verification Steps

After implementation provide:

1) Install deps (if needed):
   pip install -r requirements.txt

2) Run tests:
   pytest -q

3) (Optional) show how to run only coach tests:
   pytest -q tests/api/test_coach.py

---

# Implementation Requirements

- Keep diffs minimal
- Deterministic fixtures
- Clear test names
- No brittle assertions (assert shape and key fields)
- Use FastAPI dependency override pattern (do not monkeypatch internals everywhere)

---

# Deliverables Format

You must respond with:

1. PLAN
2. FILE CHANGES
3. FULL CODE FOR EACH CHANGED/CREATED FILE
4. HOW TO VERIFY
5. NOTES (assumptions + follow-ups)

---

# Reminder

This slice is only the testing harness.
No new features beyond DI hooks required for testing.

