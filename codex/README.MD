# The Longevity Alchemist (Codex Workspace)

The Longevity Alchemist is an AI-powered longevity coaching project built with a strict slice-based workflow.
This `codex/` area defines how coding agents should execute work with minimal drift.

## Summary (From User Needs)
The Longevity Alchemist is a structured, adaptive longevity coaching system that helps users:
- establish a baseline,
- define measurable goals,
- track metrics over time,
- receive contextual, science-informed coaching,
- and improve guidance through ongoing feedback.

It is designed to be evidence-informed, supportive, and practical, with strong privacy defaults:
- authenticated multi-user accounts,
- strict per-user data isolation,
- per-user AI provider/model configuration (BYOK),
- support for OpenAI (ChatGPT) and Gemini,
- server-side AI integration,
- SQLite-backed persistence,
- and no long-term image/audio storage in early slices.

The product is explicitly **not** a medical diagnosis tool. It provides coaching and educational guidance, includes safety guardrails for urgent symptom language, and maintains transparent scoring and recommendation logic as the system evolves.
## Source Of Truth
Use these files in order:
1. `../AGENTS.md`
2. `system_prompt.md` (index + load order + precedence)
3. One active slice file:
   - `slice_prompt_1.md`
   - `slice_prompt_2.md`
   - `slice_prompt_3.md`
   - `slice_prompt_4.md`

## Supporting Docs
Load only what is needed for the active task:
- `../PROJECT_CONTEXT.md`
- `../docs/USERNEEDS.md`
- `../docs/USERNEEDS_CHECKLIST.md`
- `../docs/TRACEABILITY.md`
- `../docs/DRIFT_DETECTION_CHECKLIST.md`
- `../docs/TESTING_HARNESS.md`
- `../docs/ARCHITECTURE.md`
- `../docs/BLUEPRINT.md`
- `../docs/BUILD_ROADMAP.md`

## Instruction Precedence
If instructions conflict:
1. Active `slice_prompt_<n>.md`
2. `../AGENTS.md`
3. Project reference docs (`../docs/*`, `../PROJECT_CONTEXT.md`, `system_prompt.md`)

## Vibe Coding Rules
- Work one slice at a time.
- Do not blend slice scopes unless explicitly requested.
- Keep diffs small and focused.
- Respect each slice's "Out of Scope" and "Files Allowed to Change" sections.
- Verify with acceptance criteria and tests before finishing.

## Quickstart
See `QUICKSTART.md` for the 60-second startup flow.

## Safety + Security Baseline
- No medical diagnosis claims.
- Escalate urgent red-flag symptom language.
- Keep LLM/API keys server-side only.
- Preserve per-user data isolation.
- Use SQLite on persistent storage path (`/var/data/longevity.db`) for deployed runtime.
- Keep external integrations modular (provider adapters) so Apple Health/Hume sync can be added later without coupling core logic.

## Notes
This `codex/README.MD` is intentionally concise. Detailed product, architecture, and roadmap context lives in `../docs/` and `../PROJECT_CONTEXT.md`.
