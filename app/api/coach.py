import json
import logging
import os
import re
import time
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
from app.services.llm import LLMClient, LLMRequestError, get_llm_client

router = APIRouter(prefix="/coach", tags=["coach"])
logger = logging.getLogger("uvicorn.error")
CACHE_TTL_SECONDS = int(os.getenv("COACH_CACHE_TTL_SECONDS", "75"))
_COACH_RESPONSE_CACHE: dict[tuple[int, str, str, bool], tuple[float, Any]] = {}


class CoachMode(str, Enum):
    quick = "quick"
    deep = "deep"


class CoachQuestionRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1000)
    mode: CoachMode = CoachMode.quick
    deep_think: bool = False
    context_hint: Optional[str] = Field(default=None, max_length=120)


class CoachVoiceRequest(BaseModel):
    transcript: str = Field(min_length=2, max_length=2000)
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


def _agent_profiles(include_supplement_audit: bool) -> list[dict[str, str]]:
    profiles = [
        {
            "id": "goal_strategist",
            "title": "Goal Strategist",
            "instruction": (
                "Prioritize the plan against user's primary and top goals. "
                "Recommend the highest-leverage sequence of changes."
            ),
            "task_type": "reasoning",
        },
        {
            "id": "risk_guard",
            "title": "Risk Guard",
            "instruction": (
                "Identify safety constraints, contraindication risks, overreach, and missing clarifiers. "
                "Be conservative and non-alarmist."
            ),
            "task_type": "utility",
        },
        {
            "id": "behavior_designer",
            "title": "Behavior Designer",
            "instruction": (
                "Turn strategy into practical habits, schedules, and tracking steps that are easy to execute."
            ),
            "task_type": "reasoning",
        },
    ]
    if include_supplement_audit:
        profiles.append(
            {
                "id": "supplement_auditor",
                "title": "Supplement Auditor",
                "instruction": (
                    "Review supplement stack for overlap, timing, safety caveats, and monitoring suggestions. "
                    "Do not diagnose disease."
                ),
                "task_type": "deep_think",
            }
        )
    return profiles


def _build_agent_prompt(
    *,
    question: str,
    context_hint: Optional[str],
    context: dict[str, Any],
    mode: str,
    agent_title: str,
    agent_instruction: str,
    prior_agents: Optional[list[dict[str, Any]]] = None,
) -> str:
    body = {
        "question": question,
        "context_hint": context_hint,
        "context": context,
        "agent_profile": {
            "name": agent_title,
            "instruction": agent_instruction,
        },
        "prior_agent_outputs": prior_agents or [],
        "instructions": {
            "tone": "warm, practical, science-informed, never shame-based",
            "mode": mode,
            "format": (
                "answer must be readable markdown with short sections, bullets, and spacing for easy human scanning. "
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


def _run_agentic_pipeline(
    *,
    db: Session,
    user_id: int,
    payload: CoachQuestionRequest,
    context: dict[str, Any],
    llm_client: LLMClient,
) -> tuple[CoachQuestionResponse, list[dict[str, Any]]]:
    include_supplement_audit = has_supplement_topic(payload.question)
    if payload.mode == CoachMode.quick and not payload.deep_think:
        # Cost-optimized quick path: one specialist pass + synthesis.
        profiles = [
            {
                "id": "risk_guard",
                "title": "Risk Guard",
                "instruction": (
                    "Identify safety constraints, contraindication risks, overreach, and missing clarifiers. "
                    "Be conservative and non-alarmist."
                ),
                "task_type": "utility",
            }
        ]
    else:
        profiles = _agent_profiles(include_supplement_audit=include_supplement_audit)
    agent_outputs: list[dict[str, Any]] = []
    for profile in profiles:
        prompt = _build_agent_prompt(
            question=payload.question,
            context_hint=payload.context_hint,
            context=context,
            mode=payload.mode.value,
            agent_title=profile["title"],
            agent_instruction=profile["instruction"],
            prior_agents=agent_outputs,
        )
        task_type = profile["task_type"]
        if payload.deep_think and task_type == "reasoning":
            task_type = "deep_think"
        raw = llm_client.generate_json(db=db, user_id=user_id, prompt=prompt, task_type=task_type)
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
            }
        )

    synthesis_prompt = _build_agent_prompt(
        question=payload.question,
        context_hint=payload.context_hint,
        context=context,
        mode=payload.mode.value,
        agent_title="Orchestrator",
        agent_instruction=(
            "Synthesize all agent outputs into one final coaching response. "
            "Resolve conflicts conservatively and prefer safer, actionable steps."
        ),
        prior_agents=agent_outputs,
    )
    synthesis_task_type = "deep_think" if payload.deep_think else "reasoning"
    synthesis_raw = llm_client.generate_json(
        db=db,
        user_id=user_id,
        prompt=synthesis_prompt,
        task_type=synthesis_task_type,
    )
    response = _response_from_raw(synthesis_raw, payload.mode.value)
    return response, agent_outputs


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
    cached = _cache_get(user.id, payload)
    if cached is not None:
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
    agent_trace: list[dict[str, Any]] = []
    try:
        response, agent_trace = _run_agentic_pipeline(
            db=db,
            user_id=user.id,
            payload=payload,
            context=context,
            llm_client=llm_client,
        )
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

    if llm_error:
        response.suggested_questions = response.suggested_questions[:8]

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
    )
    return ask_coach_question(payload=text_payload, user=user, db=db, llm_client=llm_client)
