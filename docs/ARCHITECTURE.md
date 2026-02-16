# The Longevity Alchemist  System Architecture

## 1. Overview

The Longevity Alchemist is a web-based, AI-powered longevity coaching system designed to:

- Establish user baseline health
- Define measurable longevity goals
- Generate adaptive, science-informed plans
- Track metrics over time
- Run structured N-of-1 experiments
- Provide contextual coaching via AI

The system is fully self-contained within a Docker container deployed on Render.

Persistent data is stored locally using SQLite on an attached persistent disk.

External services (LLM, speech-to-text, vision, optional web search) are accessed securely via backend API calls.

---

## 2. High-Level Architecture

Client (Browser)
    ? HTTPS
Single Docker Container (Render Web Service)
    +-- FastAPI Backend
    +-- AI Council Orchestrator
    +-- SQLite Database (Persistent Disk)
    +-- Local Background Jobs
    +-- External AI Service Clients

---

## 3. Core Architectural Principles

### 3.1 Self-Contained State
- All structured data lives inside SQLite.
- No external database.
- Images are never stored.
- Audio is not stored (only transcripts retained).

### 3.2 Stateless AI Layer
- AI does not hold long-term memory.
- Context is reconstructed from structured DB state.
- Conversation summaries stored locally.

### 3.3 Domain-Scoped Intelligence
- User input is analyzed by multiple discipline agents.
- Each agent sees only relevant structured data.
- A synthesis layer produces final output.

### 3.4 Privacy First
- All LLM calls occur server-side.
- API keys never exposed to browser.
- User data isolated per account.

### 3.5 Triple Model Profiles
- Each user has three model profiles:
  - deep thinker profile
  - reasoning profile
  - utility profile
- Model selection must be explicit and deterministic per task class.
- Deep-think submissions use deep thinker profile by default.
- Utility tasks (routing/summarization/extraction/classification) use utility profile by default.
- Reasoning-heavy tasks use reasoning profile by default.

### 3.6 Cost + Reliability Guardrails
- Auto chat mode defaults to quick path for cost control.
- Quick path uses bounded specialist fan-out (up to 3 specialists + synthesis), selected by query relevance.
- Deep-think remains explicit and user-invoked.
- Per-task token budgets are enforced (utility < reasoning < deep-think).
- Short TTL response cache deduplicates repeated identical submissions.
- GPT-5 provider path prefers Responses API and falls back safely when text output is incomplete.
- Fallback guidance remains useful and safe when provider errors/timeouts occur.

---

## 4. Component Breakdown

### 4.1 Frontend

Responsibilities:
- Onboarding UI
- Main workspace UI with menu views (chat, intake, settings, usage)
- Exactly one workspace view is visible at a time (active view contract)
- Threaded chat history panel (new chat + prior thread selection)
- Intake completion status indicator
- Guided question prompts
- Settings flows (AI config, password change, user-data reinitialize, model-usage reset)
- Settings flows (AI config, password change, daily-data-only reset, user-data reinitialize, model-usage reset)
- Settings reminder notification controls (enable/disable + interval + permission flow)
- Shared feedback capture flow (feature/idea/bug), CSV export, and clear-all action
- Chat progress feedback during multi-step reasoning (context, specialists, synthesis)
- Visible agent/personality status chips during response generation
- Per-question web-search toggle so specialists can optionally use current external evidence
- Rendered answer formatting optimized for readable markdown-like output
- Coach follow-up questions presented as questions for the user to answer next
- Proactive guidance framing with checkpoints, measurable success markers, and pivot triggers derived from user history/trends

Technology:
- React or Next.js SPA
- Charting library (Recharts/D3)

---

### 4.2 Backend (FastAPI)

Responsibilities:
- Authentication (JWT or session-based)
- REST API endpoints
- Data validation
- AI orchestration
- Chat thread/message persistence and retrieval endpoints
- Intake status + baseline upsert endpoints
- Settings endpoints (AI config, password change)
- Settings reset endpoints (user-data reinitialize, model-usage reset)
- Feedback endpoints (submit, export CSV, clear shared entries)
- Model usage stats endpoint
- Intake coach orchestration endpoints
- Daily log endpoints (upsert + list)
- Overall summary endpoint (today/7d/30d deterministic aggregation)
- Image coaching endpoint (`/coach/image`) with no persistent media storage
- Score calculation
- Experiment lifecycle logic
- LLM resilience logic (timeouts/retries/fallback path)
- Cost guardrails (mode routing + token caps + duplicate-response cache)
- Utility-model parsing pipeline for free-form user updates (food/hydration/meds/vitals/workouts/sleep)
- Structured coaching memory ledger persisted in `daily_logs.checkin_payload_json` (`events`, `answers`, `extras`) for context-window-safe recall

