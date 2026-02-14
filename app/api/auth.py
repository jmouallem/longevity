from datetime import timedelta
from enum import Enum
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field, model_validator
from sqlalchemy.orm import Session

from app.core.security import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    decrypt_api_key,
    decode_access_token,
    encrypt_api_key,
    get_password_hash,
    mask_api_key,
    verify_password,
)
from app.db.models import User, UserAIConfig
from app.db.session import get_db

router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


class AIProvider(str, Enum):
    openai = "openai"
    gemini = "gemini"


class AIConfigInput(BaseModel):
    ai_provider: AIProvider
    ai_model: Optional[str] = Field(default=None, min_length=1, max_length=128)
    ai_reasoning_model: Optional[str] = Field(default=None, min_length=1, max_length=128)
    ai_deep_thinker_model: Optional[str] = Field(default=None, min_length=1, max_length=128)
    ai_utility_model: Optional[str] = Field(default=None, min_length=1, max_length=128)
    ai_api_key: str = Field(min_length=8, max_length=512)

    @model_validator(mode="after")
    def validate_models(self):
        if self.ai_reasoning_model and self.ai_deep_thinker_model and self.ai_utility_model:
            return self
        if self.ai_model:
            self.ai_reasoning_model = self.ai_reasoning_model or self.ai_model
            self.ai_deep_thinker_model = self.ai_deep_thinker_model or self.ai_model
            self.ai_utility_model = self.ai_utility_model or self.ai_model
            return self
        raise ValueError(
            "Provide ai_model or all of ai_reasoning_model, ai_deep_thinker_model, and ai_utility_model"
        )


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    ai_config: Optional[AIConfigInput] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AIConfigResponse(BaseModel):
    ai_provider: AIProvider
    ai_model: str
    ai_reasoning_model: str
    ai_deep_thinker_model: str
    ai_utility_model: str
    api_key_masked: str
    configured: bool = True


class ModelOptionsRequest(BaseModel):
    ai_provider: AIProvider
    ai_api_key: Optional[str] = Field(default=None, min_length=8, max_length=512)


class ModelOptionsResponse(BaseModel):
    class ModelOption(BaseModel):
        model: str
        input_cost_per_1m_usd: Optional[float] = None
        output_cost_per_1m_usd: Optional[float] = None
        cost_known: bool = False

    ai_provider: AIProvider
    models: list[str]
    model_options: list[ModelOption]
    default_model: str
    default_reasoning_model: str
    default_deep_thinker_model: str
    default_utility_model: str
    source: str


def _bad_credentials() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


MODEL_DEFAULTS: dict[str, list[str]] = {
    "openai": ["gpt-4.1", "gpt-4.1-mini", "gpt-4o-mini"],
    "gemini": ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"],
}

MODEL_PRICING_USD_PER_1M: dict[str, dict[str, tuple[float, float]]] = {
    # Estimated values. Keep this table maintainable and refreshable over time.
    "openai": {
        "gpt-4.1": (2.0, 8.0),
        "gpt-4.1-mini": (0.4, 1.6),
        "gpt-4o-mini": (0.15, 0.6),
    },
    "gemini": {
        "gemini-2.0-flash": (0.1, 0.4),
        "gemini-1.5-flash": (0.075, 0.3),
        "gemini-1.5-pro": (1.25, 5.0),
    },
}


def _upsert_ai_config(db: Session, user_id: int, ai: AIConfigInput) -> UserAIConfig:
    existing = db.query(UserAIConfig).filter(UserAIConfig.user_id == user_id).first()
    encrypted = encrypt_api_key(ai.ai_api_key)
    if existing:
        existing.ai_provider = ai.ai_provider.value
        existing.ai_model = (ai.ai_reasoning_model or ai.ai_model or "").strip()
        existing.ai_reasoning_model = (ai.ai_reasoning_model or ai.ai_model or "").strip()
        existing.ai_deep_thinker_model = (ai.ai_deep_thinker_model or ai.ai_model or "").strip()
        existing.ai_utility_model = (ai.ai_utility_model or ai.ai_model or "").strip()
        existing.encrypted_api_key = encrypted
        return existing

    created = UserAIConfig(
        user_id=user_id,
        ai_provider=ai.ai_provider.value,
        ai_model=(ai.ai_reasoning_model or ai.ai_model or "").strip(),
        ai_reasoning_model=(ai.ai_reasoning_model or ai.ai_model or "").strip(),
        ai_deep_thinker_model=(ai.ai_deep_thinker_model or ai.ai_model or "").strip(),
        ai_utility_model=(ai.ai_utility_model or ai.ai_model or "").strip(),
        encrypted_api_key=encrypted,
    )
    db.add(created)
    return created


