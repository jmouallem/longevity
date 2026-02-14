# 🧪 The Longevity Alchemist — Project Context

## 1 — High-Level Overview

**The Longevity Alchemist** is a web-based, AI-powered longevity and healthspan coaching system that helps users assess their current health, set personalized longevity goals, and receive adaptive, scientifically informed guidance.

The system leverages structured data, multi-agent–inspired reasoning patterns, and external AI models to guide users toward long-term health improvements. It is deployed as a **single Docker container on Render**, with persistent state stored locally using **SQLite**. External AI calls and optional web search are used for coaching logic, while sensitive credentials are kept secure on the server.

This document provides the background required to understand the project’s scope, architecture, and current state before beginning work.

---

## 2 — Purpose and Audience

This document is intended for:

- AI coding agents (e.g., Codex CLI, Codex 5.2)
- Developers onboarding to the project
- Reviewers and maintainers
- CI/CD and automation configurations

Its purpose is to capture essential, relatively static project context to ensure consistent development and reduce context loss across sessions.

---

## 3 — Project Scope

### In Scope

- User onboarding and authentication
- Structured baseline data collection and storage
- Time-series health metrics logging
- Domain scoring and composite score tracking
- AI-assisted coaching via a `/coach/question` endpoint
- Modular testing harness with mockable LLMs
- Guided question suggestions
- Simple dashboard summary API

### Out of Scope (MVP and Early Slices)

- Multi-agent council orchestration
- Meal image storage
- Voice input or storage
- Research ingestion and integration
- Genotype / omics data
- External database hosting (e.g., Postgres, cloud DBs)
- Medical diagnosis or treatment

---

## 4 — Key Artifacts (Document Map)

The repository includes the following core documents:

- **ARCHITECTURE.md** — High-level system architecture
- **BLUEPRINT.md** — Build plan and component breakdown
- **BUILD_ROADMAP.md** — Phased delivery roadmap
- **USERNEEDS.md** — Functional user needs
- **USERNEEDS_CHECKLIST.md** — User needs in checklist form
- **codex/system_prompt.md** — Codex prompt index (points to per-slice prompts)
- **SLICE prompts** — Per-slice implementation contracts
- **TESTING_HARNESS.md** — AI testing patterns and strategy
- **DRIFT_DETECTION_CHECKLIST.md** — Merge and drift guardrails
- **TRACEABILITY.md** — User-needs-to-slice coverage mapping

---

## 5 — Architecture Summary

### Runtime

- Single Docker container
- Backend: **FastAPI (Python)**
- UI: React / Next.js or static SPA
- Persistence: **SQLite** on a mounted Render persistent disk

### AI Integration

- All LLM calls occur server-side
- External LLM APIs permitted for coaching
- Strict structured JSON responses with fallback logic required

### Data Model

- Structured tables:
  - users
  - baselines
  - metrics
  - domain scores
  - composite scores
  - summaries
- Images and audio are **not stored**
- All persistent state resides in SQLite under `/var/data`

---

## 6 — Deployment Context

The project is deployed on **Render** with an attached **persistent disk** for SQLite storage.

**Important considerations:**

- Without a persistent disk, SQLite data is lost on restart or redeploy
- The database path must be mounted to `/var/data` (or equivalent)
- Persistent disks are accessible only during service runtime
- Zero-downtime deploys may be limited due to disk attach/detach behavior

---

## 7 — Repository Structure

Key directories and files:

```text
/app
  /api        # FastAPI route handlers
  /core       # Domain logic and utilities
  /services   # External integrations (LLMs, etc.)
  /db         # Models and DB session management
  main.py     # Application entry point

/codex
  system_prompt.md
  slice_prompt_1.md
  slice_prompt_2.md
  slice_prompt_3.md
  slice_prompt_4.md

/docs
  ARCHITECTURE.md
  BLUEPRINT.md
  BUILD_ROADMAP.md
  USERNEEDS.md

/tests
  /fixtures
  /unit
  /api
```

---

## 8 — Initial Setup

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Set required environment variables
export SECRET_KEY="your_string_here"
export OPENAI_API_KEY="sk_xxxx"
export DB_PATH="/var/data/longevity.db"

# Run development server
uvicorn app.main:app --reload
```

---

## 9 — Database Initialization

The system uses **SQLite** as a file-based database.

Ensure:

- **DB path** is configured via environment variables (e.g., `DB_PATH`).
- The **Render persistent disk mount** matches this path (e.g., `/var/data`).
- Tables are created on startup via:
  - migrations, **or**
  - metadata-driven schema creation on application start.

Initializing the schema early prevents failures during streaming and AI tests.

---

## 10 — Testing Strategy

All AI-dependent endpoints must support dependency injection for LLMs to enable:

- Fast, offline test execution (no network calls)
- Deterministic JSON parsing tests
- Safety and guardrail tests (keyword / pattern triggers)
- Context builder tests validating summary correctness

See **TESTING_HARNESS.md** for the full pattern.

---

## 11 — Standards and Conventions

- Use **Pydantic** for all request and response models.
- All endpoints must return stable, versionable JSON schemas.
- Authorization is required for protected endpoints.
- Domain logic must be separated from API controllers.
- Keep slice diffs minimal, focused, and reviewable.

---

## 12 — Glossary

- **Baseline** — Initial user health data snapshot
- **Metric** — Time-series user data (e.g., sleep, HR)
- **Domain Score** — Category-specific score (sleep, metabolic, etc.)
- **Composite Score** — Aggregated health score
- **Coach Question** — User query handled by AI
- **Slice** — Small, vertical unit of work

---

## 13 — Versioning

Include a `VERSION` file or a version header in the README using semantic versioning, for example:

```text
v0.1.0
```

This tracks incremental progress and supports controlled evolution.

---

## 14 — Contributors and Contacts

Maintain a short section listing:

- Project owner
- Maintainers
- Documentation contacts

This is optional but recommended for collaborative development.

---

## 15 — Review and Update Protocol

Update this document when:

- Architectural decisions change
- Major new slices are introduced
- Deployment context changes
- Persistent storage structure is modified





