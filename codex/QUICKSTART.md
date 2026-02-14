# Quickstart For Codex Sessions

## Goal
Start fast with minimal context while preserving slice discipline.

## 60-Second Startup
1. Read `AGENTS.md`.
2. Read `codex/system_prompt.md` (index and precedence only).
3. Identify active slice: `codex/slice_prompt_<n>.md`.
4. Load only the required supporting docs:
   - Always as needed: `PROJECT_CONTEXT.md`
   - Scope/requirements: `docs/USERNEEDS.md`, `docs/USERNEEDS_CHECKLIST.md`, `docs/TRACEABILITY.md`
   - Guardrails: `docs/DRIFT_DETECTION_CHECKLIST.md`, `docs/TESTING_HARNESS.md`
5. Implement only active-slice scope.
6. Verify with slice acceptance criteria and tests.
7. Update docs if scope/contracts changed.

## Defaults
- One active slice at a time.
- Keep diffs bounded and focused.
- Avoid network calls in AI tests (mock/fake LLM).
- Keep API contracts explicit and stable.
- For onboarding/model work: prefer dynamic provider model lookup with deterministic fallback lists.
- Keep deep-thinker, reasoning, and utility model profiles explicit in contracts and tests.
- For model selectors, expose per-model cost metadata when known.

## Output Checklist
- What changed
- Why it changed
- How to verify (exact commands)
- Any risks or assumptions
