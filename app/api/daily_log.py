import json
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, Path, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.db.models import DailyLog, User
from app.db.session import get_db

router = APIRouter(prefix="/daily-log", tags=["daily-log"])


class DailyLogUpsertRequest(BaseModel):
    sleep_hours: Optional[float] = Field(default=None, ge=0, le=16)
    energy: Optional[int] = Field(default=None, ge=1, le=10)
    mood: Optional[int] = Field(default=None, ge=1, le=10)
    stress: Optional[int] = Field(default=None, ge=1, le=10)
    training_done: Optional[bool] = None
    nutrition_on_plan: Optional[bool] = None
    notes: Optional[str] = Field(default=None, max_length=1200)
    checkin_payload_json: Optional[dict[str, Any]] = None


class DailyLogItem(BaseModel):
    log_date: date
    sleep_hours: float
    energy: int
    mood: int
    stress: int
    training_done: bool
    nutrition_on_plan: bool
    notes: Optional[str] = None
    checkin_payload_json: Optional[dict[str, Any]] = None
    updated_at: datetime


class DailyLogListResponse(BaseModel):
    items: list[DailyLogItem]


def _to_item(row: DailyLog) -> DailyLogItem:
    parsed_checkin_payload: Optional[dict[str, Any]] = None
    if row.checkin_payload_json:
        try:
            loaded = json.loads(row.checkin_payload_json)
            if isinstance(loaded, dict):
                parsed_checkin_payload = loaded
        except json.JSONDecodeError:
            parsed_checkin_payload = None
    return DailyLogItem(
        log_date=row.log_date,
        sleep_hours=row.sleep_hours,
        energy=row.energy,
        mood=row.mood,
        stress=row.stress,
        training_done=row.training_done,
        nutrition_on_plan=row.nutrition_on_plan,
        notes=row.notes,
        checkin_payload_json=parsed_checkin_payload,
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
    row.sleep_hours = (
        payload.sleep_hours
        if payload.sleep_hours is not None
        else (row.sleep_hours if row.sleep_hours is not None else 0.0)
    )
    row.energy = (
        payload.energy
        if payload.energy is not None
        else (row.energy if row.energy is not None else 5)
    )
    row.mood = (
        payload.mood
        if payload.mood is not None
        else (row.mood if row.mood is not None else 5)
    )
    row.stress = (
        payload.stress
        if payload.stress is not None
        else (row.stress if row.stress is not None else 5)
    )
    row.training_done = (
        payload.training_done
        if payload.training_done is not None
        else bool(row.training_done)
    )
    row.nutrition_on_plan = (
        payload.nutrition_on_plan
        if payload.nutrition_on_plan is not None
        else bool(row.nutrition_on_plan)
    )
    if payload.notes is not None:
        row.notes = payload.notes
    if payload.checkin_payload_json is not None:
        row.checkin_payload_json = json.dumps(payload.checkin_payload_json, separators=(",", ":"))
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