---

### 4.3 AI Council Orchestrator

Agents:
- Goal Strategist
- Nutritionist
- Sleep Expert
- Movement Coach
- Supplement Auditor
- Safety Clinician
- Cardiometabolic Strategist
- Behavior Architect (optional)
- Recovery & Stress Regulator (optional)
- Orchestrator

Workflow:
1. Gather structured user state
1a. Parse incoming free-form progress updates with utility model into structured log events
2. Segment into domain payloads
3. Call LLM for each agent (or sequential reasoning blocks)
4. Collect structured outputs
5. Synthesize recommendations
6. Wrap in persona tone
7. Orchestrator applies priority weights and resolves conflicts between specialists
8. Goal Strategist maintains 6-24 week targets/phases; Orchestrator executes daily/weekly tradeoffs against that strategy

Memory Contract:
- Agents must treat persisted structured logs as the source of truth for recent operational state.
- Context includes short-memory digests (recent updates + 7-day event counts) to avoid reliance on long chat transcripts.

Quick Mode Optimization:
- Run a constrained pipeline by default (Goal Strategist + selected specialists + Safety Clinician + synthesis, capped for cost).
- Reserve deeper multi-agent paths for explicit deep-think use.

### 4.5 Model Catalog Service

Responsibilities:
- Fetch provider model lists (OpenAI/Gemini) using authenticated user key when available
- Provide fallback model lists when provider lookup fails
- Return best-default model candidate for each profile slot
- Return per-model cost metadata when known

---

### 4.6 Intake Coach Agent (Planned)

Responsibilities:
- Run a guided conversational intake interview
- Ask one question at a time and adapt depth by user goals + risk signals
- Probe deeper where concern flags are detected
- Extract and map answers into deterministic baseline fields
- Produce concise intake summary and focus priorities without storing full transcript

---

### 4.7 Chat History Service

Responsibilities:
- Persist user/assistant turns into user-owned threads
- Auto-create thread on first turn when no thread is selected
- Return thread lists and message timelines for workspace rendering
- Enforce strict per-user access isolation

---

### 4.4 Database (SQLite)

Located on mounted persistent disk.

Core tables:
- users
- user_ai_configs
- baselines
- daily_logs
- goals
- metrics (time-series)
- domain_scores
- composite_scores
- model_usage_stats
- experiments
- interventions
- conversation_summaries
- agent_outputs
- supplements
- research_library (optional)

---

## 5. Data Flow Examples

### 5.1 "What should I eat for lunch?"

1. User submits question
2. Backend loads:
   - today's metrics
   - sleep
   - activity
   - fasting window
   - goals
3. Agents generate domain insights
4. Synthesis merges suggestions
5. Persona formats final response
6. Guided question suggestions added

### 5.3 Cost-Optimized Chat Flow (Current)

1. User submits question (Auto defaults to Quick)
2. Backend loads compact structured context
3. Quick path runs minimal agents
4. LLM response normalized to stable structured output
5. Answer rendered with readable markdown sections
6. Coach follow-up questions shown as user prompts for next turn
7. Response and usage stats persisted
8. Duplicate request within TTL may return cached response

---

### 5.2 Image Coaching Input

1. Photo uploaded
2. Sent to provider multimodal endpoint
3. Structured nutrition estimate returned
4. Store only:
   - foods
   - macros
   - confidence
5. Discard image

---

## 6. Composite + Domain Score Model

Domain scores:
- Metabolic
- Sleep
- Fitness
- Recovery
- Behavioral

Composite score:
- Weighted aggregation
- Transparent logic
- Used for trend tracking

---

## 7. Guided Question Engine

System generates:
- Next best question
- Contextual prompts
- Follow-up suggestions
- Experiment checks

This increases engagement and improves data collection.

---

## 8. Deployment Constraints (Render)

- Must attach persistent disk
- SQLite stored on mounted path
- Environment variables for API keys
- Single web service container
