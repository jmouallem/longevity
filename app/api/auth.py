from datetime import timedelta
from enum import Enum
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.security import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
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
    ai_model: str = Field(min_length=1, max_length=128)
    ai_api_key: str = Field(min_length=8, max_length=512)


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
    api_key_masked: str
    configured: bool = True


def _bad_credentials() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _upsert_ai_config(db: Session, user_id: int, ai: AIConfigInput) -> UserAIConfig:
    existing = db.query(UserAIConfig).filter(UserAIConfig.user_id == user_id).first()
    encrypted = encrypt_api_key(ai.ai_api_key)
    if existing:
        existing.ai_provider = ai.ai_provider.value
        existing.ai_model = ai.ai_model.strip()
        existing.encrypted_api_key = encrypted
        return existing

    created = UserAIConfig(
        user_id=user_id,
        ai_provider=ai.ai_provider.value,
        ai_model=ai.ai_model.strip(),
        encrypted_api_key=encrypted,
    )
    db.add(created)
    return created


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
        api_key_masked=mask_api_key(payload.ai_api_key),
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
        api_key_masked=masked,
    )


@router.delete("/ai-config", status_code=status.HTTP_204_NO_CONTENT)
def revoke_ai_config(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> None:
    cfg = db.query(UserAIConfig).filter(UserAIConfig.user_id == user.id).first()
    if not cfg:
        raise HTTPException(status_code=404, detail="AI config not found")
    db.delete(cfg)
    db.commit()
