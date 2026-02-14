# Slice 7 - AI-Led Conversational Intake Coach

## Objective
Implement intake as a coach-led conversation that:
- asks one question at a time,
- starts from user goals,
- probes deeper where concern/risk signals appear,
- maps answers into deterministic structured baseline fields.

## In Scope
- Intake coach agent orchestration for baseline collection.
- Goal-first opening (top goals, top 3 supported).
- Conversational capture of profile + baseline context (including age/sex + required core baseline fields).
- Adaptive concern probing:
  - deeper follow-up on high-risk values,
  - deeper follow-up in user-prioritized domains.
- Deterministic extraction/mapping into baseline schema.
- Keep transcript storage bounded (structured output + concise summary, no full transcript persistence).

## Out Of Scope
- Full multi-agent council orchestration.
- Voice/image intake modalities.
- Advanced experiment planning.

## Acceptance Criteria
- Intake runs as one-question conversational flow.
- Goal-first prompt triggers domain prioritization.
- Concern/risk signals trigger deeper clarifying questions.
- Required structured baseline fields are deterministically populated.
- User can pause/continue intake without losing structured progress.
- Full transcript is not stored long-term.
