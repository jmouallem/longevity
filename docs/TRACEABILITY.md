# Traceability Matrix

## Purpose
This document maps `docs/USERNEEDS.md` requirements to implementation slices/phases so coverage and gaps are explicit.

## Sources
- `docs/USERNEEDS.md`
- `docs/USERNEEDS_CHECKLIST.md`
- `codex/slice_prompt_1.md`
- `codex/slice_prompt_2.md`
- `codex/slice_prompt_3.md`
- `codex/slice_prompt_4.md`
- `codex/slice_prompt_5.md`
- `codex/slice_prompt_6.md`
- `codex/slice_prompt_7.md`
- `codex/slice_prompt_8.md`
- `docs/BUILD_ROADMAP.md`

## Status Legend
- `Covered` = directly implemented by an existing slice scope
- `Partial` = partially addressed; follow-on scope required
- `Planned` = explicitly planned in later roadmap phases
- `Not Planned` = not currently mapped

## Requirement Mapping

| UserNeeds Section | Requirement Summary | Primary Slice/Phase | Status | Notes |
|---|---|---|---|---|
| 1 Vision | Structured, adaptive longevity coaching system | Slices 1-4 + Roadmap Phases 2-8 | Partial | MVP slices establish foundations; full vision requires later phases. |
| 2 Target Audience | General + advanced users, mobile/desktop | Slice 5 + Roadmap Phases 6, 8 | Partial | Slice 5 introduces mobile-first onboarding UI; broader product UX remains roadmap scope. |
| 3 Core Experience Principles | Scientific, data-driven, supportive, non-medical | Slices 2-3 | Partial | Tone/safety present in Slice 3; broader UX/tone adaptation in later phases. |
| 4 Privacy & Data | Auth, isolation, server-side AI, no image/audio storage | Slice 1 + Slice 3 + guardrails | Partial | Auth and server-side AI included; media handling constraints enforced as out-of-scope in early slices. |
| 4.1 BYOK AI Provider Config | Per-user provider/model/API key setup with secure storage and masking | Slice 1 + Slice 3 | Partial | Config is captured in auth/onboarding; coaching routes use authenticated user's provider config. |
| 4.3 Triple Model Profiles + Dynamic Catalog | Dynamic model lookup + deep-thinker/reasoning/utility model slots + explicit task routing defaults + cost metadata | Slice 5 + follow-on coaching slices | Partial | Dynamic model lookup/default selection/cost metadata can be implemented in onboarding; full routing coverage expands with coaching/routing features. |
| 4.2 External Connector Architecture | Modular provider adapters with normalized sync into internal datasets | Roadmap Phase 5 | Planned | Explicitly deferred; design requires provider abstraction, per-user consent/auth, and incremental sync. |
| 5 Baseline Establishment | Objective + subjective intake + derived outputs | Slice 1 + Slice 2 | Partial | Baseline capture in Slice 1; derived scoring begins in Slice 2. Optional labs/meds/supplements are later scope. |
| 5.4 Adaptive Intake Experience | Goal/risk/engagement adaptive intake with hybrid required+optional modules and intake persona | Slice 1 (foundational) + later enhancements in Phases 1-2 | Partial | Required core capture is in Slice 1 scope; focus-area highlights can be produced without numeric scoring. Full adaptive logic, motivational framing, and numeric completion outputs are progressively delivered. |
| 5.11 Intake Lifecycle + Main Workspace | Optional/re-runnable intake, completion status in menu, post-intake chat routing, settings menu access + shared feedback capture/export/clear | Slice 6 + follow-on workspace updates | Covered | Workspace includes one-view menu navigation, settings actions, model usage visibility, and shared feedback operations. |
| 5.7.1 AI-Led Intake Coach Agent | Conversational intake coach with batched flow (6-10 prompts), concern probing, deterministic mapping, and completion profile/config/open-question outputs | Slice 7 | Covered | Intake coach flow implemented with goal/risk-adaptive batches, deterministic baseline mapping, and structured completion outputs for downstream coaching configuration. Intake answer parsing uses deterministic extraction first, then AI-assisted batch parsing for unresolved fields with strict field-level coercion/validation before persistence. |
| 6 Goal Definition | Measurable goals and timeline guidance | Roadmap Phases 2-4 | Planned | Not in Slices 1-4 contracts. |
| 7 Personalized Planning | Step-by-step nutrition/exercise/sleep/stress/supplements | Slice 3 + Roadmap Phases 2-4 | Partial | Initial coaching endpoint in Slice 3; full planning system later. |
| 8 Multi-Disciplinary Reasoning | Domain agents + synthesis + confidence | Roadmap Phase 2 | Planned | Explicitly out-of-scope for Slice 3 (single-call only). |
| 9 Scoring | Domain + composite score transparency | Slice 2 | Covered | Slice 2 defines deterministic domain/composite scoring. |
| 10 Multi-Modal Input | Text, voice, image coaching input with discard policy | Slice 8 + Roadmap Phase 5 | Partial | Text + voice + image upload endpoint are implemented; broader multimodal expansion remains roadmap scope. |
| 11 Ongoing Coaching | Contextual Q&A with rationale and next actions | Slice 3 | Covered | `/coach/question` contract includes structured answer + suggestions. |
| 11.1 Interaction + Presentation | Progress feedback, readable markdown output, and coach-led follow-up question framing | Slice 6 + Slice 7 | Covered | Workspace chat now shows reasoning-stage progress; agent system prompts enforce rich markdown response structures for progress updates (logged entry, estimated impact, daily snapshot, insight, next task, coach question) and personalization to user goals/objectives. |
| 11.3 Conversational Continuity + Agent Transparency | Threaded chat history + visible specialist personalities during run | Slice 8 | Covered | Chat threads/messages are persisted per user and UI surfaces active/completed agent roles. |
| 11.4 Strategy Layering | Distinct Goal Strategist (6-24 week) and Orchestrator (daily/weekly) roles with hierarchy | Slice 8 | Covered | Goal Strategist added as strategic layer; Orchestrator performs operational conflict resolution and weighted priority selection. Specialist prompts are now formalized through runtime agent contracts (`app/core/agent_contracts.py`) with mission override by user goals/objectives. |
| 11.5 Proactive Coaching Evolution | Coaching uses user history/trends to set success checkpoints and pivot triggers | Slice 8 | Covered | Response shaping adds proactive checkpoint/pivot framing using baseline + 7-day logs + recent conversation history. |
| 11.6 Specialist-Aligned Daily Check-In | Daily check-in uses AI-specialist-generated, time-of-day-adaptive questions with cancel support | Slice 8 (chat workflow refinement) | Covered | `/coach/daily-checkin-plan` now builds dynamic, non-core-field check-ins from specialist context plus orchestrator prioritization using actual local time, same-day log state, and 7-day trend context (with deterministic fallback). Prompts instruct specialists to avoid already-captured signals and request detail values in-line. Free-text answers are parsed via utility-model extraction (`/coach/daily-checkin/parse-answer`) so mixed replies (status + details) are captured in one turn. Check-in resumes intake-style by loading prior same-day state and skipping answered items. Each step can produce a goal-aware expanded coaching summary via `/coach/daily-checkin/step-summary`; nutrition logs render detailed meal summaries via `/coach/daily-checkin/food-log-summary`. Dynamic check-in artifacts are persisted in `daily_logs.checkin_payload_json` for future suppression/analysis. |
| 11.7 Context-Window-Safe Memory | Important user updates from free chat are converted to structured logs and reused by all specialists | Slice 8 (runtime hardening) | Covered | Free-form chat updates are parsed by utility-model extraction into structured event records (`events`, `answers`, `extras`) and stored in daily logs; coaching context exposes structured memory digests so agent decisions can query persisted operational history without depending on full transcript context. |
| 11.5 Specialist Data Coverage + Runtime Gap Capture | Specialist runs validate data coverage and auto-log missing runtime datasets/features | Slice 8 (agent runtime hardening) | Covered | Coach pipeline checks specialist data prerequisites; degraded coverage is marked in agent trace and runtime gaps are written to shared `feedback_entries` with 24h dedupe. |
| 11.2 Cost + Latency Guardrails | Auto->quick routing, constrained orchestration, token budgets, safe retries, response cache | Slice 7 + Roadmap Phase 8 | Partial | Core controls implemented; ongoing tuning/telemetry thresholds remain continuous optimization work. |
| 12 Guided Question Engine | Proactive next-best-question generation | Slice 3 + Roadmap Phase 4 | Partial | Suggested questions required in Slice 3 response; proactive engine later. |
| 13 Experiment & Adaptation | N-of-1 experiment lifecycle and adaptation | Roadmap Phase 3 | Planned | Explicitly out-of-scope in early slices. |
| 14 Override & Consequence | User override with consequences/mitigation | Roadmap Phases 3-4 | Planned | Not in Slices 1-4. |
| 15 Knowledge Updating | Research ingestion + confidence + acceptance | Roadmap Phase 7 | Planned | Explicitly out-of-scope in Slice 3. |
| 16 Dashboard | Daily/weekly/monthly, scores, progress, experiment impact | Slice 2 + Slice 8 + Roadmap Phase 6 | Partial | Slice 2 delivers score summary; Slice 8 adds deterministic overall summary and daily-log-driven snapshots. Chat actions (`Daily Summary`, `Daily Plan`, `What Next`) route through agent synthesis (`/coach/proactive-card`) with explicit daily-log + weekly + monthly summary inputs. `Daily Summary` prompt now requires operational reporting (estimated calories/macros, hydration, meds/supplements, remaining-vs-goal, and missing-data assumptions). |
| 17 System Boundaries | Not diagnosis, no over-promising, safety checks | Slice 3 + drift/safety docs | Partial | Emergency guardrails in Slice 3; broader policy enforcement should be tested continuously. |

## Checklist Mapping (`docs/USERNEEDS_CHECKLIST.md`)

- Core MVP checklist items currently targeted by slices:
  - Auth + isolation: Slice 1
  - Baseline intake: Slice 1
  - Metrics/scoring/dashboard API: Slice 2
  - Contextual coaching endpoint: Slice 3
  - Deterministic AI test harness: Slice 4
  - GUI onboarding + LLM setup gate before intake: Slice 5
  - Workspace menu + optional/re-runnable intake + settings + model usage stats: Slice 6
  - AI-led conversational intake coach agent: Slice 7

- Checklist groups primarily mapped to later phases:
  - Full round-table agents
  - Experiment engine
  - Guided question engine (proactive)
  - Multi-modal input (voice/photo)
  - Advanced dashboard UI and research ingestion

## Traceability Rules
- Any change to `docs/USERNEEDS.md` must update this matrix in the same PR.
- Any new slice must add/update row mappings above.
- Drift checks should reference this file plus `docs/DRIFT_DETECTION_CHECKLIST.md`.

## Open Decisions
- Whether supplement/medication baseline fields should move into a near-term slice.
- Minimum dashboard requirements for MVP release gate.
