import json
import re
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.db.models import Baseline, IntakeConversationSession, User, UserAIConfig
from app.db.session import get_db
from app.services.llm import LLMClient, get_llm_client

router = APIRouter(prefix="/intake", tags=["intake"])


class ActivityLevel(str):
    sedentary = "sedentary"
    light = "light"
    moderate = "moderate"
    high = "high"
    athlete = "athlete"


VALID_ACTIVITY = {"sedentary", "light", "moderate", "high", "athlete"}
VALID_ENGAGEMENT = {"concise", "detailed", "playful", "serious"}
VALID_FASTING_INTEREST = {"yes", "no", "unsure"}


class BaselineRequest(BaseModel):
    primary_goal: str = Field(min_length=2, max_length=64)
    top_goals: Optional[list[str]] = None
    goal_notes: Optional[str] = Field(default=None, max_length=2000)
    target_outcome: Optional[str] = Field(default=None, max_length=2000)
    timeline: Optional[str] = Field(default=None, max_length=64)
    biggest_challenge: Optional[str] = Field(default=None, max_length=2000)
    age_years: Optional[int] = Field(default=None, ge=10, le=120)
    sex_at_birth: Optional[str] = Field(default=None, max_length=32)
    height_text: Optional[str] = Field(default=None, max_length=64)

    weight: float = Field(ge=30, le=350)
    waist: float = Field(ge=40, le=250)
    systolic_bp: int = Field(ge=70, le=240)
    diastolic_bp: int = Field(ge=40, le=150)
    resting_hr: int = Field(ge=30, le=220)
    sleep_hours: float = Field(ge=0, le=16)
    activity_level: str = Field(min_length=3, max_length=32)

    energy: int = Field(ge=1, le=10)
    mood: int = Field(ge=1, le=10)
    stress: int = Field(ge=1, le=10)
    sleep_quality: int = Field(ge=1, le=10)
    motivation: int = Field(ge=1, le=10)

    engagement_style: Optional[str] = Field(default=None, max_length=32)
    nutrition_patterns: Optional[str] = Field(default=None, max_length=2000)
    training_history: Optional[str] = Field(default=None, max_length=2000)
    training_experience: Optional[str] = Field(default=None, max_length=32)
    equipment_access: Optional[str] = Field(default=None, max_length=64)
    limitations: Optional[str] = Field(default=None, max_length=2000)
    strength_benchmarks: Optional[str] = Field(default=None, max_length=2000)
    bedtime: Optional[str] = Field(default=None, max_length=32)
    wake_time: Optional[str] = Field(default=None, max_length=32)
    energy_pattern: Optional[str] = Field(default=None, max_length=64)
    health_conditions: Optional[str] = Field(default=None, max_length=2000)
    physician_restrictions: Optional[str] = Field(default=None, max_length=2000)
    supplement_stack: Optional[str] = Field(default=None, max_length=2000)
    lab_markers: Optional[str] = Field(default=None, max_length=2000)
    fasting_practices: Optional[str] = Field(default=None, max_length=2000)
    fasting_interest: Optional[str] = Field(default=None, max_length=32)
    fasting_style: Optional[str] = Field(default=None, max_length=32)
    fasting_experience: Optional[str] = Field(default=None, max_length=32)
    fasting_reason: Optional[str] = Field(default=None, max_length=2000)
    fasting_flexibility: Optional[str] = Field(default=None, max_length=64)
    recovery_practices: Optional[str] = Field(default=None, max_length=2000)
    medication_details: Optional[str] = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_fields(self):
        if self.diastolic_bp >= self.systolic_bp:
            raise ValueError("diastolic_bp must be lower than systolic_bp")
        if self.activity_level not in VALID_ACTIVITY:
            raise ValueError("activity_level must be sedentary/light/moderate/high/athlete")
        if self.engagement_style and self.engagement_style not in VALID_ENGAGEMENT:
            raise ValueError("engagement_style must be concise/detailed/playful/serious")
        if self.fasting_interest and self.fasting_interest not in VALID_FASTING_INTEREST:
            raise ValueError("fasting_interest must be yes/no/unsure")
        if self.top_goals:
            self.top_goals = [g.strip() for g in self.top_goals if g and g.strip()][:3]
        return self


class BaselineResponse(BaseModel):
    baseline_id: int
    user_id: int
    primary_goal: str
    focus_areas: list[str]
    risk_flags: list[str]
    next_steps: list[str]
    suggested_questions: list[str]
    disclaimer: str


class IntakeStatusResponse(BaseModel):
    baseline_completed: bool
    baseline_updated_at: Optional[str] = None
    primary_goal: Optional[str] = None


class ConversationStartRequest(BaseModel):
    top_goals: Optional[list[str]] = None
    goal_notes: Optional[str] = Field(default=None, max_length=2000)


class ConversationAnswerRequest(BaseModel):
    session_id: int
    answer: str = Field(min_length=1, max_length=2000)


class ConversationCompleteRequest(BaseModel):
    session_id: int


class ConversationCoachResponse(BaseModel):
    session_id: int
    status: str
    coach_message: str
    current_step: Optional[str] = None
    pending_steps: list[str]
    captured_fields: list[str]
    concern_flags: list[str]
    ready_to_complete: bool = False


class ConversationCompleteResponse(BaselineResponse):
    session_id: int
    user_profile_json: dict[str, Any]
    coaching_config_json: dict[str, Any]
    open_questions: list[str]


BASE_STEPS = [
    "top_goals",
    "target_outcome",
    "timeline",
    "biggest_challenge",
    "age_years",
    "sex_at_birth",
    "height_text",
    "weight",
    "waist",
    "systolic_bp",
    "diastolic_bp",
    "resting_hr",
    "activity_level",
    "training_experience",
    "training_history",
    "equipment_access",
    "limitations",
    "strength_benchmarks",
    "bedtime",
    "wake_time",
    "sleep_hours",
    "energy_pattern",
    "energy",
    "mood",
    "stress",
    "sleep_quality",
    "motivation",
    "health_conditions",
    "medication_details",
    "supplement_stack",
    "physician_restrictions",
    "lab_markers",
    "fasting_interest",
    "fasting_style",
    "fasting_experience",
    "fasting_reason",
    "fasting_flexibility",
    "fasting_practices",
    "recovery_practices",
    "goal_notes",
]

OPTIONAL_PROFILE_FIELDS = {
    "sex_at_birth",
    "height_text",
    "target_outcome",
    "timeline",
    "biggest_challenge",
    "training_experience",
    "equipment_access",
    "limitations",
    "strength_benchmarks",
    "bedtime",
    "wake_time",
    "energy_pattern",
    "health_conditions",
    "physician_restrictions",
    "fasting_interest",
    "fasting_style",
    "fasting_experience",
    "fasting_reason",
    "fasting_flexibility",
    "goal_notes",
    "nutrition_patterns",
    "training_history",
    "supplement_stack",
    "lab_markers",
    "fasting_practices",
    "recovery_practices",
    "medication_details",
}

