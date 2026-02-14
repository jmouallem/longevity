# 🧪 The Longevity Alchemist  
## User Needs Checklist

---

# 1️⃣ Core Purpose

- [ ] System establishes structured health baseline
- [ ] System helps define measurable longevity goals
- [ ] System generates personalized, science-informed plan
- [ ] System tracks measurable progress over time
- [ ] System adapts recommendations based on outcomes
- [ ] System explains reasoning clearly in lay terms
- [ ] System clearly states it is not medical advice

---

# 2️⃣ Privacy & Infrastructure

- [ ] Multi-user authentication implemented
- [ ] User data isolated per account
- [ ] SQLite database used (embedded in container)
- [ ] Database stored on persistent disk
- [ ] No external hosted database used
- [ ] No image storage
- [ ] No audio storage (transcript only)
- [ ] LLM API keys never exposed client-side
- [ ] All AI calls handled server-side

---

# 3️⃣ Baseline Intake

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

---

# 4️⃣ Goal Definition

- [ ] System translates vague goals into measurable targets
- [ ] Timeline estimates provided
- [ ] Conservative and aggressive options offered
- [ ] Bottlenecks identified
- [ ] Goals editable over time

---

# 5️⃣ Personalized Plan Generation

- [ ] Nutrition guidance generated
- [ ] Exercise guidance generated
- [ ] Sleep guidance generated
- [ ] Stress management suggestions provided
- [ ] Supplement guidance (with dosage ranges) provided
- [ ] Recommendations prioritized by leverage
- [ ] Monitoring guidance included

---

# 6️⃣ Multi-Modal Input

- [ ] Text input supported
- [ ] Voice input supported (transcribed)
- [ ] Meal photo input supported
- [ ] Meal photo interpreted via AI
- [ ] Structured macro estimate stored
- [ ] Image discarded immediately

---

# 7️⃣ AI Round Table Reasoning

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

# 8️⃣ Ongoing Coaching

- [ ] User can ask free-form questions
- [ ] “What next?” supported
- [ ] Meal planning questions supported
- [ ] Energy analysis supported
- [ ] Supplement safety checks supported
- [ ] Coaching references stored metrics
- [ ] Reasoning explained clearly

---

# 9️⃣ Guided Question Engine

- [ ] System generates “Next Best Question”
- [ ] Contextual prompts provided
- [ ] Follow-up experiment suggestions provided
- [ ] Data clarification prompts triggered when needed
- [ ] Prompting adapts to user engagement style

---

# 🔟 Experiment Engine

- [ ] Hypothesis structure defined
- [ ] Intervention stored
- [ ] Metrics linked to experiment
- [ ] Duration tracked
- [ ] Outcome evaluated
- [ ] Confidence updated
- [ ] Results influence future recommendations

---

# 1️⃣1️⃣ Scoring System

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

# 1️⃣2️⃣ Override & Safety

- [ ] Users can override recommendations
- [ ] Consequences explained
- [ ] Risk warnings generated when needed
- [ ] Monitoring checklist provided
- [ ] Follow-up reminders scheduled

---

# 1️⃣3️⃣ Knowledge Updating

- [ ] PubMed ingestion capability implemented (optional)
- [ ] Research summarized in lay language
- [ ] Evidence strength indicated
- [ ] User can accept/reject updates
- [ ] Plan updates logged

---

# 1️⃣4️⃣ Dashboard

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

# 1️⃣5️⃣ Character & Tone

- [ ] Warm and supportive tone
- [ ] Adaptive wit (only if user responds positively)
- [ ] Never shame-based
- [ ] Encourages experimentation
- [ ] Celebrates progress
- [ ] Normalizes setbacks

---

# 1️⃣6️⃣ System Boundaries

- [ ] Does not claim medical diagnosis
- [ ] Does not promise lifespan extension
- [ ] Avoids extreme or unsafe recommendations
- [ ] Safety checks performed before supplement guidance

---

# ✅ Completion Criteria

The Longevity Alchemist is considered functionally complete when:

- [ ] Users can complete intake
- [ ] Users can define goals
- [ ] Users receive personalized plan
- [ ] Users can log metrics
- [ ] Users can ask contextual questions
- [ ] Domain and composite scores update over time
- [ ] Experiments influence future recommendations
- [ ] System operates fully within a single Docker container

