# The Longevity Alchemist  Implementation Blueprint

Backend: Python 3.11 + FastAPI
Database: SQLite
Deployment: Docker + Render

---

# 1. Project Structure

/app
    /api
        auth.py
        intake.py
        coach.py
        dashboard.py
        metrics.py
        experiments.py
    /core
        config.py
        security.py
        scoring.py
        experiment_engine.py
    /agents
        metabolic.py
        nutrition.py
        sleep.py
        exercise.py
        supplements.py
        behavioral.py
        trends.py
        safety.py
        synthesis.py
    /services
        llm.py
        connectors/
            apple_health.py
            hume.py
            base.py
        vision.py
        speech.py
        research.py
    /db
        models.py
        session.py
        migrations.py
    main.py

Dockerfile
requirements.txt
render.yaml

---

# 2. Core Dependencies

fastapi
uvicorn
sqlalchemy
pydantic
python-jose
passlib
httpx
openai (or LLM SDK)
google-generativeai (Gemini SDK)

---

# 3. SQLite Setup

Database file location:
    /var/data/longevity.db

Ensure Render persistent disk mounted at /var/data

---

# 4. Core API Routes

POST /auth/signup
POST /auth/login
GET  /auth/session
PUT  /auth/ai-config
GET  /auth/ai-config
PUT  /auth/change-password
GET  /auth/model-usage
DELETE /auth/model-usage
DELETE /auth/data
POST /auth/model-options
POST /feedback/entries
GET  /feedback/entries/export
DELETE /feedback/entries
GET  /chat/threads
POST /chat/threads
GET  /chat/threads/{thread_id}/messages

POST /intake/baseline
GET  /intake/status
POST /intake/conversation/start
POST /intake/conversation/answer
POST /intake/conversation/complete
PUT  /daily-log/{date}
GET  /daily-log
GET  /summary/overall
POST /metrics
GET  /dashboard/summary
POST /integrations/apple-health/sync
POST /integrations/hume/sync

POST /coach/question
POST /coach/image
POST /coach/voice

GET  /experiments
POST /experiments

Internal behavior notes:
- `/coach/question` must return stable structured JSON even on provider failures.
- `/coach/image` must validate image type/size and return the same structured response contract.
- Chat responses should preserve readable markdown formatting in `answer`.
- Follow-up items should be direct coach questions for user reply.
- Coach responses should include thread continuity metadata (`thread_id`) and agent trace metadata for UI transparency.
- Feedback entries are shared across users in one table, exportable to CSV, and clearable from app settings/workspace.
- Specialist hierarchy:
  - Strategic layer: Goal Strategist (6-24 week targets/phases/pivots)
  - Operational layer: Orchestrator (daily/weekly conflict resolution + weighted priorities)
  - Specialist layer: Nutritionist, Sleep Expert, Movement Coach, Cardiometabolic Strategist, Supplement Auditor, Safety Clinician
  - Optional contextual specialists: Behavior Architect, Recovery & Stress Regulator
- Safety Clinician has veto authority over unsafe plans.

---

# 5. AI Council Orchestration Flow

function coach_question(user_id, question):

    user_state = load_structured_state(user_id)

    domain_payloads = segment_by_domain(user_state)

    agent_outputs = []

    for agent in agents:
        result = call_llm(agent.prompt, domain_payload)
        agent_outputs.append(result)

    synthesis = merge_outputs(agent_outputs)

    final_response = persona_wrapper(synthesis)

    save_conversation_summary()

    return final_response

Cost-optimized runtime behavior:
- Auto mode resolves to quick mode by default.
- Quick mode runs constrained orchestration (up to 3 selected specialists + synthesis).
- Deep-think is explicit and routes to deep thinker profile.
- Enforce per-task output token ceilings.
- Apply short TTL duplicate-response cache for repeated identical questions.
- Prefer provider path with lowest empty-output failure risk for GPT-5 models.

---

# 6. Domain Score Computation

Each domain:

score = weighted_function(normalized_metrics)

Composite:

composite = weighted_average(domain_scores)

Store historical score snapshots.

---

# 7. Experiment Engine

Experiment model:
- hypothesis
- intervention
- metrics
- start_date
- end_date
- evaluation
- confidence_delta

Evaluation logic:
- Compare pre vs post metrics
- Determine signal strength
- Update domain weights

---

# 8. Dockerfile

FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]

---

# 9. Render Configuration

- Create Web Service
- Attach Persistent Disk (mounted at /var/data)
- Set environment variables:
    OPENAI_API_KEY
    SECRET_KEY
- Enable auto deploy

---

# 10. MVP Slice

Phase 1:
- Per-user provider configuration (OpenAI/Gemini) + encrypted BYOK storage
- Dynamic model options lookup endpoint with fallback model lists
- Triple model profiles in config:
  - deep thinker model
  - reasoning model
  - utility model
- Deep-think submission toggle routes to deep thinker model
- Model options include cost metadata when known
- Utility-task routing defaults to utility model
- Main workspace route with menu views (chat/intake/settings/usage)
- Intake can be skipped at setup and completed/re-run later from workspace menu
- Post-intake success routes user back to default chat
- Settings menu includes AI config updates, password change, user-data reinitialize, and model-usage reset (separate actions)
- Per-model token usage stats are persisted and exposed
- AI-led intake coach agent asks one question at a time and adapts depth by concern
- Conversational intake maps deterministically into baseline schema
- Auth
- Baseline intake
- Adaptive intake (goal/risk/engagement)
- Manual metrics entry
- Simple coaching endpoint
- Domain score display

Phase 2:
- Meal photo
- Voice input
- Guided question engine

Phase 3:
- PubMed ingestion
- Research toggles
- Advanced experiment analytics

Phase 4:
- Modular connector interface for third-party data sync
- Apple Health normalized metric sync (planned)
- Hume normalized signal sync (planned)
