# The Longevity Alchemist
## User Needs Specification

---

# 1. Vision

The Longevity Alchemist is an AI-powered, adaptive healthspan and lifespan coaching system.

Its purpose is to help individuals:

- Understand where they are starting
- Define meaningful longevity goals
- Build a personalized, science-informed plan
- Track measurable progress
- Adapt intelligently based on outcomes
- Learn why changes matter

It is structured, evidence-informed, multi-disciplinary, and supportive  not a simplistic wellness chatbot.

---

# 2. Target Audience

The system is designed for:

- General population seeking better health
- Longevity enthusiasts / biohackers
- Users with limited or advanced health knowledge
- Mobile and desktop users

It must balance accessibility with scientific rigor.

---

# 3. Core Experience Principles

The Longevity Alchemist must be:

- Scientifically grounded
- Data-driven
- Adaptive
- Supportive but honest
- Clear about not being medical advice
- Allowing user autonomy with guidance

Tone:
- Warm
- Witty (adaptive to user)
- Encouraging
- Never shame-based
- Never over-promising lifespan extension

---

# 4. Privacy & Data Requirements

- Multi-user authentication required
- Data stored locally in SQLite inside container
- Persistent storage via mounted disk
- No image storage
- No audio storage
- Only structured data retained
- External AI services used securely via backend
- API keys never exposed client-side

### 4.1 User-Owned AI Provider Configuration (BYOK)

Users must be able to configure AI provider credentials tied to their own account.

Minimum provider support:
- OpenAI (ChatGPT models)
- Google Gemini

Requirements:
- User can set preferred AI provider + model + API key during signup or immediately after signup
- Configuration is stored per user account (no shared user keys)
- API keys are encrypted at rest and never returned in full from APIs
- API keys are never written to logs
- User can rotate or revoke their key
- Coaching calls use the authenticated user's selected provider/model when configured
- If user key is missing/invalid, system returns clear remediation guidance
- User can load model options dynamically from provider APIs after authentication
- System provides a safe fallback model list per provider if dynamic lookup fails

### 4.3 Triple Model Profiles + Dynamic Model Catalog

The system must support three user-configurable model profiles:
- **Deep thinker model** for manually-invoked high-depth analysis during a coaching submission
- **Reasoning model** for default planning/analysis/coaching reasoning
- **Utility model** for routing, summarization, extraction, and other lightweight utility tasks

Requirements:
- Model lists should be fetched dynamically from provider APIs when possible
- A deterministic fallback model list must exist per provider
- UI must preselect the best default model from available options
- UI should show model cost metadata when available
- Deep thinker routing must be explicit and opt-in per submission
- Utility tasks must default to the utility model profile
- Routing rules must be explicit and testable (no hidden model switching)

### 4.2 External Data Connector Architecture (Future, Modular)

The system must support future third-party data ingestion through modular connectors, without coupling core domain logic to provider-specific APIs.

Initial planned providers:
- Apple Health
- Hume

Requirements:
- Use provider adapters/connectors behind a stable internal interface
- Support pull/sync workflows with deterministic normalization into internal metric schemas
- Preserve per-user consent and per-user authorization boundaries
- Store normalized structured data in first-class internal tables (not opaque blobs)
- Support incremental sync and conflict-safe upserts
- Provider failures must not break core app flows

---

# 5. Baseline Establishment Needs

The system must gather an initial structured baseline including:

## 5.1 Objective Data
- Weight
- Waist measurement
- Blood pressure
- Resting heart rate
- HRV (optional)
- Sleep duration and quality
- Activity level
- Lab values (optional)
- Medications
- Supplements

## 5.2 Subjective Data
- Energy level
- Mood
- Stress
- Sleep satisfaction
- Motivation

## 5.3 Derived Outputs
The system must compute:
- Cardiometabolic risk estimate
- Sleep quality index
- Recovery index
- Behavioral consistency score
- Initial domain scores

Intake must be adaptive  asking only relevant follow-up questions.
### 5.4 Adaptive Intake Experience

The intake experience must be:
- Structured and clinically grounded
- Adaptive to goals and context
- Personalized in tone and engagement
- Intelligent about what to ask next
- Efficient (not unnecessarily long)
- Motivating and confidence-building

The intake must dynamically adjust depth and tone based on:
- User goals
- Risk signals
- Data availability
- Engagement style

### 5.5 Intake Personality

Intake persona baseline:
"You are The Longevity Alchemist  a warm, witty, science-informed guide helping users optimize their healthspan and lifespan."

