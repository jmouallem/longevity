# 🧪 The Longevity Alchemist  
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

It is structured, evidence-informed, multi-disciplinary, and supportive — not a simplistic wellness chatbot.

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

Intake must be adaptive — asking only relevant follow-up questions.

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
→ Improve sleep efficiency  
→ Stabilize glucose variability  
→ Improve recovery score  

"Avoid heart disease"  
→ Improve lipid markers  
→ Improve VO2 max  
→ Optimize blood pressure  

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

- “What next?”
- “What should I eat for lunch?”
- “Why am I tired?”
- “Should I fast today?”
- “Is this supplement safe?”
- “Am I improving?”

The system must:
- Use stored data and trends
- Provide contextual recommendations
- Explain reasoning in plain language
- Offer monitoring advice
- Suggest next best questions

---

# 12. Guided Question Engine

The system must proactively suggest:

- Contextual prompts
- Next best questions
- Clarifying data requests
- Experiment follow-ups

Examples:

“Would you like to explore why your sleep dipped?”  
“Ask me how to optimize dinner after training.”  
“Curious whether your fasting window is helping recovery?”

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

