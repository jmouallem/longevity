import json
import logging
import os
import re
import time
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional, Union

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api import summary as summary_api
from app.api.auth import get_current_user
from app.api.chat_history import get_or_create_chat_thread, persist_chat_turn
from app.core.agent_contracts import render_agent_system_prompt
from app.core.context_builder import build_coaching_context
from app.core.persona import apply_longevity_alchemist_voice
from app.core.safety import (
    detect_urgent_flags,
    emergency_response,
    has_supplement_topic,
    supplement_caution_text,
)
from app.db.models import ConversationSummary, DailyLog, FeedbackEntry, Metric, User
from app.db.session import get_db
from app.services.llm import LLMClient, LLMRequestError, get_llm_client

router = APIRouter(prefix="/coach", tags=["coach"])
logger = logging.getLogger("uvicorn.error")
CACHE_TTL_SECONDS = int(os.getenv("COACH_CACHE_TTL_SECONDS", "75"))
COACH_IMAGE_MAX_BYTES = int(os.getenv("COACH_IMAGE_MAX_BYTES", str(8 * 1024 * 1024)))
_COACH_RESPONSE_CACHE: dict[tuple[int, str, str, bool], tuple[float, Any]] = {}


class CoachMode(str, Enum):
    quick = "quick"
    deep = "deep"


class CoachQuestionRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1000)
    mode: CoachMode = CoachMode.quick
    deep_think: bool = False
    context_hint: Optional[str] = Field(default=None, max_length=120)
    thread_id: Optional[int] = None
    web_search: bool = True


class CoachVoiceRequest(BaseModel):
    transcript: str = Field(min_length=2, max_length=2000)
    mode: CoachMode = CoachMode.quick
    deep_think: bool = False
    context_hint: Optional[str] = Field(default=None, max_length=120)
    thread_id: Optional[int] = None
    web_search: bool = True


class RecommendedAction(BaseModel):
    title: str
    steps: list[str]


class CoachQuestionResponse(BaseModel):
    answer: str
    rationale_bullets: list[str]
    recommended_actions: list[RecommendedAction]
    suggested_questions: list[str]
    safety_flags: list[str]
    disclaimer: str
    thread_id: Optional[int] = None
    agent_trace: list[dict[str, Any]] = Field(default_factory=list)


class DailyCheckinPlanRequest(BaseModel):
    local_hour: Optional[int] = Field(default=None, ge=0, le=23)
    timezone_offset_minutes: Optional[int] = Field(default=None, ge=-840, le=840)
    generate_with_ai: bool = True


class DailyCheckinQuestion(BaseModel):
    key: str
    label: str
    specialist: str
    question: str
    type: str
    min: Optional[float] = None
    max: Optional[float] = None


class DailyCheckinPlanResponse(BaseModel):
    goal_focus: str
    time_bucket: str
    intro: str
    questions: list[DailyCheckinQuestion]


class DailyCheckinAnswerParseRequest(BaseModel):
    key: str = Field(min_length=1, max_length=64)
    question: str = Field(min_length=2, max_length=400)
    answer_text: str = Field(min_length=1, max_length=1200)
    value_type: str = Field(default="bool", min_length=1, max_length=32)
    goal_focus: Optional[str] = Field(default=None, max_length=64)
    time_bucket: Optional[str] = Field(default=None, max_length=64)


class DailyCheckinAnswerParseResponse(BaseModel):
    parsed_bool: Optional[bool] = None
    captured_text: Optional[str] = None
    notes: Optional[str] = None


class DailyCheckinFoodLogRequest(BaseModel):
    entry_text: str = Field(min_length=2, max_length=1200)
    log_date: Optional[date] = None
    local_time_label: Optional[str] = Field(default=None, max_length=64)


class DailyCheckinFoodLogResponse(BaseModel):
    markdown: str


class DailyCheckinStepSummaryRequest(BaseModel):
    key: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=120)
    specialist: str = Field(min_length=1, max_length=120)
    raw_answer: str = Field(min_length=1, max_length=1200)
    parsed_value: Optional[Any] = None
    log_date: Optional[date] = None
    time_bucket: Optional[str] = Field(default=None, max_length=64)
    current_payload: dict[str, Any] = Field(default_factory=dict)
    current_extras: dict[str, Any] = Field(default_factory=dict)


class DailyCheckinStepSummaryResponse(BaseModel):
    markdown: str


class ProactiveCardRequest(BaseModel):
    card_type: str = Field(min_length=3, max_length=24)


class ProactiveCardResponse(BaseModel):
    card_type: str
    markdown: str


def _disclaimer() -> str:
    return "This is coaching guidance, not medical diagnosis."


def _fallback_response(answer: str, safety_flags: Optional[list[str]] = None) -> CoachQuestionResponse:
    return CoachQuestionResponse(
        answer=answer,
        rationale_bullets=[
            "Baseline and recent trends are the strongest inputs for tailored coaching.",
            "Small, consistent changes beat aggressive short-term plans.",
            "We can tighten recommendations once more data is available.",
        ],
        recommended_actions=[
            {
                "title": "Take one low-friction next step",
                "steps": [
                    "Pick one behavior to execute daily for 7 days.",
                    "Log the result at the same time each day.",
                    "Review trend direction before changing plan.",
                ],
            }
        ],
        suggested_questions=[
            "What is the one outcome you want to improve first over the next 14 days?",
            "What single daily metric can you reliably track at the same time each day?",
            "What usually gets in the way of consistency for you during a typical week?",
        ],
        safety_flags=safety_flags or [],
        disclaimer=_disclaimer(),
    )


def _practical_non_llm_response(payload: CoachQuestionRequest, context: dict[str, Any], flag: str) -> CoachQuestionResponse:
    question_lower = payload.question.lower()
    is_supplement = "supplement" in question_lower or has_supplement_topic(payload.question)
    if flag == "llm_rate_limited":
        issue_prefix = "I hit provider limits right now"
    elif flag in {"llm_auth_error", "llm_model_not_found"}:
        issue_prefix = "I could not use your configured AI model for this request"
    else:
        issue_prefix = "I hit a temporary AI service/network issue right now"
    if is_supplement:
        return CoachQuestionResponse(
            answer=(
                f"{issue_prefix}, so here is a safe starter supplement framework you can use immediately. "
                "First, list exact dosages and labels for omega-3, CoQ10, Centrum 50+, B12, and vitamin D. "
                "Then remove overlap risk (multi + single vitamins) before adding anything new."
            ),
            rationale_bullets=[
                "Rate limits prevented a full model-generated plan in this request.",
                "Duplicate nutrients are common when combining a multivitamin with stand-alone supplements.",
                "Dose, timing, and symptom tracking are the highest-value first steps.",
                "Use one change at a time for 7-14 days to attribute effects.",
            ],
            recommended_actions=[
                RecommendedAction(
                    title="Build a clean baseline stack",
                    steps=[
                        "Create one table with supplement name, dose, timing, and reason.",
                        "Mark overlaps from Centrum 50+ against B12 and vitamin D.",
                        "Pause non-essential extras until overlap is clarified.",
                    ],
                ),
                RecommendedAction(
                    title="Run a 2-week response check",
                    steps=[
                        "Keep timing consistent each day.",
                        "Track energy, sleep quality, and GI tolerance daily (1-10).",
                        "If side effects appear, revert to last well-tolerated setup.",
                    ],
                ),
            ],
            suggested_questions=[
                "What are the exact dosages on each bottle (EPA+DHA total, vitamin D IU/form, B12 mcg, CoQ10 mg)?",
                "Are you taking any prescription meds (statin, blood thinners, BP, diabetes, thyroid), or have reflux/anxiety/palpitations?",
                "What are your height, current weight, target weight, and typical daily eating pattern (including alcohol)?",
            ],
            safety_flags=[flag],
            disclaimer=_disclaimer(),
        )

    goal = ((context.get("baseline") or {}).get("primary_goal") or "your goal")
    return CoachQuestionResponse(
        answer=(
            f"{issue_prefix}, but we can still run a practical plan for {goal}. "
            "Use one small daily action this week and track one outcome metric."
        ),
        rationale_bullets=[
            "Rate limits prevented a full model-generated response in this request.",
            "Simple plans with one measurable behavior are easiest to execute.",
            "Weekly review improves adaptation and consistency.",
        ],
        recommended_actions=[
            RecommendedAction(
                title="Run a 7-day micro-plan",
                steps=[
                    "Pick one behavior linked to your goal.",
                    "Pick one metric to track at the same time daily.",
                    "Review trend after 7 days before changing plan.",
                ],
            ),
        ],
        suggested_questions=[
            "What exact behavior are you willing to do daily for the next 7 days?",
            "What metric will you track daily to verify this is working?",
            "What time each day will you complete the check-in so it is realistic and repeatable?",
        ],
        safety_flags=[flag],
        disclaimer=_disclaimer(),
    )


def _safe_list(value: Any, min_items: int, max_items: int, fallback: list[str]) -> list[str]:
    if not isinstance(value, list):
        return fallback
    cleaned = [str(v).strip() for v in value if str(v).strip()]
    if len(cleaned) < min_items:
        return fallback
    return cleaned[:max_items]


def _safe_actions(value: Any) -> list[RecommendedAction]:
    if not isinstance(value, list):
        return []
    actions: list[RecommendedAction] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        steps_raw = item.get("steps", [])
        if not title or not isinstance(steps_raw, list):
            continue
        steps = [str(step).strip() for step in steps_raw if str(step).strip()]
        if not steps:
            continue
        actions.append(RecommendedAction(title=title, steps=steps[:5]))
    return actions[:3]


def _extract_answer_from_json_blob(text: str) -> str:
    candidate = (text or "").strip()
    if not candidate:
        return ""
    if '"answer"' not in candidate:
        return ""
    match = re.search(r'"answer"\s*:\s*"((?:\\.|[^"\\])*)"', candidate, flags=re.DOTALL)
    if not match:
        return ""
    raw_value = match.group(1)
    try:
        return str(json.loads(f"\"{raw_value}\"")).strip()
    except json.JSONDecodeError:
        return raw_value.replace("\\n", "\n").replace('\\"', '"').strip()


def _normalize_answer_text(answer: str) -> str:
    text = (answer or "").strip()
    if not text:
        return text
    extracted = _extract_answer_from_json_blob(text)
    if extracted:
        return extracted
    # If the model echoed a malformed JSON object, hide it and keep only any prefix text.
    if "{" in text and '"answer"' in text:
        return text.split("{", 1)[0].strip() or "I generated a partial response. Please retry."
    return text


def _response_from_raw(raw: dict[str, Any], mode: str) -> CoachQuestionResponse:
    answer = ""
    for key in ("answer", "final_answer", "response", "content", "message", "summary"):
        candidate = str(raw.get(key, "")).strip()
        if candidate:
            answer = candidate
            break
    if not answer:
        answer = (
            "Here is a practical next step: run one conservative 7-day experiment, "
            "track daily response, and adjust based on trend direction."
        )
    answer = _normalize_answer_text(answer)
    rationale_bullets = _safe_list(
        raw.get("rationale_bullets"),
        min_items=3,
        max_items=7,
        fallback=[
            "Your baseline and 7-day trends were used to shape this answer.",
            "Focus on consistency before increasing plan complexity.",
            "A weekly review helps adjust the plan with better signal.",
        ],
    )
    recommended_actions = _safe_actions(raw.get("recommended_actions"))
    if not recommended_actions:
        recommended_actions = _fallback_response("x").recommended_actions
    suggested_questions = _safe_list(
        raw.get("suggested_questions"),
        min_items=3,
        max_items=8,
        fallback=_fallback_response("x").suggested_questions,
    )
    safety_flags = _safe_list(raw.get("safety_flags"), min_items=0, max_items=8, fallback=[])
    return CoachQuestionResponse(
        answer=apply_longevity_alchemist_voice(answer, mode),
        rationale_bullets=rationale_bullets,
        recommended_actions=recommended_actions[:3],
        suggested_questions=suggested_questions,
        safety_flags=safety_flags,
        disclaimer=_disclaimer(),
    )


def _daily_log_focus(context: dict[str, Any], question: str) -> tuple[str, list[str]]:
    baseline = context.get("baseline") or {}
    primary_goal = str(baseline.get("primary_goal") or "").strip()
    top_goals = baseline.get("top_goals") if isinstance(baseline.get("top_goals"), list) else []
    goal_blob = " ".join([primary_goal] + [str(g) for g in top_goals]).lower()
    question_lower = (question or "").lower()

    # Always keep core structured fields, but reorder emphasis by goal/interest.
    fields = ["sleep hours", "energy", "mood", "stress", "training", "nutrition", "short note"]
    focus = "consistency and trend quality"
    if any(k in goal_blob for k in ["energy", "fatigue"]):
        fields = ["sleep hours", "stress", "energy", "mood", "training", "nutrition", "short note"]
        focus = "energy and recovery"
    elif any(k in goal_blob for k in ["weight", "fat loss", "body comp", "metabolic"]):
        fields = ["nutrition", "training", "sleep hours", "energy", "stress", "mood", "short note"]
        focus = "body composition and metabolic consistency"
    elif any(k in goal_blob for k in ["heart", "bp", "blood pressure", "cardio"]):
        fields = ["stress", "sleep hours", "training", "nutrition", "energy", "mood", "short note"]
        focus = "cardiometabolic stability"
    elif any(k in goal_blob for k in ["mental", "clarity", "focus", "cognitive"]):
        fields = ["sleep hours", "mood", "stress", "energy", "training", "nutrition", "short note"]
        focus = "mental clarity and resilience"

    if "supplement" in question_lower:
        focus = f"{focus} and supplement response tracking"
    goal_label = primary_goal or "your goal"
    focus_line = f"For {goal_label}, prioritize logging for {focus}."
    return focus_line, fields


def _apply_daily_log_nudge(
    response: CoachQuestionResponse, context: dict[str, Any], question: str
) -> CoachQuestionResponse:
    summary = context.get("daily_log_summary") or {}
    entries_7d = int(summary.get("entries_7d", 0) or 0)
    if entries_7d >= 4:
        return response

    focus_line, fields = _daily_log_focus(context, question)
    field_text = ", ".join(fields[:-1]) + ", and " + fields[-1]
    nudge = (
        f"Daily logs will make your coaching sharper. {focus_line} "
        f"Log: {field_text}."
    )
    if all(nudge not in item for item in response.rationale_bullets):
        response.rationale_bullets = (response.rationale_bullets[:6] + [nudge])[:7]

    follow_up = (
        f"Can you log daily for the next 7 days for {focus_line.split('For ', 1)[-1].rstrip('.')} "
        f"using: {field_text}?"
    )
    if all(follow_up != item for item in response.suggested_questions):
        response.suggested_questions = (response.suggested_questions + [follow_up])[:8]

    if "Daily logs will make your coaching sharper." not in response.answer:
        response.answer = (
            f"{response.answer}\n\n"
            "### Daily Log Hint\n"
            f"Daily logs will make your coaching sharper. {focus_line} "
            f"Please track: {field_text}."
        )
    return response


def _goal_bucket(context: dict[str, Any]) -> str:
    baseline = context.get("baseline") or {}
    primary_goal = str(baseline.get("primary_goal") or "").lower()
    top_goals = baseline.get("top_goals") if isinstance(baseline.get("top_goals"), list) else []
    blob = " ".join([primary_goal] + [str(g).lower() for g in top_goals])
    if any(k in blob for k in ["weight", "fat", "body comp", "metabolic"]):
        return "weight"
    if any(k in blob for k in ["heart", "bp", "blood pressure", "lipid", "cholesterol", "cardio"]):
        return "cardio"
    if any(k in blob for k in ["energy", "fatigue", "recovery"]):
        return "energy"
    if any(k in blob for k in ["mental", "clarity", "focus", "mood", "stress"]):
        return "clarity"
    return "general"


def _daily_checkin_time_bucket(local_hour: Optional[int]) -> tuple[str, int]:
    hour = int(local_hour) if local_hour is not None else datetime.now().hour
    if 5 <= hour <= 11:
        return "morning", hour
    if 12 <= hour <= 16:
        return "afternoon", hour
    if 17 <= hour <= 21:
        return "evening", hour
    return "late_night", hour


def _daily_checkin_local_date(timezone_offset_minutes: Optional[int]) -> date:
    now_utc = datetime.now(timezone.utc)
    if timezone_offset_minutes is None:
        return now_utc.date()
    return (now_utc - timedelta(minutes=int(timezone_offset_minutes))).date()


