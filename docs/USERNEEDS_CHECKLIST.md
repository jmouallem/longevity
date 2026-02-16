# The Longevity Alchemist
## User Needs Checklist

---

# 1?? Core Purpose

- [ ] System establishes structured health baseline
- [ ] System helps define measurable longevity goals
- [ ] System generates personalized, science-informed plan
- [ ] System tracks measurable progress over time
- [ ] System adapts recommendations based on outcomes
- [ ] System explains reasoning clearly in lay terms
- [ ] System clearly states it is not medical advice

---

# 2?? Privacy & Infrastructure

- [ ] Multi-user authentication implemented
- [ ] User data isolated per account
- [ ] SQLite database used (embedded in container)
- [ ] Database stored on persistent disk
- [ ] No external hosted database used
- [ ] No image storage
- [ ] No audio storage (transcript only)
- [ ] LLM API keys never exposed client-side
- [ ] All AI calls handled server-side
- [ ] User can configure AI provider/model/key per account
- [ ] OpenAI (ChatGPT) and Gemini are supported
- [ ] Model list can be fetched dynamically from provider API
- [ ] Deterministic fallback model list exists when provider lookup fails
- [ ] User can configure a reasoning model profile
- [ ] User can configure a deep thinker model profile
- [ ] User can configure a utility model profile
- [ ] User can manually enable deep-think mode on a coaching submission
- [ ] Utility tasks route to utility model by default
- [ ] Deep-think submissions route to deep thinker model by default
- [ ] Model selectors show cost metadata when available
- [ ] User AI keys are encrypted at rest
- [ ] User AI keys are masked in responses and never logged
- [ ] User can rotate/revoke AI key
- [ ] Coaching uses the authenticated user's configured provider/model
- [ ] Token usage tracked per user/provider/model
- [ ] Token usage endpoint returns prompt/completion/total token counts and request counts
- [ ] External connectors use modular provider adapters (not hard-coded provider logic in core domain)
- [ ] Per-user consent/auth enforced for each external connector
- [ ] Synced provider data is normalized into internal structured metrics
- [ ] Incremental sync supported (no full re-import required each run)
- [ ] Provider sync failures degrade gracefully (no app-wide outage)

---

# 3?? Baseline Intake

## Objective Data
- [ ] Weight captured
- [ ] Waist measurement captured
- [ ] Blood pressure captured
- [ ] Resting heart rate captured
- [ ] HRV (optional)
- [ ] Sleep duration captured
- [ ] Activity level captured
- [ ] Labs (optional)
- [ ] Medications recorded
- [ ] Supplements recorded

## Subjective Data
- [ ] Energy level recorded
- [ ] Mood recorded
- [ ] Stress recorded
- [ ] Sleep satisfaction recorded
- [ ] Motivation recorded

## Derived Metrics
- [ ] Cardiometabolic risk estimate generated
- [ ] Sleep quality index generated
- [ ] Recovery score generated
- [ ] Behavioral consistency score generated
- [ ] Initial domain scores generated

- [ ] Intake adapts with follow-up questions when needed


## Adaptive Intake Experience
- [ ] Intake starts with a goal-identification question
- [ ] Intake coach asks for user's top goals first (top 3 supported)
- [ ] Intake coach gathers early profile context (age, sex, weight, BP, sleep, stress)
- [ ] Intake runs one question at a time with adaptive follow-up prompts
- [ ] Goal-based adaptive depth is applied
- [ ] Risk-based clarifying prompts trigger for high-risk baseline values
- [ ] Engagement style adaptation works (concise vs deep)
- [ ] Intake tone starts neutral/professional and adapts safely
- [ ] Required structured core is always captured
- [ ] Optional modules remain optional and goal-triggered
- [ ] Intake coach probes deeper in concern areas
- [ ] Conversational answers are mapped to deterministic structured baseline fields
- [ ] Motivational framing is shown before completion
- [ ] Data-use transparency and non-diagnostic boundary are shown
- [ ] Intake completion summary is generated
- [ ] Post-intake focus areas highlighted without requiring numeric scores
- [ ] No full free-form intake transcript is stored
- [ ] User can skip intake after setup and complete later from workspace menu
- [ ] Existing users can re-run/update intake at any time
- [ ] Intake menu clearly shows completion status
- [ ] Successful intake submission routes user to default chat view

## Main Workspace + Settings
- [ ] Main workspace has one-view-at-a-time menu navigation
- [ ] Workspace includes chat, intake, settings, and usage views
- [ ] Settings include AI config updates
- [ ] Settings include password change
- [ ] Settings include user-data reinitialize
- [ ] Settings include model-usage reset independent of data reinitialize
- [ ] App includes quick feedback capture (feature/idea/bug)
- [ ] Feedback store is shared across users (single table)
- [ ] Feedback can be exported as downloadable CSV
- [ ] Feedback store can be cleared from UI action
- [ ] Chat shows processing progress feedback during reasoning pipeline
- [ ] Chat answer rendering is readable markdown-style (sections/bullets/spacing)
- [ ] Follow-up prompts are framed as coach questions for the user to answer next
---

