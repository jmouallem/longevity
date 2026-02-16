import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Optional, Protocol, Tuple

import httpx
from sqlalchemy.orm import Session

from app.core.security import decrypt_api_key
from app.db.models import ModelUsageStat, UserAIConfig

LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "60"))
LLM_CONNECT_TIMEOUT_SECONDS = float(os.getenv("LLM_CONNECT_TIMEOUT_SECONDS", "10"))
LLM_WRITE_TIMEOUT_SECONDS = float(os.getenv("LLM_WRITE_TIMEOUT_SECONDS", "30"))
LLM_POOL_TIMEOUT_SECONDS = float(os.getenv("LLM_POOL_TIMEOUT_SECONDS", "60"))
LLM_RETRY_COUNT = int(os.getenv("LLM_RETRY_COUNT", "1"))
LLM_RETRY_BACKOFF_SECONDS = float(os.getenv("LLM_RETRY_BACKOFF_SECONDS", "0.75"))
LLM_MAX_TOKENS_UTILITY = int(os.getenv("LLM_MAX_TOKENS_UTILITY", "320"))
LLM_MAX_TOKENS_REASONING = int(os.getenv("LLM_MAX_TOKENS_REASONING", "700"))
LLM_MAX_TOKENS_DEEP = int(os.getenv("LLM_MAX_TOKENS_DEEP", "900"))


def _http_timeout() -> httpx.Timeout:
    return httpx.Timeout(
        connect=LLM_CONNECT_TIMEOUT_SECONDS,
        read=LLM_TIMEOUT_SECONDS,
        write=LLM_WRITE_TIMEOUT_SECONDS,
        pool=LLM_POOL_TIMEOUT_SECONDS,
    )


def _max_output_tokens(task_type: str) -> int:
    normalized = (task_type or "").strip().lower()
    if normalized in UTILITY_TASK_TYPES:
        return LLM_MAX_TOKENS_UTILITY
    if normalized in DEEP_THINK_TASK_TYPES:
        return LLM_MAX_TOKENS_DEEP
    return LLM_MAX_TOKENS_REASONING


