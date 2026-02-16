from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
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
    metrics: Mapped[list["Metric"]] = relationship(
        "Metric", back_populates="user", cascade="all, delete-orphan"
    )
    domain_scores: Mapped[list["DomainScore"]] = relationship(
        "DomainScore", back_populates="user", cascade="all, delete-orphan"
    )
    composite_scores: Mapped[list["CompositeScore"]] = relationship(
        "CompositeScore", back_populates="user", cascade="all, delete-orphan"
    )
    conversation_summaries: Mapped[list["ConversationSummary"]] = relationship(
        "ConversationSummary", back_populates="user", cascade="all, delete-orphan"
    )


class Baseline(Base):
    __tablename__ = "baselines"
    __table_args__ = (UniqueConstraint("user_id", name="uq_baselines_user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

    primary_goal: Mapped[str] = mapped_column(String(64), nullable=False)
    top_goals_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    goal_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    age_years: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sex_at_birth: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

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
    ai_reasoning_model: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    ai_deep_thinker_model: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    ai_utility_model: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    encrypted_api_key: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped[User] = relationship("User", back_populates="ai_config")


class Metric(Base):
    __tablename__ = "metrics"
    __table_args__ = (Index("ix_metrics_user_type_taken", "user_id", "metric_type", "taken_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    metric_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    value_num: Mapped[float] = mapped_column(Float, nullable=False)
    taken_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    user: Mapped[User] = relationship("User", back_populates="metrics")


class DomainScore(Base):
    __tablename__ = "domain_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    sleep_score: Mapped[int] = mapped_column(Integer, nullable=False)
    metabolic_score: Mapped[int] = mapped_column(Integer, nullable=False)
    recovery_score: Mapped[int] = mapped_column(Integer, nullable=False)
    behavioral_score: Mapped[int] = mapped_column(Integer, nullable=False)
    fitness_score: Mapped[int] = mapped_column(Integer, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    user: Mapped[User] = relationship("User", back_populates="domain_scores")


class CompositeScore(Base):
    __tablename__ = "composite_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    longevity_score: Mapped[int] = mapped_column(Integer, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    user: Mapped[User] = relationship("User", back_populates="composite_scores")


class ConversationSummary(Base):
    __tablename__ = "conversation_summaries"
    __table_args__ = (Index("ix_conv_summary_user_created", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    question: Mapped[str] = mapped_column(String(512), nullable=False)
    answer_summary: Mapped[str] = mapped_column(String(1024), nullable=False)
    tags: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    safety_flags: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    agent_trace_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    user: Mapped[User] = relationship("User", back_populates="conversation_summaries")


class ModelUsageStat(Base):
    __tablename__ = "model_usage_stats"
    __table_args__ = (
        UniqueConstraint("user_id", "provider", "model", name="uq_model_usage_user_provider_model"),
        Index("ix_model_usage_user_last_used", "user_id", "last_used_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_used_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class IntakeConversationSession(Base):
    __tablename__ = "intake_conversation_sessions"
    __table_args__ = (
        Index("ix_intake_conv_user_updated", "user_id", "updated_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    current_step: Mapped[str] = mapped_column(String(64), nullable=False)
    answers_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    concern_flags_csv: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    coach_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
