from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Path, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.db.models import DailyLog, User
from app.db.session import get_db

router = APIRouter(prefix="/daily-log", tags=["daily-log"])


class DailyLogUpsertRequest(BaseModel):
    sleep_hours: float = Field(ge=0, le=16)
    energy: int = Field(ge=1, le=10)
    mood: int = Field(ge=1, le=10)
    stress: int = Field(ge=1, le=10)
    training_done: bool = False
    nutrition_on_plan: bool = False
    notes: Optional[str] = Field(default=None, max_length=1200)


class DailyLogItem(BaseModel):
    log_date: date
    sleep_hours: float
    energy: int
    mood: int
    stress: int
    training_done: bool
    nutrition_on_plan: bool
    notes: Optional[str] = None
    updated_at: datetime


class DailyLogListResponse(BaseModel):
    items: list[DailyLogItem]


def _to_item(row: DailyLog) -> DailyLogItem:
    return DailyLogItem(
        log_date=row.log_date,
        sleep_hours=row.sleep_hours,
        energy=row.energy,
        mood=row.mood,
        stress=row.stress,
        training_done=row.training_done,
        nutrition_on_plan=row.nutrition_on_plan,
        notes=row.notes,
        updated_at=row.updated_at,
    )


@router.put("/{log_date}", response_model=DailyLogItem, status_code=status.HTTP_200_OK)
def upsert_daily_log(
    payload: DailyLogUpsertRequest,
    log_date: date = Path(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DailyLogItem:
    row = db.query(DailyLog).filter(DailyLog.user_id == user.id, DailyLog.log_date == log_date).first()
    if not row:
        row = DailyLog(user_id=user.id, log_date=log_date)
        db.add(row)
    row.sleep_hours = payload.sleep_hours
    row.energy = payload.energy
    row.mood = payload.mood
    row.stress = payload.stress
    row.training_done = payload.training_done
    row.nutrition_on_plan = payload.nutrition_on_plan
    row.notes = payload.notes
    db.commit()
    db.refresh(row)
    return _to_item(row)


@router.get("", response_model=DailyLogListResponse)
def list_daily_logs(
    from_date: Optional[date] = Query(default=None, alias="from"),
    to_date: Optional[date] = Query(default=None, alias="to"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DailyLogListResponse:
    today = datetime.now(timezone.utc).date()
    start = from_date or (today - timedelta(days=29))
    end = to_date or today
    rows = (
        db.query(DailyLog)
        .filter(DailyLog.user_id == user.id, DailyLog.log_date >= start, DailyLog.log_date <= end)
        .order_by(DailyLog.log_date.desc())
        .all()
    )
    return DailyLogListResponse(items=[_to_item(row) for row in rows])
