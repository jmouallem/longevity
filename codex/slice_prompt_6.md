# Slice 6 - Main Workspace + Intake Lifecycle

## Objective
Implement intake lifecycle in the main workspace:
- new users can start intake immediately after setup or skip it,
- existing users can run/re-run intake anytime,
- intake completion is visible in the UI,
- intake completion returns user to default chat,
- settings are available from a menu,
- token usage is tracked per model.

## In Scope
- Main workspace page (`/app`) with one-screen-at-a-time menu views:
  - Chat (default)
  - Intake
  - Settings
  - Model Usage
- Chat UX behavior:
  - processing/progress notice while coach pipeline runs
  - follow-up prompts rendered as coach questions for the user to answer next
  - readable markdown-style answer rendering
- Onboarding completion screen supports:
  - `Start Intake Now`
  - `Skip For Now`
  - Instruction that intake can be run later from main menu.
- Existing-user login path:
  - if AI config exists, go directly to `/app`.
- Intake lifecycle APIs:
  - `GET /intake/status`
  - `POST /intake/baseline` upsert remains re-runnable.
- Settings APIs:
  - `PUT /auth/change-password`
  - existing AI config update endpoints from settings menu.
- Usage API:
  - `GET /auth/model-usage`.
- Persist token usage stats per user/provider/model.

## Out Of Scope
- Multi-agent orchestration
- Full chat history UI
- Billing/monetization
- External integrations (Apple Health/Hume live sync)

## Acceptance Criteria
- New-user flow after AI setup offers both intake start and skip.
- Main workspace shows intake completion status (`completed` vs `pending`).
- Intake can be completed or updated from main menu at any time.
- After successful intake submit, UI switches to chat view.
- Settings menu allows:
  - updating AI model config,
  - changing password.
- Token usage endpoint returns per-model counters.
- Chat view clearly distinguishes successful response vs practical fallback response.
- Test suite passes.
