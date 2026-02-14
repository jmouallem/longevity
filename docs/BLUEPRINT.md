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
POST /auth/model-options

POST /intake/baseline
GET  /intake/status
POST /intake/conversation/start     (planned)
POST /intake/conversation/answer    (planned)
POST /intake/conversation/complete  (planned)
POST /metrics
GET  /dashboard/summary
POST /integrations/apple-health/sync
POST /integrations/hume/sync

POST /coach/question
POST /coach/meal-photo
POST /coach/voice

GET  /experiments
POST /experiments

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
- Settings menu includes AI config updates and password change
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