Rules:
- Start neutral and professional
- Use light wit only when the user responds positively
- Never shame-based
- Never alarmist

Intake persona differs from coaching persona:
- Intake: structured, guiding, efficient, goal-aligned questioning
- Coaching: advisory, reflective, contextual recommendation

### 5.6 Adaptive Logic Requirements

Goal-based adaptation:
- Begin with: "What would you most like to improve right now?"
- Emphasize domain depth by goal category
- Prioritize relevant questions, defer low-priority domains
- Offer optional deeper assessment

Risk-based adaptation:
- If high BP, high waist, very low sleep, or severe stress appears:
  - Probe gently with clarifying questions
  - Flag domain for coaching priority

Engagement-based adaptation:
- Short answers -> keep concise
- Detailed answers -> allow deeper probing
- Playful tone -> allow mild wit
- Serious tone -> remain professional

### 5.7 Structured + Conversational Hybrid Model

Required structured core (always captured):
- Weight
- Waist
- Blood pressure
- Resting heart rate
- Sleep hours
- Activity level
- Energy
- Mood
- Stress
- Sleep quality
- Motivation

Optional adaptive modules (goal-triggered):
- Nutrition patterns
- Training history
- Supplement stack
- Lab markers
- Fasting practices
- Sauna/cold exposure
- Medication details

### 5.7.1 AI-Led Intake Coach Agent

The intake should be conducted as a guided conversation by a dedicated intake coach agent.

Requirements:
- Intake starts with a coach-led opener and asks for top goals first (for example: top 3 goals).
- Intake coach should gather key profile context early (for example: age, sex, weight, blood pressure, sleep, stress).
- The coach must ask one question at a time, then adapt the next question from user response.
- The coach must probe deeper in concern areas (risk signals or user-prioritized pain points).
- The coach must remain supportive, neutral-professional first, and avoid interrogative tone.
- The coach must map conversational answers into deterministic structured fields required by baseline schema.
- The system should avoid persisting full free-form intake transcript long term; store structured output and concise summaries only.

### 5.8 Motivational + Transparency Requirements

Before intake completion, the system must:
- Explain why baseline matters
- Reinforce this is not judgment
- Emphasize experimentation mindset
- Set expectation of adaptation over time

Data transparency must include:
- How data will be used
- High-level scoring explanation
- Adaptive recommendation behavior
- Not-medical-diagnosis clarification

### 5.9 Intake Completion Output

After intake, the system should produce:
- Initial focus-area highlights (and domain score estimates only when scoring is available)
- 24 high-leverage improvement areas
- One suggested first experiment
- 3 suggested follow-up questions
- Clear next-step explanation

Intake boundaries:
- Do not overwhelm with too many questions at once
- Do not require lab data
- Do not diagnose disease
- Do not provide extreme recommendations
- Do not force optional modules
### 5.10 Adaptive Intake Acceptance Criteria

Adaptive intake is considered complete when:
- Required structured baseline captured
- Goal-based adaptive questioning triggered
- Tone adapts safely to user engagement
- Risk-based clarifications triggered when needed
- Intake coach asked one-question-at-a-time and adapted follow-up depth by concern
- Intake summary generated
- User feels guided, not interrogated
- Structured data stored deterministically
- No full free-form AI transcript storage

### 5.11 Intake Lifecycle + Main Workspace

The intake lifecycle must support:
- New user can start intake immediately after account + AI setup
- New user can skip intake and do it later
- Existing user can re-run/update intake at any time

Main workspace requirements:
- Menu-driven navigation with one view at a time (chat, intake, settings, usage)
- Intake menu must show completion status (pending vs completed)
- Clear guidance on how to run/update intake later from menu
- After successful intake submit, route user to default chat view

Settings requirements:
- User can update AI configuration from settings menu
- User can change password from settings menu
- User can reinitialize health/coaching data from settings menu
- User can reset model usage stats independently from settings menu
- User can quickly capture feature ideas and bugs from the app UI
- Feedback entries are stored in one shared table across users
- User can export all feedback entries as a downloadable CSV
- User can clear all feedback entries from the shared table

Token usage requirements:
- Track tokens per user/provider/model
- Expose prompt/completion/total token counters and request counts

---

# 6. Goal Definition Needs

The system must:

- Translate vague desires into measurable targets
- Suggest realistic timelines
- Identify bottlenecks
- Offer conservative and aggressive pathways
- Allow goal updates over time

