from datetime import datetime, timedelta, timezone
from statistics import mean
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from app.db.models import CompositeScore, DomainScore, Metric


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _clamp_score(value: float) -> int:
    return int(max(0, min(100, round(value))))


def _avg(values: Iterable[float], fallback: float) -> float:
    data = list(values)
    if not data:
        return fallback
    return float(mean(data))


def _latest_value(metrics: list[Metric], metric_type: str) -> float:
    filtered = [m.value_num for m in metrics if m.metric_type == metric_type]
    if not filtered:
        return 0.0
    return filtered[-1]


def _metric_values(metrics: list[Metric], metric_type: str) -> list[float]:
    return [m.value_num for m in metrics if m.metric_type == metric_type]


def compute_domain_scores(db: Session, user_id: int, now: Optional[datetime] = None) -> DomainScore:
    timestamp = now or _utc_now()
    last_7 = timestamp - timedelta(days=7)
    last_14 = timestamp - timedelta(days=14)
    last_30 = timestamp - timedelta(days=30)

    metrics_7 = (
        db.query(Metric)
        .filter(Metric.user_id == user_id, Metric.taken_at >= last_7, Metric.taken_at <= timestamp)
        .order_by(Metric.taken_at.asc())
        .all()
    )
    metrics_14 = (
        db.query(Metric)
        .filter(Metric.user_id == user_id, Metric.taken_at >= last_14, Metric.taken_at <= timestamp)
        .order_by(Metric.taken_at.asc())
        .all()
    )
    metrics_30 = (
        db.query(Metric)
        .filter(Metric.user_id == user_id, Metric.taken_at >= last_30, Metric.taken_at <= timestamp)
        .order_by(Metric.taken_at.asc())
        .all()
    )

    sleep_hours_avg = _avg(_metric_values(metrics_7, "sleep_hours"), 7.0)
    sleep_quality_avg = _avg(_metric_values(metrics_7, "sleep_quality_1_10"), 7.0)
    sleep_hours_component = (sleep_hours_avg / 8.0) * 100.0
    sleep_quality_component = (sleep_quality_avg / 10.0) * 100.0
    sleep_score = _clamp_score((sleep_hours_component * 0.6) + (sleep_quality_component * 0.4))

    waist = _latest_value(metrics_30, "waist_cm")
    systolic = _latest_value(metrics_30, "bp_systolic")
    diastolic = _latest_value(metrics_30, "bp_diastolic")
    weight_values = _metric_values(metrics_30, "weight_kg")
    weight_stability = 100.0
    if len(weight_values) >= 2:
        delta = abs(weight_values[-1] - weight_values[0])
        weight_stability = max(0.0, 100.0 - (delta * 5.0))
    waist_component = 70.0 if waist == 0 else max(0.0, 100.0 - max(0.0, waist - 85.0) * 1.4)
    bp_component = 70.0
    if systolic > 0 and diastolic > 0:
        systolic_penalty = max(0.0, systolic - 120.0) * 1.0
        diastolic_penalty = max(0.0, diastolic - 80.0) * 1.2
        bp_component = max(0.0, 100.0 - (systolic_penalty + diastolic_penalty))
    metabolic_score = _clamp_score((bp_component * 0.5) + (waist_component * 0.3) + (weight_stability * 0.2))

    stress_avg = _avg(_metric_values(metrics_14, "stress_1_10"), 5.0)
    resting_hr_avg = _avg(_metric_values(metrics_14, "resting_hr_bpm"), 65.0)
    stress_component = 100.0 - ((stress_avg - 1.0) / 9.0) * 100.0
    hr_component = max(0.0, 100.0 - max(0.0, resting_hr_avg - 55.0) * 2.0)
    recovery_score = _clamp_score((stress_component * 0.4) + (sleep_score * 0.4) + (hr_component * 0.2))

    days_with_logs = {m.taken_at.date().isoformat() for m in metrics_7}
    behavioral_score = _clamp_score((len(days_with_logs) / 7.0) * 100.0)

    steps_avg = _avg(_metric_values(metrics_7, "steps"), 0.0)
    active_minutes_avg = _avg(_metric_values(metrics_7, "active_minutes"), 0.0)
    steps_component = 0.0 if steps_avg <= 0 else min(100.0, (steps_avg / 8000.0) * 100.0)
    active_component = 0.0 if active_minutes_avg <= 0 else min(100.0, (active_minutes_avg / 45.0) * 100.0)
    if steps_component == 0.0 and active_component == 0.0:
        fitness_score = 60
    else:
        fitness_score = _clamp_score((steps_component * 0.6) + (active_component * 0.4))

    snapshot = DomainScore(
        user_id=user_id,
        sleep_score=sleep_score,
        metabolic_score=metabolic_score,
        recovery_score=recovery_score,
        behavioral_score=behavioral_score,
        fitness_score=fitness_score,
        computed_at=timestamp,
    )
    db.add(snapshot)
    return snapshot


def compute_composite_score(
    db: Session, domain_score: DomainScore, now: Optional[datetime] = None
) -> CompositeScore:
    timestamp = now or _utc_now()
    longevity = _clamp_score(
        (domain_score.sleep_score * 0.25)
        + (domain_score.metabolic_score * 0.25)
        + (domain_score.recovery_score * 0.2)
        + (domain_score.behavioral_score * 0.15)
        + (domain_score.fitness_score * 0.15)
    )
    snapshot = CompositeScore(user_id=domain_score.user_id, longevity_score=longevity, computed_at=timestamp)
    db.add(snapshot)
    return snapshot


def ensure_fresh_scores(db: Session, user_id: int, freshness_hours: int = 24) -> tuple[DomainScore, CompositeScore]:
    domain = (
        db.query(DomainScore)
        .filter(DomainScore.user_id == user_id)
        .order_by(DomainScore.computed_at.desc())
        .first()
    )
    composite = (
        db.query(CompositeScore)
        .filter(CompositeScore.user_id == user_id)
        .order_by(CompositeScore.computed_at.desc())
        .first()
    )
    latest_metric = (
        db.query(Metric).filter(Metric.user_id == user_id).order_by(Metric.taken_at.desc()).first()
    )

    needs_compute = domain is None or composite is None
    if not needs_compute and latest_metric is not None:
        score_time = min(domain.computed_at, composite.computed_at)
        metric_newer = latest_metric.taken_at > score_time
        stale = (_utc_now() - domain.computed_at.replace(tzinfo=timezone.utc)) > timedelta(hours=freshness_hours)
        needs_compute = metric_newer or stale

    if needs_compute:
        domain = compute_domain_scores(db, user_id=user_id)
        composite = compute_composite_score(db, domain_score=domain)
        db.commit()
        db.refresh(domain)
        db.refresh(composite)

    return domain, composite
