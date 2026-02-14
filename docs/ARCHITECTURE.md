# 🧪 The Longevity Alchemist — System Architecture

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
    ↓ HTTPS
Single Docker Container (Render Web Service)
    ├── FastAPI Backend
    ├── AI Council Orchestrator
    ├── SQLite Database (Persistent Disk)
    ├── Local Background Jobs
    └── External AI Service Clients

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

---

## 4. Component Breakdown

### 4.1 Frontend

Responsibilities:
- Authentication UI
- Dashboard (domain scores + composite score)
- Guided question prompts
- Metrics input forms
- Voice & image upload
- Experiment views

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
- Image and voice handling
- Score calculation
- Experiment lifecycle logic

---

### 4.3 AI Council Orchestrator

Agents:
- Cardio/Metabolic
- Nutrition
- Sleep
- Exercise
- Supplements
- Behavioral
- Data Trends
- Safety Moderator

Workflow:
1. Gather structured user state
2. Segment into domain payloads
3. Call LLM for each agent (or sequential reasoning blocks)
4. Collect structured outputs
5. Synthesize recommendations
6. Wrap in persona tone

---

### 4.4 Database (SQLite)

Located on mounted persistent disk.

Core tables:
- users
- baselines
- goals
- metrics (time-series)
- domain_scores
- composite_scores
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

---

### 5.2 Meal Photo

1. Photo uploaded
2. Sent to vision model
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