def _build_daily_weekly_checkin_context(
    *,
    db: Session,
    user_id: int,
    local_date: date,
    timezone_offset_minutes: Optional[int],
) -> tuple[dict[str, Any], dict[str, Any]]:
    today_row = (
        db.query(DailyLog)
        .filter(DailyLog.user_id == user_id, DailyLog.log_date == local_date)
        .first()
    )
    weekly_rows = (
        db.query(DailyLog)
        .filter(
            DailyLog.user_id == user_id,
            DailyLog.log_date >= (local_date - timedelta(days=6)),
            DailyLog.log_date <= local_date,
        )
        .order_by(DailyLog.log_date.asc())
        .all()
    )
    metric_types = [
        "weight_kg",
        "bp_systolic",
        "bp_diastolic",
        "resting_hr_bpm",
        "sleep_hours",
        "energy_1_10",
        "stress_1_10",
        "mood_1_10",
    ]
    offset_min = int(timezone_offset_minutes or 0)
    # Convert local-day boundaries to UTC for metric querying.
    start_dt = (
        datetime.combine(local_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        + timedelta(minutes=offset_min)
    )
    end_dt = (
        datetime.combine(local_date, datetime.max.time()).replace(tzinfo=timezone.utc)
        + timedelta(minutes=offset_min)
    )
    today_metrics = (
        db.query(Metric)
        .filter(
            Metric.user_id == user_id,
            Metric.metric_type.in_(metric_types),
            Metric.taken_at >= start_dt,
            Metric.taken_at <= end_dt,
        )
        .order_by(Metric.taken_at.asc())
        .all()
    )
    by_metric: dict[str, list[float]] = {}
    for m in today_metrics:
        by_metric.setdefault(m.metric_type, []).append(float(m.value_num))

    parsed_checkin: dict[str, Any] = {}
    if today_row and today_row.checkin_payload_json:
        try:
            loaded = json.loads(today_row.checkin_payload_json)
            if isinstance(loaded, dict):
                parsed_checkin = loaded
        except json.JSONDecodeError:
            parsed_checkin = {}

    answered_keys = set()
    if isinstance(parsed_checkin.get("answers"), dict):
        answered_keys = {str(k) for k in parsed_checkin["answers"].keys() if str(k).strip()}

    captured_keys = set()
    if today_row and today_row.sleep_hours is not None:
        captured_keys.add("sleep_hours")
    if today_row and today_row.energy is not None:
        captured_keys.add("energy")
    if today_row and today_row.mood is not None:
        captured_keys.add("mood")
    if today_row and today_row.stress is not None:
        captured_keys.add("stress")
    if today_row and today_row.training_done:
        captured_keys.add("training_done")
    if today_row and today_row.nutrition_on_plan:
        captured_keys.add("nutrition_on_plan")
    if by_metric.get("weight_kg"):
        captured_keys.add("weight_kg")
    if by_metric.get("bp_systolic") or by_metric.get("bp_diastolic"):
        captured_keys.add("bp")
    if by_metric.get("resting_hr_bpm"):
        captured_keys.add("resting_hr_bpm")
    if "meds_taken" in answered_keys:
        captured_keys.add("meds_taken")
    if "hydration_progress" in answered_keys:
        captured_keys.add("hydration_progress")

    def _avg(values: list[Optional[float]]) -> Optional[float]:
        numbers = [float(v) for v in values if v is not None]
        if not numbers:
            return None
        return round(sum(numbers) / len(numbers), 2)

    weekly_summary = {
        "entries": len(weekly_rows),
        "avg_sleep_hours": _avg([row.sleep_hours for row in weekly_rows]),
        "avg_energy": _avg([float(row.energy) for row in weekly_rows]),
        "avg_mood": _avg([float(row.mood) for row in weekly_rows]),
        "avg_stress": _avg([float(row.stress) for row in weekly_rows]),
        "training_days": sum(1 for row in weekly_rows if row.training_done),
        "nutrition_logged_days": sum(1 for row in weekly_rows if row.nutrition_on_plan),
    }
    daily_summary = {
        "log_date": local_date.isoformat(),
        "daily_log_exists": bool(today_row),
        "captured_keys": sorted(captured_keys),
        "answered_keys": sorted(answered_keys),
        "today_log": {
            "sleep_hours": (today_row.sleep_hours if today_row else None),
            "energy": (today_row.energy if today_row else None),
            "mood": (today_row.mood if today_row else None),
            "stress": (today_row.stress if today_row else None),
            "training_done": (bool(today_row.training_done) if today_row else False),
            "nutrition_on_plan": (bool(today_row.nutrition_on_plan) if today_row else False),
        },
        "today_metrics": {
            "weight_kg": (by_metric.get("weight_kg") or [None])[-1],
            "bp_systolic": (by_metric.get("bp_systolic") or [None])[-1],
            "bp_diastolic": (by_metric.get("bp_diastolic") or [None])[-1],
            "resting_hr_bpm": (by_metric.get("resting_hr_bpm") or [None])[-1],
        },
        "checkin_payload": parsed_checkin,
    }
    return daily_summary, weekly_summary


def _daily_checkin_specialist_plan(
    *,
    context: dict[str, Any],
    local_hour: Optional[int],
    daily_summary: dict[str, Any],
    weekly_summary: dict[str, Any],
) -> DailyCheckinPlanResponse:
    bucket, hour = _daily_checkin_time_bucket(local_hour)
    goal_focus = _goal_bucket(context)
    baseline = context.get("baseline") or {}
    primary_goal = str(baseline.get("primary_goal") or "").strip() or "your current goal"
    captured_keys = {str(k) for k in (daily_summary.get("captured_keys") or [])}
    answered_keys = {str(k) for k in (daily_summary.get("answered_keys") or [])}
    has_meds = bool(str(baseline.get("medication_details") or "").strip()) and str(
        baseline.get("medication_details")
    ).lower() != "unknown"

    def _needs(key: str) -> bool:
        return key not in captured_keys and key not in answered_keys

    proposals: dict[str, DailyCheckinQuestion] = {}

    if _needs("sleep_hours"):
        proposals["sleep_hours"] = DailyCheckinQuestion(
            key="sleep_hours",
            label="Sleep Hours",
            specialist="Sleep Expert",
            question="How many total hours did you sleep in your most recent sleep period?",
            type="float",
            min=0,
            max=16,
        )
    if _needs("energy"):
        proposals["energy"] = DailyCheckinQuestion(
            key="energy",
            label="Energy",
            specialist="Recovery & Stress Regulator",
            question=f"What is your {bucket.replace('_', ' ')} energy right now (1-10)?",
            type="int",
            min=1,
            max=10,
        )
    if _needs("mood"):
        proposals["mood"] = DailyCheckinQuestion(
            key="mood",
            label="Mood",
            specialist="Behavior Architect",
            question=f"What is your {bucket.replace('_', ' ')} mood right now (1-10)?",
            type="int",
            min=1,
            max=10,
        )
    if _needs("stress"):
        proposals["stress"] = DailyCheckinQuestion(
            key="stress",
            label="Stress",
            specialist="Recovery & Stress Regulator",
            question=f"What is your {bucket.replace('_', ' ')} stress load right now (1-10)?",
            type="int",
            min=1,
            max=10,
        )
    if _needs("training_done"):
        proposals["training_done"] = DailyCheckinQuestion(
            key="training_done",
            label="Training Done",
            specialist="Movement Coach",
            question=(
                "Did you complete training yet today? (yes/no). "
                "If yes, include what you did and duration."
            ),
            type="bool",
        )
    if _needs("nutrition_on_plan"):
        proposals["nutrition_on_plan"] = DailyCheckinQuestion(
            key="nutrition_on_plan",
            label="Food Logged",
            specialist="Nutritionist",
            question=(
                "Did you log what you ate so far today? (yes/no). "
                "If yes, include foods/portions. If no, include what you ate and whether you want to log details now or later."
            ),
            type="bool",
        )
    if _needs("hydration_progress"):
        proposals["hydration_progress"] = DailyCheckinQuestion(
            key="hydration_progress",
            label="Hydration",
            specialist="Recovery & Stress Regulator",
            question=(
                "How much water/fluids have you had so far today (cups or ml), and what is your target for today?"
            ),
            type="text",
        )
    if has_meds and _needs("meds_taken"):
        time_hint = "morning meds" if bucket in {"morning", "afternoon"} else "evening meds"
        proposals["meds_taken"] = DailyCheckinQuestion(
            key="meds_taken",
            label="Medication Check",
            specialist="Safety Clinician",
            question=(
                f"Which prescribed {time_hint} have you taken today, and at what time? "
                "If not yet, say when you plan to take them."
            ),
            type="text",
        )
    if _needs("weight_kg") and bucket in {"morning", "afternoon"}:
        proposals["weight_kg"] = DailyCheckinQuestion(
            key="weight_kg",
            label="Weight",
            specialist="Cardiometabolic Strategist",
            question="What was your latest body weight today? (kg or lb)",
            type="weight",
        )
    if _needs("bp") and goal_focus in {"cardio", "weight", "general"}:
        proposals["bp"] = DailyCheckinQuestion(
            key="bp",
            label="Blood Pressure",
            specialist="Cardiometabolic Strategist",
            question="If available, share your latest blood-pressure reading today (for example 122/82).",
            type="bp",
        )
    if _needs("resting_hr_bpm") and goal_focus in {"cardio", "energy", "general"}:
        proposals["resting_hr_bpm"] = DailyCheckinQuestion(
            key="resting_hr_bpm",
            label="Resting HR",
            specialist="Cardiometabolic Strategist",
            question="If available, share your latest resting heart rate today (bpm).",
            type="int",
            min=35,
            max=180,
        )
    if _needs("notes"):
        proposals["notes"] = DailyCheckinQuestion(
            key="notes",
            label="Goal Strategist Note",
            specialist="Goal Strategist",
            question=(
                "What is the biggest blocker or win from today that impacts your weekly goal progression?"
            ),
            type="text",
        )
    proposals["tracked_signals"] = DailyCheckinQuestion(
        key="tracked_signals",
        label="Signals Logged",
        specialist="Orchestrator",
        question=(
            "What else did you track today that should influence coaching right now "
            "(for example: meals, hydration, meds, sleep timing, symptoms, workout details)?"
        ),
        type="text",
    )

    preferred_order = {
        "weight": [
            "weight_kg",
            "nutrition_on_plan",
            "training_done",
            "hydration_progress",
            "sleep_hours",
            "energy",
            "stress",
            "mood",
            "bp",
            "resting_hr_bpm",
            "meds_taken",
            "tracked_signals",
            "notes",
        ],
        "cardio": [
            "bp",
            "resting_hr_bpm",
            "meds_taken",
            "hydration_progress",
            "sleep_hours",
            "stress",
            "energy",
            "training_done",
            "nutrition_on_plan",
            "weight_kg",
            "tracked_signals",
            "notes",
        ],
        "energy": [
            "sleep_hours",
            "energy",
            "stress",
            "mood",
            "hydration_progress",
            "nutrition_on_plan",
            "training_done",
            "resting_hr_bpm",
            "meds_taken",
            "tracked_signals",
            "notes",
        ],
        "clarity": [
            "sleep_hours",
            "stress",
            "mood",
            "energy",
            "hydration_progress",
            "nutrition_on_plan",
            "training_done",
            "tracked_signals",
            "notes",
        ],
    }.get(goal_focus, [
        "sleep_hours",
        "energy",
        "stress",
        "mood",
        "training_done",
        "nutrition_on_plan",
        "hydration_progress",
        "bp",
        "resting_hr_bpm",
        "meds_taken",
        "weight_kg",
        "tracked_signals",
        "notes",
    ])

    ordered = [proposals[k] for k in preferred_order if k in proposals][:12]
    if len(ordered) < 4:
        ordered.extend(
            q for _, q in proposals.items() if q.key not in {x.key for x in ordered}
        )
        ordered = ordered[:8]
    intro = (
        f"{bucket.replace('_', ' ').title()} check-in (hour {hour}) aligned to {primary_goal}. "
        f"Weekly context: {weekly_summary.get('entries', 0)} logs in last 7 days."
    )
    return DailyCheckinPlanResponse(
        goal_focus=goal_focus,
        time_bucket=bucket,
        intro=intro,
        questions=ordered,
    )


def _daily_checkin_plan_prompt(
    *,
    context: dict[str, Any],
    fallback: DailyCheckinPlanResponse,
    local_hour: Optional[int],
    daily_summary: dict[str, Any],
    weekly_summary: dict[str, Any],
) -> str:
    body = {
        "task": "Generate a dynamic daily check-in plan from specialist proposals orchestrated into one flow.",
        "context": context,
        "time_context": {
            "local_hour": local_hour,
            "time_bucket": fallback.time_bucket,
        },
        "daily_summary": daily_summary,
        "weekly_summary": weekly_summary,
        "goal_focus": fallback.goal_focus,
        "constraints": {
            "required_keys": ["goal_focus", "time_bucket", "intro", "questions"],
            "question_schema": {
                "key": "short stable key",
                "label": "short label",
                "specialist": "one of Nutritionist, Sleep Expert, Movement Coach, Supplement Auditor, Safety Clinician, Cardiometabolic Strategist, Goal Strategist, Recovery & Stress Regulator, Behavior Architect, Orchestrator",
                "question": "plain-language question aligned to user goals/objectives, actual time of day, and today's/weekly data. For bool items, ask yes/no and request detail/value in same question.",
                "type": "one of float,int,bool,signals,text,weight,bp",
                "min": "optional for float/int",
                "max": "optional for float/int",
            },
            "workflow": [
                "First reason as each specialist would propose a check-in item for this user/time.",
                "Then orchestrator selects 6-10 high-value items for right now.",
                "Do not ask for data already captured today (daily_summary.captured_keys or daily_summary.answered_keys).",
                "No fixed core fields; choose dynamic fields based on user goals/objectives and recent trends.",
            ],
            "question_count": "6-10",
            "safety": "No diagnosis. Supportive, non-shaming tone.",
        },
        "output_rules": {
            "return_json_only": True,
            "no_markdown": True,
        },
    }
    return json.dumps(body, separators=(",", ":"))


def _coerce_daily_checkin_questions(raw_questions: Any) -> list[DailyCheckinQuestion]:
    if not isinstance(raw_questions, list):
        return []
    allowed_types = {"float", "int", "bool", "signals", "text", "weight", "bp"}
    out: list[DailyCheckinQuestion] = []
    seen_keys: set[str] = set()
    for item in raw_questions:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key", "")).strip()
        label = str(item.get("label", "")).strip() or key
        specialist = str(item.get("specialist", "")).strip() or "Coach"
        question = str(item.get("question", "")).strip()
        qtype = str(item.get("type", "")).strip().lower()
        if not key or key in seen_keys or not question or qtype not in allowed_types:
            continue
        min_v = item.get("min")
        max_v = item.get("max")
        try:
            min_num = float(min_v) if min_v is not None else None
        except Exception:
            min_num = None
        try:
            max_num = float(max_v) if max_v is not None else None
        except Exception:
            max_num = None
        out.append(
            DailyCheckinQuestion(
                key=key,
                label=label,
                specialist=specialist,
                question=question,
                type=qtype,
                min=min_num,
                max=max_num,
            )
        )
        seen_keys.add(key)
    return out


def _merge_ai_daily_checkin_plan(
    fallback: DailyCheckinPlanResponse, raw: dict[str, Any]
) -> DailyCheckinPlanResponse:
    if not isinstance(raw, dict):
        return fallback
    goal_focus = str(raw.get("goal_focus", "")).strip() or fallback.goal_focus
    time_bucket = str(raw.get("time_bucket", "")).strip() or fallback.time_bucket
    intro = str(raw.get("intro", "")).strip() or fallback.intro
    questions = _coerce_daily_checkin_questions(raw.get("questions"))
    if len(questions) < 4:
        return fallback
    return DailyCheckinPlanResponse(
        goal_focus=goal_focus,
        time_bucket=time_bucket,
        intro=intro,
        questions=questions[:12],
    )


def _suppress_completed_checkin_questions(
    plan: DailyCheckinPlanResponse, daily_summary: dict[str, Any]
) -> DailyCheckinPlanResponse:
    captured = {str(k) for k in (daily_summary.get("captured_keys") or [])}
    answered = {str(k) for k in (daily_summary.get("answered_keys") or [])}
    skip = captured.union(answered)
    if not skip:
        return plan
    filtered = [q for q in plan.questions if q.key not in skip]
    return DailyCheckinPlanResponse(
        goal_focus=plan.goal_focus,
        time_bucket=plan.time_bucket,
        intro=plan.intro,
        questions=filtered,
    )


def _apply_proactive_success_guidance(response: CoachQuestionResponse, context: dict[str, Any]) -> CoachQuestionResponse:
    daily = context.get("daily_log_summary") or {}
    metrics = context.get("metrics_7d_summary") or {}
    recent = context.get("recent_conversations") or []
    bucket = _goal_bucket(context)

    if bucket == "weight":
        checkpoint = "7-day checkpoint: keep nutrition and training adherence above 80% for this week."
        pivot = "Pivot trigger: if weight trend stalls for 14 days, adjust calories by 100-150/day or add Zone 2 volume."
        metric_focus = "weight_kg"
    elif bucket == "cardio":
        checkpoint = "7-day checkpoint: collect a stable BP trend (same time daily) and keep stress/sleep consistent."
        pivot = "Pivot trigger: if BP trend does not improve over 2 weeks, shift priority to recovery + sodium/stress controls."
        metric_focus = "bp_systolic"
    elif bucket == "energy":
        checkpoint = "7-day checkpoint: anchor wake time and track sleep-hours + energy daily."
        pivot = "Pivot trigger: if energy stays low for 7 days, prioritize sleep/recovery before adding workload."
        metric_focus = "energy_1_10"
    elif bucket == "clarity":
        checkpoint = "7-day checkpoint: keep sleep timing stable and reduce stress load spikes."
        pivot = "Pivot trigger: if clarity/mood trend does not improve in 10-14 days, simplify plan and reduce cognitive friction."
        metric_focus = "mood_1_10"
    else:
        checkpoint = "7-day checkpoint: execute one high-leverage behavior daily and log results at a fixed time."
        pivot = "Pivot trigger: if consistency drops below 70% for 2 weeks, reduce plan complexity and reset to one core behavior."
        metric_focus = "sleep_hours"

    metric_latest = ((metrics.get(metric_focus) or {}).get("latest") if isinstance(metrics, dict) else None)
    metric_line = f"Current signal: {metric_focus} latest={metric_latest}." if metric_latest is not None else None
    conv_line = None
    if recent:
        conv_line = "History-aware note: recent conversations were used to keep guidance consistent with your current direction."
    log_line = f"Logging momentum: {int(daily.get('entries_7d', 0) or 0)} entries in the last 7 days."

    block_lines = [
        "### Proactive Success Path",
        checkpoint,
        pivot,
        log_line,
    ]
    if metric_line:
        block_lines.append(metric_line)
    if conv_line:
        block_lines.append(conv_line)
    proactive_block = "\n".join(block_lines)
    if "### Proactive Success Path" not in response.answer:
        response.answer = f"{response.answer}\n\n{proactive_block}"

    proactive_q = "Want me to set your next weekly checkpoint and auto-adjust triggers from your trend data?"
    if all(proactive_q != item for item in response.suggested_questions):
        response.suggested_questions = (response.suggested_questions + [proactive_q])[:8]

    proactive_rationale = "Guidance is proactive: targets, checkpoints, and pivot triggers use your recent data/history."
    if all(proactive_rationale != item for item in response.rationale_bullets):
        response.rationale_bullets = (response.rationale_bullets[:6] + [proactive_rationale])[:7]
    return response


@router.post("/daily-checkin-plan", response_model=DailyCheckinPlanResponse, status_code=status.HTTP_200_OK)
def get_daily_checkin_plan(
    payload: DailyCheckinPlanRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    llm_client: LLMClient = Depends(get_llm_client),
) -> DailyCheckinPlanResponse:
    context = build_coaching_context(db=db, user_id=user.id)
    local_date = _daily_checkin_local_date(payload.timezone_offset_minutes)
    daily_summary, weekly_summary = _build_daily_weekly_checkin_context(
        db=db,
        user_id=user.id,
        local_date=local_date,
        timezone_offset_minutes=payload.timezone_offset_minutes,
    )
    fallback = _daily_checkin_specialist_plan(
        context=context,
        local_hour=payload.local_hour,
        daily_summary=daily_summary,
        weekly_summary=weekly_summary,
    )
    fallback = _suppress_completed_checkin_questions(fallback, daily_summary)
    if not payload.generate_with_ai:
        return fallback
    try:
        raw = llm_client.generate_json(
            db=db,
            user_id=user.id,
            prompt=_daily_checkin_plan_prompt(
                context=context,
                fallback=fallback,
                local_hour=payload.local_hour,
                daily_summary=daily_summary,
                weekly_summary=weekly_summary,
            ),
            task_type="utility",
            allow_web_search=False,
        )
        merged = _merge_ai_daily_checkin_plan(fallback, raw)
        return _suppress_completed_checkin_questions(merged, daily_summary)
    except Exception:
        return fallback


def _daily_checkin_answer_parse_prompt(payload: DailyCheckinAnswerParseRequest) -> str:
    body = {
        "task": "Parse a daily check-in free-text answer into structured fields.",
        "context": {
            "key": payload.key,
            "value_type": payload.value_type,
            "question": payload.question,
            "goal_focus": payload.goal_focus or "general",
            "time_bucket": payload.time_bucket or "unknown",
        },
        "input": {
            "answer_text": payload.answer_text,
        },
        "output_schema": {
            "parsed_bool": "boolean or null; infer yes/no intent for bool questions even when mixed with details",
            "captured_text": "short extracted details from answer_text (for logging), or null",
            "notes": "short parser note, or null",
        },
        "rules": [
            "If user provides concrete details (for example meals, meds, measurements), preserve them in captured_text.",
            "For key=nutrition_on_plan: if user says no but provides meal details, parsed_bool should be false (truthful) and captured_text should include the meal log.",
            "Return strict JSON only.",
        ],
    }
    return json.dumps(body, separators=(",", ":"))


def _heuristic_parse_daily_checkin_answer(payload: DailyCheckinAnswerParseRequest) -> DailyCheckinAnswerParseResponse:
    text = str(payload.answer_text or "").strip()
    if not text:
        return DailyCheckinAnswerParseResponse()
    lower = text.lower()
    yes_terms = (" yes", "y ", "yeah", "yep", "done", "completed", "logged", "took", "did")
    no_terms = (" no", "n ", "not yet", "didn't", "didnt", "haven't", "have not", "missed")
    parsed_bool: Optional[bool] = None
    if payload.value_type == "bool":
        if any(term in f" {lower} " for term in no_terms):
            parsed_bool = False
        if parsed_bool is None and any(term in f" {lower} " for term in yes_terms):
            parsed_bool = True
        if parsed_bool is None:
            # If no explicit yes/no but user gave concrete data, treat as affirmative capture.
            has_number = bool(re.search(r"\d", lower))
            has_food = any(word in lower for word in ("ate", "meal", "breakfast", "lunch", "dinner", "snack", "pizza"))
            has_measure = any(word in lower for word in ("bp", "blood pressure", "hr", "heart rate", "weight", "kg", "lb"))
            if has_number or has_food or has_measure:
                parsed_bool = True
    captured_text = text[:600]
    return DailyCheckinAnswerParseResponse(parsed_bool=parsed_bool, captured_text=captured_text, notes="heuristic")


@router.post(
    "/daily-checkin/parse-answer",
    response_model=DailyCheckinAnswerParseResponse,
    status_code=status.HTTP_200_OK,
)
def parse_daily_checkin_answer(
    payload: DailyCheckinAnswerParseRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    llm_client: LLMClient = Depends(get_llm_client),
) -> DailyCheckinAnswerParseResponse:
    # Use utility model for low-cost extraction from free-text check-in responses.
    try:
        raw = llm_client.generate_json(
            db=db,
            user_id=user.id,
            prompt=_daily_checkin_answer_parse_prompt(payload),
            task_type="utility",
            allow_web_search=False,
            system_instruction=(
                "Return strict JSON only with keys: parsed_bool, captured_text, notes. "
                "No markdown, no extra keys."
            ),
        )
        parsed_bool = raw.get("parsed_bool")
        if parsed_bool not in (True, False, None):
            parsed_bool = None
        captured = raw.get("captured_text")
        if captured is not None:
            captured = str(captured).strip()[:600] or None
        notes = raw.get("notes")
        if notes is not None:
            notes = str(notes).strip()[:200] or None
        ai_result = DailyCheckinAnswerParseResponse(
            parsed_bool=parsed_bool,
            captured_text=captured,
            notes=notes,
        )
        if ai_result.parsed_bool is None:
            heuristic = _heuristic_parse_daily_checkin_answer(payload)
            if heuristic.parsed_bool is not None:
                return heuristic
        if not ai_result.captured_text:
            heuristic = _heuristic_parse_daily_checkin_answer(payload)
            if heuristic.captured_text:
                ai_result.captured_text = heuristic.captured_text
        return ai_result
    except Exception:
        return _heuristic_parse_daily_checkin_answer(payload)


def _daily_food_log_prompt(
    *,
    entry_text: str,
    goal_focus: str,
    primary_goal: str,
    log_date: date,
    local_time_label: str,
    prior_notes: str,
    prior_daily: dict[str, Any],
) -> str:
    body = {
        "task": "Convert a user food check-in into a concise coaching markdown log.",
        "context": {
            "goal_focus": goal_focus,
            "primary_goal": primary_goal or "general health",
            "log_date": str(log_date),
            "local_time_label": local_time_label or "unspecified",
            "prior_notes": prior_notes[:600],
            "prior_daily_log": prior_daily,
        },
        "input": {
            "entry_text": entry_text,
        },
        "output_schema": {
            "title_line": "short emoji title, e.g. '🍽️ Logged your meal'",
            "meal_heading": "one line heading",
            "items": ["bullet items"],
            "estimated_nutrition": {
                "calories": "string or null",
                "protein_g": "string or null",
                "carbs_g": "string or null",
                "fat_g": "string or null",
                "hydration_ml": "string or null",
            },
            "daily_progress": {
                "training_done": "yes/no/unknown",
                "nutrition_logged": "yes/no/unknown",
                "sleep_hours": "string or unknown",
                "energy": "string or unknown",
                "stress": "string or unknown",
            },
            "insights": ["2-4 short bullets"],
            "follow_up_question": "single coaching follow-up question",
        },
        "constraints": [
            "Use practical, supportive tone.",
            "Do not diagnose.",
            "Return strict JSON only.",
        ],
    }
    return json.dumps(body, separators=(",", ":"))


def _format_daily_food_log_markdown(
    payload: DailyCheckinFoodLogRequest,
    parsed: dict[str, Any],
    prior_daily: dict[str, Any],
) -> str:
    title = str(parsed.get("title_line") or "🍽️ Logged your meal").strip()
    heading = str(parsed.get("meal_heading") or f"Meal – {payload.local_time_label or 'today'}").strip()
    items = parsed.get("items") if isinstance(parsed.get("items"), list) else []
    items = [str(x).strip() for x in items if str(x).strip()][:8]
    est = parsed.get("estimated_nutrition") if isinstance(parsed.get("estimated_nutrition"), dict) else {}
    progress = parsed.get("daily_progress") if isinstance(parsed.get("daily_progress"), dict) else {}
    insights = parsed.get("insights") if isinstance(parsed.get("insights"), list) else []
    insights = [str(x).strip() for x in insights if str(x).strip()][:4]
    follow_up = str(parsed.get("follow_up_question") or "Would you like me to generate your next-step plan for today?").strip()

    # Fill progress defaults from existing daily log.
    if not progress:
        progress = {
            "training_done": "yes" if prior_daily.get("training_done") else "no",
            "nutrition_logged": "yes" if prior_daily.get("nutrition_on_plan") else "no",
            "sleep_hours": str(prior_daily.get("sleep_hours", "unknown")),
            "energy": str(prior_daily.get("energy", "unknown")),
            "stress": str(prior_daily.get("stress", "unknown")),
        }

    md: list[str] = []
    md.append(title)
    md.append("")
    md.append(f"### {heading}")
    md.append("")
    if items:
        md.append("Items:")
        md.extend([f"- {x}" for x in items])
        md.append("")
    if est:
        md.append("Estimated Nutrition:")
        calories = est.get("calories")
        protein = est.get("protein_g")
        carbs = est.get("carbs_g")
        fat = est.get("fat_g")
        hydration = est.get("hydration_ml")
        if calories:
            md.append(f"- Calories: {calories}")
        if protein:
            md.append(f"- Protein: {protein}")
        if carbs:
            md.append(f"- Carbs: {carbs}")
        if fat:
            md.append(f"- Fat: {fat}")
        if hydration:
            md.append(f"- Hydration: {hydration}")
        md.append("")

    md.append("Daily Progress:")
    md.append(f"- Training done: {progress.get('training_done', 'unknown')}")
    md.append(f"- Nutrition logged: {progress.get('nutrition_logged', 'unknown')}")
    md.append(f"- Sleep hours: {progress.get('sleep_hours', 'unknown')}")
    md.append(f"- Energy: {progress.get('energy', 'unknown')}")
    md.append(f"- Stress: {progress.get('stress', 'unknown')}")
    md.append("")
    if insights:
        md.append("Summary Insight:")
        md.extend([f"- {x}" for x in insights])
        md.append("")
    md.append(follow_up)
    return "\n".join(md).strip()


def _daily_step_summary_prompt(
    *,
    payload: DailyCheckinStepSummaryRequest,
    goal_focus: str,
    primary_goal: str,
    prior_daily: dict[str, Any],
) -> str:
    body = {
        "task": "Create a concise coaching check-in update after a single logged user entry.",
        "context": {
            "goal_focus": goal_focus,
            "primary_goal": primary_goal or "general health",
            "time_bucket": payload.time_bucket or "unknown",
            "log_date": str(payload.log_date or datetime.now(timezone.utc).date()),
            "step": {
                "key": payload.key,
                "label": payload.label,
                "specialist": payload.specialist,
                "raw_answer": payload.raw_answer,
                "parsed_value": payload.parsed_value,
            },
            "current_payload": payload.current_payload,
            "current_extras": payload.current_extras,
            "prior_daily": prior_daily,
        },
        "output_schema": {
            "logged_line": "short logged confirmation line with units/time if available",
            "updated_status": ["2-5 bullets showing progress toward user's goal/objectives"],
            "insight": "short coaching insight specific to this log item",
            "guidance": ["2-4 practical next guidance bullets"],
            "checklist": ["2-4 checklist lines with done/open markers when relevant"],
            "follow_up": "one concise follow-up prompt",
        },
        "constraints": [
            "Use readable markdown sections.",
            "Be specific to the user goal/objective and this log item.",
            "Do not diagnose.",
            "Return strict JSON only.",
        ],
    }
    return json.dumps(body, separators=(",", ":"))


def _format_daily_step_summary_markdown(
    payload: DailyCheckinStepSummaryRequest,
    raw: dict[str, Any],
    goal_label: str,
) -> str:
    logged_line = str(raw.get("logged_line") or f"Logged: {payload.label}").strip()
    status = raw.get("updated_status") if isinstance(raw.get("updated_status"), list) else []
    status = [str(x).strip() for x in status if str(x).strip()][:6]
    insight = str(raw.get("insight") or "Progress logged; keep consistency with today's plan.").strip()
    guidance = raw.get("guidance") if isinstance(raw.get("guidance"), list) else []
    guidance = [str(x).strip() for x in guidance if str(x).strip()][:5]
    checklist = raw.get("checklist") if isinstance(raw.get("checklist"), list) else []
    checklist = [str(x).strip() for x in checklist if str(x).strip()][:5]
    follow_up = str(raw.get("follow_up") or "Ready for the next check-in item?").strip()

    md: list[str] = []
    md.append("## Logged Update")
    md.append(logged_line)
    md.append("")
    md.append("## Goal Progress Snapshot")
    md.append(f"- Primary goal: {goal_label}")
    if status:
        md.extend([f"- {x}" for x in status])
    md.append("")
    md.append("## Coach Insight")
    md.append(insight)
    md.append("")
    if guidance:
        md.append("## Next Guidance")
        md.extend([f"- {x}" for x in guidance])
        md.append("")
    if checklist:
        md.append("## Checklist")
        md.extend([f"- {x}" for x in checklist])
        md.append("")
    md.append(follow_up)
    return "\n".join(md).strip()


@router.post(
    "/daily-checkin/food-log-summary",
    response_model=DailyCheckinFoodLogResponse,
    status_code=status.HTTP_200_OK,
)
def daily_checkin_food_log_summary(
    payload: DailyCheckinFoodLogRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    llm_client: LLMClient = Depends(get_llm_client),
) -> DailyCheckinFoodLogResponse:
    log_date = payload.log_date or datetime.now(timezone.utc).date()
    row = (
        db.query(DailyLog)
        .filter(DailyLog.user_id == user.id, DailyLog.log_date == log_date)
        .first()
    )
    baseline = build_coaching_context(db=db, user_id=user.id).get("baseline") or {}
    prior_daily = {
        "sleep_hours": row.sleep_hours if row else None,
        "energy": row.energy if row else None,
        "mood": row.mood if row else None,
        "stress": row.stress if row else None,
        "training_done": bool(row.training_done) if row else False,
        "nutrition_on_plan": bool(row.nutrition_on_plan) if row else False,
    }
    prior_notes = str(row.notes or "") if row and row.notes else ""
    goal_focus = _goal_bucket({"baseline": baseline})
    primary_goal = str(baseline.get("primary_goal") or "")
    local_time = str(payload.local_time_label or "")
    try:
        raw = llm_client.generate_json(
            db=db,
            user_id=user.id,
            prompt=_daily_food_log_prompt(
                entry_text=payload.entry_text,
                goal_focus=goal_focus,
                primary_goal=primary_goal,
                log_date=log_date,
                local_time_label=local_time,
                prior_notes=prior_notes,
                prior_daily=prior_daily,
            ),
            task_type="utility",
            allow_web_search=False,
            system_instruction="Return strict JSON only with keys: title_line, meal_heading, items, estimated_nutrition, daily_progress, insights, follow_up_question.",
        )
        markdown = _format_daily_food_log_markdown(payload, raw if isinstance(raw, dict) else {}, prior_daily)
    except Exception:
        markdown = (
            "🍽️ Logged your meal\n\n"
            f"### Meal – {local_time or 'today'}\n\n"
            f"- {payload.entry_text.strip()}\n\n"
            "Daily Progress:\n"
            f"- Training done: {'yes' if prior_daily['training_done'] else 'no'}\n"
            f"- Nutrition logged: {'yes' if prior_daily['nutrition_on_plan'] else 'no'}\n"
            f"- Sleep hours: {prior_daily['sleep_hours'] if prior_daily['sleep_hours'] is not None else 'unknown'}\n"
            f"- Energy: {prior_daily['energy'] if prior_daily['energy'] is not None else 'unknown'}\n"
            f"- Stress: {prior_daily['stress'] if prior_daily['stress'] is not None else 'unknown'}\n\n"
            "Would you like me to close today’s log and generate your daily plan?"
        )
    return DailyCheckinFoodLogResponse(markdown=markdown)


@router.post(
    "/daily-checkin/step-summary",
    response_model=DailyCheckinStepSummaryResponse,
    status_code=status.HTTP_200_OK,
)
def daily_checkin_step_summary(
    payload: DailyCheckinStepSummaryRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    llm_client: LLMClient = Depends(get_llm_client),
) -> DailyCheckinStepSummaryResponse:
    log_date = payload.log_date or datetime.now(timezone.utc).date()
    row = (
        db.query(DailyLog)
        .filter(DailyLog.user_id == user.id, DailyLog.log_date == log_date)
        .first()
    )
    baseline = build_coaching_context(db=db, user_id=user.id).get("baseline") or {}
    goal_focus = _goal_bucket({"baseline": baseline})
    primary_goal = str(baseline.get("primary_goal") or "general health")
    prior_daily = {
        "sleep_hours": row.sleep_hours if row else None,
        "energy": row.energy if row else None,
        "mood": row.mood if row else None,
        "stress": row.stress if row else None,
        "training_done": bool(row.training_done) if row else False,
        "nutrition_on_plan": bool(row.nutrition_on_plan) if row else False,
    }
    try:
        raw = llm_client.generate_json(
            db=db,
            user_id=user.id,
            prompt=_daily_step_summary_prompt(
                payload=payload,
                goal_focus=goal_focus,
                primary_goal=primary_goal,
                prior_daily=prior_daily,
            ),
            task_type="utility",
            allow_web_search=False,
            system_instruction=(
                "Return strict JSON only with keys: logged_line, updated_status, insight, guidance, checklist, follow_up."
            ),
        )
        markdown = _format_daily_step_summary_markdown(
            payload,
            raw if isinstance(raw, dict) else {},
            primary_goal,
        )
    except Exception:
        parsed_text = str(payload.parsed_value) if payload.parsed_value is not None else payload.raw_answer
        markdown = (
            "## Logged Update\n"
            f"{payload.label}: {parsed_text}\n\n"
            "## Goal Progress Snapshot\n"
            f"- Primary goal: {primary_goal}\n"
            f"- Time bucket: {payload.time_bucket or 'today'}\n\n"
            "## Coach Insight\n"
            "Great consistency. Keep logging in this level of detail so guidance can stay personalized.\n\n"
            "## Next Guidance\n"
            "- Continue the next check-in item.\n"
            "- Keep units and timing in each update.\n\n"
            "Ready for the next check-in item?"
        )
    return DailyCheckinStepSummaryResponse(markdown=markdown)


def _serialize_recent_daily_logs(rows: list[DailyLog]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows[:30]:
        parsed_payload: Optional[dict[str, Any]] = None
        if row.checkin_payload_json:
            try:
                loaded = json.loads(row.checkin_payload_json)
                if isinstance(loaded, dict):
                    parsed_payload = loaded
            except json.JSONDecodeError:
                parsed_payload = None
        out.append(
            {
                "log_date": row.log_date.isoformat(),
                "sleep_hours": row.sleep_hours,
                "energy": row.energy,
                "mood": row.mood,
                "stress": row.stress,
                "training_done": bool(row.training_done),
                "nutrition_on_plan": bool(row.nutrition_on_plan),
                "notes": row.notes,
                "checkin_payload": parsed_payload,
            }
        )
    return out


def _extract_today_operational_signals(today_log: Optional[dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(today_log, dict):
        return {
            "hydration_progress": None,
            "meds_taken": None,
            "supplements_taken": None,
            "food_details": None,
            "training_details": None,
        }
    checkin_payload = today_log.get("checkin_payload")
    answers = (
        checkin_payload.get("answers")
        if isinstance(checkin_payload, dict) and isinstance(checkin_payload.get("answers"), dict)
        else {}
    )
    extras = (
        checkin_payload.get("extras")
        if isinstance(checkin_payload, dict) and isinstance(checkin_payload.get("extras"), dict)
        else {}
    )
    events = (
        checkin_payload.get("events")
        if isinstance(checkin_payload, dict) and isinstance(checkin_payload.get("events"), list)
        else []
    )
    notes_text = str(today_log.get("notes") or "").strip() if isinstance(today_log, dict) else ""
    unparsed_updates = (
        extras.get("unparsed_progress_updates")
        if isinstance(extras.get("unparsed_progress_updates"), list)
        else []
    )

    def _answer_text(key: str) -> Optional[str]:
        value = answers.get(key)
        if isinstance(value, dict):
            raw = value.get("raw_answer")
            if raw is not None:
                text = str(raw).strip()
                return text or None
        if key in extras and extras.get(key) is not None:
            text = str(extras.get(key)).strip()
            return text or None
        return None

    def _latest_event_text(event_type: str) -> Optional[str]:
        for item in reversed(events):
            if not isinstance(item, dict):
                continue
            if str(item.get("event_type") or "").strip().lower() != event_type:
                continue
            details = str(item.get("details") or "").strip()
            if details:
                return details[:600]
        return None

    fallback_food = _latest_event_text("food")
    fallback_hydration = _latest_event_text("hydration")
    fallback_meds = _latest_event_text("medication")
    fallback_supplements = _latest_event_text("supplement")
    fallback_training = _latest_event_text("workout")
    fallback_unparsed_text = None
    if unparsed_updates:
        last = unparsed_updates[-1]
        if isinstance(last, dict):
            txt = str(last.get("text") or "").strip()
            fallback_unparsed_text = txt[:600] if txt else None

    fallback_note_text = None
    if notes_text:
        # Notes often contain "chat_progress: ..." lines that should remain usable for summaries.
        match = re.findall(r"chat_progress:\s*([^|]+)", notes_text, flags=re.IGNORECASE)
        if match:
            candidate = str(match[-1]).strip()
            if candidate:
                fallback_note_text = candidate[:600]
        elif any(k in notes_text.lower() for k in ("ate", "meal", "breakfast", "lunch", "dinner", "supper", "snack", "pizza", "toast", "muffin", "eggs", "rice")):
            fallback_note_text = notes_text[:600]

    return {
        "hydration_progress": _answer_text("hydration_progress") or fallback_hydration,
        "meds_taken": _answer_text("meds_taken") or fallback_meds,
        "supplements_taken": _answer_text("supplements_taken") or fallback_supplements,
        "food_details": _answer_text("nutrition_food_details") or _answer_text("nutrition_on_plan") or fallback_food or fallback_unparsed_text or fallback_note_text,
        "training_details": _answer_text("training_done") or fallback_training,
    }


def _estimate_food_totals_from_text(food_text: Optional[str]) -> Optional[dict[str, str]]:
    text = str(food_text or "").strip().lower()
    if not text or text == "not logged":
        return None

    text = re.sub(r"\bsour\s*dough\b", "sourdough", text)
    text = re.sub(r"\b(to|too)\s+pieces?\b", "2 pieces", text)

    number_words = {
        "zero": 0,
        "one": 1,
        "two": 2,
        "to": 2,
        "too": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
        "half": 0.5,
        "quarter": 0.25,
    }

    def _qty(token: Optional[str]) -> float:
        raw = str(token or "").strip().lower()
        if not raw:
            return 1.0
        if raw.isdigit():
            return float(int(raw))
        if raw in number_words:
            return float(number_words[raw])
        if "/" in raw:
            try:
                num, den = raw.split("/", 1)
                return float(num) / float(den)
            except Exception:
                return 1.0
        return 1.0

    # Coarse heuristic portions for common logged items.
    catalog = [
        (
            r"(\d+|[a-z]+)\s*(?:slice|slices|piece|pieces).{0,20}pizza",
            {"kcal": 285, "protein": 12, "carbs": 34, "fat": 11},
        ),
        (
            r"(\d+|[a-z]+)\s*(?:slice|slices|piece|pieces).{0,20}(?:sourdough|toast)",
            {"kcal": 120, "protein": 4.5, "carbs": 24.5, "fat": 0.7},
        ),
        (
            r"(\d+|[a-z]+)\s*(?:tbsp|tablespoon|tablespoons).{0,20}peanut butter",
            {"kcal": 95, "protein": 3.5, "carbs": 3, "fat": 8},
        ),
        (r"(\d+|[a-z]+)\s*(?:banana|bananas)", {"kcal": 105, "protein": 1.3, "carbs": 27, "fat": 0.4}),
        (r"(\d+|[a-z]+)\s*(?:egg|eggs)", {"kcal": 72, "protein": 6.3, "carbs": 0.4, "fat": 4.8}),
        (
            r"(\d+|[a-z]+)\s*(?:cup|cups).{0,20}cottage cheese",
            {"kcal": 200, "protein": 28, "carbs": 12, "fat": 5},
        ),
        (r"(\d+|[a-z]+)\s*(?:cup|cups).{0,20}grapes", {"kcal": 105, "protein": 1, "carbs": 27, "fat": 0}),
        (r"(\d+|[a-z]+)\s*(?:cup|cups).{0,20}rice", {"kcal": 205, "protein": 4.3, "carbs": 45, "fat": 0.4}),
    ]

    totals = {"kcal": 0.0, "protein": 0.0, "carbs": 0.0, "fat": 0.0}
    matched_any = False
    for pattern, macros in catalog:
        for m in re.finditer(pattern, text):
            qty = _qty(m.group(1))
            totals["kcal"] += macros["kcal"] * qty
            totals["protein"] += macros["protein"] * qty
            totals["carbs"] += macros["carbs"] * qty
            totals["fat"] += macros["fat"] * qty
            matched_any = True

    # Additional keyword-only coarse additions when quantity is unclear.
    if "peanut butter" in text and not re.search(
        r"(\d+|[a-z]+)\s*(?:tbsp|tablespoon|tablespoons).{0,20}peanut butter", text
    ):
        totals["kcal"] += 190
        totals["protein"] += 7
        totals["carbs"] += 6
        totals["fat"] += 16
        matched_any = True

    if "banana" in text and not re.search(r"(\d+|[a-z]+)\s*(?:banana|bananas)", text):
        totals["kcal"] += 105
        totals["protein"] += 1.3
        totals["carbs"] += 27
        totals["fat"] += 0.4
        matched_any = True

    if not matched_any:
        return None

    # Add uncertainty band to avoid false precision.
    low = 0.85
    high = 1.15
    return {
        "calories_range": f"~{int(totals['kcal'] * low)}-{int(totals['kcal'] * high)} kcal",
        "protein_range": f"~{int(totals['protein'] * low)}-{int(totals['protein'] * high)} g",
        "carbs_range": f"~{int(totals['carbs'] * low)}-{int(totals['carbs'] * high)} g",
        "fat_range": f"~{int(totals['fat'] * low)}-{int(totals['fat'] * high)} g",
    }


def _proactive_card_prompt(
    *,
    card_type: str,
    context: dict[str, Any],
    overall_summary: summary_api.OverallSummaryResponse,
    daily_logs: list[dict[str, Any]],
    today_signals: dict[str, Any],
) -> str:
    card_requirements = {
        "daily_summary": [
            "Include a Daily Totals Snapshot section with: calories (estimated if needed), protein, carbs, fat, hydration/water, sleep, training status, meds taken status, supplements taken status.",
            "Include Remaining Today vs Goal with calories/macros remaining. If explicit goal targets are missing, state estimated target range with assumptions.",
            "Include Goal Progress & Adaptive Learning using weekly and monthly summary trends.",
            "Include Missing Data section that asks only high-value missing items needed for better precision.",
        ],
        "daily_plan": [
            "Convert current-day status into a concrete execution checklist for the rest of today.",
            "Include macro and hydration targets for remaining day window.",
            "Include medication/supplement timing reminders if applicable to user context.",
            "Use weekly/monthly trend data to prioritize the highest ROI tasks.",
        ],
        "what_next": [
            "Prioritize next 3 moves tied to user goals/objectives and trend signals.",
            "Include one measurable target and one adaptive pivot trigger.",
            "Reference monthly and weekly trends to justify why these are next.",
        ],
    }.get(card_type, ["Provide a concise goal-aligned coaching card."])

    body = {
        "task": "Generate an agentic coaching card markdown for the requested card type.",
        "card_type": card_type,
        "inputs": {
            "coaching_context": context,
            "daily_logs_recent": daily_logs,
            "daily_summary": overall_summary.today.model_dump(),
            "weekly_summary": overall_summary.trend_7d.model_dump(),
            "monthly_summary": overall_summary.trend_30d.model_dump(),
            "today_operational_signals": today_signals,
            "wins": overall_summary.top_wins,
            "risks": overall_summary.top_risks,
            "next_best_action": overall_summary.next_best_action,
            "weekly_personalized_insights": overall_summary.weekly_personalized_insights,
        },
        "agent_workflow": [
            "Nutritionist, Movement Coach, Sleep Expert, Cardiometabolic Strategist, and Safety Clinician review the provided summaries/logs.",
            "Goal Strategist maps findings to objective progress and phase direction.",
            "Orchestrator synthesizes one clear user-facing output.",
        ],
        "output_requirements": {
            "format": "markdown",
            "must_be_readable": True,
            "must_reference_data": "Use concrete values from daily/weekly/monthly summaries where available.",
            "must_be_goal_aligned": True,
            "card_specific_requirements": card_requirements,
            "no_diagnosis": True,
        },
        "return_schema": {
            "markdown": "string",
        },
    }
    return json.dumps(body, separators=(",", ":"))


def _fallback_proactive_card_markdown(
    *,
    card_type: str,
    overall_summary: summary_api.OverallSummaryResponse,
    primary_goal: str,
    today_signals: dict[str, Any],
) -> str:
    today = overall_summary.today
    hydration = today_signals.get("hydration_progress") or "not logged"
    meds = today_signals.get("meds_taken") or "not logged"
    supplements = today_signals.get("supplements_taken") or "not logged"
    food_details = today_signals.get("food_details") or "not logged"
    estimated = _estimate_food_totals_from_text(food_details)
    food_logged = bool(today.nutrition_on_plan) or (bool(food_details) and str(food_details).strip().lower() != "not logged")
    if card_type == "daily_plan":
        checklist = [
            f"- {'[x]' if today.sleep_hours is not None else '[ ]'} Log sleep hours",
            f"- {'[x]' if today.energy is not None else '[ ]'} Log energy (1-10)",
            f"- {'[x]' if today.mood is not None else '[ ]'} Log mood (1-10)",
            f"- {'[x]' if today.stress is not None else '[ ]'} Log stress (1-10)",
            f"- {'[x]' if bool(today.training_done) else '[ ]'} Complete/mark training",
            f"- {'[x]' if bool(today.nutrition_on_plan) else '[ ]'} Log food intake",
        ]
        return "\n".join(
            [
                "## Daily Plan",
                "",
                f"- Goal alignment: **{primary_goal}**",
                f"- Weekly entries: **{overall_summary.trend_7d.entries}**",
                f"- Monthly entries: **{overall_summary.trend_30d.entries}**",
                "",
                "### Complete Today",
                *checklist,
                "",
                "### Remaining Macro + Hydration Window",
                "- Calories/macros remaining: estimate from logged intake and target range.",
                f"- Hydration status: {hydration}",
                "",
                "### Medication + Supplement Timing",
                f"- Medications: {meds}",
                f"- Supplements: {supplements}",
                "",
                "### Priority",
                f"- {overall_summary.next_best_action}",
            ]
        )
    if card_type == "what_next":
        insights = overall_summary.weekly_personalized_insights[:3] if overall_summary.weekly_personalized_insights else []
        next_moves = (
            [f"- {x}" for x in insights]
            if insights
            else [
                "- Keep logging consistently for 7 days.",
                "- Review weekly trend direction.",
                "- Adjust one lever at a time.",
            ]
        )
        return "\n".join(
            [
                "## What Next",
                "",
                f"For **{primary_goal}**, your next priority is:",
                f"- **{overall_summary.next_best_action}**",
                "",
                "### Next 3 Moves",
                *next_moves,
                "",
                "### Adaptive Trigger",
                "- If weekly trend stalls, tighten one lever only (calories, movement, or sleep consistency) and reassess in 7 days.",
            ]
        )
    return "\n".join(
        [
            "## Daily Summary",
            "",
            f"- Goal focus: **{primary_goal}**",
            f"- Health score: **{overall_summary.health_score}**",
            f"- Next best action: {overall_summary.next_best_action}",
            "",
            "### Daily Totals Snapshot",
            f"- Calories: {estimated['calories_range'] if estimated else 'estimate requires more detailed meal logging.'}",
            f"- Protein: {estimated['protein_range'] if estimated else 'estimate requires more detailed meal logging.'}",
            f"- Carbs: {estimated['carbs_range'] if estimated else 'estimate requires more detailed meal logging.'}",
            f"- Fat: {estimated['fat_range'] if estimated else 'estimate requires more detailed meal logging.'}",
            f"- Food log details: {food_details}",
            f"- Hydration: {hydration}",
            f"- Sleep: {today.sleep_hours if today.sleep_hours is not None else 'not logged'}",
            f"- Training: {'done' if bool(today.training_done) else 'not done / not logged'}",
            f"- Medications: {meds}",
            f"- Supplements: {supplements}",
            "",
            "### Remaining Today vs Goal",
            (
                "- Calories remaining: compare estimated intake vs your current target range."
                if estimated
                else "- Calories remaining: estimate requires clear calorie target and full meal logging."
            ),
            (
                "- Macro remaining: prioritize protein at next meal and keep fats/carbs aligned to plan."
                if estimated
                else "- Macro remaining: estimate requires protein/carb/fat target and full meal logging."
            ),
            "",
            "### Today Signals",
            f"- Energy/Mood/Stress: {today.energy if today.energy is not None else 'n/a'} / {today.mood if today.mood is not None else 'n/a'} / {today.stress if today.stress is not None else 'n/a'}",
            f"- Food logged: {'yes' if food_logged else 'no / not logged'}",
            "",
            "### Goal Progress & Adaptive Learning",
            f"- Weekly trend entries: {overall_summary.trend_7d.entries}",
            f"- Monthly trend entries: {overall_summary.trend_30d.entries}",
            "",
            "### Top Wins",
            *(f"- {x}" for x in overall_summary.top_wins[:4]),
            "",
            "### Top Risks",
            *(f"- {x}" for x in overall_summary.top_risks[:4]),
            "",
            "### Missing Data To Improve Precision",
            "- Add exact meal portions/macros and hydration totals.",
            "- Add medication/supplement timing confirmations when taken.",
        ]
    )


@router.post(
    "/proactive-card",
    response_model=ProactiveCardResponse,
    status_code=status.HTTP_200_OK,
)
def proactive_card(
    payload: ProactiveCardRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    llm_client: LLMClient = Depends(get_llm_client),
) -> ProactiveCardResponse:
    card_type = str(payload.card_type or "").strip().lower()
    if card_type not in {"daily_summary", "daily_plan", "what_next"}:
        raise HTTPException(status_code=422, detail="card_type must be one of daily_summary, daily_plan, what_next")

    context = build_coaching_context(db=db, user_id=user.id)
    baseline = context.get("baseline") or {}
    primary_goal = str(baseline.get("primary_goal") or "your current goal")
    overall = summary_api.get_overall_summary(user=user, db=db)
    now = datetime.now(timezone.utc).date()
    rows_30 = (
        db.query(DailyLog)
        .filter(DailyLog.user_id == user.id, DailyLog.log_date >= (now - timedelta(days=29)), DailyLog.log_date <= now)
        .order_by(DailyLog.log_date.desc())
        .all()
    )
    serialized_logs = _serialize_recent_daily_logs(rows_30)
    today_signals = _extract_today_operational_signals(serialized_logs[0] if serialized_logs else None)
    orchestrator_prompt = render_agent_system_prompt(
        agent_id="orchestrator",
        user_goals=primary_goal,
        context_hint=", ".join((baseline.get("top_goals") or [])[:3]) if isinstance(baseline.get("top_goals"), list) else None,
        extra_instruction=(
            "Generate the requested proactive card by synthesizing specialist findings from the provided daily logs, "
            "weekly summary, and monthly summary. Use concrete values from inputs."
        ),
    )
    goal_strategist_prompt = render_agent_system_prompt(
        agent_id="goal_strategist",
        user_goals=primary_goal,
        context_hint=", ".join((baseline.get("top_goals") or [])[:3]) if isinstance(baseline.get("top_goals"), list) else None,
        extra_instruction=(
            "Map output to measurable progress and near-term objective execution."
        ),
    )
    try:
        raw = llm_client.generate_json(
            db=db,
            user_id=user.id,
            prompt=_proactive_card_prompt(
                card_type=card_type,
                context=context,
                overall_summary=overall,
                daily_logs=serialized_logs,
                today_signals=today_signals,
            ),
            task_type="utility",
            allow_web_search=False,
            system_instruction=(
                orchestrator_prompt
                + "\n\n"
                + goal_strategist_prompt
                + "\n\nReturn strict JSON only with key: markdown."
            ),
        )
        markdown = str((raw or {}).get("markdown") or "").strip()
        if not markdown:
            markdown = _fallback_proactive_card_markdown(
                card_type=card_type,
                overall_summary=overall,
                primary_goal=primary_goal,
                today_signals=today_signals,
            )
    except Exception:
        markdown = _fallback_proactive_card_markdown(
            card_type=card_type,
            overall_summary=overall,
            primary_goal=primary_goal,
            today_signals=today_signals,
        )
    return ProactiveCardResponse(card_type=card_type, markdown=markdown)


def _agent_profiles(include_supplement_audit: bool) -> list[dict[str, str]]:
    base = [
        {
            "id": "goal_strategist",
            "title": "Goal Strategist",
            "instruction": (
                "Operate at a 6-24 week horizon. Define measurable objectives, phase blocks, and pivot triggers. "
                "Set strategic targets across body composition, cardiometabolic markers, performance, and recovery. "
                "Do not micromanage meals/workouts and do not override safety constraints. "
                "When user logs progress, map it to current phase and objective completion signals."
            ),
            "task_type": "reasoning",
        },
        {
            "id": "nutritionist",
            "title": "Nutritionist",
            "instruction": (
                "Prioritize DASH-aligned nutrition strategy, protein targeting, carb timing, "
                "sodium/potassium balance, and calorie control against user goals. "
                "For meal logs, return itemized estimates (calories/macros/hydration impact) with clear assumptions."
            ),
            "task_type": "reasoning",
        },
        {
            "id": "sleep_expert",
            "title": "Sleep Expert",
            "instruction": (
                "Prioritize sleep architecture, circadian timing, and recovery behaviors that support "
                "blood pressure regulation, cortisol control, and fat-loss consistency. "
                "When sleep/fatigue updates are logged, provide immediate same-day adjustment guidance."
            ),
            "task_type": "reasoning",
        },
        {
            "id": "movement_coach",
            "title": "Movement Coach",
            "instruction": (
                "Design training and activity guidance for strength retention, Zone 2 balance, recovery pacing, "
                "and avoiding overtraining. When workout updates are logged, summarize session effect and next recovery step."
            ),
            "task_type": "reasoning",
        },
        {
            "id": "cardiometabolic_strategist",
            "title": "Cardiometabolic Strategist",
            "instruction": (
                "Focus on cardiometabolic strategy: LDL/triglyceride/HDL patterns, insulin sensitivity, "
                "arterial risk direction, blood pressure trends, and conservative lab-interpretation logic. "
                "For BP/HR/weight logs, interpret in trend context (not single-point alarmism)."
            ),
            "task_type": "reasoning",
        },
        {
            "id": "safety_clinician",
            "title": "Safety Clinician",
            "instruction": (
                "Identify contraindications, medication-related cautions, unsafe fasting/load recommendations, "
                "and urgent red-flag language. Keep advice conservative and non-alarmist. "
                "If user asks medication timing or adherence, provide scheduling-safe guidance without diagnosis."
            ),
            "task_type": "utility",
        },
    ]
    return base


def _is_behavior_question(question: str) -> bool:
    q = (question or "").lower()
    return any(
        k in q
        for k in [
            "habit",
            "adherence",
            "compliance",
            "consistency",
            "friction",
            "motivation",
            "discipline",
            "routine",
        ]
    )


def _is_recovery_stress_question(question: str) -> bool:
    q = (question or "").lower()
    return any(
        k in q
        for k in [
            "recovery",
            "stress",
            "hrv",
            "cortisol",
            "deload",
            "burnout",
            "alcohol",
            "nervous system",
        ]
    )


def _enriched_profiles(question: str, include_supplement_audit: bool) -> list[dict[str, str]]:
    profiles = [
        *_agent_profiles(include_supplement_audit=False),
    ]
    if _is_behavior_question(question):
        profiles.append(
            {
                "id": "behavior_architect",
                "title": "Behavior Architect",
                "instruction": (
                    "Engineer adherence systems: reduce decision fatigue, simplify rules, and convert goals "
                    "into low-friction autopilot habits."
                ),
                "task_type": "utility",
            }
        )
    if _is_recovery_stress_question(question):
        profiles.append(
            {
                "id": "recovery_stress_regulator",
                "title": "Recovery & Stress Regulator",
                "instruction": (
                    "Assess CNS load, recovery pacing, stress burden, alcohol impact, and when to deload "
                    "to protect long-term progress."
                ),
                "task_type": "utility",
            }
        )
    if include_supplement_audit:
        profiles.append(
            {
                "id": "supplement_auditor",
                "title": "Supplement Auditor",
                "instruction": (
                    "Review supplement stack for overlap, timing, safety caveats, and monitoring suggestions. "
                    "Do not diagnose disease."
                ),
                "task_type": "utility",
            }
        )
    return profiles


def _is_goal_strategy_question(question: str) -> bool:
    q = (question or "").lower()
    return any(
        k in q
        for k in [
            "goal",
            "target",
            "milestone",
            "phase",
            "6 week",
            "12 week",
            "3 month",
            "6 month",
            "roadmap",
            "plan",
            "stall",
            "pivot",
            "arc",
            "objective",
        ]
    )


def _quick_mode_profiles(question: str, include_supplement_audit: bool) -> list[dict[str, str]]:
    q = (question or "").lower()
    profiles: list[dict[str, str]] = []
    by_id = {p["id"]: p for p in _enriched_profiles(question, include_supplement_audit)}
    if _is_goal_strategy_question(question):
        profiles.append(by_id["goal_strategist"])
    if any(k in q for k in ["ldl", "hdl", "triglyceride", "cholesterol", "lipid", "bp", "blood pressure", "insulin"]):
        profiles.append(by_id["cardiometabolic_strategist"])
    if any(k in q for k in ["eat", "meal", "nutrition", "diet", "protein", "carb", "sodium", "potassium", "calorie"]):
        profiles.append(by_id["nutritionist"])
    if any(k in q for k in ["sleep", "wake", "tired", "fatigue"]):
        profiles.append(by_id["sleep_expert"])
    if any(k in q for k in ["train", "exercise", "steps", "workout", "zone 2", "strength", "overtraining"]):
        profiles.append(by_id["movement_coach"])
    if include_supplement_audit and "supplement_auditor" in by_id:
        profiles.append(by_id["supplement_auditor"])
    if _is_behavior_question(question) and "behavior_architect" in by_id:
        profiles.append(by_id["behavior_architect"])
    if _is_recovery_stress_question(question) and "recovery_stress_regulator" in by_id:
        profiles.append(by_id["recovery_stress_regulator"])
    profiles.append(by_id["safety_clinician"])

    seen = set()
    deduped = []
    for p in profiles:
        if p["id"] in seen:
            continue
        seen.add(p["id"])
        deduped.append(p)
    return deduped[:3]


def _build_agent_prompt(
    *,
    question: str,
    context_hint: Optional[str],
    context: dict[str, Any],
    mode: str,
    agent_title: str,
    agent_instruction: str,
    web_search_enabled: bool = True,
    prior_agents: Optional[list[dict[str, Any]]] = None,
) -> str:
    baseline = context.get("baseline") or {}
    primary_goal = str(baseline.get("primary_goal") or "improve healthspan").strip()
    top_goals = baseline.get("top_goals") if isinstance(baseline.get("top_goals"), list) else []
    goal_vector = ", ".join([primary_goal, *[str(g) for g in top_goals[:3] if str(g).strip()]])
    if not goal_vector:
        goal_vector = "general longevity improvement"
    body = {
        "question": question,
        "context_hint": context_hint,
        "context": context,
        "agent_profile": {
            "name": agent_title,
            "instruction": agent_instruction,
        },
        "web_search_enabled": bool(web_search_enabled),
        "prior_agent_outputs": prior_agents or [],
        "instructions": {
            "tone": "warm, practical, science-informed, never shame-based",
            "mode": mode,
            "goal_personalization": (
                f"Customize guidance to this user's goals/objectives: {goal_vector}. "
                "Tie recommendations and follow-up questions directly to those goals."
            ),
            "interaction_contract": (
                "Operate as a proactive coaching loop. When the user provides progress updates "
                "(food, hydration, meds, vitals, workouts, sleep, fasting), always: "
                "1) confirm what was logged, "
                "2) provide structured estimated impact/macros where relevant, "
                "3) show an updated day-status snapshot against goals, "
                "4) give one next best task, "
                "5) ask one targeted follow-up question."
            ),
            "memory_contract": (
                "Use context.structured_memory and context.daily_log_summary as authoritative short-memory inputs. "
                "Assume chat context window can be incomplete and rely on stored updates/trends when deciding guidance."
            ),
            "proactive": (
                "Be proactive and success-oriented. Use available trend/history context to define near-term checkpoints, "
                "clear success measures, and pivot triggers instead of only reactive advice."
            ),
            "format": (
                "answer must be readable markdown with short sections, bullets, spacing, and explicit headers. "
                "Prefer structures like: Weekly Progress Report, Metrics, Key Actions, Learnings, Outcomes, Next Focus. "
                "For daily interactions prefer: Logged Update, Entry, Estimated Nutrition/Impact, Daily Totals Snapshot, Coach Insight, Next Task, Coach Question. "
                "Avoid one long paragraph."
            ),
            "detail_requirements": [
                "For food/beverage logs include: itemized entry, estimated calories/macros/hydration impact when inferable.",
                "For fasting logs include: start/end/duration and whether aligned to current goal and day type.",
                "For vitals logs include: quick interpretation in context of recent trend and safety guardrails.",
                "For workout logs include: session summary, likely training effect, and immediate recovery adjustment.",
                "Use explicit units and timestamps when provided by user; ask for missing time only when needed.",
            ],
            "must_include": [
                "answer",
                "rationale_bullets (3-7)",
                "recommended_actions (1-3 items with title + steps)",
                "suggested_questions (3-8 direct coach questions for the user to answer next)",
                "safety_flags",
            ],
        },
    }
    return json.dumps(body, separators=(",", ":"))


def _looks_like_progress_log(question: str) -> bool:
    q = (question or "").lower()
    tokens = [
        "log",
        "logged",
        "drank",
        "water",
        "cups",
        "ml",
        "ate",
        "meal",
        "dinner",
        "lunch",
        "break fast",
        "broke my fast",
        "fasting",
        "weight",
        "lb",
        "lbs",
        "kg",
        "bp",
        "blood pressure",
        "hr",
        "heart rate",
        "took",
        "took my",
        "supplement",
        "vitamin",
        "workout",
        "zone 2",
        "treadmill",
        "sleep",
        "woke up",
    ]
    return any(t in q for t in tokens)


def _chat_progress_parse_prompt(question: str) -> str:
    body = {
        "task": "Parse a free-form user coaching update into structured events for logging/memory.",
        "input": {
            "text": question,
        },
        "output_schema": {
            "has_progress_update": "bool",
            "events": [
                {
                    "event_type": "food|hydration|medication|supplement|workout|sleep|weight|blood_pressure|heart_rate|fasting|note",
                    "timestamp_text": "string|null",
                    "details": "string",
                    "quantity_text": "string|null",
                    "value_num": "number|null",
                    "value_unit": "string|null",
                }
            ],
            "rollup": {
                "nutrition_on_plan": "bool|null",
                "training_done": "bool|null",
                "sleep_hours": "number|null",
                "weight_kg": "number|null",
                "bp_systolic": "number|null",
                "bp_diastolic": "number|null",
                "resting_hr_bpm": "number|null",
                "nutrition_food_details": "string|null",
                "hydration_progress": "string|null",
                "meds_taken": "string|null",
                "supplements_taken": "string|null",
                "training_details": "string|null",
            },
        },
        "rules": [
            "Extract only what is explicitly stated or strongly implied.",
            "Convert weight to kg when unit is lb/lbs/pounds.",
            "For blood pressure, split systolic/diastolic only when clearly present.",
            "Use null for unknown fields.",
            "Return strict JSON only.",
        ],
    }
    return json.dumps(body, separators=(",", ":"))


def _extract_chat_progress_signals(
    *,
    db: Session,
    user_id: int,
    question: str,
    llm_client: LLMClient,
) -> dict[str, Any]:
    text = str(question or "").strip()
    if not text or not _looks_like_progress_log(text):
        return {}
    try:
        raw = llm_client.generate_json(
            db=db,
            user_id=user_id,
            prompt=_chat_progress_parse_prompt(text),
            task_type="utility",
            allow_web_search=False,
            system_instruction=(
                "Return strict JSON only with keys: has_progress_update, events, rollup. "
                "No markdown, no prose, no extra keys."
            ),
        )
    except Exception:
        return {
            "raw_text": text[:800],
            "parse_status": "ai_unavailable",
            "events": [],
            "rollup": {},
        }

    if not isinstance(raw, dict):
        return {
            "raw_text": text[:800],
            "parse_status": "invalid_ai_payload",
            "events": [],
            "rollup": {},
        }

    parsed: dict[str, Any] = {
        "raw_text": text[:800],
        "parse_status": "ok",
        "has_progress_update": bool(raw.get("has_progress_update")),
        "events": [],
        "rollup": {},
    }

    incoming_events = raw.get("events")
    if isinstance(incoming_events, list):
        for item in incoming_events[:20]:
            if not isinstance(item, dict):
                continue
            event_type = str(item.get("event_type") or "").strip().lower()
            details = str(item.get("details") or "").strip()
            if not event_type or not details:
                continue
            evt = {
                "event_type": event_type[:32],
                "timestamp_text": (str(item.get("timestamp_text")).strip()[:64] if item.get("timestamp_text") else None),
                "details": details[:600],
                "quantity_text": (str(item.get("quantity_text")).strip()[:80] if item.get("quantity_text") else None),
                "value_num": None,
                "value_unit": (str(item.get("value_unit")).strip()[:16] if item.get("value_unit") else None),
            }
            try:
                if item.get("value_num") is not None:
                    evt["value_num"] = float(item.get("value_num"))
            except Exception:
                evt["value_num"] = None
            parsed["events"].append(evt)

    incoming_rollup = raw.get("rollup")
    if isinstance(incoming_rollup, dict):
        rollup: dict[str, Any] = {}
        bool_fields = ("nutrition_on_plan", "training_done")
        for key in bool_fields:
            val = incoming_rollup.get(key)
            if val in (True, False):
                rollup[key] = bool(val)
        numeric_fields = ("sleep_hours", "weight_kg", "bp_systolic", "bp_diastolic", "resting_hr_bpm")
        for key in numeric_fields:
            val = incoming_rollup.get(key)
            if val is None:
                continue
            try:
                rollup[key] = float(val)
            except Exception:
                continue
        text_fields = (
            "nutrition_food_details",
            "hydration_progress",
            "meds_taken",
            "supplements_taken",
            "training_details",
        )
        for key in text_fields:
            val = incoming_rollup.get(key)
            if val is None:
                continue
            txt = str(val).strip()
            if txt:
                rollup[key] = txt[:600]
        parsed["rollup"] = rollup
    has_structured = bool(parsed["events"]) or bool(parsed["rollup"])
    if not has_structured:
        parsed["parse_status"] = "no_structured_data"
        if isinstance(raw.get("answer"), str) and raw.get("answer").strip():
            parsed["raw_ai_output"] = str(raw.get("answer")).strip()[:600]
    return parsed


def _merge_chat_signals_into_daily_log(
    *,
    db: Session,
    user_id: int,
    question: str,
    llm_client: LLMClient,
) -> None:
    signals = _extract_chat_progress_signals(
        db=db,
        user_id=user_id,
        question=question,
        llm_client=llm_client,
    )
    if not signals:
        return
    rollup = signals.get("rollup") if isinstance(signals.get("rollup"), dict) else {}
    signal_events = signals.get("events") if isinstance(signals.get("events"), list) else []
    today_utc = datetime.now(timezone.utc).date()
    row = (
        db.query(DailyLog)
        .filter(DailyLog.user_id == user_id, DailyLog.log_date == today_utc)
        .first()
    )
    if not row:
        row = DailyLog(
            user_id=user_id,
            log_date=today_utc,
            sleep_hours=0.0,
            energy=5,
            mood=5,
            stress=5,
            training_done=False,
            nutrition_on_plan=False,
        )
        db.add(row)
        db.flush()

    if "sleep_hours" in rollup:
        row.sleep_hours = float(rollup["sleep_hours"])
    if "training_done" in rollup:
        row.training_done = bool(rollup["training_done"]) or bool(row.training_done)
    if "nutrition_on_plan" in rollup:
        row.nutrition_on_plan = bool(rollup["nutrition_on_plan"]) or bool(row.nutrition_on_plan)

    existing_payload: dict[str, Any] = {}
    if row.checkin_payload_json:
        try:
            loaded = json.loads(row.checkin_payload_json)
            if isinstance(loaded, dict):
                existing_payload = loaded
        except json.JSONDecodeError:
            existing_payload = {}
    payload = existing_payload.get("payload") if isinstance(existing_payload.get("payload"), dict) else {}
    extras = existing_payload.get("extras") if isinstance(existing_payload.get("extras"), dict) else {}
    answers = existing_payload.get("answers") if isinstance(existing_payload.get("answers"), dict) else {}
    events = existing_payload.get("events") if isinstance(existing_payload.get("events"), list) else []

    def _upsert_answer(key: str, parsed_value: Any) -> None:
        answers[key] = {
            "specialist": "Orchestrator",
            "question": "Captured from chat progress update via utility parser",
            "raw_answer": question[:600],
            "parsed_value": parsed_value,
            "at_local": datetime.now(timezone.utc).isoformat(),
        }

    def _infer_categories_from_unparsed(text: str) -> dict[str, bool]:
        lower = str(text or "").lower()
        food_terms = (
            " ate ",
            "meal",
            "breakfast",
            "lunch",
            "dinner",
            "supper",
            "snack",
            "pizza",
            "sandwich",
            "ramen",
            "muffin",
            "toast",
            "rice",
            "eggs",
        )
        hydration_terms = ("drank", "drink", "water", "hydration", "cups", " ml", "liter", "litre")
        meds_terms = ("med", "medication", "blood pressure meds", "pill", "dose", "ezetimibe", "candesartan")
        supp_terms = ("supplement", "vitamin", "creatine", "fish oil", "coq10", "magnesium", "b12", "d3")
        workout_terms = ("workout", "trained", "training", "zone 2", "treadmill", "deadlift", "lifted", "exercise")
        return {
            "food": any(t in lower for t in food_terms),
            "hydration": any(t in lower for t in hydration_terms),
            "meds": any(t in lower for t in meds_terms),
            "supplements": any(t in lower for t in supp_terms),
            "workout": any(t in lower for t in workout_terms),
        }

    def _split_clauses(text: str) -> list[str]:
        src = str(text or "").strip()
        if not src:
            return []
        return [str(c).strip() for c in re.split(r"[;,]| and ", src) if str(c).strip()]

    def _extract_fragment(text: str, include_terms: tuple[str, ...], exclude_terms: tuple[str, ...]) -> str:
        src = str(text or "").strip()
        if not src:
            return src
        clauses = _split_clauses(src)
        selected: list[str] = []
        for c in clauses:
            part = str(c).strip()
            if not part:
                continue
            lower = part.lower()
            if any(t in lower for t in exclude_terms) and not any(t in lower for t in include_terms):
                continue
            if any(t in lower for t in include_terms):
                selected.append(part)
        if selected:
            return ", ".join(selected)[:600]
        return ""

    def _extract_food_fragment(text: str) -> str:
        return _extract_fragment(
            text,
            include_terms=(
                "ate",
                "meal",
                "breakfast",
                "lunch",
                "dinner",
                "supper",
                "snack",
                "pizza",
                "sandwich",
                "ramen",
                "muffin",
                "toast",
                "rice",
                "egg",
                "coffee",
                "banana",
                "apple",
                "berries",
                "grapes",
                "cottage cheese",
                "yogurt",
                "protein shake",
                "shake",
            ),
            exclude_terms=(
                "woke",
                "wake",
                "sleep",
                "blood pressure",
                "bp",
                "med",
                "medication",
                "pill",
                "dose",
                "hr",
                "heart rate",
                "hydration",
                "water",
            ),
        )

    def _extract_meds_fragment(text: str) -> str:
        return _extract_fragment(
            text,
            include_terms=("med", "medication", "blood pressure med", "blood pressure meds", "pill", "dose", "ezetimibe", "candesartan"),
            exclude_terms=("ate", "meal", "breakfast", "lunch", "dinner", "supper", "snack", "pizza", "sandwich", "ramen", "muffin"),
        )

    def _extract_hydration_fragment(text: str) -> str:
        return _extract_fragment(
            text,
            include_terms=("drank", "drink", "water", "hydration", "cups", " ml", "liter", "litre"),
            exclude_terms=("med", "medication", "pill", "dose"),
        )

    def _extract_supplement_fragment(text: str) -> str:
        return _extract_fragment(
            text,
            include_terms=("supplement", "vitamin", "creatine", "fish oil", "coq10", "magnesium", "b12", "d3"),
            exclude_terms=("med", "medication", "pill", "dose"),
        )

    def _extract_workout_fragment(text: str) -> str:
        return _extract_fragment(
            text,
            include_terms=("workout", "trained", "training", "zone 2", "treadmill", "deadlift", "lifted", "exercise"),
            exclude_terms=("med", "medication", "pill", "dose"),
        )

    def _sanitize_rollup_text(key: str, value: Any, source_text: str) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""
        if key == "nutrition_food_details":
            return _extract_food_fragment(raw) or _extract_food_fragment(source_text)
        if key == "hydration_progress":
            return _extract_hydration_fragment(raw) or _extract_hydration_fragment(source_text)
        if key == "meds_taken":
            return _extract_meds_fragment(raw) or _extract_meds_fragment(source_text)
        if key == "supplements_taken":
            return _extract_supplement_fragment(raw) or _extract_supplement_fragment(source_text)
        if key == "training_details":
            return _extract_workout_fragment(raw) or _extract_workout_fragment(source_text)
        return raw[:600]

    for key in ("nutrition_food_details", "hydration_progress", "meds_taken", "supplements_taken", "training_details"):
        if key in rollup:
            cleaned = _sanitize_rollup_text(key, rollup.get(key), str(signals.get("raw_text") or question))
            if cleaned:
                extras[key] = cleaned
                _upsert_answer(key, cleaned)
    # If food detail exists after sanitization, mark food logged even if rollup omitted explicit boolean.
    if extras.get("nutrition_food_details"):
        row.nutrition_on_plan = True
        payload["nutrition_on_plan"] = True
        _upsert_answer("nutrition_on_plan", True)
    if "sleep_hours" in rollup:
        payload["sleep_hours"] = float(rollup["sleep_hours"])
        _upsert_answer("sleep_hours", float(rollup["sleep_hours"]))
    if "training_done" in rollup:
        payload["training_done"] = bool(rollup["training_done"])
        _upsert_answer("training_done", bool(rollup["training_done"]))
    if "nutrition_on_plan" in rollup:
        payload["nutrition_on_plan"] = bool(rollup["nutrition_on_plan"])
        _upsert_answer("nutrition_on_plan", bool(rollup["nutrition_on_plan"]))

    now_iso = datetime.now(timezone.utc).isoformat()
    food_event_details: Optional[str] = None
    hydration_event_details: Optional[str] = None
    meds_event_details: Optional[str] = None
    supplements_event_details: Optional[str] = None
    training_event_details: Optional[str] = None
    has_food_event = False
    has_training_event = False
    for evt in signal_events:
        if not isinstance(evt, dict):
            continue
        event_type = str(evt.get("event_type") or "").strip().lower()
        details = str(evt.get("details") or "").strip()
        if not event_type or not details:
            continue
        if event_type == "food":
            has_food_event = True
            food_event_details = details[:600]
        elif event_type == "hydration":
            hydration_event_details = details[:600]
        elif event_type == "medication":
            meds_event_details = details[:600]
        elif event_type == "supplement":
            supplements_event_details = details[:600]
        elif event_type == "workout":
            has_training_event = True
            training_event_details = details[:600]
        events.append(
            {
                "event_type": event_type[:32],
                "details": details[:600],
                "timestamp_text": (str(evt.get("timestamp_text")).strip()[:64] if evt.get("timestamp_text") else None),
                "quantity_text": (str(evt.get("quantity_text")).strip()[:80] if evt.get("quantity_text") else None),
                "value_num": (float(evt.get("value_num")) if evt.get("value_num") is not None else None),
                "value_unit": (str(evt.get("value_unit")).strip()[:16] if evt.get("value_unit") else None),
                "captured_at_utc": now_iso,
            }
        )
    events = events[-80:]

    if has_food_event:
        row.nutrition_on_plan = True
        payload["nutrition_on_plan"] = True
        _upsert_answer("nutrition_on_plan", True)
        if food_event_details and "nutrition_food_details" not in extras:
            extras["nutrition_food_details"] = food_event_details
            _upsert_answer("nutrition_food_details", food_event_details)
    if has_training_event:
        row.training_done = True
        payload["training_done"] = True
        _upsert_answer("training_done", True)
    if hydration_event_details and "hydration_progress" not in extras:
        extras["hydration_progress"] = hydration_event_details
        _upsert_answer("hydration_progress", hydration_event_details)
    if meds_event_details and "meds_taken" not in extras:
        extras["meds_taken"] = meds_event_details
        _upsert_answer("meds_taken", meds_event_details)
    if supplements_event_details and "supplements_taken" not in extras:
        extras["supplements_taken"] = supplements_event_details
        _upsert_answer("supplements_taken", supplements_event_details)
    if training_event_details and "training_details" not in extras:
        extras["training_details"] = training_event_details
        _upsert_answer("training_details", training_event_details)

    if signals.get("parse_status") != "ok":
        fallback_updates = extras.get("unparsed_progress_updates")
        if not isinstance(fallback_updates, list):
            fallback_updates = []
        raw_text = str(signals.get("raw_text") or question)[:600]
        inferred = _infer_categories_from_unparsed(raw_text)
        fallback_updates.append(
            {
                "text": raw_text,
                "captured_at_utc": now_iso,
                "parse_status": str(signals.get("parse_status") or "unknown"),
                "raw_ai_output": (str(signals.get("raw_ai_output")).strip()[:600] if signals.get("raw_ai_output") else None),
                "inferred_categories": inferred,
            }
        )
        extras["unparsed_progress_updates"] = fallback_updates[-20:]

        # Strict-by-category fallback: only populate categories with explicit evidence.
        if inferred.get("food") and "nutrition_food_details" not in extras:
            food_text = _extract_food_fragment(raw_text)
            if food_text:
                extras["nutrition_food_details"] = food_text
                _upsert_answer("nutrition_food_details", food_text)
                row.nutrition_on_plan = True
                payload["nutrition_on_plan"] = True
                _upsert_answer("nutrition_on_plan", True)
        if inferred.get("hydration") and "hydration_progress" not in extras:
            hydration_text = _extract_hydration_fragment(raw_text)
            if hydration_text:
                extras["hydration_progress"] = hydration_text
                _upsert_answer("hydration_progress", hydration_text)
        if inferred.get("meds") and "meds_taken" not in extras:
            meds_text = _extract_meds_fragment(raw_text)
            if meds_text:
                extras["meds_taken"] = meds_text
                _upsert_answer("meds_taken", meds_text)
        if inferred.get("supplements") and "supplements_taken" not in extras:
            supplements_text = _extract_supplement_fragment(raw_text)
            if supplements_text:
                extras["supplements_taken"] = supplements_text
                _upsert_answer("supplements_taken", supplements_text)
        if inferred.get("workout") and "training_details" not in extras:
            workout_text = _extract_workout_fragment(raw_text)
            if workout_text:
                extras["training_details"] = workout_text
                _upsert_answer("training_details", workout_text)
                row.training_done = True
                payload["training_done"] = True
                _upsert_answer("training_done", True)

    row.checkin_payload_json = json.dumps(
        {
            "payload": payload,
            "extras": extras,
            "answers": answers,
            "events": events,
            "evidence": existing_payload.get("evidence") if isinstance(existing_payload.get("evidence"), dict) else {},
            "updated_at_local": datetime.now(timezone.utc).isoformat(),
        },
        separators=(",", ":"),
    )

    existing_notes = str(row.notes or "")
    note_line = f"chat_progress: {question[:220]}"
    if note_line not in existing_notes:
        joined = (existing_notes + " | " + note_line).strip(" |")
        row.notes = joined[:1200]

    metric_specs: list[tuple[str, Any]] = []
    if "weight_kg" in rollup:
        metric_specs.append(("weight_kg", float(rollup["weight_kg"])))
    if "bp_systolic" in rollup:
        metric_specs.append(("bp_systolic", int(float(rollup["bp_systolic"]))))
    if "bp_diastolic" in rollup:
        metric_specs.append(("bp_diastolic", int(float(rollup["bp_diastolic"]))))
    if "resting_hr_bpm" in rollup:
        metric_specs.append(("resting_hr_bpm", int(float(rollup["resting_hr_bpm"]))))
    if "sleep_hours" in rollup:
        metric_specs.append(("sleep_hours", float(rollup["sleep_hours"])))

    now_utc = datetime.now(timezone.utc)
    for metric_type, metric_value in metric_specs:
        exists = (
            db.query(Metric)
            .filter(
                Metric.user_id == user_id,
                Metric.metric_type == metric_type,
                Metric.taken_at >= (now_utc - timedelta(hours=3)),
                Metric.taken_at <= (now_utc + timedelta(minutes=1)),
            )
            .first()
        )
        if exists:
            exists.value_num = float(metric_value)
            exists.taken_at = now_utc
        else:
            db.add(
                Metric(
                    user_id=user_id,
                    metric_type=metric_type,
                    value_num=float(metric_value),
                    taken_at=now_utc,
                )
            )

    db.commit()


def _looks_like_weekly_report_request(question: str) -> bool:
    q = (question or "").lower()
    return any(
        t in q
        for t in [
            "weekly report",
            "weekly progress",
            "week summary",
            "week 1",
            "week 2",
            "rolling report",
            "snapshot",
        ]
    )


def _apply_interaction_style(
    response: CoachQuestionResponse, context: dict[str, Any], question: str
) -> CoachQuestionResponse:
    if _looks_like_weekly_report_request(question):
        if "## Weekly Progress Report" not in response.answer:
            response.answer = (
                "## Weekly Progress Report\n"
                f"{response.answer}\n\n"
                "### Next Week Focus\n"
                "- Protein precision (post-workout target)\n"
                "- Hydration front-load and evening taper\n"
                "- Sleep and recovery consistency\n"
            )
        weekly_q = "Do you want this as a rolling report stack or a one-page weekly snapshot?"
        if all(weekly_q != item for item in response.suggested_questions):
            response.suggested_questions = [weekly_q, *response.suggested_questions][:8]
        return response

    if _looks_like_progress_log(question):
        baseline = context.get("baseline") or {}
        primary_goal = str(baseline.get("primary_goal") or "your goal")
        metrics = context.get("metrics_7d_summary") or {}
        daily = context.get("daily_log_summary") or {}
        sleep_latest = ((metrics.get("sleep_hours") or {}).get("latest") if isinstance(metrics, dict) else None)
        weight_latest = ((metrics.get("weight_kg") or {}).get("latest") if isinstance(metrics, dict) else None)
        bp_sys = ((metrics.get("bp_systolic") or {}).get("latest") if isinstance(metrics, dict) else None)
        bp_dia = ((metrics.get("bp_diastolic") or {}).get("latest") if isinstance(metrics, dict) else None)
        entries_7d = int(daily.get("entries_7d", 0) or 0)
        snapshot_bits = [
            f"- Primary goal: {primary_goal}",
            f"- Recent check-ins (7d): {entries_7d}",
        ]
        if weight_latest is not None:
            snapshot_bits.append(f"- Latest weight: {weight_latest} kg")
        if bp_sys is not None and bp_dia is not None:
            snapshot_bits.append(f"- Latest BP: {bp_sys}/{bp_dia}")
        if sleep_latest is not None:
            snapshot_bits.append(f"- Latest sleep: {sleep_latest} h")
        snapshot_text = "\n".join(snapshot_bits)
        if "## Logged Update" not in response.answer:
            response.answer = (
                "## Logged Update\n"
                "Progress entry captured.\n\n"
                "## Daily Totals Snapshot\n"
                f"{snapshot_text}\n\n"
                "## Coach Insight\n"
                f"{response.answer}\n\n"
                "## Next Task\n"
                "- Keep today aligned with your primary goal and hydration/protein targets.\n"
                "- Continue the daily coaching loop with your next measurable update.\n"
            )
        elif "## Daily Totals Snapshot" not in response.answer:
            response.answer = (
                f"{response.answer}\n\n"
                "## Daily Totals Snapshot\n"
                f"{snapshot_text}\n"
            )
        loop_q = "What is your next measurable update (weight, BP/HR, hydration, meal, workout, or sleep)?"
        if all(loop_q != item for item in response.suggested_questions):
            response.suggested_questions = [loop_q, *response.suggested_questions][:8]
        return response

    # Default conversational coaching structure.
    if "## Coach Plan" not in response.answer and "## Weekly Progress Report" not in response.answer:
        response.answer = "## Coach Plan\n" + response.answer
    return response


def _metric_count(context: dict[str, Any], metric_type: str) -> int:
    summary = (context.get("metrics_7d_summary") or {}).get(metric_type) or {}
    return int(summary.get("count", 0) or 0)


def _runtime_data_gaps_for_specialist(
    *, specialist_id: str, context: dict[str, Any], question: str
) -> tuple[list[str], list[str]]:
    baseline = context.get("baseline") or {}
    daily = context.get("daily_log_summary") or {}
    q = (question or "").lower()
    missing_data: list[str] = []
    missing_features: list[str] = []

    has_sleep = bool(_metric_count(context, "sleep_hours") > 0 or baseline.get("sleep_hours") is not None)
    has_stress = bool(_metric_count(context, "stress_1_10") > 0 or baseline.get("stress") is not None)
    has_energy = bool(_metric_count(context, "energy_1_10") > 0 or baseline.get("energy") is not None)
    has_bp = bool(
        _metric_count(context, "bp_systolic") > 0
        or _metric_count(context, "bp_diastolic") > 0
        or baseline.get("systolic_bp") is not None
    )

    if specialist_id == "supplement_auditor" and not baseline.get("supplement_stack"):
        missing_data.append("baseline.supplement_stack")
    safety_medication_keywords = [
        "medication",
        "medications",
        "prescription",
        "drug",
        "dose",
        "dosage",
        "interaction",
        "side effect",
        "contraindication",
        "supplement",
        "stack",
        "blood pressure",
        "bp",
        "cholesterol",
        "statin",
        "ezetimibe",
        "candesartan",
        "fasting",
        "taper",
    ]
    needs_medication_context = any(k in q for k in safety_medication_keywords)

    if specialist_id == "safety_clinician" and needs_medication_context and not baseline.get("medication_details"):
        missing_data.append("baseline.medication_details")
    if specialist_id == "sleep_expert" and not has_sleep:
        missing_data.append("sleep dataset (baseline sleep_hours or recent sleep metric)")
    if specialist_id == "recovery_stress_regulator":
        if not has_stress:
            missing_data.append("stress dataset (baseline stress or recent stress metric)")
        if not has_energy:
            missing_data.append("energy dataset (baseline energy or recent energy metric)")
    if specialist_id == "movement_coach" and int(daily.get("entries_7d", 0) or 0) == 0:
        missing_data.append("daily training adherence signals (daily logs)")
    if specialist_id == "nutritionist" and int(daily.get("entries_7d", 0) or 0) == 0:
        missing_data.append("daily nutrition adherence signals (daily logs)")
    if specialist_id == "cardiometabolic_strategist":
        if not has_bp:
            missing_data.append("blood pressure dataset (baseline BP or recent BP metrics)")
        if any(k in q for k in ["ldl", "hdl", "triglyceride", "cholesterol", "apo", "a1c", "hba1c"]):
            if not baseline.get("lab_markers"):
                missing_data.append("baseline.lab_markers")
            missing_features.append("structured longitudinal lab-results store and trend analyzer")
        if "glucose" in q and _metric_count(context, "glucose_mg_dl") == 0:
            missing_features.append("glucose metric ingestion/store not configured")
    if specialist_id == "goal_strategist":
        if not baseline.get("primary_goal"):
            missing_data.append("baseline.primary_goal")
        if int(daily.get("entries_7d", 0) or 0) == 0:
            missing_data.append("recent daily logs for weekly checkpoint calibration")
    if specialist_id == "behavior_architect" and int(daily.get("entries_7d", 0) or 0) == 0:
        missing_data.append("adherence history from daily logs")
    if specialist_id == "recovery_stress_regulator" and "hrv" in q:
        missing_features.append("HRV metric ingestion/store not configured")

    return sorted(set(missing_data)), sorted(set(missing_features))


def _log_runtime_gap_feedback(
    *,
    db: Session,
    user_id: int,
    user_email: str,
    specialist_title: str,
    missing_data: list[str],
    missing_features: list[str],
    question: str,
) -> None:
    if not missing_data and not missing_features:
        return
    title = f"Runtime Coverage Gap - {specialist_title}"
    now = datetime.now(timezone.utc)
    dedupe_since = now - timedelta(hours=24)
    exists = (
        db.query(FeedbackEntry)
        .filter(
            FeedbackEntry.user_id == user_id,
            FeedbackEntry.title == title,
            FeedbackEntry.page == "coach_runtime",
            FeedbackEntry.created_at >= dedupe_since,
        )
        .first()
    )
    if exists:
        return
    details = (
        f"Specialist: {specialist_title}\n"
        f"Question sample: {question[:220]}\n"
        f"Missing data: {', '.join(missing_data) if missing_data else 'none'}\n"
        f"Missing feature: {', '.join(missing_features) if missing_features else 'none'}\n"
        "Action: prompt user for missing data and/or implement missing feature to improve specialist quality."
    )
    system_actor = f"system:{specialist_title}".strip()[:255]
    db.add(
        FeedbackEntry(
            user_id=user_id,
            user_email=system_actor or user_email,
            category="feature",
            title=title[:160],
            details=details,
            page="coach_runtime",
        )
    )


def _run_agentic_pipeline(
    *,
    db: Session,
    user_id: int,
    user_email: str,
    payload: CoachQuestionRequest,
    context: dict[str, Any],
    llm_client: LLMClient,
) -> tuple[CoachQuestionResponse, list[dict[str, Any]]]:
    include_supplement_audit = has_supplement_topic(payload.question)
    baseline = context.get("baseline") or {}
    primary_goal = str(baseline.get("primary_goal") or "").strip()
    top_goals = baseline.get("top_goals") if isinstance(baseline.get("top_goals"), list) else []
    user_goals = ", ".join([primary_goal] + [str(g).strip() for g in top_goals[:3] if str(g).strip()]).strip(", ")
    if not user_goals:
        user_goals = "general longevity improvement"
    if payload.mode == CoachMode.quick and not payload.deep_think:
        # Cost-optimized quick path: small specialist set + synthesis.
        profiles = _quick_mode_profiles(payload.question, include_supplement_audit)
    else:
        profiles = _enriched_profiles(payload.question, include_supplement_audit)
    agent_outputs: list[dict[str, Any]] = []
    for profile in profiles:
        missing_data, missing_features = _runtime_data_gaps_for_specialist(
            specialist_id=profile["id"],
            context=context,
            question=payload.question,
        )
        _log_runtime_gap_feedback(
            db=db,
            user_id=user_id,
            user_email=user_email,
            specialist_title=profile["title"],
            missing_data=missing_data,
            missing_features=missing_features,
            question=payload.question,
        )
        specialist_system_prompt = render_agent_system_prompt(
            agent_id=profile["id"],
            user_goals=user_goals,
            context_hint=payload.context_hint,
            extra_instruction=profile.get("instruction", ""),
        )
        prompt = _build_agent_prompt(
            question=payload.question,
            context_hint=payload.context_hint,
            context=context,
            mode=payload.mode.value,
            agent_title=profile["title"],
            agent_instruction=specialist_system_prompt,
            web_search_enabled=payload.web_search,
            prior_agents=agent_outputs,
        )
        task_type = profile["task_type"]
        if payload.deep_think and task_type == "reasoning":
            task_type = "deep_think"
        raw = llm_client.generate_json(
            db=db,
            user_id=user_id,
            prompt=prompt,
            task_type=task_type,
            allow_web_search=payload.web_search,
        )
        agent_outputs.append(
            {
                "agent_id": profile["id"],
                "agent_title": profile["title"],
                "task_type": task_type,
                "answer": str(raw.get("answer", "")).strip(),
                "rationale_bullets": _safe_list(raw.get("rationale_bullets"), min_items=0, max_items=8, fallback=[]),
                "recommended_actions": raw.get("recommended_actions", []),
                "suggested_questions": _safe_list(raw.get("suggested_questions"), min_items=0, max_items=8, fallback=[]),
                "safety_flags": _safe_list(raw.get("safety_flags"), min_items=0, max_items=8, fallback=[]),
                "missing_data": missing_data,
                "missing_features": missing_features,
            }
        )

    orchestrator_contract_prompt = render_agent_system_prompt(
        agent_id="orchestrator",
        user_goals=user_goals,
        context_hint=payload.context_hint,
        extra_instruction=(
            "Synthesize all agent outputs into one final coaching response. "
            "Treat Goal Strategist as strategic direction (6-24 week horizon) and Orchestrator as operational execution (daily/weekly horizon). "
            "Assign explicit priority weights by risk and leverage, resolve conflicts conservatively, "
            "and decide which specialist leads today based on user context (sleep, BP, recovery, fat-loss, etc.). "
            "Apply hierarchy: Safety Clinician veto > cardiometabolic/sleep risk > movement/nutrition optimization. "
            "Prefer safer, actionable steps and avoid over-optimization."
        ),
    )
    synthesis_prompt = _build_agent_prompt(
        question=payload.question,
        context_hint=payload.context_hint,
        context=context,
        mode=payload.mode.value,
        agent_title="Orchestrator",
        agent_instruction=orchestrator_contract_prompt,
        web_search_enabled=payload.web_search,
        prior_agents=agent_outputs,
    )
    synthesis_task_type = "deep_think" if payload.deep_think else "reasoning"
    synthesis_raw = llm_client.generate_json(
        db=db,
        user_id=user_id,
        prompt=synthesis_prompt,
        task_type=synthesis_task_type,
        allow_web_search=payload.web_search,
    )
    # Expose synthesis/orchestration as part of the visible agent trace.
    agent_outputs.append(
        {
            "agent_id": "orchestrator",
            "agent_title": "Orchestrator",
            "task_type": synthesis_task_type,
            "answer": str(synthesis_raw.get("answer", "")).strip(),
            "rationale_bullets": _safe_list(synthesis_raw.get("rationale_bullets"), min_items=0, max_items=8, fallback=[]),
            "recommended_actions": synthesis_raw.get("recommended_actions", []),
            "suggested_questions": _safe_list(synthesis_raw.get("suggested_questions"), min_items=0, max_items=8, fallback=[]),
            "safety_flags": _safe_list(synthesis_raw.get("safety_flags"), min_items=0, max_items=8, fallback=[]),
            "missing_data": [],
            "missing_features": [],
        }
    )
    response = _response_from_raw(synthesis_raw, payload.mode.value)
    return response, agent_outputs


def request_coaching_json(
    *,
    db: Session,
    user_id: int,
    user_email: Optional[str] = None,
    payload: CoachQuestionRequest,
    context: dict[str, Any],
    llm_client: LLMClient,
    deep_think: bool = False,
) -> Union[tuple[CoachQuestionResponse, list[dict[str, Any]]], dict[str, Any]]:
    # Backward-compatible hook for tests/overrides that monkeypatch this symbol.
    _ = deep_think
    return _run_agentic_pipeline(
        db=db,
        user_id=user_id,
        user_email=(user_email or ""),
        payload=payload,
        context=context,
        llm_client=llm_client,
    )


def _public_agent_trace(agent_outputs: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {
            "agent_id": str(item.get("agent_id") or ""),
            "agent_title": str(item.get("agent_title") or ""),
            "task_type": str(item.get("task_type") or ""),
            "status": "complete",
            "data_status": (
                "degraded"
                if (item.get("missing_data") or item.get("missing_features"))
                else "ok"
            ),
            "missing_data_count": str(len(item.get("missing_data") or [])),
            "missing_feature_count": str(len(item.get("missing_features") or [])),
        }
        for item in agent_outputs
    ]


def _build_image_prompt(
    *,
    question: str,
    context_hint: Optional[str],
    context: dict[str, Any],
    mode: str,
    web_search_enabled: bool,
) -> str:
    baseline = context.get("baseline") or {}
    primary_goal = str(baseline.get("primary_goal") or "improve healthspan").strip()
    body = {
        "question": question,
        "context_hint": context_hint,
        "context": context,
        "web_search_enabled": bool(web_search_enabled),
        "image_instruction": (
            "Analyze the uploaded image as health context (for example meals, labels, workouts, biometrics screenshots). "
            "If details are uncertain, state uncertainty and ask direct clarifying questions."
        ),
        "instructions": {
            "tone": "warm, practical, science-informed, never shame-based",
            "mode": mode,
            "goal_personalization": (
                f"Customize interpretation and advice to user's primary goal: {primary_goal}."
            ),
            "proactive": (
                "Be proactive and success-oriented. Use available trend/history context to define near-term checkpoints, "
                "clear success measures, and pivot triggers."
            ),
            "format": (
                "answer must be readable markdown with short sections, bullets, and spacing for easy human scanning. "
                "For image-based food/workout logs, include: Logged Update, Estimated Impact, Daily Totals Snapshot, Coach Insight, Next Task. "
                "Avoid one long paragraph."
            ),
            "must_include": [
                "answer",
                "rationale_bullets (3-7)",
                "recommended_actions (1-3 items with title + steps)",
                "suggested_questions (3-8 direct coach questions for the user to answer next)",
                "safety_flags",
            ],
        },
    }
    return json.dumps(body, separators=(",", ":"))


def _tags_from_context(payload: CoachQuestionRequest, context: dict[str, Any]) -> str:
    tags = [payload.mode.value]
    if payload.deep_think:
        tags.append("deep_think")
    if payload.context_hint:
        tags.append(payload.context_hint.lower().replace(" ", "_"))
    missing = context.get("missing_data", [])
    if missing:
        tags.append("missing_data")
    return ",".join(tags[:5])


def _cache_key(user_id: int, payload: CoachQuestionRequest) -> tuple[int, str, str, bool]:
    normalized_q = " ".join(payload.question.lower().split())
    return (user_id, normalized_q, payload.mode.value, bool(payload.deep_think))


def _cache_get(user_id: int, payload: CoachQuestionRequest) -> Optional[CoachQuestionResponse]:
    if CACHE_TTL_SECONDS <= 0:
        return None
    key = _cache_key(user_id, payload)
    entry = _COACH_RESPONSE_CACHE.get(key)
    if not entry:
        return None
    ts, response = entry
    if (time.time() - ts) > CACHE_TTL_SECONDS:
        _COACH_RESPONSE_CACHE.pop(key, None)
        return None
    return response


def _cache_set(user_id: int, payload: CoachQuestionRequest, response: CoachQuestionResponse) -> None:
    if CACHE_TTL_SECONDS <= 0:
        return
    _COACH_RESPONSE_CACHE[_cache_key(user_id, payload)] = (time.time(), response)


def _persist_summary(
    db: Session,
    user_id: int,
    question: str,
    answer: str,
    tags: str,
    safety_flags: list[str],
    agent_trace: Optional[list[dict[str, Any]]] = None,
) -> None:
    summary = ConversationSummary(
        user_id=user_id,
        created_at=datetime.now(timezone.utc),
        question=question[:512],
        answer_summary=answer[:1024],
        tags=tags or None,
        safety_flags=",".join(safety_flags) if safety_flags else None,
        agent_trace_json=(json.dumps(agent_trace, separators=(",", ":")) if agent_trace else None),
    )
    db.add(summary)
    db.commit()


@router.post("/question", response_model=CoachQuestionResponse, status_code=status.HTTP_200_OK)
def ask_coach_question(
    payload: CoachQuestionRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    llm_client: LLMClient = Depends(get_llm_client),
) -> CoachQuestionResponse:
    # Capture operational progress signals from free-form chat so summaries/agents can use them.
    _merge_chat_signals_into_daily_log(
        db=db,
        user_id=user.id,
        question=payload.question,
        llm_client=llm_client,
    )

    thread = get_or_create_chat_thread(
        db=db,
        user_id=user.id,
        question=payload.question,
        thread_id=payload.thread_id,
    )

    cached = _cache_get(user.id, payload)
    if cached is not None:
        cached.thread_id = thread.id
        cached.agent_trace = []
        persist_chat_turn(
            db=db,
            user_id=user.id,
            thread=thread,
            user_text=payload.question,
            assistant_text=cached.answer,
            mode=payload.mode.value,
        )
        _persist_summary(
            db=db,
            user_id=user.id,
            question=payload.question,
            answer=cached.answer,
            tags="cached_response",
            safety_flags=cached.safety_flags,
        )
        return cached
    urgent_flags = detect_urgent_flags(payload.question)
    if urgent_flags:
        emergency = emergency_response()
        response = CoachQuestionResponse(**emergency)
        response.thread_id = thread.id
        response.agent_trace = []
        persist_chat_turn(
            db=db,
            user_id=user.id,
            thread=thread,
            user_text=payload.question,
            assistant_text=response.answer,
            mode=payload.mode.value,
        )
        _persist_summary(
            db=db,
            user_id=user.id,
            question=payload.question,
            answer=response.answer,
            tags="safety,urgent",
            safety_flags=response.safety_flags,
        )
        return response

    context = build_coaching_context(db=db, user_id=user.id)
    if not context.get("baseline_present"):
        response = _fallback_response(
            answer=(
                "I can give more precise guidance once your baseline is complete. "
                "Please complete baseline intake first, then ask this again for personalized coaching."
            ),
            safety_flags=["baseline_missing"],
        )
        response.thread_id = thread.id
        response.agent_trace = []
        persist_chat_turn(
            db=db,
            user_id=user.id,
            thread=thread,
            user_text=payload.question,
            assistant_text=response.answer,
            mode=payload.mode.value,
        )
        _persist_summary(
            db=db,
            user_id=user.id,
            question=payload.question,
            answer=response.answer,
            tags=_tags_from_context(payload, context),
            safety_flags=response.safety_flags,
        )
        return response

    llm_error = False
    agent_trace: list[dict[str, Any]] = []
    try:
        raw_or_tuple = request_coaching_json(
            db=db,
            user_id=user.id,
            user_email=user.email,
            payload=payload,
            context=context,
            llm_client=llm_client,
            deep_think=payload.deep_think,
        )
        if isinstance(raw_or_tuple, tuple):
            response, agent_trace = raw_or_tuple
        elif isinstance(raw_or_tuple, dict):
            response = _response_from_raw(raw_or_tuple, payload.mode.value)
            agent_trace = []
        else:
            raise ValueError("Unsupported coaching response type")
    except LLMRequestError as exc:
        logger.exception("coach_llm_request_error user_id=%s detail=%s", user.id, str(exc))
        llm_error = True
        detail_flag = "llm_unavailable"
        if exc.status_code == 401:
            detail_flag = "llm_auth_error"
        elif exc.status_code == 404:
            detail_flag = "llm_model_not_found"
        elif exc.status_code == 429:
            detail_flag = "llm_rate_limited"
        elif exc.status_code and exc.status_code >= 500:
            detail_flag = "llm_provider_error"
        # Always provide practical guidance even when model generation fails.
        response = _practical_non_llm_response(payload=payload, context=context, flag=detail_flag)
    except Exception as exc:
        logger.exception("coach_unhandled_error user_id=%s detail=%s", user.id, str(exc))
        llm_error = True
        response = _fallback_response(
            answer=(
                "I could not generate a full coaching response right now. "
                "Please retry in a moment, and I can still help with a practical next step."
            ),
            safety_flags=["llm_unavailable"],
        )

    if has_supplement_topic(payload.question):
        response.safety_flags = list({*response.safety_flags, "supplement_caution"})
        response.rationale_bullets = response.rationale_bullets[:6] + [supplement_caution_text()]

    response = _apply_daily_log_nudge(response, context, payload.question)
    response = _apply_proactive_success_guidance(response, context)
    response = _apply_interaction_style(response, context, payload.question)

    if llm_error:
        response.suggested_questions = response.suggested_questions[:8]
    response.thread_id = thread.id
    response.agent_trace = _public_agent_trace(agent_trace)

    persist_chat_turn(
        db=db,
        user_id=user.id,
        thread=thread,
        user_text=payload.question,
        assistant_text=response.answer,
        mode=payload.mode.value,
    )

    _persist_summary(
        db=db,
        user_id=user.id,
        question=payload.question,
        answer=response.answer,
        tags=_tags_from_context(payload, context),
        safety_flags=response.safety_flags,
        agent_trace=agent_trace,
    )
    _cache_set(user.id, payload, response)
    return response


@router.post("/voice", response_model=CoachQuestionResponse, status_code=status.HTTP_200_OK)
def ask_coach_voice(
    payload: CoachVoiceRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    llm_client: LLMClient = Depends(get_llm_client),
) -> CoachQuestionResponse:
    # Voice path is transcript-first for MVP: no audio persistence, same coaching pipeline.
    text_payload = CoachQuestionRequest(
        question=payload.transcript,
        mode=payload.mode,
        deep_think=payload.deep_think,
        context_hint=payload.context_hint,
        thread_id=payload.thread_id,
        web_search=payload.web_search,
    )
    return ask_coach_question(payload=text_payload, user=user, db=db, llm_client=llm_client)


@router.post("/image", response_model=CoachQuestionResponse, status_code=status.HTTP_200_OK)
def ask_coach_image(
    image: UploadFile = File(...),
    question: str = Form(""),
    mode: CoachMode = Form(CoachMode.quick),
    deep_think: bool = Form(False),
    context_hint: Optional[str] = Form(default=None),
    thread_id: Optional[int] = Form(default=None),
    web_search: bool = Form(True),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    llm_client: LLMClient = Depends(get_llm_client),
) -> CoachQuestionResponse:
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image uploads are supported.")
    image_bytes = image.file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Uploaded image is empty.")
    if len(image_bytes) > COACH_IMAGE_MAX_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"Image too large. Max size is {COACH_IMAGE_MAX_BYTES // (1024 * 1024)}MB.",
        )

    prompt_text = (question or "").strip() or "Please analyze this image and provide personalized coaching guidance."
    payload = CoachQuestionRequest(
        question=prompt_text,
        mode=mode,
        deep_think=deep_think,
        context_hint=context_hint,
        thread_id=thread_id,
        web_search=web_search,
    )

    thread = get_or_create_chat_thread(
        db=db,
        user_id=user.id,
        question=f"[image] {payload.question}",
        thread_id=payload.thread_id,
    )

    urgent_flags = detect_urgent_flags(payload.question)
    if urgent_flags:
        emergency = emergency_response()
        response = CoachQuestionResponse(**emergency)
        response.thread_id = thread.id
        _persist_summary(
            db=db,
            user_id=user.id,
            question=f"[image] {payload.question}",
            answer=response.answer,
            tags="safety,urgent,image",
            safety_flags=response.safety_flags,
        )
        persist_chat_turn(
            db=db,
            user_id=user.id,
            thread=thread,
            user_text=f"[image] {payload.question}",
            assistant_text=response.answer,
            mode=payload.mode.value,
        )
        return response

    context = build_coaching_context(db=db, user_id=user.id)
    if not context.get("baseline_present"):
        response = _fallback_response(
            answer=(
                "I can give more precise guidance once your baseline is complete. "
                "Please complete baseline intake first, then upload this again for personalized coaching."
            ),
            safety_flags=["baseline_missing"],
        )
        response.thread_id = thread.id
        _persist_summary(
            db=db,
            user_id=user.id,
            question=f"[image] {payload.question}",
            answer=response.answer,
            tags="image,baseline_missing",
            safety_flags=response.safety_flags,
        )
        persist_chat_turn(
            db=db,
            user_id=user.id,
            thread=thread,
            user_text=f"[image] {payload.question}",
            assistant_text=response.answer,
            mode=payload.mode.value,
        )
        return response

    llm_error = False
    try:
        task_type = "deep_think" if (payload.mode == CoachMode.deep or payload.deep_think) else "reasoning"
        raw = llm_client.generate_json_from_image(
            db=db,
            user_id=user.id,
            prompt=_build_image_prompt(
                question=payload.question,
                context_hint=payload.context_hint,
                context=context,
                mode=payload.mode.value,
                web_search_enabled=payload.web_search,
            ),
            image_bytes=image_bytes,
            image_mime_type=image.content_type,
            task_type=task_type,
            allow_web_search=payload.web_search,
        )
        response = _response_from_raw(raw, payload.mode.value)
    except LLMRequestError as exc:
        logger.exception("coach_llm_image_request_error user_id=%s detail=%s", user.id, str(exc))
        llm_error = True
        detail_flag = "llm_unavailable"
        if exc.status_code == 401:
            detail_flag = "llm_auth_error"
        elif exc.status_code == 404:
            detail_flag = "llm_model_not_found"
        elif exc.status_code == 429:
            detail_flag = "llm_rate_limited"
        elif exc.status_code and exc.status_code >= 500:
            detail_flag = "llm_provider_error"
        response = _practical_non_llm_response(payload=payload, context=context, flag=detail_flag)
    except Exception as exc:
        logger.exception("coach_image_unhandled_error user_id=%s detail=%s", user.id, str(exc))
        llm_error = True
        response = _fallback_response(
            answer=(
                "I could not process the image right now. Please retry in a moment, "
                "or ask your question in text and I can still help."
            ),
            safety_flags=["llm_unavailable"],
        )

    if has_supplement_topic(payload.question):
        response.safety_flags = list({*response.safety_flags, "supplement_caution"})
        response.rationale_bullets = response.rationale_bullets[:6] + [supplement_caution_text()]

    response = _apply_daily_log_nudge(response, context, payload.question)
    response = _apply_proactive_success_guidance(response, context)
    response = _apply_interaction_style(response, context, payload.question)
    if llm_error:
        response.suggested_questions = response.suggested_questions[:8]
    response.thread_id = thread.id
    response.agent_trace = []

    persist_chat_turn(
        db=db,
        user_id=user.id,
        thread=thread,
        user_text=f"[image] {payload.question}",
        assistant_text=response.answer,
        mode=payload.mode.value,
    )

    _persist_summary(
        db=db,
        user_id=user.id,
        question=f"[image:{image.filename or 'upload'}] {payload.question}",
        answer=response.answer,
        tags="image," + _tags_from_context(payload, context),
        safety_flags=response.safety_flags,
    )
    return response
