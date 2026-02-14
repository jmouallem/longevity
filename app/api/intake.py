import json
import re
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.db.models import Baseline, IntakeConversationSession, User, UserAIConfig
from app.db.session import get_db

router = APIRouter(prefix="/intake", tags=["intake"])


class ActivityLevel(str):
    sedentary = "sedentary"
    light = "light"
    moderate = "moderate"
    high = "high"
    athlete = "athlete"


VALID_ACTIVITY = {"sedentary", "light", "moderate", "high", "athlete"}
VALID_ENGAGEMENT = {"concise", "detailed", "playful", "serious"}


class BaselineRequest(BaseModel):
    primary_goal: str = Field(min_length=2, max_length=64)
    top_goals: Optional[list[str]] = None
    goal_notes: Optional[str] = Field(default=None, max_length=2000)
    age_years: Optional[int] = Field(default=None, ge=10, le=120)
    sex_at_birth: Optional[str] = Field(default=None, max_length=32)

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
    supplement_stack: Optional[str] = Field(default=None, max_length=2000)
    lab_markers: Optional[str] = Field(default=None, max_length=2000)
    fasting_practices: Optional[str] = Field(default=None, max_length=2000)
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


BASE_STEPS = [
    "top_goals",
    "age_years",
    "sex_at_birth",
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
]


def _question_for_step(step: str, answers: dict[str, Any]) -> str:
    prompts = {
        "top_goals": "Tell me your top 3 goals right now (comma separated is fine).",
        "age_years": "What is your age in years?",
        "sex_at_birth": "What sex were you assigned at birth? (male/female/intersex/other/prefer_not_to_say)",
        "weight": "What is your current weight in kg?",
        "waist": "What is your waist measurement in cm?",
        "systolic_bp": "What is your systolic blood pressure (top number)?",
        "diastolic_bp": "What is your diastolic blood pressure (bottom number)?",
        "resting_hr": "What is your resting heart rate?",
        "sleep_hours": "How many hours do you usually sleep per night?",
        "activity_level": "How would you describe your activity level? (sedentary/light/moderate/high/athlete)",
        "energy": "On a 1-10 scale, what is your energy level?",
        "mood": "On a 1-10 scale, what is your mood?",
        "stress": "On a 1-10 scale, what is your stress?",
        "sleep_quality": "On a 1-10 scale, how is your sleep quality?",
        "motivation": "On a 1-10 scale, what is your motivation?",
        "probe_high_stress": "I see elevated stress. What are the top stress drivers right now?",
        "probe_low_sleep": "Sleep looks low. What is the main blocker to more sleep?",
        "probe_elevated_bp": "Your blood pressure may need attention. Have you noticed patterns or recent readings over time?",
        "goal_notes": "Any additional context you want me to capture before we finalize baseline?",
    }
    return prompts.get(step, "Please share the next detail.")


def _coerce_step_answer(step: str, raw: str) -> Any:
    value = raw.strip()
    if step == "top_goals":
        goals = [g.strip() for g in value.replace("\n", ",").split(",") if g.strip()]
        if not goals:
            raise ValueError("Please provide at least one goal.")
        return goals[:3]
    if step == "age_years":
        return int(_extract_number(value))
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
    return value


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
    record.age_years = payload.age_years
    record.sex_at_birth = payload.sex_at_birth
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
    record.supplement_stack = payload.supplement_stack
    record.lab_markers = payload.lab_markers
    record.fasting_practices = payload.fasting_practices
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
    steps.append("goal_notes")
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
        age_years=record.age_years,
        sex_at_birth=record.sex_at_birth,
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
        supplement_stack=record.supplement_stack,
        lab_markers=record.lab_markers,
        fasting_practices=record.fasting_practices,
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
    current_step = "top_goals" if "top_goals" not in answers else "age_years"
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
    answers = _load_answers(session)
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
        age_years=answers.get("age_years"),
        sex_at_birth=answers.get("sex_at_birth"),
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
        supplement_stack=answers.get("supplement_stack"),
        lab_markers=answers.get("lab_markers"),
        fasting_practices=answers.get("fasting_practices"),
        recovery_practices=answers.get("recovery_practices"),
        medication_details=answers.get("medication_details"),
    )
    record = _upsert_baseline_record(db, user.id, baseline_payload)
    flags = _risk_flags(baseline_payload)
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
    )