def _best_model(provider: str, models: list[str]) -> str:
    preferred = MODEL_DEFAULTS.get(provider, [])
    for candidate in preferred:
        if candidate in models:
            return candidate
    if models:
        return models[0]
    return preferred[0] if preferred else ""


def _best_utility_model(provider: str, models: list[str]) -> str:
    utility_candidates = {
        "openai": ["gpt-4.1-mini", "gpt-4o-mini", "gpt-4.1"],
        "gemini": ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"],
    }
    preferred = utility_candidates.get(provider, [])
    for candidate in preferred:
        if candidate in models:
            return candidate
    return _best_model(provider, models)


def _best_deep_thinker_model(provider: str, models: list[str]) -> str:
    deep_candidates = {
        "openai": ["gpt-4.1", "gpt-4.1-mini", "gpt-4o-mini"],
        "gemini": ["gemini-1.5-pro", "gemini-2.0-flash", "gemini-1.5-flash"],
    }
    preferred = deep_candidates.get(provider, [])
    for candidate in preferred:
        if candidate in models:
            return candidate
    return _best_model(provider, models)


def _fallback_models(provider: str) -> list[str]:
    return MODEL_DEFAULTS.get(provider, [])


def _resolve_lookup_key(
    db: Session, user_id: int, provider: str, override_key: Optional[str]
) -> Optional[str]:
    if override_key:
        return override_key.strip()
    cfg = db.query(UserAIConfig).filter(UserAIConfig.user_id == user_id).first()
    if cfg and cfg.ai_provider == provider and cfg.encrypted_api_key:
        try:
            return decrypt_api_key(cfg.encrypted_api_key)
        except Exception:
            return None
    return None


def _fetch_openai_models(api_key: str) -> list[str]:
    response = httpx.get(
        "https://api.openai.com/v1/models",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=8.0,
    )
    response.raise_for_status()
    data = response.json()
    names: list[str] = []
    for item in data.get("data", []):
        model_id = str(item.get("id", "")).strip()
        if model_id.startswith("gpt-"):
            names.append(model_id)
    return sorted(set(names))


def _fetch_gemini_models(api_key: str) -> list[str]:
    response = httpx.get(
        f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}",
        timeout=8.0,
    )
    response.raise_for_status()
    data = response.json()
    names: list[str] = []
    for item in data.get("models", []):
        raw = str(item.get("name", "")).strip()
        model_id = raw.split("/")[-1]
        if "gemini" in model_id:
            names.append(model_id)
    return sorted(set(names))


