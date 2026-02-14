from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, declarative_base, mapped_column, relationship

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    baseline: Mapped["Baseline"] = relationship(
        "Baseline", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    ai_config: Mapped["UserAIConfig"] = relationship(
        "UserAIConfig", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )


class Baseline(Base):
    __tablename__ = "baselines"
    __table_args__ = (UniqueConstraint("user_id", name="uq_baselines_user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

    primary_goal: Mapped[str] = mapped_column(String(64), nullable=False)

    weight: Mapped[float] = mapped_column(Float, nullable=False)
    waist: Mapped[float] = mapped_column(Float, nullable=False)
    systolic_bp: Mapped[int] = mapped_column(Integer, nullable=False)
    diastolic_bp: Mapped[int] = mapped_column(Integer, nullable=False)
    resting_hr: Mapped[int] = mapped_column(Integer, nullable=False)
    sleep_hours: Mapped[float] = mapped_column(Float, nullable=False)
    activity_level: Mapped[str] = mapped_column(String(32), nullable=False)

    energy: Mapped[int] = mapped_column(Integer, nullable=False)
    mood: Mapped[int] = mapped_column(Integer, nullable=False)
    stress: Mapped[int] = mapped_column(Integer, nullable=False)
    sleep_quality: Mapped[int] = mapped_column(Integer, nullable=False)
    motivation: Mapped[int] = mapped_column(Integer, nullable=False)

    engagement_style: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    nutrition_patterns: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    training_history: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    supplement_stack: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    lab_markers: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fasting_practices: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recovery_practices: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    medication_details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped[User] = relationship("User", back_populates="baseline")


class UserAIConfig(Base):
    __tablename__ = "user_ai_configs"
    __table_args__ = (UniqueConstraint("user_id", name="uq_user_ai_configs_user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

    ai_provider: Mapped[str] = mapped_column(String(32), nullable=False)
    ai_model: Mapped[str] = mapped_column(String(128), nullable=False)
    encrypted_api_key: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped[User] = relationship("User", back_populates="ai_config")
