# 🧪 SLICE PROMPT — The Longevity Alchemist (Slice #1)

You are implementing a small vertical slice for The Longevity Alchemist.

Follow AGENTS.md and this slice prompt strictly.
Work only within the defined scope.
Do not refactor unrelated code.
Keep changes minimal and testable.

---

# 🎯 Slice Goal

Implement user authentication and structured baseline intake persistence.

This slice must allow:

1. User signup
2. User login
3. Authenticated baseline submission
4. Baseline retrieval
5. Data stored in SQLite at /var/data/longevity.db

No AI integration yet.
No scoring yet.
No coaching yet.

---

# 📦 What This Slice Must Include

## Authentication

- POST /auth/signup
- POST /auth/login
- JWT-based authentication
- Password hashing (secure)
- Per-user data isolation

## Baseline Intake

- POST /intake/baseline (authenticated)
- GET /intake/baseline (authenticated)

Baseline must store:

Objective:
- weight (float)
- waist (float)
- systolic_bp (int)
- diastolic_bp (int)
- resting_hr (int)
- sleep_hours (float)
- activity_level (string enum)

Subjective:
- energy (1–10 int)
- mood (1–10 int)
- stress (1–10 int)
- sleep_quality (1–10 int)
- motivation (1–10 int)

Validation required:
- All numeric values validated for reasonable range
- Enums validated
- Required fields enforced

---

# 🚫 Out of Scope (Critical)

You MUST NOT:

- Implement domain scoring
- Implement composite score
- Implement coaching endpoint
- Implement AI Council
- Add experiment engine
- Add guided question engine
- Add photo or voice handling
- Refactor future architecture

This slice is strictly auth + baseline persistence.

---

# 📂 Files Allowed to Change

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

# 🗄 Database Constraints

- SQLite only
- Database path: /var/data/longevity.db
- Use SQLAlchemy ORM
- Define:

Tables:
- users
- baselines

Constraints:
- baselines.user_id is foreign key
- One baseline per user (enforced unique)

---

# 🔐 Security Requirements

- Password hashing (bcrypt or passlib)
- JWT signed with SECRET_KEY env var
- Auth middleware protects intake routes
- User cannot access another user’s baseline

---

# 🧪 Acceptance Criteria

This slice is complete when:

- [ ] User can sign up
- [ ] User can log in
- [ ] JWT returned
- [ ] Authenticated user can submit baseline
- [ ] Baseline stored in SQLite
- [ ] Authenticated user can retrieve own baseline
- [ ] Unauthorized requests are rejected
- [ ] Server runs without errors

---

# 🧪 Verification Steps

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

# 📏 Implementation Requirements

- Production-grade code
- Pydantic validation models
- Clear error handling
- Proper HTTP status codes
- Minimal but clean structure
- No placeholder TODO logic

---

# 📋 Deliverables Format

You must respond with:

1. PLAN
2. FILE CHANGES
3. FULL CODE FOR EACH CHANGED FILE
4. HOW TO VERIFY
5. NOTES

---

# 🧘 Reminder

This is a foundational slice.
Keep it tight.
No future features.
No AI yet.
No scoring yet.

—--------------------------------------------------------------------------------------—--------------------



