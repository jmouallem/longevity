import json
import os
from typing import Any, Protocol

import httpx
from sqlalchemy.orm import Session

from app.core.security import decrypt_api_key
from app.db.models import UserAIConfig

LLM_TIMEOUT_SECONDS = 20.0


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


def _resolve_model_config(db: Session, user_id: int) -> tuple[str, str, str]:
    cfg = db.query(UserAIConfig).filter(UserAIConfig.user_id == user_id).first()
    if cfg:
        return cfg.ai_provider, cfg.ai_model, decrypt_api_key(cfg.encrypted_api_key)

    provider = os.getenv("DEFAULT_AI_PROVIDER", "").strip().lower()
    model = os.getenv("DEFAULT_AI_MODEL", "").strip()
    if provider == "openai":
        key = os.getenv("OPENAI_API_KEY", "")
    elif provider == "gemini":
        key = os.getenv("GEMINI_API_KEY", "")
    else:
        key = ""

    if provider and model and key:
        return provider, model, key
    raise ValueError("AI config missing")


def _openai_request(model: str, api_key: str, prompt: str) -> str:
    response = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
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
            "temperature": 0.3,
        },
        timeout=LLM_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"]


def _gemini_request(model: str, api_key: str, prompt: str) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    response = httpx.post(
        url,
        headers={"Content-Type": "application/json"},
        json={
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.3},
            "contents": [{"parts": [{"text": prompt}]}],
        },
        timeout=LLM_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    data = response.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


class LLMClient(Protocol):
    def generate_json(self, db: Session, user_id: int, prompt: str) -> dict[str, Any]:
        ...


class RealLLMClient:
    def generate_json(self, db: Session, user_id: int, prompt: str) -> dict[str, Any]:
        provider, model, api_key = _resolve_model_config(db, user_id)
        if provider == "openai":
            raw = _openai_request(model, api_key, prompt)
        elif provider == "gemini":
            raw = _gemini_request(model, api_key, prompt)
        else:
            raise ValueError("Unsupported AI provider")
        return parse_llm_json(raw)


def get_llm_client() -> LLMClient:
    return RealLLMClient()
