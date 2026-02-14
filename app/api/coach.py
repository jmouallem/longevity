import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.context_builder import build_coaching_context
from app.core.persona import apply_longevity_alchemist_voice
from app.core.safety import (
    detect_urgent_flags,
    emergency_response,
    has_supplement_topic,
    supplement_caution_text,
)
from app.db.models import ConversationSummary, User
from app.db.session import get_db
from app.services.llm import LLMClient, get_llm_client

router = APIRouter(prefix="/coach", tags=["coach"])


class CoachMode(str, Enum):
    quick = "quick"
    deep = "deep"


class CoachQuestionRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1000)
    mode: CoachMode = CoachMode.quick
    deep_think: bool = False
    context_hint: Optional[str] = Field(default=None, max_length=120)


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


def request_coaching_json(
    db: Session, user_id: int, prompt: str, llm_client: LLMClient, deep_think: bool = False
) -> dict[str, Any]:
    task_type = "deep_think" if deep_think else "reasoning"
    return llm_client.generate_json(db=db, user_id=user_id, prompt=prompt, task_type=task_type)


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
            "Want a 7-day plan based on your current trends?",
            "Want help choosing one metric to prioritize this week?",
            "Want a quick daily check-in template?",
        ],
        safety_flags=safety_flags or [],
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


def _build_llm_prompt(payload: CoachQuestionRequest, context: dict[str, Any]) -> str:
    instructions = {
        "tone": "warm, practical, science-informed, never shame-based",
        "mode": payload.mode.value,
        "must_include": [
            "answer",
            "rationale_bullets (3-7)",
            "recommended_actions (1-3 items with title + steps)",
            "suggested_questions (3-8)",
            "safety_flags",
        ],
    }
    body = {
        "question": payload.question,
        "context_hint": payload.context_hint,
        "context": context,
        "instructions": instructions,
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


def _persist_summary(
    db: Session,
    user_id: int,
    question: str,
    answer: str,
    tags: str,
    safety_flags: list[str],
) -> None:
    summary = ConversationSummary(
        user_id=user_id,
        created_at=datetime.now(timezone.utc),
        question=question[:512],
        answer_summary=answer[:1024],
        tags=tags or None,
        safety_flags=",".join(safety_flags) if safety_flags else None,
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
    urgent_flags = detect_urgent_flags(payload.question)
    if urgent_flags:
        emergency = emergency_response()
        response = CoachQuestionResponse(**emergency)
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
    try:
        llm_prompt = _build_llm_prompt(payload, context)
        raw = request_coaching_json(
            db=db,
            user_id=user.id,
            prompt=llm_prompt,
            llm_client=llm_client,
            deep_think=payload.deep_think,
        )
        answer = str(raw.get("answer", "")).strip()
        if not answer:
            raise ValueError("missing answer")
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
        response = CoachQuestionResponse(
            answer=apply_longevity_alchemist_voice(answer, payload.mode.value),
            rationale_bullets=rationale_bullets,
            recommended_actions=recommended_actions[:3],
            suggested_questions=suggested_questions,
            safety_flags=safety_flags,
            disclaimer=_disclaimer(),
        )
    except Exception:
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

    if llm_error:
        response.suggested_questions = response.suggested_questions[:8]

    _persist_summary(
        db=db,
        user_id=user.id,
        question=payload.question,
        answer=response.answer,
        tags=_tags_from_context(payload, context),
        safety_flags=response.safety_flags,
    )
    return response
