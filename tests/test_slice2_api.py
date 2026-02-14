import os
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

# Ensure DB session engine is bound to a test-specific SQLite file before app import.
TEST_DB_PATH = Path(__file__).resolve().parent / "tmp_slice2_test.db"
if TEST_DB_PATH.exists():
    TEST_DB_PATH.unlink()
os.environ["DB_PATH"] = str(TEST_DB_PATH)

from app.main import app  # noqa: E402


def _signup_and_login(client: TestClient) -> str:
    email = f"slice2_{uuid4().hex[:8]}@test.com"
    password = "StrongPass123"
    signup = client.post("/auth/signup", json={"email": email, "password": password})
    assert signup.status_code == 201
    login = client.post("/auth/login", data={"username": email, "password": password})
    assert login.status_code == 200
    return login.json()["access_token"]


def test_metrics_unauthorized_rejected() -> None:
    with TestClient(app) as client:
        response = client.post("/metrics", json={"metric_type": "sleep_hours", "value": 7.0})
        assert response.status_code == 401


def test_metrics_validation_rejects_out_of_range() -> None:
    with TestClient(app) as client:
        token = _signup_and_login(client)
        headers = {"Authorization": f"Bearer {token}"}
        response = client.post(
            "/metrics",
            headers=headers,
            json={"metric_type": "sleep_hours", "value": 20.0},
        )
        assert response.status_code == 422


def test_dashboard_summary_shape_and_score_bounds() -> None:
    with TestClient(app) as client:
        token = _signup_and_login(client)
        headers = {"Authorization": f"Bearer {token}"}

        metrics = [
            {"metric_type": "sleep_hours", "value": 7.5},
            {"metric_type": "sleep_quality_1_10", "value": 8},
            {"metric_type": "energy_1_10", "value": 7},
            {"metric_type": "weight_kg", "value": 82.1},
            {"metric_type": "waist_cm", "value": 92},
            {"metric_type": "bp_systolic", "value": 122},
            {"metric_type": "bp_diastolic", "value": 79},
            {"metric_type": "stress_1_10", "value": 4},
            {"metric_type": "resting_hr_bpm", "value": 61},
            {"metric_type": "steps", "value": 9000},
            {"metric_type": "active_minutes", "value": 45},
        ]
        for payload in metrics:
            response = client.post("/metrics", headers=headers, json=payload)
            assert response.status_code == 201

        summary = client.get("/dashboard/summary", headers=headers)
        assert summary.status_code == 200

        body = summary.json()
        assert set(body.keys()) == {"domain_scores", "composite_score", "trends"}
        domain = body["domain_scores"]
        for field in [
            "sleep_score",
            "metabolic_score",
            "recovery_score",
            "behavioral_score",
            "fitness_score",
        ]:
            assert 0 <= domain[field] <= 100
        assert 0 <= body["composite_score"]["longevity_score"] <= 100
