# The Longevity Alchemist
## Build Priority Roadmap

---

# Guiding Principles

- Ship usable value early
- Build foundation before intelligence
- Keep AI orchestration modular
- Defer complexity until data flow works
- Prioritize structured data over clever prompts
- Make it useful before making it beautiful

---

# Phase 0 - Foundation (Infrastructure First)

## Goal: Running, persistent, authenticated system

### 0.1 Project Setup
- [ ] Initialize repo structure
- [ ] FastAPI backend scaffold
- [ ] Dockerfile created
- [ ] Local dev environment working
- [ ] Environment variable handling

### 0.2 Deployment Foundation
- [ ] Deploy to Render
- [ ] Attach persistent disk
- [ ] Configure SQLite at `/var/data`
- [ ] Environment variables configured

### 0.3 Authentication
- [ ] User model
- [ ] Password hashing
- [ ] JWT or session auth
- [ ] Login & signup endpoints
- [ ] Protected routes middleware
- [ ] Per-user AI provider/model/key configuration (BYOK)
- [ ] Support OpenAI (ChatGPT) and Gemini provider selection
- [ ] Encrypt user AI keys at rest and support key rotation

---

# Phase 1 - Core Usable MVP

## Goal: Intake ? Basic Coaching ? Simple Dashboard

This phase makes the product real.

### 1.0 Onboarding GUI Initialization Gate
- [ ] Modern onboarding UI (board/card style, mobile responsive)
- [ ] Signup/login in GUI
- [ ] LLM provider/model/key setup in GUI
- [ ] Dynamic model list lookup from provider API
- [ ] Deep thinker + reasoning + utility model slots in setup UI
- [ ] Manual deep-think toggle on coaching submissions
- [ ] Model option list includes cost metadata when known
- [ ] Utility-task routing defaults to utility model profile
- [ ] Deep-think submissions route to deep thinker profile
- [ ] Block intake start until account + LLM config are complete
- [ ] Clear setup progress and error handling in UI
- [ ] Offer "Start intake now" and "Skip for now" after setup
- [ ] Existing-user login routes to main workspace if setup already complete

### 1.1 Baseline Intake
- [ ] Baseline schema created
- [ ] Intake endpoint
- [ ] Save baseline to DB
- [ ] Goal-first intake opening question
- [ ] Goal-based adaptive depth logic
- [ ] Risk-based clarifying prompts for high-risk values
- [ ] Engagement-based tone/depth adaptation
- [ ] Required-core + optional-module intake model
- [ ] Motivational + data-transparency completion framing
- [ ] Intake can be launched/re-launched from main workspace menu
- [ ] Intake completion status is visible in workspace menu
- [ ] Intake completion routes user to default chat view

### 1.1.1 Main Workspace + Settings
- [ ] Main workspace menu with one-view-at-a-time navigation
- [ ] Chat, Intake, Settings, and Usage views are available
- [ ] Settings menu supports AI config updates
- [ ] Settings menu supports password change
- [ ] Track per-user/per-model token usage stats
- [ ] Expose token usage endpoint for workspace usage view

### 1.2 Metrics System
- [ ] Time-series metrics table
- [ ] Add metric endpoint
- [ ] Retrieve metrics endpoint
- [ ] Basic validation

### 1.3 Basic Coaching Endpoint
- [ ] `/coach/question` endpoint
- [ ] Load user state
- [ ] Call LLM once (single agent mode) using authenticated user's provider/model config
- [ ] Route utility sub-tasks (summarization/routing/extraction) to utility model profile
- [ ] Return contextual response
- [ ] Save conversation summary

### 1.4 Simple Domain Scoring
- [ ] Sleep score logic
- [ ] Basic metabolic score
- [ ] Basic behavioral consistency score
- [ ] Composite score (simple weighted average)

### 1.5 Minimal Dashboard
- [ ] Fetch metrics
- [ ] Display domain scores
- [ ] Display composite score
- [ ] Basic trend chart

**Milestone Outcome:**
User can sign up ? complete intake ? log metrics ? ask -what next?- ? see scores.

---

# Phase 2 - Multi-Disciplinary Intelligence

## Goal: Introduce Round Table Architecture

### 2.1 AI Council Framework
- [ ] Create domain agent modules
- [ ] Structured JSON output schema
- [ ] Synthesis layer
- [ ] Safety moderator pass

### 2.2 Domain Agents (MVP versions)
- [ ] Nutrition agent
- [ ] Sleep agent
- [ ] Exercise agent
- [ ] Metabolic agent
- [ ] Safety agent

### 2.3 Structured Agent Logging
- [ ] Save agent outputs
- [ ] Confidence scoring
- [ ] Risk flags stored

### 2.4 Improved Coaching Endpoint
- [ ] Multi-agent orchestration
- [ ] Persona wrapper applied
- [ ] Guided question suggestions appended

