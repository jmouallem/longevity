# Drift Detection Checklist
## The Longevity Alchemist (Vibe Coding Guardrails)

Use this checklist after every Codex CLI session (or before you merge) to catch drift:
scope creep, architecture mutation, unsafe behavior, and creeping complexity.

---

# 1) Scope Drift (Did we build more than we intended?)

- [ ] The change matches the Slice Goal exactly (no extra features).
- [ ] Out of Scope items were not implemented.
- [ ] No new endpoints were added beyond what the slice required.
- [ ] No new tables/models were added beyond what the slice required.
- [ ] No future-proof abstractions were introduced just in case.
- [ ] No unrelated refactors were included (naming, formatting, reorganizing).
- [ ] Files changed match the Files Allowed to Change list.

**Red flags**
- While I was here changes
- broad renames/moves
- new frameworks introduced without request

---

# 2) Architecture Drift (Are we still following the intended architecture?)

## Container & Services
- [ ] Still a **single Docker container** runtime.
- [ ] No external databases were introduced (Postgres/Supabase/etc.).
- [ ] SQLite remains the source of truth.

## Data Persistence
- [ ] SQLite path is still `/var/data/longevity.db` (or configured path).
- [ ] Writes/reads use the DB access layer consistently.
- [ ] No in-memory-only critical state introduced.

## Media Rules
- [ ] No image storage (only structured results stored).
- [ ] No audio storage (only transcripts stored).
- [ ] Temporary files are cleaned up.

## AI Calls
- [ ] LLM calls are **server-side only**.
- [ ] No client-side API keys or direct browser calls to LLM providers.
- [ ] Dynamic model catalog lookup has deterministic fallback list behavior.
- [ ] Model selectors expose cost metadata when available.
- [ ] Deep-think submissions route to deep thinker model profile by default.
- [ ] Utility tasks route to utility model profile by default.
- [ ] Reasoning tasks route to reasoning model profile by default.

---

# 3) Contract Drift (Did data shapes stay stable?)

## API Contracts
- [ ] Request/response schemas match documented contracts.
- [ ] Response always includes required fields (especially for AI endpoints).
- [ ] Error responses are consistent and predictable.
- [ ] Intake status contract (`/intake/status`) remains stable.
- [ ] Model usage contract (`/auth/model-usage`) remains stable.

## AI Output Contracts
- [ ] LLM responses are validated against schema.
- [ ] JSON parsing is robust (handles invalid/missing fields).
- [ ] Fallback responses exist and remain safe.
- [ ] Confidence values and enums are clamped/validated.

## DB Schema
- [ ] Schema changes were intentional and documented.
- [ ] No breaking schema changes without migrations or compatibility plan.
- [ ] Indexes added where time-series queries need them.

---

# 4) Safety Drift (Are we still safe and responsible?)

- [ ] Non-medical disclaimer still present where appropriate.
- [ ] Red-flag symptom detection still works (e.g., chest pain).
- [ ] System does NOT diagnose emergencies.
- [ ] Supplement guidance includes safety cautions and contraindication awareness.
- [ ] User override logic explains consequences and monitoring.
- [ ] No overconfident medical claims were introduced.

**Red flags**
- This will fix your condition
- dosage advice without warnings
- no escalation guidance for urgent symptoms

---

# 5) Security Drift (Did we accidentally weaken security?)

- [ ] Auth still required for user-specific endpoints.
- [ ] Per-user isolation enforced on every read/write.
- [ ] Passwords are hashed (never stored in plaintext).
- [ ] JWT/session secret is required and loaded from env var.
- [ ] No secrets committed to repo.
- [ ] No secrets logged (API keys, tokens, password fields).
- [ ] Rate limiting considered on AI endpoints (optional early, required later).

---

# 6) Complexity Drift (Did we over-engineer?)

- [ ] New abstractions were introduced only if used by = 2 features.
- [ ] New frameworks were not introduced unnecessarily.
- [ ] Code remains readable and simple.
- [ ] No giant god classes or manager objects appeared.
- [ ] Business logic is separated from transport (API layer vs core logic).

**Red flags**
- multiple layers of indirection for simple tasks
- too many design patterns in early MVP
- refactor churn

---

# 7) Test Drift (Are we still testable?)

- [ ] Tests exist for core logic touched.
- [ ] AI endpoints are tested with mocked LLM (no network).
- [ ] DB tests use isolated SQLite instances (no state leakage).
- [ ] The test suite still runs quickly (`pytest -q` under ~20s).
- [ ] New behavior has at least one deterministic test.

**Red flags**
- Well add tests later
- integration tests calling the real LLM on every run

---

# 8) Performance Drift (Did we introduce obvious inefficiencies?)

- [ ] No unbounded queries (especially metrics/time-series).
- [ ] Pagination exists where needed.
- [ ] Context builder summarizes (doesnt dump huge raw history).
- [ ] LLM context is compact and relevant.

---

# 9) User Experience Drift (Is the product still aligned with user needs?)

- [ ] Responses include practical next actions.
- [ ] Suggested next questions are present (guided questioning).
- [ ] Tone remains warm and supportive (no shame).
- [ ] The system is still scientific coach, not generic advice bot.
- [ ] Setup completion offers both start-intake-now and skip-for-now paths.
- [ ] Intake can be re-run from main workspace menu at any time.
- [ ] Workspace settings menu still supports AI config update and password change.
- [ ] Intake coach flow remains one-question-at-a-time, not multi-question dumps.
- [ ] Intake concern probing deepens only in flagged/prioritized domains.

---

# 10) Quick Diff Smell Test (Fast check)

When you look at the git diff, verify:

- [ ] < ~400 lines changed for a small slice (rule of thumb)
- [ ] Mostly additive changes (not sweeping rewrites)
- [ ] Changes concentrated in expected files
- [ ] No surprise dependency additions
- [ ] No massive file moves/renames

---

# What To Do If You Detect Drift

If any box fails:

1) **Stop merging**
2) Identify drift type:
   - scope / architecture / safety / security / complexity
3) Re-scope into a separate slice:
   - revert unrelated changes
   - keep only slice-aligned commits
4) Add a guardrail:
   - update system prompt / slice template
   - add tests to lock behavior

---

# ? Ready to Merge Gate

You may merge only if:

- [ ] No high-risk drift detected (Safety/Security/Architecture)
- [ ] Slice Acceptance Criteria met
- [ ] Tests pass
- [ ] Diff smell test passes