# 4?? Goal Definition

- [ ] System translates vague goals into measurable targets
- [ ] Timeline estimates provided
- [ ] Conservative and aggressive options offered
- [ ] Bottlenecks identified
- [ ] Goals editable over time

---

# 5?? Personalized Plan Generation

- [ ] Nutrition guidance generated
- [ ] Exercise guidance generated
- [ ] Sleep guidance generated
- [ ] Stress management suggestions provided
- [ ] Supplement guidance (with dosage ranges) provided
- [ ] Recommendations prioritized by leverage
- [ ] Monitoring guidance included

---

# 6?? Multi-Modal Input

- [ ] Text input supported
- [ ] Voice input supported (transcribed)
- [ ] Meal photo input supported
- [ ] Meal photo interpreted via AI
- [ ] Structured macro estimate stored
- [ ] Image discarded immediately

---

# 7?? AI Round Table Reasoning

- [ ] Cardio/Metabolic domain active
- [ ] Nutrition domain active
- [ ] Sleep domain active
- [ ] Exercise domain active
- [ ] Supplement domain active
- [ ] Behavioral domain active
- [ ] Data trend analysis active
- [ ] Safety moderator active
- [ ] Domain outputs synthesized into final response

---

# 8?? Ongoing Coaching

- [ ] User can ask free-form questions
- [ ] What next? supported
- [ ] Meal planning questions supported
- [ ] Energy analysis supported
- [ ] Supplement safety checks supported
- [ ] Coaching references stored metrics
- [ ] Reasoning explained clearly
- [ ] Provider failures still return practical fallback guidance
- [ ] Auto mode defaults to cost-efficient quick path
- [ ] Quick mode uses constrained orchestration by default
- [ ] Per-task token ceilings are enforced
- [ ] Duplicate identical submissions can return short-TTL cached responses

---

# 9?? Guided Question Engine

- [ ] System generates Next Best Question
- [ ] Contextual prompts provided
- [ ] Follow-up experiment suggestions provided
- [ ] Data clarification prompts triggered when needed
- [ ] Prompting adapts to user engagement style

---

# Experiment Engine

- [ ] Hypothesis structure defined
- [ ] Intervention stored
- [ ] Metrics linked to experiment
- [ ] Duration tracked
- [ ] Outcome evaluated
- [ ] Confidence updated
- [ ] Results influence future recommendations

---

# 1??1?? Scoring System

## Domain Scores
- [ ] Metabolic Health score
- [ ] Sleep Quality score
- [ ] Fitness Capacity score
- [ ] Recovery score
- [ ] Behavioral Consistency score

## Composite Score
- [ ] Composite Longevity Score calculated
- [ ] Weighting logic defined
- [ ] Scoring logic transparent
- [ ] Historical score tracking implemented

---

# 1??2?? Override & Safety

- [ ] Users can override recommendations
- [ ] Consequences explained
- [ ] Risk warnings generated when needed
- [ ] Monitoring checklist provided
- [ ] Follow-up reminders scheduled

---

# 1??3?? Knowledge Updating

- [ ] PubMed ingestion capability implemented (optional)
- [ ] Research summarized in lay language
- [ ] Evidence strength indicated
- [ ] User can accept/reject updates
- [ ] Plan updates logged

---

# 1??4?? Dashboard

- [ ] Daily view implemented
- [ ] Weekly trend view implemented
- [ ] Monthly trend view implemented
- [ ] Goal progress displayed
- [ ] Experiment results displayed
- [ ] Domain scores visualized
- [ ] Composite score visualized
- [ ] UI is mobile responsive
- [ ] UI is modern and graph-rich

---

# 1??5?? Character & Tone

- [ ] Warm and supportive tone
- [ ] Adaptive wit (only if user responds positively)
- [ ] Never shame-based
- [ ] Encourages experimentation
- [ ] Celebrates progress
- [ ] Normalizes setbacks

---

# 1??6?? System Boundaries

- [ ] Does not claim medical diagnosis
- [ ] Does not promise lifespan extension
- [ ] Avoids extreme or unsafe recommendations
- [ ] Safety checks performed before supplement guidance

---

# ? Completion Criteria

The Longevity Alchemist is considered functionally complete when:

- [ ] Users can complete intake
- [ ] Users can define goals
- [ ] Users receive personalized plan
- [ ] Users can log metrics
- [ ] Users can ask contextual questions
- [ ] Domain and composite scores update over time
- [ ] Experiments influence future recommendations
- [ ] System operates fully within a single Docker container