STRING_FIELD_MAX_LENGTHS: dict[str, int] = {
    "target_outcome": 2000,
    "timeline": 64,
    "biggest_challenge": 2000,
    "sex_at_birth": 32,
    "height_text": 64,
    "activity_level": 32,
    "engagement_style": 32,
    "nutrition_patterns": 2000,
    "training_history": 2000,
    "training_experience": 32,
    "equipment_access": 64,
    "limitations": 2000,
    "strength_benchmarks": 2000,
    "bedtime": 32,
    "wake_time": 32,
    "energy_pattern": 64,
    "health_conditions": 2000,
    "physician_restrictions": 2000,
    "supplement_stack": 2000,
    "lab_markers": 2000,
    "fasting_practices": 2000,
    "fasting_interest": 32,
    "fasting_style": 32,
    "fasting_experience": 32,
    "fasting_reason": 2000,
    "fasting_flexibility": 64,
    "recovery_practices": 2000,
    "goal_notes": 2000,
    "medication_details": 2000,
}


def _primary_goal_from_answers(answers: dict[str, Any]) -> str:
    direct = str(answers.get("primary_goal") or "").strip()
    if direct:
        return direct
    goals = answers.get("top_goals") if isinstance(answers.get("top_goals"), list) else []
    if goals:
        return str(goals[0]).strip()
    return "longevity optimization"


def _batch_for_step(step: str) -> str:
    if step in {
        "top_goals",
        "age_years",
        "sex_at_birth",
        "height_text",
        "weight",
        "waist",
        "systolic_bp",
        "diastolic_bp",
        "activity_level",
    }:
        return "A"
    if step in {"target_outcome", "timeline", "biggest_challenge"}:
        return "B"
    if step in {"training_experience", "training_history", "equipment_access", "limitations", "strength_benchmarks"}:
        return "C"
    if step in {"resting_hr", "bedtime", "wake_time", "sleep_hours", "sleep_quality", "stress", "energy", "energy_pattern", "mood", "motivation"}:
        return "D"
    if step in {
        "probe_high_stress",
        "probe_low_sleep",
        "probe_elevated_bp",
        "health_conditions",
        "medication_details",
        "supplement_stack",
        "physician_restrictions",
        "lab_markers",
    }:
        return "E"
    return "F"


def _batch_steps(batch: str) -> list[str]:
    mapping = {
        "A": ["top_goals", "age_years", "sex_at_birth", "height_text", "weight", "waist", "systolic_bp", "diastolic_bp", "activity_level"],
        "B": ["target_outcome", "timeline", "biggest_challenge"],
        "C": ["training_experience", "training_history", "equipment_access", "limitations", "strength_benchmarks"],
        "D": ["resting_hr", "bedtime", "wake_time", "sleep_hours", "sleep_quality", "stress", "energy", "energy_pattern", "mood", "motivation"],
        "E": ["health_conditions", "medication_details", "supplement_stack", "physician_restrictions", "lab_markers"],
        "F": ["fasting_interest", "fasting_style", "fasting_experience", "fasting_reason", "fasting_flexibility", "fasting_practices", "recovery_practices", "goal_notes"],
    }
    return mapping.get(batch, [])


def _batch_prompt(batch: str, answers: dict[str, Any]) -> str:
    goal = _primary_goal_from_answers(answers)
    emphasis = ", ".join(_goal_focus(goal))
    pending = [s for s in _batch_steps(batch) if s not in answers]
    if batch == "A":
        if not pending:
            return "### Intake Agent - Batch A complete.\nMoving to the next section."
        lines = []
        if "age_years" in pending:
            lines.append("1. Age")
        if "sex_at_birth" in pending:
            lines.append("2. Sex at birth (optional)")
        if "weight" in pending:
            lines.append("3. Current weight (kg or lbs)")
        if "waist" in pending:
            lines.append("4. Waist (cm or inches)")
        if "systolic_bp" in pending or "diastolic_bp" in pending:
            lines.append("5. Blood pressure (top/bottom, e.g., 122/79)")
        if "activity_level" in pending:
            lines.append("6. Occupation/activity level (sedentary/light/moderate/high/athlete)")
        if "top_goals" in pending:
            lines.append("7. Top goals (if not already captured)")
        if "height_text" in pending:
            lines.append("8. Height (optional, if you want better body-composition context)")
        return (
            "### Intake Agent - Batch A (Basics)\n"
            "Data collection only. No coaching.\n"
            "Please provide what you can (unknown is allowed for optional fields):\n"
            f"{chr(10).join(lines)}\n"
            "Reply with one item or multiple items."
        )
    if batch == "B":
        lines = []
        if "target_outcome" in pending:
            lines.append("1. Primary target outcome (weight/waist/strength/BP/labs)")
        if "timeline" in pending:
            lines.append("2. Timeline (4-12 weeks / 3-6 months / long-term)")
        if "biggest_challenge" in pending:
            lines.append("3. Biggest challenge (cravings, schedule, sleep, stress, consistency)")
        return (
            f"### Intake Agent - Batch B (Goals)\n"
            f"Current goal context: {goal}\n"
            "Please provide:\n"
            f"{chr(10).join(lines) if lines else 'Batch B complete.'}\n"
            "Reply with one item or multiple items."
        )
    if batch == "C":
        if not pending:
            return "### Intake Agent - Batch C complete.\nMoving to the next section."
        lines = []
        if "training_experience" in pending:
            lines.append("1. Training experience (beginner/intermediate/advanced)")
        if "training_history" in pending:
            lines.append("2. Current weekly training (strength + cardio)")
        if "equipment_access" in pending:
            lines.append("3. Equipment access (gym/home/bodyweight)")
        if "limitations" in pending:
            lines.append("4. Injuries or limitations (optional)")
        if "strength_benchmarks" in pending:
            lines.append("5. Strength benchmarks (optional)")
        return (
            "### Intake Agent - Batch C (Training + Strength)\n"
            "Please provide:\n"
            f"{chr(10).join(lines)}\n"
            "Reply with one item or multiple items."
        )
    if batch == "D":
        if not pending:
            return "### Intake Agent - Batch D complete.\nMoving to the next section."
        lines = []
        if "resting_hr" in pending:
            lines.append("1. Resting heart rate")
        if "bedtime" in pending or "wake_time" in pending:
            lines.append("2. Typical bedtime and wake time (optional)")
        if "sleep_hours" in pending:
            lines.append("3. Typical sleep hours per night")
        if "sleep_quality" in pending:
            lines.append("4. Sleep quality (1-10)")
        if "stress" in pending:
            lines.append("5. Stress (1-10)")
        if "energy" in pending or "energy_pattern" in pending:
            lines.append("6. Energy (1-10) and AM/PM pattern (optional)")
        if "mood" in pending:
            lines.append("7. Mood (1-10)")
        if "motivation" in pending:
            lines.append("8. Motivation (1-10)")
        return (
            "### Intake Agent - Batch D (Sleep + Recovery)\n"
            f"Goal emphasis for this profile: {emphasis}\n"
            "Please provide:\n"
            f"{chr(10).join(lines)}\n"
            "Reply with one item or multiple items."
        )
    if batch == "E":
        if not pending:
            return "### Intake Agent - Batch E complete.\nMoving to the next section."
        lines = []
        if "health_conditions" in pending:
            lines.append("1. Known conditions (optional)")
        if "medication_details" in pending:
            lines.append("2. Current meds name/dose/timing (optional)")
        if "supplement_stack" in pending:
            lines.append("3. Supplement stack (optional)")
        if "physician_restrictions" in pending:
            lines.append("4. Physician restrictions (optional)")
        if "lab_markers" in pending:
            lines.append("5. Any relevant lab markers (optional)")
        return (
            "### Intake Agent - Batch E (Health Context)\n"
            "Please provide what is relevant (unknown/skip is acceptable):\n"
            f"{chr(10).join(lines)}\n"
            "Reply with one item or multiple items."
        )
    if not pending:
        return "### Intake Agent - Batch F complete.\nYou can finalize intake when ready."
    lines = []
    if "fasting_interest" in pending:
        lines.append("1. Interested in fasting (yes/no/unsure)")
    if "fasting_style" in pending:
        lines.append("2. Preferred style (12:12, 14:10, 16:8, flexible)")
    if "fasting_experience" in pending:
        lines.append("3. Experience level (new/experienced)")
    if "fasting_reason" in pending:
        lines.append("4. Why fasting (fat loss / metabolic health / schedule / focus)")
    if "fasting_flexibility" in pending:
        lines.append("5. Willingness to vary on training vs rest days")
    if "fasting_practices" in pending:
        lines.append("6. Current fasting practices (optional)")
    if "recovery_practices" in pending:
        lines.append("7. Recovery practices (optional)")
    if "goal_notes" in pending:
        lines.append("8. Any extra context to personalize coaching (optional)")
    return (
        "### Intake Agent - Batch F (Fasting Preference)\n"
        "Please provide if relevant (optional):\n"
        f"{chr(10).join(lines)}\n"
        "Reply with one item or multiple items."
    )