Example transformations:

"More energy"
? Improve sleep efficiency
? Stabilize glucose variability
? Improve recovery score

"Avoid heart disease"
? Improve lipid markers
? Improve VO2 max
? Optimize blood pressure

---

# 7. Personalized Planning Needs

The system must generate step-by-step guidance covering:

- Nutrition
- Exercise
- Sleep
- Stress management
- Supplement guidance (with dosage ranges)
- Habit formation

Recommendations must:
- Explain reasoning clearly
- Be prioritized by leverage
- Include monitoring suggestions
- Be modifiable by user

---

# 8. Multi-Disciplinary Reasoning

The system must evaluate inputs using domain-scoped reasoning:

Domains include:
- Cardio / Metabolic
- Nutrition
- Sleep
- Exercise
- Supplements
- Behavioral
- Data trends
- Safety moderation

Outputs must include:
- Observations
- Hypotheses
- Risks
- Recommendations
- Confidence level

Final output must synthesize these domains into coherent guidance.

---

# 9. Composite and Domain Scoring

The system must provide:

## 9.1 Domain Scores
- Metabolic Health
- Sleep Quality
- Fitness Capacity
- Recovery
- Behavioral Consistency

## 9.2 Composite Longevity Score
- Weighted aggregation of domain scores
- Transparent scoring logic
- Used for trend tracking
- Not presented as medical diagnosis

---

# 10. Multi-Modal Input

The system must support:

- Text input
- Voice input (converted to text)
- Meal photo input

For meal photos:
- Image sent to AI
- Structured food + macro estimate returned
- Only structured data stored
- Image discarded immediately

---

# 11. Ongoing Coaching Needs

Users must be able to ask:

- What next?
- What should I eat for lunch?
- Why am I tired?
- Should I fast today?
- Is this supplement safe?
- Am I improving?

The system must:
- Use stored data and trends
- Provide contextual recommendations
- Explain reasoning in plain language
- Offer monitoring advice
- Suggest next best questions

### 11.1 Interaction + Presentation Requirements

- Chat must provide clear progress feedback while processing (for example: context load, specialist passes, synthesis).
- Final answer must be readable markdown-style text with short sections, bullets, and spacing.
- The UI must render follow-up items as **coach questions for the user to answer next**, not as questions the user should ask the system.
- Follow-up questions should drive iterative refinement and allow the system to store important structured details over time.
- On provider failure, the user should still receive practical and safe fallback guidance.

### 11.2 Cost + Latency Guardrails

- Auto mode should default to a cost-efficient quick path.
- Quick path should run constrained orchestration by default.
- Deep-think should remain explicit and user-invoked.
- Per-task token budgets must be enforced.
- Duplicate submissions within a short time window should use response caching where safe.
- Provider retries/fallbacks should avoid excessive duplicate billable calls.

---

# 12. Guided Question Engine

The system must proactively suggest:

- Contextual prompts
- Next best questions
- Clarifying data requests
- Experiment follow-ups

Examples:

Would you like to explore why your sleep dipped?
Ask me how to optimize dinner after training.
Curious whether your fasting window is helping recovery?

This feature is mandatory.

---

# 13. Experiment & Adaptation Engine

Recommendations may become structured experiments including:

- Hypothesis
- Intervention
- Metrics to monitor
- Duration
- Success criteria
- Evaluation
- Confidence update

The system must adapt future guidance based on experiment outcomes.

---

# 14. Override & Consequence Modeling

Users must be allowed to override recommendations.

The system must:
- Explain potential consequences
- Provide risk warnings when appropriate
- Suggest mitigation steps
- Offer monitoring checklist
- Maintain supportive tone

---

# 15. Knowledge Updating

If research ingestion is enabled:

The system must:
- Summarize findings in lay language
- Explain impact on current plan
- Provide evidence confidence rating
- Allow user acceptance or rejection

---

# 16. Dashboard Requirements

The system must provide:

- Daily view
- Weekly trends
- Monthly trends
- Domain scores
- Composite score
- Goal progress
- Experiment impact
- Adherence consistency

UI must be:
- Modern
- Clean
- Graph-rich
- Mobile responsive

---

# 17. What The Longevity Alchemist Is Not

- Not a calorie counter
- Not a static diet plan generator
- Not a medical diagnosis tool
- Not a supplement hype engine

It is:

A structured, adaptive longevity coaching system grounded in measurable data, guided experimentation, and multidisciplinary reasoning.
