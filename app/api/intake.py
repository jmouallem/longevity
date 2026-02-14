from enum import Enum
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.db.models import Baseline, User, UserAIConfig
from app.db.session import get_db

router = APIRouter(prefix="/intake", tags=["intake"])


class PrimaryGoal(str, Enum):
    energy = "energy"
    heart_health = "heart_health"
    longevity_optimization = "longevity_optimization"
    weight_loss = "weight_loss"
    mental_clarity = "mental_clarity"


class ActivityLevel(str, Enum):
    sedentary = "sedentary"
    light = "light"
    moderate = "moderate"
    high = "high"
    athlete = "athlete"


class EngagementStyle(str, Enum):
    concise = "concise"
    detailed = "detailed"
    playful = "playful"
    serious = "serious"


class BaselineRequest(BaseModel):
    primary_goal: PrimaryGoal
    weight: float = Field(ge=30, le=350)
    waist: float = Field(ge=40, le=250)
    systolic_bp: int = Field(ge=70, le=240)
    diastolic_bp: int = Field(ge=40, le=150)
    resting_hr: int = Field(ge=30, le=220)
    sleep_hours: float = Field(ge=0, le=16)
    activity_level: ActivityLevel

    energy: int = Field(ge=1, le=10)
    mood: int = Field(ge=1, le=10)
    stress: int = Field(ge=1, le=10)
    sleep_quality: int = Field(ge=1, le=10)
    motivation: int = Field(ge=1, le=10)

    engagement_style: Optional[EngagementStyle] = None
    nutrition_patterns: Optional[str] = Field(default=None, max_length=2000)
    training_history: Optional[str] = Field(default=None, max_length=2000)
    supplement_stack: Optional[str] = Field(default=None, max_length=2000)
    lab_markers: Optional[str] = Field(default=None, max_length=2000)
    fasting_practices: Optional[str] = Field(default=None, max_length=2000)
    recovery_practices: Optional[str] = Field(default=None, max_length=2000)
    medication_details: Optional[str] = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_bp(self):
        if self.diastolic_bp >= self.systolic_bp:
            raise ValueError("diastolic_bp must be lower than systolic_bp")
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


def _goal_focus(goal: PrimaryGoal) -> list[str]:
    mapping = {
        PrimaryGoal.energy: ["sleep quality", "stress load", "daytime movement"],
        PrimaryGoal.heart_health: ["blood pressure", "waist trend", "activity consistency"],
        PrimaryGoal.longevity_optimization: ["sleep", "metabolic markers", "behavior consistency"],
        PrimaryGoal.weight_loss: ["weight trend", "nutrition patterns", "activity consistency"],
        PrimaryGoal.mental_clarity: ["sleep quality", "stress regulation", "training load"],
    }
    return mapping[goal]


def _risk_flags(payload: BaselineRequest) -> list[str]:
    flags: list[str] = []
    if payload.systolic_bp >= 140 or payload.diastolic_bp >= 90:
        flags.append("elevated_bp")
    if payload.waist >= 102:
        flags.append("high_waist")
    if payload.sleep_hours < 6:
        flags.append("low_sleep")
    if payload.stress >= 8:
        flags.append("high_stress")
    return flags


def _focus_areas(payload: BaselineRequest) -> list[str]:
    focus = []
    for topic in _goal_focus(payload.primary_goal):
        focus.append(f"Improve {topic}")
    return focus[:3]


def _next_steps(payload: BaselineRequest, flags: list[str]) -> list[str]:
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


def _suggested_questions(payload: BaselineRequest) -> list[str]:
    goal = payload.primary_goal.value.replace("_", " ")
    tone = "Want" if payload.engagement_style != EngagementStyle.serious else "Would you like"
    return [
        f"{tone} a 7-day plan focused on {goal}?",
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


@router.post("/baseline", response_model=BaselineResponse, status_code=status.HTTP_200_OK)
def upsert_baseline(
    payload: BaselineRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BaselineResponse:
    _require_ai_config(user, db)
    record = db.query(Baseline).filter(Baseline.user_id == user.id).first()
    if not record:
        record = Baseline(user_id=user.id)
        db.add(record)

    record.primary_goal = payload.primary_goal.value
    record.weight = payload.weight
    record.waist = payload.waist
    record.systolic_bp = payload.systolic_bp
    record.diastolic_bp = payload.diastolic_bp
    record.resting_hr = payload.resting_hr
    record.sleep_hours = payload.sleep_hours
    record.activity_level = payload.activity_level.value
    record.energy = payload.energy
    record.mood = payload.mood
    record.stress = payload.stress
    record.sleep_quality = payload.sleep_quality
    record.motivation = payload.motivation
    record.engagement_style = payload.engagement_style.value if payload.engagement_style else None
    record.nutrition_patterns = payload.nutrition_patterns
    record.training_history = payload.training_history
    record.supplement_stack = payload.supplement_stack
    record.lab_markers = payload.lab_markers
    record.fasting_practices = payload.fasting_practices
    record.recovery_practices = payload.recovery_practices
    record.medication_details = payload.medication_details

    db.commit()
    db.refresh(record)

    flags = _risk_flags(payload)
    return BaselineResponse(
        baseline_id=record.id,
        user_id=user.id,
        primary_goal=payload.primary_goal.value,
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

    return BaselineRequest(
        primary_goal=PrimaryGoal(record.primary_goal),
        weight=record.weight,
        waist=record.waist,
        systolic_bp=record.systolic_bp,
        diastolic_bp=record.diastolic_bp,
        resting_hr=record.resting_hr,
        sleep_hours=record.sleep_hours,
        activity_level=ActivityLevel(record.activity_level),
        energy=record.energy,
        mood=record.mood,
        stress=record.stress,
        sleep_quality=record.sleep_quality,
        motivation=record.motivation,
        engagement_style=EngagementStyle(record.engagement_style) if record.engagement_style else None,
        nutrition_patterns=record.nutrition_patterns,
        training_history=record.training_history,
        supplement_stack=record.supplement_stack,
        lab_markers=record.lab_markers,
        fasting_practices=record.fasting_practices,
        recovery_practices=record.recovery_practices,
        medication_details=record.medication_details,
    )