class LLMRequestError(RuntimeError):
    def __init__(self, provider: str, model: str, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.provider = provider
        self.model = model
        self.status_code = status_code


def parse_llm_json(raw_text: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw_text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    start = raw_text.find("{")
    end = raw_text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            parsed = json.loads(raw_text[start : end + 1])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
    raise ValueError("Invalid JSON response from LLM")


UTILITY_TASK_TYPES = {
    "utility",
    "summarization",
    "routing",
    "classification",
    "extraction",
}

DEEP_THINK_TASK_TYPES = {
    "deep_think",
    "deep_thinker",
}


def _resolve_model_config(db: Session, user_id: int) -> Tuple[str, str, str, str, str]:
    cfg = db.query(UserAIConfig).filter(UserAIConfig.user_id == user_id).first()
    if cfg:
        reasoning_model = cfg.ai_reasoning_model or cfg.ai_model
        deep_thinker_model = cfg.ai_deep_thinker_model or reasoning_model
        utility_model = cfg.ai_utility_model or cfg.ai_model
        return (
            cfg.ai_provider,
            reasoning_model,
            deep_thinker_model,
            utility_model,
            decrypt_api_key(cfg.encrypted_api_key),
        )

    provider = os.getenv("DEFAULT_AI_PROVIDER", "").strip().lower()
    reasoning_model = os.getenv("DEFAULT_REASONING_MODEL", "").strip() or os.getenv("DEFAULT_AI_MODEL", "").strip()
    deep_thinker_model = os.getenv("DEFAULT_DEEP_THINKER_MODEL", "").strip() or reasoning_model
    utility_model = os.getenv("DEFAULT_UTILITY_MODEL", "").strip() or reasoning_model
    if provider == "openai":
        key = os.getenv("OPENAI_API_KEY", "")
    elif provider == "gemini":
        key = os.getenv("GEMINI_API_KEY", "")
    else:
        key = ""

    if provider and reasoning_model and deep_thinker_model and utility_model and key:
        return provider, reasoning_model, deep_thinker_model, utility_model, key
    raise ValueError("AI config missing")


def select_model_for_task(
    reasoning_model: str, deep_thinker_model: str, utility_model: str, task_type: str
) -> str:
    normalized_task = (task_type or "").strip().lower()
    if normalized_task in UTILITY_TASK_TYPES:
        return utility_model
    if normalized_task in DEEP_THINK_TASK_TYPES:
        return deep_thinker_model
    return reasoning_model


def _openai_request_v1_chat(
    model: str, api_key: str, prompt: str, max_output_tokens: int
) -> Tuple[str, dict[str, int]]:
    payload = {
        "model": model,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": (
                    "Return strict JSON with keys: answer, rationale_bullets, recommended_actions, "
                    "suggested_questions, safety_flags."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "max_completion_tokens": max_output_tokens,
    }
    # GPT-5 family may consume all tokens on reasoning unless explicitly lowered.
    if model.startswith("gpt-5"):
        payload["reasoning_effort"] = "low"
    response = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=_http_timeout(),
    )
    response.raise_for_status()
    data = response.json()
    usage = data.get("usage", {}) if isinstance(data, dict) else {}
    usage_tokens = {
        "prompt_tokens": int(usage.get("prompt_tokens", 0) or 0),
        "completion_tokens": int(usage.get("completion_tokens", 0) or 0),
        "total_tokens": int(usage.get("total_tokens", 0) or 0),
    }
    text = str(data["choices"][0]["message"].get("content", "")).strip()
    if not text:
        raise ValueError("OpenAI chat completion returned empty content")
    return text, usage_tokens


def _openai_request_v1_responses(
    model: str, api_key: str, prompt: str, max_output_tokens: int
) -> Tuple[str, dict[str, int]]:
    payload = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "Return strict JSON with keys: answer, rationale_bullets, recommended_actions, "
                            "suggested_questions, safety_flags."
                        ),
                    }
                ],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": prompt}],
            },
        ],
        "max_output_tokens": max_output_tokens,
    }
    if model.startswith("gpt-5"):
        payload["reasoning"] = {"effort": "low"}
        payload["text"] = {"verbosity": "low"}
    response = httpx.post(
        "https://api.openai.com/v1/responses",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=_http_timeout(),
    )
    response.raise_for_status()
    data = response.json()
    text_out = ""
    if isinstance(data.get("output_text"), str) and data.get("output_text"):
        text_out = data["output_text"]
    if not text_out:
        for item in data.get("output", []):
            for content in item.get("content", []):
                if content.get("type") in {"output_text", "text"}:
                    text_out = str(content.get("text", "")).strip()
                    if text_out:
                        break
            if text_out:
                break
    if not text_out:
        # Some GPT-5 responses can end as "incomplete" with reasoning summaries only.
        # Recover summary text so callers still get useful content instead of a hard failure.
        for item in data.get("output", []):
            if item.get("type") != "reasoning":
                continue
            for summary in item.get("summary", []):
                summary_text = str(summary.get("text", "")).strip()
                if summary_text:
                    text_out = summary_text
                    break
            if text_out:
                break
    if not text_out:
        raise ValueError("OpenAI responses API returned no text output")
    usage = data.get("usage", {}) if isinstance(data, dict) else {}
    in_tokens = int(usage.get("input_tokens", usage.get("prompt_tokens", 0)) or 0)
    out_tokens = int(usage.get("output_tokens", usage.get("completion_tokens", 0)) or 0)
    total_tokens = int(usage.get("total_tokens", in_tokens + out_tokens) or 0)
    usage_tokens = {
        "prompt_tokens": in_tokens,
        "completion_tokens": out_tokens,
        "total_tokens": total_tokens,
    }
    return text_out, usage_tokens


def _openai_request(
    model: str, api_key: str, prompt: str, max_output_tokens: int
) -> Tuple[str, dict[str, int]]:
    attempts = max(1, LLM_RETRY_COUNT + 1)
    last_error = "unknown error"
    prefer_responses = model.startswith("gpt-5")
    for idx in range(attempts):
        try:
            if prefer_responses:
                raw, usage_tokens = _openai_request_v1_responses(
                    model, api_key, prompt, max_output_tokens
                )
            else:
                raw, usage_tokens = _openai_request_v1_chat(
                    model, api_key, prompt, max_output_tokens
                )
                if not raw.strip():
                    raw, usage_tokens = _openai_request_v1_responses(
                        model, api_key, prompt, max_output_tokens
                    )
            return raw, usage_tokens
        except ValueError as exc:
            # Empty payload or output: retry once with a larger budget on responses endpoint.
            try:
                boosted_tokens = min(max_output_tokens * 2, 1800)
                return _openai_request_v1_responses(model, api_key, prompt, boosted_tokens)
            except Exception as fallback_exc:
                last_error = str(fallback_exc)[:220]
                if idx < attempts - 1:
                    time.sleep(LLM_RETRY_BACKOFF_SECONDS * (idx + 1))
                    continue
                raise LLMRequestError(
                    provider="openai",
                    model=model,
                    message=f"OpenAI request failed: {str(exc)[:220]}",
                ) from fallback_exc
        except httpx.ReadTimeout as exc:
            last_error = "read timeout"
            if idx < attempts - 1:
                time.sleep(LLM_RETRY_BACKOFF_SECONDS * (idx + 1))
                continue
            raise LLMRequestError(
                provider="openai",
                model=model,
                message="OpenAI request timed out while waiting for response.",
            ) from exc
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code if exc.response else None
            detail = ""
            if exc.response is not None:
                detail = (exc.response.text or "").strip()[:220]
            # Some newer model families may require the /v1/responses endpoint.
            if status in {400, 404}:
                try:
                    return _openai_request_v1_responses(model, api_key, prompt, max_output_tokens)
                except Exception as fallback_exc:
                    last_error = str(fallback_exc)[:220]
            raise LLMRequestError(
                provider="openai",
                model=model,
                status_code=status,
                message=f"OpenAI request failed (status={status}): {detail or 'no response body'}",
            ) from exc
        except Exception as exc:
            last_error = str(exc)[:220]
            if idx < attempts - 1:
                time.sleep(LLM_RETRY_BACKOFF_SECONDS * (idx + 1))
                continue
            raise LLMRequestError(
                provider="openai",
                model=model,
                message=f"OpenAI request failed: {last_error}",
            ) from exc
    raise LLMRequestError(provider="openai", model=model, message=f"OpenAI request failed: {last_error}")


