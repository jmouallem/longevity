# SLICE PROMPT  The Longevity Alchemist (Slice #5)

You are implementing a small vertical slice for The Longevity Alchemist.

Follow AGENTS.md and this slice prompt strictly.
Work only within the defined scope.
Do not refactor unrelated code.
Keep changes minimal and testable.

---

# Slice Goal

Implement the first user-facing GUI for new-user onboarding and initialization.

This slice must provide:
1) a modern, card/board-style onboarding UI (Trello-like visual direction),
2) responsive mobile-first behavior,
3) account creation/login flow in the GUI,
4) mandatory LLM provider + deep thinker model + reasoning model + utility model + API key configuration in the GUI,
5) gating so intake cannot start until user account and LLM config are complete.

Intake is NOT started in this slice.

---

# What This Slice Must Include

## A) Frontend Onboarding Shell

Create a frontend onboarding experience with:
- clean modern layout (board/cards, clear sections, strong hierarchy),
- progress indicator for setup steps,
- clear desktop and phone behavior,
- accessible forms (labels, focus states, errors).

Visual direction requirements:
- Trello-inspired card/board feel (not a copy),
- modern spacing and typography,
- responsive breakpoints for mobile and desktop.

## B) Setup Flow Steps (Required Order)

Step 1: Create account or log in
- signup: email + password
- login: email + password
- persist auth token client-side securely for session use

Step 2: Configure LLM
- provider selector: `openai` | `gemini`
- dynamic model list loaded from provider API when possible
- deep thinker model selector
- reasoning model selector
- utility model selector
- model costs visible per option when known
- API key input
- submit to existing backend auth config endpoint

Step 3: Initialization complete
- show completion state
- show explicit CTA: "Start Intake"
- do not launch intake automatically

## C) Setup Gating Rules

Enforce:
- user cannot continue to completion without successful auth
- user cannot continue to completion without successful LLM config save
- intake routes/entry points remain disabled until both are complete

If LLM config is missing:
- show clear guidance to complete provider/model/key setup
- keep "Start Intake" disabled

## D) Backend Integration (Use Existing APIs)

Use current backend APIs only:
- `POST /auth/signup`
- `POST /auth/login`
- `PUT /auth/ai-config`
- `GET /auth/ai-config` (to verify setup state when needed)
- `POST /auth/model-options` (for dynamic provider model lists + best-default selection)

No new coaching/intake logic in this slice.
Only wiring for auth and LLM setup.

## E) UX + Validation

Required client-side and server-side aligned validation:
- email format
- password minimum requirements
- provider required
- deep thinker model required
- reasoning model required
- utility model required
- API key required

Required UX behavior:
- inline error messaging
- loading states on submit
- success confirmation after LLM config save
- no exposure of full API key after save

---

# Out of Scope (Critical)

You MUST NOT:
- start intake automatically
- implement intake questions UI
- implement coaching UI/chat interface
- add multi-agent council
- add experiments engine
- add photo/voice features
- refactor backend scoring/coaching logic

This slice is onboarding + initialization UI only.

---

# Files Allowed to Change

You may modify/create only files needed for:
- frontend onboarding UI
- frontend API client wiring for auth + LLM config
- minimal backend adjustments only if strictly required for integration compatibility
- tests for onboarding flow and gating behavior

If a non-UI backend feature is needed:
STOP and explain why before proceeding.

---

# Tests (Minimum)

Add tests that verify:
1) user can sign up or log in from GUI flow
2) user can configure provider/model/key from GUI flow
3) intake start action remains disabled until auth + LLM config are complete
4) mobile viewport layout remains usable
5) API errors render user-friendly messages

Prefer deterministic component/integration tests.

---

# Acceptance Criteria

This slice is complete when:

- [ ] New user can complete GUI setup in ordered steps
- [ ] Auth works from GUI (signup/login)
- [ ] LLM provider/model/key can be saved from GUI
- [ ] Start Intake remains blocked until setup is complete
- [ ] Trello-like modern board/card visual direction is implemented
- [ ] UI works on phone and desktop
- [ ] Validation and error states are clear
- [ ] Tests pass

---

# Verification Steps

After implementation provide:

1) Run app locally (backend + frontend as applicable)
2) Perform new-user setup manually:
   - signup/login
   - LLM config save
   - confirm Start Intake unlocks only after both
3) Verify mobile behavior using responsive dev tools
4) Run tests for onboarding and gating behavior

---

# Implementation Requirements

- Keep diffs minimal and focused
- Maintain stable existing backend contracts
- Use accessible form semantics
- Keep API keys server-side only after submission
- No hidden scope expansion

---

# Deliverables Format

You must respond with:

1. PLAN
2. FILE CHANGES
3. FULL CODE FOR EACH CHANGED/CREATED FILE
4. HOW TO VERIFY
5. NOTES

---

# Reminder

This slice is GUI onboarding and initialization only.
Account + LLM setup must complete before intake begins.
Do not start intake flow in this slice.
