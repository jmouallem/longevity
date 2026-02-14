# 🧪 The Longevity Alchemist  
## Build Priority Roadmap

---

# 🎯 Guiding Principles

- Ship usable value early
- Build foundation before intelligence
- Keep AI orchestration modular
- Defer complexity until data flow works
- Prioritize structured data over clever prompts
- Make it useful before making it beautiful

---

# 🟢 Phase 0 — Foundation (Infrastructure First)

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

---

# 🟢 Phase 1 — Core Usable MVP

## Goal: Intake → Basic Coaching → Simple Dashboard

This phase makes the product real.

### 1.1 Baseline Intake
- [ ] Baseline schema created
- [ ] Intake endpoint
- [ ] Save baseline to DB
- [ ] Adaptive follow-up logic (basic)

### 1.2 Metrics System
- [ ] Time-series metrics table
- [ ] Add metric endpoint
- [ ] Retrieve metrics endpoint
- [ ] Basic validation

### 1.3 Basic Coaching Endpoint
- [ ] `/coach/question` endpoint
- [ ] Load user state
- [ ] Call LLM once (single agent mode)
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

✅ **Milestone Outcome:**  
User can sign up → complete intake → log metrics → ask “what next?” → see scores.

---

# 🟡 Phase 2 — Multi-Disciplinary Intelligence

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

✅ **Milestone Outcome:**  
The Longevity Alchemist now thinks in domains.

---

# 🟡 Phase 3 — Experiment Engine

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

✅ **Milestone Outcome:**  
System supports structured N-of-1 experimentation.

---

# 🟡 Phase 4 — Guided Question Engine

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

✅ **Milestone Outcome:**  
System proactively guides engagement.

---

# 🟠 Phase 5 — Multi-Modal Input

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

✅ **Milestone Outcome:**  
Users can log via text, voice, or photo.

---

# 🟠 Phase 6 — Advanced Scoring & Visualization

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

# 🔵 Phase 7 — Research & Knowledge Updating (Optional Advanced Layer)

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

# 🔴 Phase 8 — Refinement & Optimization

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

# 🏁 Suggested Build Order Summary

1️⃣ Foundation (Auth + SQLite + Deploy)  
2️⃣ Intake + Metrics + Basic Coaching  
3️⃣ Domain Scoring + Dashboard  
4️⃣ Multi-Agent Round Table  
5️⃣ Experiment Engine  
6️⃣ Guided Question Engine  
7️⃣ Multi-Modal Input  
8️⃣ Advanced Scoring & Visualization  
9️⃣ Research Ingestion  
🔟 Production hardening  

---

# 📌 MVP Definition

Minimum viable “Longevity Alchemist”:

- User authentication
- Baseline intake
- Metric logging
- Single-agent contextual coaching
- Domain + composite scoring
- Basic dashboard
- Deployed to Render with persistent SQLite

Everything beyond that increases intelligence, retention, and sophistication.

---

# 🚀 Long-Term Vision

The Longevity Alchemist becomes:

A structured, adaptive, evidence-informed longevity operating system that evolves with the user.