def _gemini_request(
    model: str, api_key: str, prompt: str, max_output_tokens: int
) -> Tuple[str, dict[str, int]]:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    response = httpx.post(
        url,
        headers={"Content-Type": "application/json"},
        json={
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.3, "maxOutputTokens": max_output_tokens},
            "contents": [{"parts": [{"text": prompt}]}],
        },
        timeout=_http_timeout(),
    )
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code if exc.response else None
        detail = ""
        if exc.response is not None:
            detail = (exc.response.text or "").strip()[:220]
        raise LLMRequestError(
            provider="gemini",
            model=model,
            status_code=status,
            message=f"Gemini request failed (status={status}): {detail or 'no response body'}",
        ) from exc
    data = response.json()
    usage = data.get("usageMetadata", {}) if isinstance(data, dict) else {}
    prompt_tokens = int(usage.get("promptTokenCount", 0) or 0)
    completion_tokens = int(usage.get("candidatesTokenCount", 0) or 0)
    total_tokens = int(usage.get("totalTokenCount", prompt_tokens + completion_tokens) or 0)
    usage_tokens = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
    }
    return data["candidates"][0]["content"]["parts"][0]["text"], usage_tokens


def _record_usage(
    db: Session, user_id: int, provider: str, model: str, usage_tokens: dict[str, int]
) -> None:
    prompt_tokens = max(0, int(usage_tokens.get("prompt_tokens", 0) or 0))
    completion_tokens = max(0, int(usage_tokens.get("completion_tokens", 0) or 0))
    total_tokens = max(0, int(usage_tokens.get("total_tokens", prompt_tokens + completion_tokens) or 0))
    row = (
        db.query(ModelUsageStat)
        .filter(
            ModelUsageStat.user_id == user_id,
            ModelUsageStat.provider == provider,
            ModelUsageStat.model == model,
        )
        .first()
    )
    now = datetime.now(timezone.utc)
    if not row:
        row = ModelUsageStat(
            user_id=user_id,
            provider=provider,
            model=model,
            request_count=0,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            last_used_at=now,
        )
        db.add(row)
    row.request_count += 1
    row.prompt_tokens += prompt_tokens
    row.completion_tokens += completion_tokens
    row.total_tokens += total_tokens
    row.last_used_at = now


class LLMClient(Protocol):
    def generate_json(
        self, db: Session, user_id: int, prompt: str, task_type: str = "reasoning"
    ) -> dict[str, Any]:
        ...


class RealLLMClient:
    def generate_json(
        self, db: Session, user_id: int, prompt: str, task_type: str = "reasoning"
    ) -> dict[str, Any]:
        provider, reasoning_model, deep_thinker_model, utility_model, api_key = _resolve_model_config(
            db, user_id
        )
        model = select_model_for_task(reasoning_model, deep_thinker_model, utility_model, task_type)
        max_output_tokens = _max_output_tokens(task_type)
        if provider == "openai":
            raw, usage_tokens = _openai_request(model, api_key, prompt, max_output_tokens)
        elif provider == "gemini":
            raw, usage_tokens = _gemini_request(model, api_key, prompt, max_output_tokens)
        else:
            raise ValueError("Unsupported AI provider")
        _record_usage(db, user_id, provider, model, usage_tokens)
        db.commit()
        try:
            return parse_llm_json(raw)
        except ValueError:
            # Recover from non-JSON model output instead of failing the entire request path.
            text = str(raw).strip()
            return {
                "answer": text or "Model returned an empty response.",
                "rationale_bullets": [],
                "recommended_actions": [],
                "suggested_questions": [],
                "safety_flags": [],
            }


def get_llm_client() -> LLMClient:
    return RealLLMClient()
