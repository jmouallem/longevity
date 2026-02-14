import os
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

TEST_DB_PATH = Path(__file__).resolve().parent / "tmp_slice3_test.db"
if TEST_DB_PATH.exists():
    TEST_DB_PATH.unlink()
os.environ["DB_PATH"] = str(TEST_DB_PATH)

from app.main import app  # noqa: E402


def _signup_and_login(client: TestClient) -> str:
    email = f"slice3_{uuid4().hex[:8]}@test.com"
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


def _baseline_payload() -> dict:
    return {
        "primary_goal": "energy",
        "weight": 80.0,
        "waist": 92.0,
        "systolic_bp": 122,
        "diastolic_bp": 79,
        "resting_hr": 61,
        "sleep_hours": 7.2,
        "activity_level": "moderate",
        "energy": 7,
        "mood": 7,
        "stress": 4,
        "sleep_quality": 7,
        "motivation": 8,
    }


def test_coach_unauthorized_rejected() -> None:
    with TestClient(app) as client:
        response = client.post("/coach/question", json={"question": "What should I do next?"})
        assert response.status_code == 401


def test_coach_authorized_success_with_mocked_llm(monkeypatch) -> None:
    with TestClient(app) as client:
        token = _signup_and_login(client)
        headers = {"Authorization": f"Bearer {token}"}
        baseline = client.post("/intake/baseline", headers=headers, json=_baseline_payload())
        assert baseline.status_code == 200

        def fake_llm(*args, **kwargs):
            return {
                "answer": "Focus on sleep timing and morning activity this week.",
                "rationale_bullets": [
                    "Your current stress and energy pattern suggests recovery drag.",
                    "A stable wake window supports better energy consistency.",
                    "Morning movement improves daytime alertness.",
                ],
                "recommended_actions": [
                    {
                        "title": "Sleep anchor",
                        "steps": ["Set a fixed wake time", "Keep it for 7 days"],
                    }
                ],
                "suggested_questions": [
                    "Want a 7-day sleep plan?",
                    "Want a lunch option set for energy?",
                    "Want a 10-minute evening wind-down routine?",
                ],
                "safety_flags": [],
            }

        monkeypatch.setattr("app.api.coach.request_coaching_json", fake_llm)
        response = client.post(
            "/coach/question",
            headers=headers,
            json={"question": "What should I do next?", "mode": "quick"},
        )
        assert response.status_code == 200
        body = response.json()
        assert "answer" in body
        assert "rationale_bullets" in body
        assert "recommended_actions" in body
        assert "suggested_questions" in body
        assert "safety_flags" in body
        assert "disclaimer" in body


def test_coach_requires_baseline_for_detailed_advice() -> None:
    with TestClient(app) as client:
        token = _signup_and_login(client)
        headers = {"Authorization": f"Bearer {token}"}
        response = client.post(
            "/coach/question",
            headers=headers,
            json={"question": "I am tired all day. What should I do?"},
        )
        assert response.status_code == 200
        body = response.json()
        assert "complete baseline" in body["answer"].lower()
        assert "baseline_missing" in body["safety_flags"]


def test_coach_safety_trigger_emergency_guidance() -> None:
    with TestClient(app) as client:
        token = _signup_and_login(client)
        headers = {"Authorization": f"Bearer {token}"}
        response = client.post(
            "/coach/question",
            headers=headers,
            json={"question": "I have chest pain and feel faint."},
        )
        assert response.status_code == 200
        body = response.json()
        assert "emergency" in body["answer"].lower() or "urgent" in body["answer"].lower()
        assert "urgent_symptom_language" in body["safety_flags"]


def test_coach_json_parse_failure_fallback(monkeypatch) -> None:
    with TestClient(app) as client:
        token = _signup_and_login(client)
        headers = {"Authorization": f"Bearer {token}"}
        baseline = client.post("/intake/baseline", headers=headers, json=_baseline_payload())
        assert baseline.status_code == 200

        def fake_llm_failure(*args, **kwargs):
            raise ValueError("Invalid JSON response from LLM")

        monkeypatch.setattr("app.api.coach.request_coaching_json", fake_llm_failure)
        response = client.post(
            "/coach/question",
            headers=headers,
            json={"question": "What should I eat for lunch?", "mode": "quick"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["safety_flags"] == ["llm_unavailable"]
        assert len(body["suggested_questions"]) >= 3


def test_coach_deep_think_flag_routes_request(monkeypatch) -> None:
    with TestClient(app) as client:
        token = _signup_and_login(client)
        headers = {"Authorization": f"Bearer {token}"}
        baseline = client.post("/intake/baseline", headers=headers, json=_baseline_payload())
        assert baseline.status_code == 200

        called = {"deep_think": None}

        def fake_llm_router(*args, **kwargs):
            called["deep_think"] = kwargs.get("deep_think")
            return {
                "answer": "Deep-think response.",
                "rationale_bullets": ["a", "b", "c"],
                "recommended_actions": [{"title": "One step", "steps": ["Do this now"]}],
                "suggested_questions": ["Q1", "Q2", "Q3"],
                "safety_flags": [],
            }

        monkeypatch.setattr("app.api.coach.request_coaching_json", fake_llm_router)
        response = client.post(
            "/coach/question",
            headers=headers,
            json={"question": "Help me plan deeply.", "mode": "deep", "deep_think": True},
        )
        assert response.status_code == 200
        assert called["deep_think"] is True