def _model_option(provider: str, model: str) -> ModelOptionsResponse.ModelOption:
    price = MODEL_PRICING_USD_PER_1M.get(provider, {}).get(model)
    if not price:
        return ModelOptionsResponse.ModelOption(model=model)
    return ModelOptionsResponse.ModelOption(
        model=model,
        input_cost_per_1m_usd=price[0],
        output_cost_per_1m_usd=price[1],
        cost_known=True,
    )


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    try:
        subject = decode_access_token(token)
        user_id = int(subject)
    except Exception:
        raise _bad_credentials()

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise _bad_credentials()
    return user


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, db: Session = Depends(get_db)) -> TokenResponse:
    existing = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(email=payload.email.lower(), password_hash=get_password_hash(payload.password))
    db.add(user)
    db.flush()

    if payload.ai_config:
        _upsert_ai_config(db, user.id, payload.ai_config)

    db.commit()

    token = create_access_token(
        subject=str(user.id), expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(User).filter(User.email == form_data.username.lower()).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise _bad_credentials()

    token = create_access_token(
        subject=str(user.id), expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return TokenResponse(access_token=token)


@router.put("/ai-config", response_model=AIConfigResponse)
def set_ai_config(
    payload: AIConfigInput,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AIConfigResponse:
    cfg = _upsert_ai_config(db, user.id, payload)
    db.commit()
    return AIConfigResponse(
        ai_provider=AIProvider(cfg.ai_provider),
        ai_model=cfg.ai_model,
        ai_reasoning_model=cfg.ai_reasoning_model or cfg.ai_model,
        ai_deep_thinker_model=cfg.ai_deep_thinker_model or cfg.ai_reasoning_model or cfg.ai_model,
        ai_utility_model=cfg.ai_utility_model or cfg.ai_model,
        api_key_masked=mask_api_key(payload.ai_api_key),
    )


@router.post("/model-options", response_model=ModelOptionsResponse)
def get_model_options(
    payload: ModelOptionsRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ModelOptionsResponse:
    provider = payload.ai_provider.value
    key = _resolve_lookup_key(db, user.id, provider, payload.ai_api_key)
    if not key:
        models = _fallback_models(provider)
        return ModelOptionsResponse(
            ai_provider=payload.ai_provider,
            models=models,
            model_options=[_model_option(provider, name) for name in models],
            default_model=_best_model(provider, models),
            default_reasoning_model=_best_model(provider, models),
            default_deep_thinker_model=_best_deep_thinker_model(provider, models),
            default_utility_model=_best_utility_model(provider, models),
            source="fallback_no_key",
        )

    try:
        if provider == "openai":
            models = _fetch_openai_models(key)
        else:
            models = _fetch_gemini_models(key)
    except Exception:
        models = _fallback_models(provider)
        return ModelOptionsResponse(
            ai_provider=payload.ai_provider,
            models=models,
            model_options=[_model_option(provider, name) for name in models],
            default_model=_best_model(provider, models),
            default_reasoning_model=_best_model(provider, models),
            default_deep_thinker_model=_best_deep_thinker_model(provider, models),
            default_utility_model=_best_utility_model(provider, models),
            source="fallback_provider_error",
        )

    if not models:
        models = _fallback_models(provider)
        source = "fallback_provider_empty"
    else:
        source = "provider_api"
    return ModelOptionsResponse(
        ai_provider=payload.ai_provider,
        models=models,
        model_options=[_model_option(provider, name) for name in models],
        default_model=_best_model(provider, models),
        default_reasoning_model=_best_model(provider, models),
        default_deep_thinker_model=_best_deep_thinker_model(provider, models),
        default_utility_model=_best_utility_model(provider, models),
        source=source,
    )


@router.get("/ai-config", response_model=AIConfigResponse)
def get_ai_config(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> AIConfigResponse:
    cfg = db.query(UserAIConfig).filter(UserAIConfig.user_id == user.id).first()
    if not cfg:
        raise HTTPException(status_code=404, detail="AI config not found")

    # Do not return full key.
    masked = "configured"
    if cfg.encrypted_api_key:
        # Mask format is intentionally generic on reads.
        masked = "****...****"

    return AIConfigResponse(
        ai_provider=AIProvider(cfg.ai_provider),
        ai_model=cfg.ai_model,
        ai_reasoning_model=cfg.ai_reasoning_model or cfg.ai_model,
        ai_deep_thinker_model=cfg.ai_deep_thinker_model or cfg.ai_reasoning_model or cfg.ai_model,
        ai_utility_model=cfg.ai_utility_model or cfg.ai_model,
        api_key_masked=masked,
    )


@router.delete("/ai-config", status_code=status.HTTP_204_NO_CONTENT)
def revoke_ai_config(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> None:
    cfg = db.query(UserAIConfig).filter(UserAIConfig.user_id == user.id).first()
    if not cfg:
        raise HTTPException(status_code=404, detail="AI config not found")
    db.delete(cfg)
    db.commit()
