from datetime import datetime, timedelta, timezone
from typing import Optional, Union

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.db.models import Baseline, ConversationSummary, DailyLog, Metric, User
from app.db.session import get_db

router = APIRouter(prefix="/summary", tags=["summary"])


class DailySnapshot(BaseModel):
    log_date: Optional[str] = None
    sleep_hours: Optional[float] = None
    energy: Optional[int] = None
    mood: Optional[int] = None
    stress: Optional[int] = None
    training_done: Optional[bool] = None
    nutrition_on_plan: Optional[bool] = None
    notes: Optional[str] = None


class TrendWindowSummary(BaseModel):
    days: int
    entries: int
    avg_sleep_hours: Optional[float] = None
    avg_energy: Optional[float] = None
    avg_mood: Optional[float] = None
    avg_stress: Optional[float] = None
    training_adherence_pct: Optional[float] = None
    nutrition_adherence_pct: Optional[float] = None


class OverallSummaryResponse(BaseModel):
    health_score: int
    category_scores: dict[str, int]
    today: DailySnapshot
    trend_7d: TrendWindowSummary
    trend_30d: TrendWindowSummary
    wellness_report: list[dict[str, Union[str, int]]]
    weekly_personalized_insights: list[str]
    personalized_journey: dict[str, Union[str, list[dict[str, str]], list[str]]]
    top_wins: list[str]
    top_risks: list[str]
    next_best_action: str
    summary_generated_at: str


def _avg(values: list[float]) -> Optional[float]:
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def _window_summary(rows: list[DailyLog], days: int) -> TrendWindowSummary:
    sleep = [row.sleep_hours for row in rows]
    energy = [float(row.energy) for row in rows]
    mood = [float(row.mood) for row in rows]
    stress = [float(row.stress) for row in rows]
    training_rate = (sum(1 for row in rows if row.training_done) / len(rows) * 100.0) if rows else None
    nutrition_rate = (sum(1 for row in rows if row.nutrition_on_plan) / len(rows) * 100.0) if rows else None
    return TrendWindowSummary(
        days=days,
        entries=len(rows),
        avg_sleep_hours=_avg(sleep),
        avg_energy=_avg(energy),
        avg_mood=_avg(mood),
        avg_stress=_avg(stress),
        training_adherence_pct=(round(training_rate, 1) if training_rate is not None else None),
        nutrition_adherence_pct=(round(nutrition_rate, 1) if nutrition_rate is not None else None),
    )


def _wins_and_risks(
    trend_7d: TrendWindowSummary, trend_30d: TrendWindowSummary, baseline: Optional[Baseline]
) -> tuple[list[str], list[str], str]:
    wins: list[str] = []
    risks: list[str] = []

    if trend_7d.entries >= 3 and trend_7d.avg_sleep_hours is not None and trend_7d.avg_sleep_hours >= 7.0:
        wins.append("Sleep is trending in a strong range over the last 7 days.")
    if trend_7d.training_adherence_pct is not None and trend_7d.training_adherence_pct >= 60.0:
        wins.append("Training consistency is solid this week.")
    if trend_7d.nutrition_adherence_pct is not None and trend_7d.nutrition_adherence_pct >= 60.0:
        wins.append("Nutrition adherence is holding steady this week.")
    if trend_7d.avg_stress is not None and trend_7d.avg_stress <= 5.0:
        wins.append("Stress load is in a manageable range.")

    if trend_7d.avg_sleep_hours is not None and trend_7d.avg_sleep_hours < 6.0:
        risks.append("Sleep is below target and may limit recovery and energy.")
    if trend_7d.avg_stress is not None and trend_7d.avg_stress >= 7.0:
        risks.append("Stress is elevated and should be prioritized.")
    if trend_7d.training_adherence_pct is not None and trend_7d.training_adherence_pct < 30.0:
        risks.append("Training consistency is low, which can slow progress.")
    if trend_7d.nutrition_adherence_pct is not None and trend_7d.nutrition_adherence_pct < 40.0:
        risks.append("Nutrition adherence is inconsistent, reducing plan signal quality.")

    if baseline:
        if baseline.systolic_bp >= 140 or baseline.diastolic_bp >= 90:
            risks.append("Baseline blood pressure suggests elevated cardiometabolic risk.")
        if baseline.primary_goal and not wins:
            wins.append(f"Baseline goal focus remains clear: {baseline.primary_goal}.")

    if not wins:
        wins.append("Daily tracking is building a stronger coaching signal.")
    if not risks:
        risks.append("No major risk spikes detected from current daily log signal.")

    if trend_7d.avg_sleep_hours is not None and trend_7d.avg_sleep_hours < 6.5:
        action = "Protect a fixed sleep window for the next 7 days and log adherence daily."
    elif trend_7d.avg_stress is not None and trend_7d.avg_stress >= 7.0:
        action = "Run one 10-minute daily stress downshift routine and track stress before bed."
    elif trend_7d.training_adherence_pct is not None and trend_7d.training_adherence_pct < 50.0:
        action = "Schedule 3 realistic training sessions this week and mark completion in daily log."
    else:
        action = "Pick one measurable habit tied to your primary goal and execute it daily for 7 days."
    return wins[:4], risks[:4], action


