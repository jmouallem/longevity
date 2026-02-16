from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.db.models import ChatMessage, ChatThread, User
from app.db.session import get_db

router = APIRouter(prefix="/chat", tags=["chat"])


class ThreadCreateRequest(BaseModel):
    title: Optional[str] = Field(default=None, max_length=180)


class ThreadItem(BaseModel):
    thread_id: int
    title: str
    message_count: int
    updated_at: str


class ThreadListResponse(BaseModel):
    items: list[ThreadItem]


class MessageItem(BaseModel):
    id: int
    role: str
    content: str
    mode: Optional[str] = None
    created_at: str


class ThreadMessagesResponse(BaseModel):
    thread_id: int
    title: str
    messages: list[MessageItem]


def get_or_create_chat_thread(
    db: Session,
    *,
    user_id: int,
    question: str,
    thread_id: Optional[int],
) -> ChatThread:
    if thread_id is not None:
        thread = (
            db.query(ChatThread)
            .filter(ChatThread.id == thread_id, ChatThread.user_id == user_id)
            .first()
        )
        if not thread:
            raise HTTPException(status_code=404, detail="Chat thread not found")
        return thread

    first_line = " ".join((question or "").strip().split())
    title = first_line[:90] if first_line else "New Chat"
    if len(first_line) > 90:
        title = f"{title.rstrip()}..."
    thread = ChatThread(
        user_id=user_id,
        title=title or "New Chat",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        last_message_at=datetime.now(timezone.utc),
    )
    db.add(thread)
    db.flush()
    return thread


def persist_chat_turn(
    db: Session,
    *,
    user_id: int,
    thread: ChatThread,
    user_text: str,
    assistant_text: str,
    mode: Optional[str],
) -> None:
    now = datetime.now(timezone.utc)
    user_msg = ChatMessage(
        thread_id=thread.id,
        user_id=user_id,
        role="user",
        content=user_text[:8000],
        mode=mode,
        created_at=now,
    )
    assistant_msg = ChatMessage(
        thread_id=thread.id,
        user_id=user_id,
        role="assistant",
        content=assistant_text[:20000],
        mode=mode,
        created_at=now,
    )
    thread.last_message_at = now
    thread.updated_at = now
    db.add(user_msg)
    db.add(assistant_msg)
    db.commit()


@router.get("/threads", response_model=ThreadListResponse)
def list_threads(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ThreadListResponse:
    rows = (
        db.query(
            ChatThread.id.label("thread_id"),
            ChatThread.title,
            ChatThread.updated_at,
            func.count(ChatMessage.id).label("message_count"),
        )
        .outerjoin(ChatMessage, ChatMessage.thread_id == ChatThread.id)
        .filter(ChatThread.user_id == user.id)
        .group_by(ChatThread.id)
        .order_by(ChatThread.last_message_at.desc(), ChatThread.id.desc())
        .all()
    )
    items = [
        ThreadItem(
            thread_id=int(row.thread_id),
            title=row.title,
            message_count=int(row.message_count or 0),
            updated_at=row.updated_at.isoformat(),
        )
        for row in rows
    ]
    return ThreadListResponse(items=items)


@router.post("/threads", response_model=ThreadItem, status_code=status.HTTP_201_CREATED)
def create_thread(
    payload: ThreadCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ThreadItem:
    title = (payload.title or "New Chat").strip()[:180] or "New Chat"
    now = datetime.now(timezone.utc)
    thread = ChatThread(
        user_id=user.id,
        title=title,
        created_at=now,
        updated_at=now,
        last_message_at=now,
    )
    db.add(thread)
    db.commit()
    db.refresh(thread)
    return ThreadItem(
        thread_id=thread.id,
        title=thread.title,
        message_count=0,
        updated_at=thread.updated_at.isoformat(),
    )


@router.get("/threads/{thread_id}/messages", response_model=ThreadMessagesResponse)
def get_thread_messages(
    thread_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ThreadMessagesResponse:
    thread = (
        db.query(ChatThread)
        .filter(ChatThread.id == thread_id, ChatThread.user_id == user.id)
        .first()
    )
    if not thread:
        raise HTTPException(status_code=404, detail="Chat thread not found")
    rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.thread_id == thread.id, ChatMessage.user_id == user.id)
        .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        .all()
    )
    messages = [
        MessageItem(
            id=row.id,
            role=row.role,
            content=row.content,
            mode=row.mode,
            created_at=row.created_at.isoformat(),
        )
        for row in rows
    ]
    return ThreadMessagesResponse(thread_id=thread.id, title=thread.title, messages=messages)
