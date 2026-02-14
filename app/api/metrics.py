from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.db.models import Metric, User
from app.db.session import get_db

router = APIRouter(prefix="/metrics", tags=["metrics"])


class MetricType(str, Enum):
    weight_kg = "weight_kg"
    waist_cm = "waist_cm"
    bp_systolic = "bp_systolic"
    bp_diastolic = "bp_diastolic"
    resting_hr_bpm = "resting_hr_bpm"
    sleep_hours = "sleep_hours"
    steps = "steps"
    active_minutes = "active_minutes"
    energy_1_10 = "energy_1_10"
    mood_1_10 = "mood_1_10"
    stress_1_10 = "stress_1_10"
    sleep_quality_1_10 = "sleep_quality_1_10"
    motivation_1_10 = "motivation_1_10"


METRIC_RULES: dict[MetricType, tuple[float, float, bool]] = {
    MetricType.weight_kg: (30, 350, False),
    MetricType.waist_cm: (40, 250, False),
    MetricType.bp_systolic: (70, 240, True),
    MetricType.bp_diastolic: (40, 150, True),
    MetricType.resting_hr_bpm: (30, 220, True),
    MetricType.sleep_hours: (0, 16, False),
    MetricType.steps: (0, 100000, True),
    MetricType.active_minutes: (0, 600, True),
    MetricType.energy_1_10: (1, 10, True),
    MetricType.mood_1_10: (1, 10, True),
    MetricType.stress_1_10: (1, 10, True),
    MetricType.sleep_quality_1_10: (1, 10, True),
    MetricType.motivation_1_10: (1, 10, True),
}


class MetricWriteRequest(BaseModel):
    metric_type: MetricType
    value: float
    taken_at: Optional[datetime] = None


class MetricItem(BaseModel):
    id: int
    metric_type: MetricType
    value: float
    taken_at: datetime


class MetricListResponse(BaseModel):
    items: list[MetricItem]


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _validate_metric(metric_type: MetricType, value: float) -> None:
    lower, upper, must_be_int = METRIC_RULES[metric_type]
    if value < lower or value > upper:
        raise HTTPException(status_code=422, detail=f"value out of range for {metric_type.value}")
    if must_be_int and int(value) != value:
        raise HTTPException(status_code=422, detail=f"value for {metric_type.value} must be an integer")


@router.post("", response_model=MetricItem, status_code=status.HTTP_201_CREATED)
def create_metric(
    payload: MetricWriteRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MetricItem:
    _validate_metric(payload.metric_type, payload.value)
    taken_at = _to_utc(payload.taken_at or datetime.now(timezone.utc))
    record = Metric(
        user_id=user.id,
        metric_type=payload.metric_type.value,
        value_num=float(payload.value),
        taken_at=taken_at,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return MetricItem(
        id=record.id,
        metric_type=MetricType(record.metric_type),
        value=record.value_num,
        taken_at=record.taken_at,
    )


@router.get("", response_model=MetricListResponse)
def list_metrics(
    metric_type: Optional[MetricType] = None,
    from_ts: Optional[datetime] = Query(default=None, alias="from"),
    to_ts: Optional[datetime] = Query(default=None, alias="to"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MetricListResponse:
    query = db.query(Metric).filter(Metric.user_id == user.id)
    if metric_type:
        query = query.filter(Metric.metric_type == metric_type.value)
    if from_ts:
        query = query.filter(Metric.taken_at >= _to_utc(from_ts))
    if to_ts:
        query = query.filter(Metric.taken_at <= _to_utc(to_ts))

    rows = query.order_by(Metric.taken_at.asc()).all()
    items = [
        MetricItem(
            id=row.id,
            metric_type=MetricType(row.metric_type),
            value=row.value_num,
            taken_at=row.taken_at,
        )
        for row in rows
    ]
    return MetricListResponse(items=items)