def _clamp_score(value: float) -> int:
    return int(max(0, min(100, round(value))))


def _calc_body_composition_score(baseline: Optional[Baseline], recent_metrics: list[Metric]) -> int:
    waist = baseline.waist if baseline and baseline.waist else 0.0
    waist_component = 70.0 if waist <= 0 else max(0.0, 100.0 - max(0.0, waist - 85.0) * 1.4)
    weight_values = [row.value_num for row in recent_metrics if row.metric_type == "weight_kg"]
    stability = 85.0
    if len(weight_values) >= 2:
        delta = abs(weight_values[-1] - weight_values[0])
        stability = max(50.0, 100.0 - delta * 6.0)
    return _clamp_score((waist_component * 0.65) + (stability * 0.35))


def _calc_nutrition_score(rows_7: list[DailyLog]) -> int:
    if not rows_7:
        return 60
    adherence = sum(1 for row in rows_7 if row.nutrition_on_plan) / len(rows_7)
    return _clamp_score(adherence * 100.0)


def _calc_movement_score(rows_7: list[DailyLog], recent_metrics: list[Metric]) -> int:
    training_component = 55.0
    if rows_7:
        training_component = (sum(1 for row in rows_7 if row.training_done) / len(rows_7)) * 100.0
    steps = [row.value_num for row in recent_metrics if row.metric_type == "steps"]
    active = [row.value_num for row in recent_metrics if row.metric_type == "active_minutes"]
    steps_component = min(100.0, ((sum(steps) / len(steps)) / 8000.0) * 100.0) if steps else 55.0
    active_component = min(100.0, ((sum(active) / len(active)) / 45.0) * 100.0) if active else 55.0
    return _clamp_score((training_component * 0.4) + (steps_component * 0.35) + (active_component * 0.25))


def _calc_sleep_score(trend_7d: TrendWindowSummary) -> int:
    if trend_7d.avg_sleep_hours is None:
        return 65
    return _clamp_score((trend_7d.avg_sleep_hours / 8.0) * 100.0)


def _calc_stress_score(trend_7d: TrendWindowSummary) -> int:
    if trend_7d.avg_stress is None:
        return 65
    return _clamp_score(100.0 - ((trend_7d.avg_stress - 1.0) / 9.0) * 100.0)


def _status_for_score(score: int) -> str:
    if score >= 80:
        return "strong"
    if score >= 65:
        return "stable"
    if score >= 50:
        return "needs_attention"
    return "priority"


def _build_wellness_report(category_scores: dict[str, int]) -> list[dict[str, Union[str, int]]]:
    report: list[dict[str, Union[str, int]]] = []
    for domain, score in category_scores.items():
        report.append(
            {
                "domain": domain,
                "score": score,
                "status": _status_for_score(score),
                "summary": f"{domain} is currently {_status_for_score(score).replace('_', ' ')}.",
            }
        )
    return report


