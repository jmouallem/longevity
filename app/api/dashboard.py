from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.scoring import ensure_fresh_scores
from app.db.models import Metric, User
from app.db.session import get_db

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class ScoreSummary(BaseModel):
    sleep_score: int
    metabolic_score: int
    recovery_score: int
    behavioral_score: int
    fitness_score: int
    computed_at: datetime


class CompositeSummary(BaseModel):
    longevity_score: int
    computed_at: datetime


class TrendPoint(BaseModel):
    taken_at: datetime
    value: float


class DashboardSummaryResponse(BaseModel):
    domain_scores: ScoreSummary
    composite_score: CompositeSummary
    trends: dict[str, list[TrendPoint]]


def _trend(db: Session, user_id: int, metric_type: str, start: datetime) -> list[TrendPoint]:
    rows = (
        db.query(Metric)
        .filter(Metric.user_id == user_id, Metric.metric_type == metric_type, Metric.taken_at >= start)
        .order_by(Metric.taken_at.asc())
        .all()
    )
    return [TrendPoint(taken_at=row.taken_at, value=row.value_num) for row in rows]


@router.get("/summary", response_model=DashboardSummaryResponse)
def get_dashboard_summary(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> DashboardSummaryResponse:
    domain, composite = ensure_fresh_scores(db, user_id=user.id)

    since = datetime.now(timezone.utc) - timedelta(days=7)
    trends = {
        "sleep_hours": _trend(db, user.id, "sleep_hours", since),
        "weight_kg": _trend(db, user.id, "weight_kg", since),
        "bp_systolic": _trend(db, user.id, "bp_systolic", since),
        "bp_diastolic": _trend(db, user.id, "bp_diastolic", since),
        "energy_1_10": _trend(db, user.id, "energy_1_10", since),
    }

    return DashboardSummaryResponse(
        domain_scores=ScoreSummary(
            sleep_score=domain.sleep_score,
            metabolic_score=domain.metabolic_score,
            recovery_score=domain.recovery_score,
            behavioral_score=domain.behavioral_score,
            fitness_score=domain.fitness_score,
            computed_at=domain.computed_at,
        ),
        composite_score=CompositeSummary(
            longevity_score=composite.longevity_score,
            computed_at=composite.computed_at,
        ),
        trends=trends,
    )