def _question_for_step(step: str, answers: dict[str, Any]) -> str:
    if step in BASE_STEPS:
        return _batch_prompt(_batch_for_step(step), answers)
    prompts = {
        "probe_high_stress": "I see elevated stress. What are the top stress drivers right now?",
        "probe_low_sleep": "Sleep looks low. What is the main blocker to more sleep?",
        "probe_elevated_bp": "Your blood pressure may need attention. Have you noticed patterns or recent readings over time?",
    }
    return prompts.get(step, "Please share the next detail.")


def _extract_goal_batch_values(raw: str) -> dict[str, str]:
    text = raw.strip()
    lower = text.lower()
    out: dict[str, str] = {}

    timeline_match = re.search(
        r"(?:(?:time\s*line|timeline)\s*[:\-]?\s*)?((?:\d+\s*(?:to|-)\s*\d+\s*(?:weeks?|months?))|(?:\d+\s*(?:weeks?|months?|years?))|long[\s-]?term)",
        lower,
    )
    if timeline_match:
        out["timeline"] = timeline_match.group(1).strip()

    challenge_match = re.search(r"(?:challenge|barrier)\s*(?:is|=|:)?\s*([^,.]+)", lower)
    if challenge_match:
        out["biggest_challenge"] = challenge_match.group(1).strip()
    elif any(k in lower for k in ["craving", "schedule", "sleep", "stress", "consisten"]):
        # If explicit challenge label is missing, store compact phrase as challenge context.
        out["biggest_challenge"] = text[:160]

    cleaned = re.sub(r"(?:time\s*line|timeline)\s*[:\-]?\s*[^,.;]+", "", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"(?:challenge|barrier)\s*(?:is|=|:)?\s*[^,.;]+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" ,.;")
    if cleaned:
        out["target_outcome"] = cleaned[:2000]
    return out


def _extract_basics_batch_values(raw: str) -> dict[str, Any]:
    text = raw.strip()
    lower = text.lower()
    out: dict[str, Any] = {}

    # Blood pressure can fill both fields in one pass.
    bp = re.search(r"(\d{2,3})\s*/\s*(\d{2,3})", text)
    if bp:
        out["systolic_bp"] = int(bp.group(1))
        out["diastolic_bp"] = int(bp.group(2))

    # Age heuristic
    age = re.search(r"\b(\d{2,3})\s*(?:y|yr|yrs|year|years)\b", lower)
    if age:
        out["age_years"] = int(age.group(1))

    # Sex heuristic
    if re.search(r"\bmale\b", lower):
        out["sex_at_birth"] = "male"
    elif re.search(r"\bfemale\b", lower):
        out["sex_at_birth"] = "female"
    elif re.search(r"\bintersex\b", lower):
        out["sex_at_birth"] = "intersex"

    # Weight heuristic
    w = re.search(r"(\d+(?:\.\d+)?)\s*(lb|lbs|pound|pounds|kg|kgs)\b", lower)
    if w:
        out["weight"] = _parse_weight_kg(f"{w.group(1)} {w.group(2)}")

    # Waist heuristic
    # Waist heuristic: prioritize explicit "waist" label, otherwise use a plausible adult waist range.
    waist_labeled = re.search(r"\bwaist\b[^0-9]*(\d+(?:\.\d+)?)\s*(in|inch|inches|cm)\b", lower)
    if waist_labeled:
        out["waist"] = _parse_waist_cm(f"{waist_labeled.group(1)} {waist_labeled.group(2)}")
    else:
        inch_candidates = re.findall(r"(\d+(?:\.\d+)?)\s*(in|inch|inches)\b", lower)
        for num, unit in inch_candidates:
            try:
                val = float(num)
            except Exception:
                continue
            # Ignore height inch fragments like "5ft 7in"; capture plausible waist values.
            if val >= 20:
                out["waist"] = _parse_waist_cm(f"{val} {unit}")
                break

    # Height heuristic
    ftin = re.search(r"(\d)\s*(?:ft|')\s*(\d{1,2})\s*(?:in|\"|inches)?", lower)
    if ftin:
        out["height_text"] = f"{ftin.group(1)} ft {ftin.group(2)} in"
    else:
        h = re.search(r"(?:height\s*)?(\d+(?:\.\d+)?)\s*(cm|in|inch|inches)\b", lower)
        if h:
            out["height_text"] = f"{h.group(1)} {h.group(2)}"

    # Activity level heuristic
    if any(k in lower for k in ["sedentary", "light", "moderate", "high", "athlete", "active", "intense", "low"]):
        out["activity_level"] = _parse_activity_level(lower)

    return out


def _extract_health_batch_values(raw: str) -> dict[str, str]:
    text = raw.strip()
    lower = text.lower()
    out: dict[str, str] = {}

    condition_terms = [
        "high blood pressure",
        "hypertension",
        "high cholesterol",
        "hyperlipidemia",
        "diabetes",
        "prediabetes",
        "thyroid",
        "sleep apnea",
    ]
    found_conditions = [term for term in condition_terms if term in lower]
    if found_conditions:
        out["health_conditions"] = ", ".join(found_conditions)

    medication_terms = [
        "candesartan",
        "ezetimibe",
        "lisinopril",
        "losartan",
        "amlodipine",
        "statin",
        "metformin",
        "levothyroxine",
    ]
    has_medication = any(term in lower for term in medication_terms) or bool(
        re.search(r"\b\d+(?:\.\d+)?\s*mg\b", lower)
    )
    if has_medication:
        out["medication_details"] = text[:2000]

    supplement_terms = [
        "supplement",
        "omega",
        "coq10",
        "magnesium",
        "vitamin",
        "creatine",
        "fish oil",
        "multivitamin",
        "centrum",
    ]
    if any(term in lower for term in supplement_terms):
        out["supplement_stack"] = text[:2000]

    lab_terms = ["ldl", "hdl", "triglyceride", "a1c", "glucose", "cholesterol", "apob"]
    if any(term in lower for term in lab_terms):
        out["lab_markers"] = text[:2000]

    if any(term in lower for term in ["restriction", "avoid", "doctor said", "physician"]):
        out["physician_restrictions"] = text[:2000]

    return out


def _extract_fasting_batch_values(raw: str) -> dict[str, str]:
    text = raw.strip()
    lower = text.lower()
    out: dict[str, str] = {}

    if any(term in lower for term in ["yes", "do fast", "fasting"]):
        if "no" in lower and "yes" not in lower:
            out["fasting_interest"] = "no"
        else:
            out["fasting_interest"] = "yes"
    elif any(term in lower for term in ["unsure", "not sure", "maybe"]):
        out["fasting_interest"] = "unsure"

    style = re.search(r"\b(12:12|14:10|16:8|18:6|20:4)\b", lower)
    if style:
        out["fasting_style"] = style.group(1)
    elif "flex" in lower:
        out["fasting_style"] = "flexible"

    if any(term in lower for term in ["new", "newish", "beginner"]):
        out["fasting_experience"] = "new"
    elif any(term in lower for term in ["experienced", "advanced", "veteran"]):
        out["fasting_experience"] = "experienced"

    if any(term in lower for term in ["fat loss", "weight"]):
        out["fasting_reason"] = "fat loss"
    elif any(term in lower for term in ["metabolic", "insulin", "glucose"]):
        out["fasting_reason"] = "metabolic health"
    elif any(term in lower for term in ["focus", "schedule", "clarity"]):
        out["fasting_reason"] = text[:2000]

    if any(term in lower for term in ["vary", "training day", "rest day", "willing", "flex"]):
        out["fasting_flexibility"] = "yes"

    if any(term in lower for term in ["currently", "practice", "usually", "most days"]):
        out["fasting_practices"] = text[:2000]

    return out


def _ai_parse_batch_values(
    llm_client: LLMClient,
    db: Session,
    user_id: int,
    raw: str,
    batch: str,
    pending_steps: list[str],
) -> dict[str, Any]:
    if not pending_steps:
        return {}
    keys_json = json.dumps(pending_steps)
    prompt = (
        "Parse the user intake reply into structured fields.\n"
        f"Batch: {batch}\n"
        f"Allowed keys: {keys_json}\n"
        "Rules:\n"
        "- Return JSON object only.\n"
        "- Include only keys from allowed list.\n"
        "- Use null when value is unknown.\n"
        "- Keep units if user gave them; do not invent values.\n"
        f"User text: {raw}"
    )
    parser_system = (
        "Return strict JSON object only. "
        "Do not add commentary, markdown, or extra keys."
    )
    try:
        parsed = llm_client.generate_json(
            db=db,
            user_id=user_id,
            prompt=prompt,
            task_type="utility",
            allow_web_search=False,
            system_instruction=parser_system,
        )
    except Exception:
        return {}
    if not isinstance(parsed, dict):
        return {}
    # Some model adapters may still wrap output in generic answer fields.
    if "answer" in parsed and isinstance(parsed["answer"], str):
        text = parsed["answer"].strip()
        if text.startswith("{") and text.endswith("}"):
            try:
                wrapped = json.loads(text)
                if isinstance(wrapped, dict):
                    parsed = wrapped
            except Exception:
                pass
    out: dict[str, Any] = {}
    for key in pending_steps:
        if key not in parsed:
            continue
        val = parsed.get(key)
        if val is None:
            continue
        if isinstance(val, str) and not val.strip():
            continue
        try:
            out[key] = _coerce_step_answer(key, str(val) if not isinstance(val, str) else val)
        except Exception:
            continue
    return out


def _coerce_step_answer(step: str, raw: str) -> Any:
    value = raw.strip()
    if not value:
        raise ValueError("Please provide a value or type unknown for optional fields.")
    if value.lower() in {"unknown", "skip", "n/a", "na"} and step in OPTIONAL_PROFILE_FIELDS:
        return "unknown"
    if step == "top_goals":
        goals = [g.strip() for g in value.replace("\n", ",").split(",") if g.strip()]
        if not goals:
            raise ValueError("Please provide at least one goal.")
        return goals[:3]
    if step in {
        "target_outcome",
        "timeline",
        "biggest_challenge",
        "training_history",
        "limitations",
        "strength_benchmarks",
        "health_conditions",
        "physician_restrictions",
        "supplement_stack",
        "lab_markers",
        "fasting_reason",
        "fasting_practices",
        "recovery_practices",
        "goal_notes",
        "medication_details",
    }:
        return value
    if step == "age_years":
        return int(_extract_number(value))
    if step == "height_text":
        return value[:64]
    if step == "systolic_bp":
        return _parse_bp(value)
    if step == "diastolic_bp":
        return int(_extract_number(value))
    if step == "resting_hr":
        return int(_extract_number(value))
    if step == "weight":
        return _parse_weight_kg(value)
    if step == "waist":
        return _parse_waist_cm(value)
    if step == "sleep_hours":
        return _parse_sleep_hours(value)
    if step in {"energy", "mood", "stress", "sleep_quality", "motivation"}:
        return int(_extract_number(value))
    if step == "activity_level":
        return _parse_activity_level(value)
    if step == "sex_at_birth":
        return value[:32]
    if step == "training_experience":
        return value[:32]
    if step == "equipment_access":
        return value[:64]
    if step in {"bedtime", "wake_time"}:
        return value[:32]
    if step == "energy_pattern":
        return value[:64]
    if step == "fasting_interest":
        low = value.lower()
        if "yes" in low:
            return "yes"
        if "no" in low:
            return "no"
        return "unsure"
    if step in {"fasting_style", "fasting_experience"}:
        return value[:32]
    if step == "fasting_flexibility":
        return value[:64]
    return value


def _normalize_answers_for_baseline(answers: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, val in answers.items():
        if val is None:
            normalized[key] = None
            continue
        if key == "top_goals":
            if isinstance(val, list):
                normalized[key] = [str(item).strip()[:64] for item in val if str(item).strip()][:3]
            else:
                normalized[key] = [str(val).strip()[:64]]
            continue
        max_len = STRING_FIELD_MAX_LENGTHS.get(key)
        if max_len and not isinstance(val, (int, float, dict, list)):
            normalized[key] = str(val).strip()[:max_len]
        else:
            normalized[key] = val
    return normalized


def _extract_number(text: str) -> float:
    match = re.search(r"(-?\d+(?:\.\d+)?)", text)
    if not match:
        raise ValueError("Please include a number.")
    return float(match.group(1))


def _parse_weight_kg(text: str) -> float:
    val = _extract_number(text)
    lower = text.lower()
    if any(unit in lower for unit in ["lb", "lbs", "pound"]):
        return round(val * 0.45359237, 2)
    return round(val, 2)


def _parse_waist_cm(text: str) -> float:
    val = _extract_number(text)
    lower = text.lower()
    if re.search(r"\b(in|inch|inches)\b", lower):
        return round(val * 2.54, 2)
    return round(val, 2)


def _parse_sleep_hours(text: str) -> float:
    lower = text.lower().strip()
    hm = re.search(r"(\d+)\s*h(?:ours?)?\s*(\d+)?\s*m?", lower)
    if hm:
        hours = int(hm.group(1))
        mins = int(hm.group(2)) if hm.group(2) else 0
        return round(hours + mins / 60.0, 2)
    return round(_extract_number(lower), 2)


def _parse_activity_level(text: str) -> str:
    lower = text.lower()
    if "athlete" in lower:
        return "athlete"
    if "high" in lower or "intense" in lower:
        return "high"
    if "light" in lower:
        return "light"
    if "sedentary" in lower or "low" in lower:
        return "sedentary"
    return "moderate"


def _parse_bp(text: str) -> Any:
    slash = re.search(r"(\d{2,3})\s*/\s*(\d{2,3})", text)
    if slash:
        return {"systolic": int(slash.group(1)), "diastolic": int(slash.group(2))}
    return int(_extract_number(text))


def _goal_focus(goal: str) -> list[str]:
    normalized = goal.lower().replace("-", " ").replace("_", " ")
    if "energy" in normalized:
        return ["sleep quality", "stress load", "daytime movement"]
    if "heart" in normalized or "bp" in normalized:
        return ["blood pressure", "waist trend", "activity consistency"]
    if "weight" in normalized:
        return ["weight trend", "nutrition patterns", "activity consistency"]
    if "mental" in normalized or "clarity" in normalized:
        return ["sleep quality", "stress regulation", "training load"]
    return ["sleep", "metabolic markers", "behavior consistency"]


def _risk_flags(data: BaselineRequest) -> list[str]:
    flags: list[str] = []
    if data.systolic_bp >= 140 or data.diastolic_bp >= 90:
        flags.append("elevated_bp")
    if data.waist >= 102:
        flags.append("high_waist")
    if data.sleep_hours < 6:
        flags.append("low_sleep")
    if data.stress >= 8:
        flags.append("high_stress")
    return flags


def _focus_areas(data: BaselineRequest) -> list[str]:
    return [f"Improve {topic}" for topic in _goal_focus(data.primary_goal)][:3]


def _next_steps(data: BaselineRequest, flags: list[str]) -> list[str]:
    steps = ["Capture baseline metrics consistently for 7 days"]
    if "low_sleep" in flags:
        steps.append("Set a fixed sleep window and track adherence")
    if "elevated_bp" in flags:
        steps.append("Recheck blood pressure at consistent times daily")
    if "high_stress" in flags:
        steps.append("Add a 10-minute stress downshift routine each evening")
    if len(steps) == 1:
        steps.append("Choose one daily habit tied to your primary goal")
    return steps[:3]


def _suggested_questions(data: BaselineRequest) -> list[str]:
    tone = "Want" if data.engagement_style != "serious" else "Would you like"
    return [
        f"{tone} a 7-day plan focused on {data.primary_goal}?",
        f"{tone} one high-impact habit to start this week?",
        f"{tone} a simple daily check-in format for progress?",
    ]


def _derive_coaching_focus(goal: str) -> str:
    g = (goal or "").lower()
    if any(k in g for k in ["fat", "weight"]):
        return "fat loss"
    if any(k in g for k in ["muscle", "strength", "performance"]):
        return "performance"
    if any(k in g for k in ["recomp", "recomposition"]):
        return "recomposition"
    if any(k in g for k in ["metabolic", "bp", "cholesterol", "heart", "lipid"]):
        return "metabolic health"
    return "longevity optimization"


def _build_user_profile_json(answers: dict[str, Any], baseline_payload: BaselineRequest) -> dict[str, Any]:
    goals = baseline_payload.top_goals if isinstance(baseline_payload.top_goals, list) else []
    primary = baseline_payload.primary_goal
    secondary = goals[1:] if len(goals) > 1 else []
    return {
        "demographics": {
            "age": baseline_payload.age_years,
            "sex": baseline_payload.sex_at_birth or "unknown",
            "height": baseline_payload.height_text or "unknown",
            "weight": baseline_payload.weight,
        },
        "lifestyle": {
            "occupation_activity": baseline_payload.activity_level,
            "schedule_constraints": baseline_payload.goal_notes or "unknown",
        },
        "goals": {
            "primary": primary,
            "secondary": secondary,
            "timeline": baseline_payload.timeline or "unknown",
            "target_outcome": baseline_payload.target_outcome or "unknown",
            "challenges": baseline_payload.biggest_challenge or "unknown",
        },
        "training": {
            "experience": baseline_payload.training_experience or "unknown",
            "current_plan": baseline_payload.training_history or "unknown",
            "equipment": baseline_payload.equipment_access or "unknown",
            "limitations": baseline_payload.limitations or "unknown",
            "benchmarks": baseline_payload.strength_benchmarks or "unknown",
        },
        "sleep": {
            "schedule": {
                "bedtime": baseline_payload.bedtime or "unknown",
                "wake_time": baseline_payload.wake_time or "unknown",
            },
            "duration": baseline_payload.sleep_hours,
            "quality": baseline_payload.sleep_quality,
            "stress": baseline_payload.stress,
            "energy": {
                "score": baseline_payload.energy,
                "pattern": baseline_payload.energy_pattern or "unknown",
            },
        },
        "health": {
            "conditions": baseline_payload.health_conditions or "unknown",
            "medications": baseline_payload.medication_details or "unknown",
            "supplements": baseline_payload.supplement_stack or "unknown",
            "restrictions": baseline_payload.physician_restrictions or "unknown",
        },
        "fasting": {
            "preference": baseline_payload.fasting_interest or "unknown",
            "style": baseline_payload.fasting_style or "unknown",
            "experience": baseline_payload.fasting_experience or "unknown",
            "reasons": baseline_payload.fasting_reason or "unknown",
            "flexibility": baseline_payload.fasting_flexibility or "unknown",
        },
    }


def _build_coaching_config_json(answers: dict[str, Any], baseline_payload: BaselineRequest) -> dict[str, Any]:
    goal = baseline_payload.primary_goal
    focus = _derive_coaching_focus(goal)
    fasting_text = str(baseline_payload.fasting_style or baseline_payload.fasting_practices or "").lower()
    if not fasting_text:
        fasting_mode = "none"
    elif "flex" in fasting_text:
        fasting_mode = "flexible"
    elif any(k in fasting_text for k in ["period", "train", "rest day"]):
        fasting_mode = "periodized"
    else:
        fasting_mode = "fixed"
    training_mode = "mixed"
    if "performance" in focus:
        training_mode = "strength priority"
    elif "fat loss" in focus:
        training_mode = "mixed"
    risk_flags: list[str] = []
    meds = (baseline_payload.medication_details or "").lower()
    if meds and meds != "unknown":
        if any(k in meds for k in ["candesartan", "lisinopril", "losartan", "amlodipine", "bp"]):
            risk_flags.append("has_hypertension_meds")
        if any(k in meds for k in ["ezetimibe", "statin", "lipid", "cholesterol"]):
            risk_flags.append("has_lipid_meds")
    adherence_style = "structured" if baseline_payload.motivation >= 7 else "flexible"
    return {
        "coaching_focus": focus,
        "macro_style": "protein-first balanced" if focus != "performance" else "balanced performance",
        "fasting_mode": fasting_mode,
        "training_mode": training_mode,
        "risk_flags": risk_flags,
        "adherence_style": adherence_style,
    }


def _open_questions(answers: dict[str, Any]) -> list[str]:
    critical = [
        ("timeline", "What timeline do you want (4-12 weeks / 3-6 months / long-term)?"),
        ("biggest_challenge", "What is your biggest adherence challenge right now?"),
        ("training_experience", "What is your training experience level?"),
        ("equipment_access", "What equipment access do you have (gym/home/bodyweight)?"),
        ("target_outcome", "What is your target outcome (weight/waist/strength/BP/labs)?"),
        ("bedtime", "What is your typical bedtime?"),
        ("wake_time", "What is your typical wake time?"),
        ("fasting_interest", "Are you interested in fasting (yes/no/unsure)?"),
    ]
    missing: list[str] = []
    for key, q in critical:
        val = answers.get(key)
        if val is None or str(val).strip() == "" or str(val).lower() == "unknown":
            missing.append(q)
    return missing[:10]


def _disclaimer() -> str:
    return "This is coaching guidance, not medical diagnosis."


def _require_ai_config(user: User, db: Session) -> None:
    config = db.query(UserAIConfig).filter(UserAIConfig.user_id == user.id).first()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Complete AI provider setup before starting intake",
        )


def _upsert_baseline_record(db: Session, user_id: int, payload: BaselineRequest) -> Baseline:
    record = db.query(Baseline).filter(Baseline.user_id == user_id).first()
    if not record:
        record = Baseline(user_id=user_id)
        db.add(record)
    record.primary_goal = payload.primary_goal[:64]
    record.top_goals_json = json.dumps(payload.top_goals or [payload.primary_goal])
    record.goal_notes = payload.goal_notes
    record.target_outcome = payload.target_outcome
    record.timeline = payload.timeline
    record.biggest_challenge = payload.biggest_challenge
    record.age_years = payload.age_years
    record.sex_at_birth = payload.sex_at_birth
    record.height_text = payload.height_text
    record.weight = payload.weight
    record.waist = payload.waist
    record.systolic_bp = payload.systolic_bp
    record.diastolic_bp = payload.diastolic_bp
    record.resting_hr = payload.resting_hr
    record.sleep_hours = payload.sleep_hours
    record.activity_level = payload.activity_level
    record.energy = payload.energy
    record.mood = payload.mood
    record.stress = payload.stress
    record.sleep_quality = payload.sleep_quality
    record.motivation = payload.motivation
    record.engagement_style = payload.engagement_style
    record.nutrition_patterns = payload.nutrition_patterns
    record.training_history = payload.training_history
    record.training_experience = payload.training_experience
    record.equipment_access = payload.equipment_access
    record.limitations = payload.limitations
    record.strength_benchmarks = payload.strength_benchmarks
    record.bedtime = payload.bedtime
    record.wake_time = payload.wake_time
    record.energy_pattern = payload.energy_pattern
    record.health_conditions = payload.health_conditions
    record.physician_restrictions = payload.physician_restrictions
    record.supplement_stack = payload.supplement_stack
    record.lab_markers = payload.lab_markers
    record.fasting_practices = payload.fasting_practices
    record.fasting_interest = payload.fasting_interest
    record.fasting_style = payload.fasting_style
    record.fasting_experience = payload.fasting_experience
    record.fasting_reason = payload.fasting_reason
    record.fasting_flexibility = payload.fasting_flexibility
    record.recovery_practices = payload.recovery_practices
    record.medication_details = payload.medication_details
    db.commit()
    db.refresh(record)
    return record


def _active_session(db: Session, user_id: int) -> Optional[IntakeConversationSession]:
    return (
        db.query(IntakeConversationSession)
        .filter(
            IntakeConversationSession.user_id == user_id,
            IntakeConversationSession.status == "active",
        )
        .order_by(IntakeConversationSession.updated_at.desc())
        .first()
    )


def _load_answers(session: IntakeConversationSession) -> dict[str, Any]:
    try:
        data = json.loads(session.answers_json or "{}")
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _concern_flags_from_answers(answers: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    if float(answers.get("sleep_hours", 7) or 7) < 6:
        flags.append("low_sleep")
    if int(answers.get("stress", 0) or 0) >= 8:
        flags.append("high_stress")
    if int(answers.get("systolic_bp", 0) or 0) >= 140 or int(answers.get("diastolic_bp", 0) or 0) >= 90:
        flags.append("elevated_bp")
    return flags


def _step_sequence(answers: dict[str, Any]) -> list[str]:
    steps = list(BASE_STEPS)
    flags = _concern_flags_from_answers(answers)
    if "high_stress" in flags:
        steps.append("probe_high_stress")
    if "low_sleep" in flags:
        steps.append("probe_low_sleep")
    if "elevated_bp" in flags:
        steps.append("probe_elevated_bp")
    return steps


def _next_pending_step(answers: dict[str, Any], current_step: str) -> Optional[str]:
    steps = _step_sequence(answers)
    if current_step in steps:
        start_index = steps.index(current_step) + 1
    else:
        start_index = 0
    for step in steps[start_index:]:
        if step not in answers:
            return step
    return None


def _coach_payload(session: IntakeConversationSession, coach_message: str, ready: bool) -> ConversationCoachResponse:
    answers = _load_answers(session)
    pending = [s for s in _step_sequence(answers) if s not in answers]
    flags = _concern_flags_from_answers(answers)
    return ConversationCoachResponse(
        session_id=session.id,
        status=session.status,
        coach_message=coach_message,
        current_step=None if ready else session.current_step,
        pending_steps=pending,
        captured_fields=sorted(list(answers.keys())),
        concern_flags=flags,
        ready_to_complete=ready,
    )


@router.post("/baseline", response_model=BaselineResponse, status_code=status.HTTP_200_OK)
def upsert_baseline(
    payload: BaselineRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BaselineResponse:
    _require_ai_config(user, db)
    record = _upsert_baseline_record(db, user.id, payload)
    flags = _risk_flags(payload)
    return BaselineResponse(
        baseline_id=record.id,
        user_id=user.id,
        primary_goal=payload.primary_goal,
        focus_areas=_focus_areas(payload),
        risk_flags=flags,
        next_steps=_next_steps(payload, flags),
        suggested_questions=_suggested_questions(payload),
        disclaimer=_disclaimer(),
    )


@router.get("/baseline", response_model=BaselineRequest)
def get_baseline(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> BaselineRequest:
    record = db.query(Baseline).filter(Baseline.user_id == user.id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Baseline not found")
    goals = None
    if record.top_goals_json:
        try:
            parsed = json.loads(record.top_goals_json)
            if isinstance(parsed, list):
                goals = [str(x) for x in parsed if str(x).strip()][:3]
        except Exception:
            goals = None
    return BaselineRequest(
        primary_goal=record.primary_goal,
        top_goals=goals,
        goal_notes=record.goal_notes,
        target_outcome=record.target_outcome,
        timeline=record.timeline,
        biggest_challenge=record.biggest_challenge,
        age_years=record.age_years,
        sex_at_birth=record.sex_at_birth,
        height_text=record.height_text,
        weight=record.weight,
        waist=record.waist,
        systolic_bp=record.systolic_bp,
        diastolic_bp=record.diastolic_bp,
        resting_hr=record.resting_hr,
        sleep_hours=record.sleep_hours,
        activity_level=record.activity_level,
        energy=record.energy,
        mood=record.mood,
        stress=record.stress,
        sleep_quality=record.sleep_quality,
        motivation=record.motivation,
        engagement_style=record.engagement_style,
        nutrition_patterns=record.nutrition_patterns,
        training_history=record.training_history,
        training_experience=record.training_experience,
        equipment_access=record.equipment_access,
        limitations=record.limitations,
        strength_benchmarks=record.strength_benchmarks,
        bedtime=record.bedtime,
        wake_time=record.wake_time,
        energy_pattern=record.energy_pattern,
        health_conditions=record.health_conditions,
        physician_restrictions=record.physician_restrictions,
        supplement_stack=record.supplement_stack,
        lab_markers=record.lab_markers,
        fasting_practices=record.fasting_practices,
        fasting_interest=record.fasting_interest,
        fasting_style=record.fasting_style,
        fasting_experience=record.fasting_experience,
        fasting_reason=record.fasting_reason,
        fasting_flexibility=record.fasting_flexibility,
        recovery_practices=record.recovery_practices,
        medication_details=record.medication_details,
    )


@router.get("/status", response_model=IntakeStatusResponse)
def intake_status(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> IntakeStatusResponse:
    record = db.query(Baseline).filter(Baseline.user_id == user.id).first()
    if not record:
        return IntakeStatusResponse(baseline_completed=False)
    updated_at_iso = record.updated_at.isoformat() if record.updated_at else None
    return IntakeStatusResponse(
        baseline_completed=True,
        baseline_updated_at=updated_at_iso,
        primary_goal=record.primary_goal,
    )


@router.post("/conversation/start", response_model=ConversationCoachResponse)
def start_intake_conversation(
    payload: ConversationStartRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConversationCoachResponse:
    _require_ai_config(user, db)
    session = _active_session(db, user.id)
    if session:
        return _coach_payload(session, _question_for_step(session.current_step, _load_answers(session)), False)
    answers: dict[str, Any] = {}
    if payload.top_goals:
        goals = [str(g).strip() for g in payload.top_goals if str(g).strip()][:3]
        if goals:
            answers["top_goals"] = goals
    if payload.goal_notes and payload.goal_notes.strip():
        answers["goal_notes"] = payload.goal_notes.strip()
    current_step = _next_pending_step(answers, "__start__") or "top_goals"
    session = IntakeConversationSession(
        user_id=user.id,
        status="active",
        current_step=current_step,
        answers_json=json.dumps(answers),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return _coach_payload(session, _question_for_step(session.current_step, answers), False)


@router.post("/conversation/answer", response_model=ConversationCoachResponse)
def answer_intake_conversation(
    payload: ConversationAnswerRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    llm_client: LLMClient = Depends(get_llm_client),
) -> ConversationCoachResponse:
    _require_ai_config(user, db)
    session = (
        db.query(IntakeConversationSession)
        .filter(
            IntakeConversationSession.id == payload.session_id,
            IntakeConversationSession.user_id == user.id,
        )
        .first()
    )
    if not session or session.status != "active":
        raise HTTPException(status_code=404, detail="Active intake conversation not found")
    answers = _load_answers(session)
    step = session.current_step
    try:
        parsed = _coerce_step_answer(step, payload.answer)
        if step == "systolic_bp" and isinstance(parsed, dict):
            answers["systolic_bp"] = parsed["systolic"]
            answers["diastolic_bp"] = parsed["diastolic"]
        else:
            answers[step] = parsed
        step_batch = _batch_for_step(step)
        batch_steps = _batch_steps(step_batch)
        if step in {"top_goals", "age_years", "sex_at_birth", "height_text", "weight", "waist", "systolic_bp", "diastolic_bp", "activity_level"}:
            derived_basics = _extract_basics_batch_values(payload.answer)
            for key in ("age_years", "sex_at_birth", "height_text", "weight", "waist", "systolic_bp", "diastolic_bp", "activity_level"):
                if key not in answers and key in derived_basics and key in batch_steps:
                    try:
                        answers[key] = _coerce_step_answer(key, str(derived_basics[key]))
                    except Exception:
                        continue
        if step in {"target_outcome", "timeline", "biggest_challenge"}:
            derived = _extract_goal_batch_values(payload.answer)
            for key in ("target_outcome", "timeline", "biggest_challenge"):
                if key not in answers and derived.get(key) and key in batch_steps:
                    try:
                        answers[key] = _coerce_step_answer(key, str(derived[key]))
                    except Exception:
                        continue
        if step in {"health_conditions", "medication_details", "supplement_stack", "physician_restrictions", "lab_markers"}:
            derived_health = _extract_health_batch_values(payload.answer)
            for key in ("health_conditions", "medication_details", "supplement_stack", "physician_restrictions", "lab_markers"):
                if key not in answers and derived_health.get(key) and key in batch_steps:
                    try:
                        answers[key] = _coerce_step_answer(key, str(derived_health[key]))
                    except Exception:
                        continue
        if step in {"fasting_interest", "fasting_style", "fasting_experience", "fasting_reason", "fasting_flexibility", "fasting_practices", "recovery_practices", "goal_notes"}:
            derived_fasting = _extract_fasting_batch_values(payload.answer)
            for key in ("fasting_interest", "fasting_style", "fasting_experience", "fasting_reason", "fasting_flexibility", "fasting_practices"):
                if key not in answers and derived_fasting.get(key) and key in batch_steps:
                    try:
                        answers[key] = _coerce_step_answer(key, str(derived_fasting[key]))
                    except Exception:
                        continue
        pending_in_batch = [key for key in batch_steps if key not in answers]
        ai_derived = _ai_parse_batch_values(
            llm_client=llm_client,
            db=db,
            user_id=user.id,
            raw=payload.answer,
            batch=step_batch,
            pending_steps=pending_in_batch,
        )
        for key, val in ai_derived.items():
            if key not in answers:
                answers[key] = val
        # Batch E is optional. If user provided rich context once, avoid repeating the same section.
        if step_batch == "E":
            captured = [
                key
                for key in ("health_conditions", "medication_details", "supplement_stack", "physician_restrictions", "lab_markers")
                if key in answers and str(answers.get(key, "")).strip() and str(answers.get(key, "")).lower() != "unknown"
            ]
            if len(captured) >= 2:
                for key in ("health_conditions", "medication_details", "supplement_stack", "physician_restrictions", "lab_markers"):
                    if key not in answers:
                        answers[key] = "unknown"
        # Batch F is optional. If user provided clear fasting context once, do not repeat the section.
        if step_batch == "F":
            captured = [
                key
                for key in ("fasting_interest", "fasting_style", "fasting_experience", "fasting_reason", "fasting_flexibility", "fasting_practices", "recovery_practices", "goal_notes")
                if key in answers and str(answers.get(key, "")).strip() and str(answers.get(key, "")).lower() != "unknown"
            ]
            if len(captured) >= 2:
                for key in ("fasting_interest", "fasting_style", "fasting_experience", "fasting_reason", "fasting_flexibility", "fasting_practices", "recovery_practices", "goal_notes"):
                    if key not in answers:
                        answers[key] = "unknown"
    except Exception as exc:
        return _coach_payload(session, f"{exc} Please try again.", False)
    next_step = _next_pending_step(answers, step)
    session.answers_json = json.dumps(answers)
    session.concern_flags_csv = ",".join(_concern_flags_from_answers(answers)) or None
    if next_step is None:
        session.current_step = "complete"
        db.commit()
        return _coach_payload(
            session,
            "Great, I captured your baseline context. Finalize intake to save your structured profile.",
            True,
        )
    session.current_step = next_step
    db.commit()
    return _coach_payload(session, _question_for_step(next_step, answers), False)


@router.post("/conversation/complete", response_model=ConversationCompleteResponse)
def complete_intake_conversation(
    payload: ConversationCompleteRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConversationCompleteResponse:
    _require_ai_config(user, db)
    session = (
        db.query(IntakeConversationSession)
        .filter(
            IntakeConversationSession.id == payload.session_id,
            IntakeConversationSession.user_id == user.id,
        )
        .first()
    )
    if not session or session.status != "active":
        raise HTTPException(status_code=404, detail="Active intake conversation not found")
    answers = _normalize_answers_for_baseline(_load_answers(session))
    required = {
        "top_goals",
        "weight",
        "waist",
        "systolic_bp",
        "diastolic_bp",
        "resting_hr",
        "sleep_hours",
        "activity_level",
        "energy",
        "mood",
        "stress",
        "sleep_quality",
        "motivation",
    }
    missing = sorted([item for item in required if item not in answers])
    if missing:
        raise HTTPException(status_code=400, detail=f"Conversation missing required fields: {', '.join(missing)}")
    top_goals = answers.get("top_goals", [])
    primary_goal = str(top_goals[0])[:64] if top_goals else "general_health"
    baseline_payload = BaselineRequest(
        primary_goal=primary_goal,
        top_goals=top_goals,
        goal_notes=answers.get("goal_notes"),
        target_outcome=answers.get("target_outcome"),
        timeline=answers.get("timeline"),
        biggest_challenge=answers.get("biggest_challenge"),
        age_years=answers.get("age_years"),
        sex_at_birth=answers.get("sex_at_birth"),
        height_text=answers.get("height_text"),
        weight=float(answers["weight"]),
        waist=float(answers["waist"]),
        systolic_bp=int(answers["systolic_bp"]),
        diastolic_bp=int(answers["diastolic_bp"]),
        resting_hr=int(answers["resting_hr"]),
        sleep_hours=float(answers["sleep_hours"]),
        activity_level=str(answers["activity_level"]),
        energy=int(answers["energy"]),
        mood=int(answers["mood"]),
        stress=int(answers["stress"]),
        sleep_quality=int(answers["sleep_quality"]),
        motivation=int(answers["motivation"]),
        engagement_style=answers.get("engagement_style"),
        nutrition_patterns=answers.get("nutrition_patterns"),
        training_history=answers.get("training_history"),
        training_experience=answers.get("training_experience"),
        equipment_access=answers.get("equipment_access"),
        limitations=answers.get("limitations"),
        strength_benchmarks=answers.get("strength_benchmarks"),
        bedtime=answers.get("bedtime"),
        wake_time=answers.get("wake_time"),
        energy_pattern=answers.get("energy_pattern"),
        health_conditions=answers.get("health_conditions"),
        physician_restrictions=answers.get("physician_restrictions"),
        supplement_stack=answers.get("supplement_stack"),
        lab_markers=answers.get("lab_markers"),
        fasting_practices=answers.get("fasting_practices"),
        fasting_interest=answers.get("fasting_interest"),
        fasting_style=answers.get("fasting_style"),
        fasting_experience=answers.get("fasting_experience"),
        fasting_reason=answers.get("fasting_reason"),
        fasting_flexibility=answers.get("fasting_flexibility"),
        recovery_practices=answers.get("recovery_practices"),
        medication_details=answers.get("medication_details"),
    )
    record = _upsert_baseline_record(db, user.id, baseline_payload)
    flags = _risk_flags(baseline_payload)
    user_profile_json = _build_user_profile_json(answers, baseline_payload)
    coaching_config_json = _build_coaching_config_json(answers, baseline_payload)
    open_questions = _open_questions(answers)
    session.status = "completed"
    session.coach_summary = (
        f"Top goals: {', '.join(top_goals[:3]) if top_goals else primary_goal}. "
        f"Concern flags: {', '.join(flags) if flags else 'none'}."
    )
    db.commit()
    return ConversationCompleteResponse(
        session_id=session.id,
        baseline_id=record.id,
        user_id=user.id,
        primary_goal=baseline_payload.primary_goal,
        focus_areas=_focus_areas(baseline_payload),
        risk_flags=flags,
        next_steps=_next_steps(baseline_payload, flags),
        suggested_questions=_suggested_questions(baseline_payload),
        disclaimer=_disclaimer(),
        user_profile_json=user_profile_json,
        coaching_config_json=coaching_config_json,
        open_questions=open_questions,
    )