def _build_weekly_insights(category_scores: dict[str, int], baseline: Optional[Baseline]) -> list[str]:
    items: list[tuple[str, int]] = sorted(category_scores.items(), key=lambda pair: pair[1])
    weakest = items[:2]
    goal = baseline.primary_goal if baseline and baseline.primary_goal else "your goal"
    insights: list[str] = [f"This week, prioritize {weakest[0][0].lower()} and {weakest[1][0].lower()} to support {goal}."]
    for domain, score in weakest:
        if domain == "Sleep":
            insights.append("Set a fixed bedtime window for 7 days and log actual sleep hours daily.")
        elif domain == "Stress":
            insights.append("Use one daily 10-minute stress reset and log pre/post stress scores.")
        elif domain == "Movement":
            insights.append("Schedule 3 realistic training sessions and track completion in daily log.")
        elif domain == "Nutrition":
            insights.append("Pre-plan your highest-risk meal each day and mark nutrition adherence.")
        elif domain == "Body Composition":
            insights.append("Track waist and weight trend weekly while keeping daily nutrition/movement consistent.")
    return insights[:3]


def _build_personalized_journey(
    *,
    trend_7d: TrendWindowSummary,
    trend_30d: TrendWindowSummary,
    baseline: Optional[Baseline],
    recent_metrics: list[Metric],
) -> dict[str, Union[str, list[dict[str, str]], list[str]]]:
    signals: list[dict[str, str]] = []
    measures: list[str] = []

    if trend_7d.avg_sleep_hours is not None and trend_7d.avg_sleep_hours < 6.0:
        signals.append(
            {
                "pattern": "Low sleep pattern",
                "evidence": f"7-day average sleep is {trend_7d.avg_sleep_hours}h",
                "potential_issue": "lower recovery capacity and daytime energy",
                "prevention_focus": "protect a fixed sleep window and reduce late stimulants",
            }
        )
        measures.append("Set a fixed bedtime/wake time for 7 days and log adherence daily.")

    if trend_7d.avg_stress is not None and trend_7d.avg_stress >= 7.0:
        signals.append(
            {
                "pattern": "Elevated stress pattern",
                "evidence": f"7-day average stress is {trend_7d.avg_stress}/10",
                "potential_issue": "fatigue, poor sleep quality, and consistency drops",
                "prevention_focus": "daily stress downshift routine and workload pacing",
            }
        )
        measures.append("Run one 10-minute daily stress reset and log stress before/after.")

    if trend_7d.training_adherence_pct is not None and trend_7d.training_adherence_pct < 30.0:
        signals.append(
            {
                "pattern": "Low movement consistency",
                "evidence": f"Training adherence is {trend_7d.training_adherence_pct}%",
                "potential_issue": "slower body composition and metabolic progress",
                "prevention_focus": "schedule smaller, realistic movement blocks",
            }
        )
        measures.append("Pre-schedule 3 realistic sessions this week and mark completion each day.")

    if baseline and (baseline.systolic_bp >= 140 or baseline.diastolic_bp >= 90):
        signals.append(
            {
                "pattern": "Elevated baseline blood pressure signal",
                "evidence": f"Baseline BP recorded as {baseline.systolic_bp}/{baseline.diastolic_bp}",
                "potential_issue": "higher cardiometabolic risk trend over time",
                "prevention_focus": "track BP regularly and prioritize sleep/stress/nutrition consistency",
            }
        )
        measures.append("Recheck BP at consistent times during the week and review trend direction.")

    weight_values = [row.value_num for row in recent_metrics if row.metric_type == "weight_kg"]
    if len(weight_values) >= 2:
        drift = weight_values[-1] - weight_values[0]
        if abs(drift) >= 1.5:
            direction = "upward" if drift > 0 else "downward"
            signals.append(
                {
                    "pattern": "Weight trend shift",
                    "evidence": f"30-day weight trend is {direction} ({round(drift, 2)} kg)",
                    "potential_issue": "body composition drift away from target trajectory",
                    "prevention_focus": "tighten nutrition and movement consistency for 2 weeks",
                }
            )
            measures.append("Track nutrition adherence daily and review average weekly weight trend.")

    if not signals:
        signals.append(
            {
                "pattern": "Stable baseline pattern",
                "evidence": "No major adverse trend detected in current signal window",
                "potential_issue": "risk of losing momentum without consistent logging",
                "prevention_focus": "maintain daily logging and weekly review cadence",
            }
        )
        measures.append("Keep daily logs consistent for another 14 days to strengthen early detection.")

    if not measures:
        measures.append("Continue consistent daily logging and weekly trend review.")

    narrative = (
        "Your Personalized Journey highlights early trend patterns from your health data so you can "
        "act early with preventive habits. These are coaching signals, not a medical diagnosis."
    )
    return {
        "narrative": narrative,
        "pattern_signals": signals[:5],
        "prevention_measures": measures[:5],
    }


