# SLICE PROMPT  The Longevity Alchemist (Slice #1)

You are implementing a small vertical slice for The Longevity Alchemist.

Follow AGENTS.md and this slice prompt strictly.
Work only within the defined scope.
Do not refactor unrelated code.
Keep changes minimal and testable.

---

# Slice Goal

Implement user authentication and structured, adaptive baseline intake persistence.

This slice must allow:

1. User signup
2. User login
3. Authenticated baseline submission
4. Baseline retrieval
5. Data stored in SQLite at /var/data/longevity.db
6. Goal/risk/engagement-adaptive intake flow (deterministic, no LLM)
7. Per-user AI provider/model/key configuration at signup (BYOK)

No AI integration yet.
No scoring yet.
No coaching yet.

---

# What This Slice Must Include

## Authentication

- POST /auth/signup
- POST /auth/login
- PUT /auth/ai-config (authenticated)
- JWT-based authentication
- Password hashing (secure)
- Per-user data isolation

Signup/config requirements:
- User can configure:
  - `ai_provider` enum: `openai` | `gemini`
  - `ai_model` string
  - `ai_api_key` string
- `ai_provider` + `ai_model` + `ai_api_key` may be supplied at signup or later via `PUT /auth/ai-config`
- API key must be encrypted at rest
- API key must never be returned in full (return masked metadata only)
- User can rotate/revoke their own key

## Baseline Intake

- POST /intake/baseline (authenticated)
- GET /intake/baseline (authenticated)

Baseline must store required structured core:

Objective:
- weight (float)
- waist (float)
- systolic_bp (int)
- diastolic_bp (int)
- resting_hr (int)
- sleep_hours (float)
- activity_level (string enum)

Subjective:
- energy (1-10 int)
- mood (1-10 int)
- stress (1-10 int)
- sleep_quality (1-10 int)
- motivation (1-10 int)

Validation required:
- All numeric values validated for reasonable range
- Enums validated
- Required fields enforced

Adaptive intake behavior (deterministic):
- Intake starts by collecting a primary goal focus
- Question depth adapts by goal category (for example: energy, heart health, longevity optimization, weight loss, mental clarity)
- High-risk baseline values trigger gentle clarifying prompts
- Engagement style adapts depth (concise vs deeper probing)
- Tone starts neutral/professional and can become lightly witty only when user tone supports it
- Required structured core fields are always captured
- Optional modules are allowed but must remain optional (nutrition patterns, training history, supplements, labs, fasting practices, recovery practices, medications)
- Intake response includes concise summary + next-step guidance


### Post-Intake Response Schema

`POST /intake/baseline` response must include:

- `baseline_id`: int
- `user_id`: int
- `primary_goal`: string
- `focus_areas`: string[] (2-4 items)
- `risk_flags`: string[] (0+ items)
- `next_steps`: string[] (1-3 items)
- `suggested_questions`: string[] (3 items)
- `disclaimer`: string

Schema constraints:
- `focus_areas` are qualitative priorities, not numeric scores
- `risk_flags` should be empty when no risk triggers are present
- `suggested_questions` should be actionable and goal-aligned
- `disclaimer` must state this is not medical diagnosis

Example response:
```json
{
  "baseline_id": 12,
  "user_id": 3,
  "primary_goal": "Energy",
  "focus_areas": [
    "Increase average sleep duration",
    "Lower evening stress load",
    "Improve daytime activity consistency"
  ],
  "risk_flags": [
    "elevated_bp"
  ],
  "next_steps": [
    "Track bedtime and wake time for 7 days",
    "Add a 10-minute wind-down routine",
    "Recheck blood pressure at consistent times"
  ],
  "suggested_questions": [
    "Want a simple evening routine to improve sleep quality?",
    "Want help choosing one weekly energy metric to track?",
    "Want a low-friction activity target for this week?"
  ],
  "disclaimer": "This is coaching guidance, not medical diagnosis."
}
```
Important boundaries:
- Do not diagnose disease
- Do not require lab data
- Do not store full free-form intake transcripts

---

# Out of Scope (Critical)

You MUST NOT:

- Implement domain scoring
- Implement composite score
- Implement coaching endpoint
- Implement AI Council
- Add experiment engine
- Add guided question engine
- Add photo or voice handling
- Refactor future architecture

This slice is strictly auth + baseline persistence + deterministic adaptive intake flow.

---

# Files Allowed to Change

You may only modify or create:

- app/main.py
- app/api/auth.py
- app/api/intake.py
- app/db/models.py
- app/db/session.py
- app/core/security.py
- requirements.txt

If additional files are required:
STOP and explain why before proceeding.

---

# Database Constraints

- SQLite only
- Database path: /var/data/longevity.db
- Use SQLAlchemy ORM
- Define:

Tables:
- users
- baselines
- user_ai_configs

Constraints:
- baselines.user_id is foreign key
- One baseline per user (enforced unique)
- user_ai_configs.user_id is foreign key
- One AI config per user (enforced unique)

---

# Security Requirements

- Password hashing (bcrypt or passlib)
- JWT signed with SECRET_KEY env var
- Auth middleware protects intake routes
- User cannot access another user's baseline
- User cannot read/modify another user's AI config
- AI keys encrypted at rest and never logged

---

# Acceptance Criteria

This slice is complete when:

- [ ] User can sign up
- [ ] User can log in
- [ ] JWT returned
- [ ] Authenticated user can submit baseline
- [ ] Baseline stored in SQLite
- [ ] Authenticated user can retrieve own baseline
- [ ] User can set/update own AI provider/model/key
- [ ] AI key is stored encrypted and returned masked
- [ ] Goal-based adaptive questioning triggered
- [ ] Risk-based clarifying prompts triggered when needed
- [ ] Intake tone adaptation behaves safely
- [ ] Structured data stored deterministically
- [ ] Focus areas highlighted after intake (without requiring numeric scores)
- [ ] Unauthorized requests are rejected
- [ ] Server runs without errors

---

# Verification Steps

After implementation provide:

1. Command to run locally:
   uvicorn app.main:app --reload

2. Example signup request:
   curl -X POST http://localhost:8000/auth/signup \
   -H "Content-Type: application/json" \
   -d '{"email":"test@test.com","password":"StrongPass123"}'

3. Example login request:
   curl -X POST http://localhost:8000/auth/login ...

4. Example baseline POST:
   curl -X POST http://localhost:8000/intake/baseline \
   -H "Authorization: Bearer <token>" ...

5. Example baseline GET:
   curl -X GET http://localhost:8000/intake/baseline \
   -H "Authorization: Bearer <token>"

---

# Implementation Requirements

- Production-grade code
- Pydantic validation models
- Clear error handling
- Proper HTTP status codes
- Minimal but clean structure
- No placeholder TODO logic

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

This is a foundational slice.
Keep it tight.
No future features.
No AI yet.
No scoring yet.

