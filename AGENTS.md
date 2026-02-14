# AGENTS.md

## Mission
Build **The Longevity Alchemist** as a focused, deployable, AI-assisted longevity coaching system.
Prioritize incremental vertical slices, stable API contracts, deterministic behavior, and user safety.

## Product Goals
- Help users establish a structured baseline, define goals, track metrics, and receive adaptive coaching.
- Keep guidance evidence-informed, practical, and supportive.
- Preserve user privacy and strict per-user data isolation.
- Ship small, testable slices rather than broad refactors.

## Current Build Strategy
Use the project slice prompts as the source of truth:
1. Slice 1: auth + baseline intake persistence
2. Slice 2: metrics + scoring + dashboard summary
3. Slice 3: coaching endpoint (single LLM call)
4. Slice 4: offline AI testing harness
5. Slice 5: GUI onboarding + initialization gate before intake
6. Slice 6: skippable/re-runnable intake from main workspace + settings menu + token usage stats

When working a slice:
- Implement only that slice's goal and acceptance criteria.
- Respect "Out of Scope" constraints.
- Change only files listed as allowed for that slice unless explicitly approved.

## Slice Selection Rule
- Work one active slice at a time.
- If the user does not specify a slice and work cannot be inferred confidently, ask one concise clarification question before coding.
- Do not blend requirements across slices unless the user explicitly requests multi-slice work.

## Instruction Precedence
If documents conflict, resolve in this order:
1. Active `codex/slice_prompt_<n>.md`
2. `AGENTS.md`
3. Project planning/reference docs (`docs/*`, `PROJECT_CONTEXT.md`, `codex/system_prompt.md` index)

## Architecture Guardrails
- Runtime: single Docker container on Render.
- Backend: FastAPI.
- Persistence: SQLite on persistent disk path (`/var/data/longevity.db`).
- LLM calls: server-side only.
- No client-side secret exposure.
- No external database for MVP.
- Do not store meal images or audio files; store only structured outputs/transcripts where applicable.
- Model catalogs should be fetched from provider APIs when possible, with deterministic fallback lists.
- Support three user model profiles:
  - deep thinker profile (manual deep-think submissions)
  - reasoning profile (default analysis/planning tasks)
  - utility profile (routing/summarization/classification/other utility tasks)
- Route deep-think submissions to the deep thinker profile by default.
- Route lightweight utility tasks to the utility profile by default.

## Data and API Requirements
- Use Pydantic models for request/response validation.
- Keep response schemas stable and explicit.
- Enforce auth on user-scoped endpoints.
- Enforce per-user data isolation in all reads/writes.
- Keep domain logic outside route handlers when possible.

## Security Requirements
- Passwords must be hashed (never plaintext).
- JWT/session secrets come from environment variables.
- Never commit or log secrets.
- Treat supplement and health-risk guidance conservatively.

## Safety Requirements
- Do not provide medical diagnosis.
- Include non-medical disclaimer where required.
- Detect urgent red-flag symptom language and escalate to professional/emergency care guidance.
- Use supportive, non-shaming tone.

## Testing Requirements
- Prefer deterministic tests.
- For AI features: no-network tests by default.
- Mock or fake LLM clients using dependency injection.
- Validate JSON contracts and fallback behavior.
- Use isolated SQLite test DB state.

## Drift Prevention
Before finalizing changes, verify:
- No scope creep beyond current slice.
- No architecture mutation (single container + SQLite remains true).
- No contract-breaking API changes unless intentionally versioned.
- No safety/security regression.
- Tests cover touched critical behavior.

## Documentation Consistency
If behavior or scope changes, update relevant docs in the same PR:
- `docs/USERNEEDS.md`
- `docs/USERNEEDS_CHECKLIST.md`
- `docs/TRACEABILITY.md`
- `docs/ARCHITECTURE.md`
- `docs/BLUEPRINT.md`
- `docs/BUILD_ROADMAP.md`
- `docs/DRIFT_DETECTION_CHECKLIST.md`
- `docs/TESTING_HARNESS.md`
- `PROJECT_CONTEXT.md`
- `codex/slice_prompt_*.md` (if slice contracts change)

## Implementation Style
- Keep diffs minimal and reviewable.
- Prefer clarity over abstraction.
- Avoid speculative frameworks and premature generalization.
- Add brief comments only where logic is non-obvious.

## Change Budget Heuristic
- Default to bounded, slice-sized diffs.
- For normal slice work, avoid broad rewrites and keep changes concentrated in expected files.
- If a larger rewrite is truly required, explain why and get user confirmation before expanding scope.

## Deliverable Style
- Keep summaries concise and concrete.
- For implementation tasks, include: what changed, why, and exact verification commands.
- For review requests, report findings first (severity-ordered), then open questions, then brief summary.

## Definition of Done (Per Slice)
A slice is done only when:
- Acceptance criteria are met.
- Required tests pass.
- Unauthorized access paths are rejected correctly.
- Output contracts are stable.
- Documentation remains consistent.

## Escalation and Clarification
Ask for clarification before implementing if:
- Requirements conflict across docs.
- A needed file is outside the allowed slice list.
- Safety expectations are ambiguous.
- A change would expand scope materially.
