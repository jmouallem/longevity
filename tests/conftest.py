import json
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Callable
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import encrypt_api_key, get_password_hash
from app.db.models import Baseline, CompositeScore, DomainScore, Metric, User, UserAIConfig
from app.db.session import SessionLocal, configure_database, create_tables
from app.services.llm import get_llm_client, parse_llm_json


class FakeScenario(str, Enum):
    OK_LUNCH_PLAN = "OK_LUNCH_PLAN"
    OK_TIRED_ANALYSIS = "OK_TIRED_ANALYSIS"
    MALFORMED_JSON = "MALFORMED_JSON"
    MISSING_FIELDS = "MISSING_FIELDS"
    TIMEOUT = "TIMEOUT"
    REFUSAL = "REFUSAL"


class FakeLLMClient:
    def __init__(self, scenario: FakeScenario, fixture_dir: Path) -> None:
        self.scenario = scenario
        self.fixture_dir = fixture_dir

    def _load_json(self, name: str) -> dict:
        raw = (self.fixture_dir / f"{name}.json").read_text(encoding="utf-8")
        return json.loads(raw)

    def generate_json(self, db: Session, user_id: int, prompt: str) -> dict:
        if self.scenario == FakeScenario.OK_LUNCH_PLAN:
            return self._load_json("OK_LUNCH_PLAN")
        if self.scenario == FakeScenario.OK_TIRED_ANALYSIS:
            return self._load_json("OK_TIRED_ANALYSIS")
        if self.scenario == FakeScenario.MISSING_FIELDS:
            return self._load_json("MISSING_FIELDS")
        if self.scenario == FakeScenario.MALFORMED_JSON:
            raw = (self.fixture_dir / "MALFORMED_JSON.txt").read_text(encoding="utf-8")
            return parse_llm_json(raw)
        if self.scenario == FakeScenario.TIMEOUT:
            raise TimeoutError("simulated timeout")
        if self.scenario == FakeScenario.REFUSAL:
            return {
                "answer": "I cannot provide that request, but I can help with a safer plan.",
                "rationale_bullets": [
                    "The requested guidance is outside safe coaching boundaries.",
                    "Safer alternatives can still support your goal.",
                    "We can use your baseline and trends for a practical next step.",
                ],
                "recommended_actions": [
                    {
                        "title": "Safer alternative",
                        "steps": [
                            "Pick one low-risk habit for 7 days.",
                            "Track response daily.",
                        ],
                    }
                ],
                "suggested_questions": [
                    "Want a safer alternative plan?",
                    "Want help setting one measurable goal for this week?",
                    "Want a daily check-in template?",
                ],
                "safety_flags": ["refusal"],
            }
        raise ValueError("Unknown fake scenario")


@pytest.fixture(scope="session")
def fixture_dir() -> Path:
    return Path(__file__).resolve().parent / "fixtures" / "llm"


@pytest.fixture(scope="session")
def test_db_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    db_path = tmp_path_factory.mktemp("db") / "longevity_test.db"
    configure_database(str(db_path))
    create_tables()
    return db_path


@pytest.fixture(scope="session")
def app(test_db_path: Path):
    from app.main import app as fastapi_app

    return fastapi_app


@pytest.fixture
def client(app):
    app.dependency_overrides = {}
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides = {}


@pytest.fixture
def db_session(test_db_path: Path):
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def create_user(db_session: Session) -> Callable[..., User]:
    def _create_user(with_ai_config: bool = True) -> User:
        email = f"user_{uuid4().hex[:10]}@test.com"
        user = User(email=email, password_hash=get_password_hash("StrongPass123"))
        db_session.add(user)
        db_session.flush()
        if with_ai_config:
            cfg = UserAIConfig(
                user_id=user.id,
                ai_provider="openai",
                ai_model="gpt-4.1-mini",
                encrypted_api_key=encrypt_api_key("sk-test-12345678"),
            )
            db_session.add(cfg)
        db_session.commit()
        db_session.refresh(user)
        return user

    return _create_user


@pytest.fixture
def auth_token(client: TestClient) -> str:
    email = f"auth_{uuid4().hex[:10]}@test.com"
    password = "StrongPass123"
    signup = client.post(
        "/auth/signup",
        json={
            "email": email,
            "password": password,
            "ai_config": {
                "ai_provider": "openai",
                "ai_model": "gpt-4.1-mini",
                "ai_api_key": "sk-test-12345678",
            },
        },
    )
    assert signup.status_code == 201
    login = client.post("/auth/login", data={"username": email, "password": password})
    assert login.status_code == 200
    return login.json()["access_token"]


@pytest.fixture
def seed_baseline(db_session: Session):
    def _seed(user_id: int) -> Baseline:
        row = Baseline(
            user_id=user_id,
            primary_goal="energy",
            weight=80.0,
            waist=92.0,
            systolic_bp=122,
            diastolic_bp=79,
            resting_hr=61,
            sleep_hours=7.0,
            activity_level="moderate",
            energy=7,
            mood=7,
            stress=4,
            sleep_quality=7,
            motivation=8,
        )
        db_session.add(row)
        db_session.commit()
        db_session.refresh(row)
        return row

    return _seed


@pytest.fixture
def seed_metrics(db_session: Session):
    def _seed(user_id: int) -> list[Metric]:
        now = datetime.now(timezone.utc)
        rows = [
            Metric(user_id=user_id, metric_type="sleep_hours", value_num=7.2, taken_at=now - timedelta(days=1)),
            Metric(user_id=user_id, metric_type="energy_1_10", value_num=7, taken_at=now - timedelta(days=1)),
            Metric(user_id=user_id, metric_type="bp_systolic", value_num=121, taken_at=now - timedelta(days=2)),
            Metric(user_id=user_id, metric_type="bp_diastolic", value_num=78, taken_at=now - timedelta(days=2)),
            Metric(user_id=user_id, metric_type="weight_kg", value_num=80.5, taken_at=now - timedelta(days=3)),
        ]
        db_session.add_all(rows)
        db_session.commit()
        for row in rows:
            db_session.refresh(row)
        return rows

    return _seed


@pytest.fixture
def seed_scores(db_session: Session):
    def _seed(user_id: int) -> tuple[DomainScore, CompositeScore]:
        now = datetime.now(timezone.utc)
        domain = DomainScore(
            user_id=user_id,
            sleep_score=80,
            metabolic_score=77,
            recovery_score=75,
            behavioral_score=70,
            fitness_score=72,
            computed_at=now,
        )
        composite = CompositeScore(user_id=user_id, longevity_score=75, computed_at=now)
        db_session.add(domain)
        db_session.add(composite)
        db_session.commit()
        db_session.refresh(domain)
        db_session.refresh(composite)
        return domain, composite

    return _seed


@pytest.fixture
def fake_llm_factory(fixture_dir: Path) -> Callable[[FakeScenario], FakeLLMClient]:
    def _factory(scenario: FakeScenario) -> FakeLLMClient:
        return FakeLLMClient(scenario=scenario, fixture_dir=fixture_dir)

    return _factory


@pytest.fixture
def override_llm(app, fake_llm_factory):
    def _override(scenario: FakeScenario) -> None:
        app.dependency_overrides[get_llm_client] = lambda: fake_llm_factory(scenario)

    return _override
