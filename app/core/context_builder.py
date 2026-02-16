import json
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.db.models import Baseline, CompositeScore, ConversationSummary, DailyLog, DomainScore, Metric

CONTEXT_METRIC_TYPES = [
    "sleep_hours",
    "bp_systolic",
    "bp_diastolic",
    "weight_kg",
    "energy_1_10",
    "mood_1_10",
    "stress_1_10",
    "steps",
    "active_minutes",
]


def _avg(values: list[float]) -> Optional[float]:
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def _latest(values: list[float]) -> Optional[float]:
    if not values:
        return None
    return round(values[-1], 2)


def build_coaching_context(db: Session, user_id: int) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=7)

    baseline = db.query(Baseline).filter(Baseline.user_id == user_id).first()
    metrics = (
        db.query(Metric)
        .filter(Metric.user_id == user_id, Metric.taken_at >= since, Metric.metric_type.in_(CONTEXT_METRIC_TYPES))
        .order_by(Metric.taken_at.asc())
        .all()
    )
    latest_domain = (
        db.query(DomainScore)
        .filter(DomainScore.user_id == user_id)
        .order_by(DomainScore.computed_at.desc())
        .first()
    )
    latest_composite = (
        db.query(CompositeScore)
        .filter(CompositeScore.user_id == user_id)
        .order_by(CompositeScore.computed_at.desc())
        .first()
    )
    recent_summaries = (
        db.query(ConversationSummary)
        .filter(ConversationSummary.user_id == user_id)
        .order_by(ConversationSummary.created_at.desc())
        .limit(5)
        .all()
    )
    recent_daily_logs = (
        db.query(DailyLog)
        .filter(DailyLog.user_id == user_id, DailyLog.log_date >= since.date())
        .order_by(DailyLog.log_date.desc())
        .all()
    )

    by_type: dict[str, list[float]] = {}
    for item in metrics:
        by_type.setdefault(item.metric_type, []).append(item.value_num)

    metric_summary: dict[str, dict[str, Optional[float]]] = {}
    for metric_type in CONTEXT_METRIC_TYPES:
        values = by_type.get(metric_type, [])
        metric_summary[metric_type] = {
            "count": len(values),
            "latest": _latest(values),
            "avg_7d": _avg(values),
        }

    baseline_summary = None
    if baseline:
        top_goals: list[str] = []
        if baseline.top_goals_json:
            try:
                parsed = json.loads(baseline.top_goals_json)
                if isinstance(parsed, list):
                    top_goals = [str(item).strip() for item in parsed if str(item).strip()][:5]
            except json.JSONDecodeError:
                top_goals = []
        baseline_summary = {
            "primary_goal": baseline.primary_goal,
            "top_goals": top_goals,
            "goal_notes": baseline.goal_notes,
            "age_years": baseline.age_years,
            "sex_at_birth": baseline.sex_at_birth,
            "activity_level": baseline.activity_level,
            "sleep_hours": baseline.sleep_hours,
            "stress": baseline.stress,
            "energy": baseline.energy,
            "waist": baseline.waist,
            "systolic_bp": baseline.systolic_bp,
            "diastolic_bp": baseline.diastolic_bp,
            "resting_hr": baseline.resting_hr,
        }

    score_summary = None
    if latest_domain and latest_composite:
        score_summary = {
            "domain_scores": {
                "sleep_score": latest_domain.sleep_score,
                "metabolic_score": latest_domain.metabolic_score,
                "recovery_score": latest_domain.recovery_score,
                "behavioral_score": latest_domain.behavioral_score,
                "fitness_score": latest_domain.fitness_score,
                "computed_at": latest_domain.computed_at.isoformat(),
            },
            "composite_score": {
                "longevity_score": latest_composite.longevity_score,
                "computed_at": latest_composite.computed_at.isoformat(),
            },
        }

    missing_data = [k for k, v in metric_summary.items() if v["count"] == 0]
    recent_conversations = [
        {
            "question": row.question,
            "answer_summary": row.answer_summary,
            "tags": row.tags,
            "safety_flags": row.safety_flags,
            "created_at": row.created_at.isoformat(),
        }
        for row in recent_summaries
    ]
    latest_daily_log = recent_daily_logs[0] if recent_daily_logs else None
    daily_log_summary = {
        "entries_7d": len(recent_daily_logs),
        "latest_log_date": (latest_daily_log.log_date.isoformat() if latest_daily_log else None),
    }

    return {
        "baseline_present": baseline is not None,
        "baseline": baseline_summary,
        "metrics_7d_summary": metric_summary,
        "daily_log_summary": daily_log_summary,
        "latest_scores": score_summary,
        "missing_data": missing_data,
        "recent_conversations": recent_conversations,
    }