@router.get("/overall", response_model=OverallSummaryResponse)
def get_overall_summary(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OverallSummaryResponse:
    now = datetime.now(timezone.utc)
    today = now.date()
    since_7 = today - timedelta(days=6)
    since_30 = today - timedelta(days=29)

    rows_30 = (
        db.query(DailyLog)
        .filter(DailyLog.user_id == user.id, DailyLog.log_date >= since_30, DailyLog.log_date <= today)
        .order_by(DailyLog.log_date.desc())
        .all()
    )
    recent_metrics = (
        db.query(Metric)
        .filter(Metric.user_id == user.id, Metric.taken_at >= (now - timedelta(days=30)), Metric.taken_at <= now)
        .order_by(Metric.taken_at.asc())
        .all()
    )
    rows_7 = [row for row in rows_30 if row.log_date >= since_7]
    latest = rows_30[0] if rows_30 else None

    baseline = db.query(Baseline).filter(Baseline.user_id == user.id).first()
    recent_summary = (
        db.query(ConversationSummary)
        .filter(ConversationSummary.user_id == user.id)
        .order_by(ConversationSummary.created_at.desc())
        .first()
    )
    trend_7d = _window_summary(rows_7, days=7)
    trend_30d = _window_summary(rows_30, days=30)
    category_scores = {
        "Body Composition": _calc_body_composition_score(baseline, recent_metrics),
        "Nutrition": _calc_nutrition_score(rows_7),
        "Movement": _calc_movement_score(rows_7, recent_metrics),
        "Sleep": _calc_sleep_score(trend_7d),
        "Stress": _calc_stress_score(trend_7d),
    }
    health_score = _clamp_score(sum(category_scores.values()) / max(1, len(category_scores)))
    wellness_report = _build_wellness_report(category_scores)
    weekly_insights = _build_weekly_insights(category_scores, baseline)
    personalized_journey = _build_personalized_journey(
        trend_7d=trend_7d,
        trend_30d=trend_30d,
        baseline=baseline,
        recent_metrics=recent_metrics,
    )
    wins, risks, action = _wins_and_risks(trend_7d, trend_30d, baseline)
    if recent_summary and "llm_" in str(recent_summary.safety_flags or ""):
        risks = (["Recent AI provider instability detected. Retry if fallback guidance appears."] + risks)[:4]

    today_snapshot = DailySnapshot(
        log_date=(latest.log_date.isoformat() if latest else None),
        sleep_hours=(latest.sleep_hours if latest else None),
        energy=(latest.energy if latest else None),
        mood=(latest.mood if latest else None),
        stress=(latest.stress if latest else None),
        training_done=(latest.training_done if latest else None),
        nutrition_on_plan=(latest.nutrition_on_plan if latest else None),
        notes=(latest.notes if latest else None),
    )
    return OverallSummaryResponse(
        health_score=health_score,
        category_scores=category_scores,
        today=today_snapshot,
        trend_7d=trend_7d,
        trend_30d=trend_30d,
        wellness_report=wellness_report,
        weekly_personalized_insights=weekly_insights,
        personalized_journey=personalized_journey,
        top_wins=wins,
        top_risks=risks,
        next_best_action=action,
        summary_generated_at=now.isoformat(),
    )