**Milestone Outcome:**
The Longevity Alchemist now thinks in domains.

---

# Phase 3 - Experiment Engine

## Goal: Adaptive learning

### 3.1 Experiment Data Model
- [ ] Hypothesis field
- [ ] Intervention field
- [ ] Linked metrics
- [ ] Start/end tracking
- [ ] Evaluation summary

### 3.2 Experiment Lifecycle
- [ ] Create experiment endpoint
- [ ] Evaluate experiment logic
- [ ] Compare baseline vs post metrics
- [ ] Update confidence delta

### 3.3 Coaching Integration
- [ ] Recommend experiments automatically
- [ ] Prompt experiment check-ins
- [ ] Reflect outcomes in future suggestions

**Milestone Outcome:**
System supports structured N-of-1 experimentation.

---

# Phase 4 - Guided Question Engine

## Goal: Proactive coaching

### 4.1 Next Best Question Logic
- [ ] Context-driven prompt generation
- [ ] Recent metric anomaly detection
- [ ] Goal-driven suggestion engine

### 4.2 UI Integration
- [ ] Display suggested prompts
- [ ] One-click ask feature
- [ ] Adaptive tone selection

### 4.3 Behavioral Nudges
- [ ] Inactivity prompts
- [ ] Experiment follow-up reminders
- [ ] Goal drift detection

**Milestone Outcome:**
System proactively guides engagement.

---

# Phase 5 - Multi-Modal Input

## Goal: Frictionless data capture

### 5.1 Meal Photo Support
- [ ] Image upload endpoint
- [ ] Vision model integration
- [ ] Structured macro extraction
- [ ] Confidence rating
- [ ] Discard image after processing

### 5.2 Voice Input
- [ ] Audio upload endpoint
- [ ] Speech-to-text integration
- [ ] Store transcript only

### 5.3 Intent Parsing
- [ ] Detect fatigue reports
- [ ] Detect supplement queries
- [ ] Detect meal questions

### 5.4 Conversational Intake (Future)
- [ ] Add guided conversational intake mode
- [ ] Support voice-first intake input (transcribe only)
- [ ] Keep required structured core deterministic
- [ ] Store structured outputs only (no full raw media retention)

### 5.5 External Connector Sync (Future)
- [ ] Add modular provider connector interface
- [ ] Add Apple Health sync connector (normalized metrics)
- [ ] Add Hume sync connector (normalized signals)
- [ ] Add per-user sync settings + consent controls
- [ ] Add incremental sync + idempotent upsert behavior

**Milestone Outcome:**
Users can log via text, voice, or photo.

---

# Phase 6 - Advanced Scoring & Visualization

## Goal: Professional-grade dashboard

### 6.1 Domain Score Refinement
- [ ] Weighted metric normalization
- [ ] Historical domain snapshots
- [ ] Smoothing logic

### 6.2 Composite Score Transparency
- [ ] Show domain breakdown
- [ ] Explain score drivers
- [ ] Track improvement trends

### 6.3 Advanced UI
- [ ] Weekly view
- [ ] Monthly view
- [ ] Experiment overlays on charts
- [ ] Goal progress bars

---

# Phase 7 - Research & Knowledge Updating (Optional Advanced Layer)

## Goal: Evidence adaptation

### 7.1 PubMed Ingestion
- [ ] Research fetch service
- [ ] Local research storage
- [ ] Summarization layer

### 7.2 Research Impact Engine
- [ ] Compare new findings to user plan
- [ ] Generate impact explanation
- [ ] Accept/reject toggle

### 7.3 Evidence Rating
- [ ] Confidence classification
- [ ] Transparency display

---

# Phase 8 - Refinement & Optimization

## Goal: Production readiness

- [ ] Performance optimization
- [ ] Rate limiting
- [ ] Logging & audit trail
- [ ] Error handling improvements
- [ ] Edge-case safety handling
- [ ] UX polish
- [ ] Tone calibration
- [ ] Accessibility improvements

---

# Suggested Build Order Summary

1. Foundation (Auth + SQLite + Deploy)`r`n2. Intake + Metrics + Basic Coaching`r`n3. Domain Scoring + Dashboard`r`n4. Multi-Agent Round Table`r`n5. Experiment Engine`r`n6. Guided Question Engine`r`n7. Multi-Modal Input`r`n8. Advanced Scoring & Visualization`r`n9. Research Ingestion`r`n10. Production hardening`r`n---

# MVP Definition

Minimum viable -Longevity Alchemist-:

- User authentication
- Baseline intake
- Metric logging
- Single-agent contextual coaching
- Domain + composite scoring
- Basic dashboard
- Deployed to Render with persistent SQLite

Everything beyond that increases intelligence, retention, and sophistication.

---

# Long-Term Vision

The Longevity Alchemist becomes:

A structured, adaptive, evidence-informed longevity operating system that evolves with the user.






