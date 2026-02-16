import csv
import io
from datetime import datetime
from enum import Enum
from typing import Optional

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.db.models import FeedbackEntry, User
from app.db.session import get_db

router = APIRouter(prefix="/feedback", tags=["feedback"])


class FeedbackCategory(str, Enum):
    feature = "feature"
    idea = "idea"
    bug = "bug"


class FeedbackCreateRequest(BaseModel):
    category: FeedbackCategory
    title: str = Field(min_length=3, max_length=160)
    details: str = Field(min_length=5, max_length=4000)
    page: Optional[str] = Field(default=None, max_length=80)


class FeedbackCreateResponse(BaseModel):
    id: int
    created_at: datetime


class FeedbackClearResponse(BaseModel):
    deleted_rows: int


@router.post("/entries", response_model=FeedbackCreateResponse, status_code=status.HTTP_201_CREATED)
def create_feedback_entry(
    payload: FeedbackCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FeedbackCreateResponse:
    row = FeedbackEntry(
        user_id=user.id,
        user_email=user.email,
        category=payload.category.value,
        title=payload.title.strip(),
        details=payload.details.strip(),
        page=(payload.page or "").strip() or None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return FeedbackCreateResponse(id=row.id, created_at=row.created_at)


@router.get("/entries/export")
def export_feedback_csv(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    # Any authenticated user can export the shared capture list.
    _ = user
    rows = db.query(FeedbackEntry).order_by(FeedbackEntry.created_at.desc(), FeedbackEntry.id.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "created_at", "category", "title", "details", "page", "user_id", "user_email"])
    for row in rows:
        writer.writerow(
            [
                row.id,
                row.created_at.isoformat(),
                row.category,
                row.title,
                row.details,
                row.page or "",
                row.user_id,
                row.user_email,
            ]
        )
    csv_content = output.getvalue()
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="feedback_entries.csv"'},
    )


@router.delete("/entries", response_model=FeedbackClearResponse)
def clear_feedback_entries(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FeedbackClearResponse:
    # Any authenticated user can clear the shared capture list.
    _ = user
    deleted_rows = db.query(FeedbackEntry).delete(synchronize_session=False)
    db.commit()
    return FeedbackClearResponse(deleted_rows=int(deleted_rows or 0))
