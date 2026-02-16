from datetime import date, datetime, timezone
from uuid import uuid4

from app.db.models import (
    Baseline,
    CompositeScore,
    ConversationSummary,
    DailyLog,
    DomainScore,
    Metric,
    ModelUsageStat,
)


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


def test_workspace_page_contract(client) -> None:
    response = client.get("/app")
    assert response.status_code == 200
    html = response.text
    assert "Longevity Workspace" in html
    assert "Intake Coach" in html
    assert "Default Chat" in html
    assert "Model Token Usage" in html
    assert "intake-alert-dot" in html
    assert "preferred units" in html


def test_intake_status_lifecycle(client, auth_token) -> None:
    headers = {"Authorization": f"Bearer {auth_token}"}
    status_before = client.get("/intake/status", headers=headers)
    assert status_before.status_code == 200
    assert status_before.json()["baseline_completed"] is False

    upsert = client.post("/intake/baseline", headers=headers, json=_baseline_payload())
    assert upsert.status_code == 200

    status_after = client.get("/intake/status", headers=headers)
    assert status_after.status_code == 200
    body = status_after.json()
    assert body["baseline_completed"] is True
    assert body["primary_goal"] == "energy"


def test_change_password_flow(client) -> None:
    email = f"pw_{uuid4().hex[:8]}@test.com"
    old_password = "StrongPass123"
    new_password = "StrongerPass456!"
    signup = client.post("/auth/signup", json={"email": email, "password": old_password})
    assert signup.status_code == 201

    login_old = client.post("/auth/login", data={"username": email, "password": old_password})
    assert login_old.status_code == 200
    token = login_old.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    change = client.put(
        "/auth/change-password",
        headers=headers,
        json={"current_password": old_password, "new_password": new_password},
    )
    assert change.status_code == 204

    login_old_again = client.post("/auth/login", data={"username": email, "password": old_password})
    assert login_old_again.status_code == 401
    login_new = client.post("/auth/login", data={"username": email, "password": new_password})
    assert login_new.status_code == 200


def test_model_usage_endpoint_returns_rows(client, auth_token) -> None:
    headers = {"Authorization": f"Bearer {auth_token}"}
    usage = client.get("/auth/model-usage", headers=headers)
    assert usage.status_code == 200
    items = usage.json()["items"]
    assert isinstance(items, list)


def test_intake_conversation_flow(client, auth_token) -> None:
    headers = {"Authorization": f"Bearer {auth_token}"}
    start = client.post("/intake/conversation/start", headers=headers, json={"top_goals": ["More energy", "Sleep"]})
    assert start.status_code == 200
    session_id = start.json()["session_id"]

    # Drive required fields to completion.
    answers = [
        "42",
        "male",
        "80",
        "92",
        "122",
        "79",
        "61",
        "7.2",
        "moderate",
        "7",
        "7",
        "4",
        "7",
        "8",
        "No additional context",
    ]
    last = None
    for answer in answers:
        last = client.post(
            "/intake/conversation/answer",
            headers=headers,
            json={"session_id": session_id, "answer": answer},
        )
        assert last.status_code == 200
    assert last is not None
    assert last.json()["ready_to_complete"] is True

    complete = client.post(
        "/intake/conversation/complete",
        headers=headers,
        json={"session_id": session_id},
    )
    assert complete.status_code == 200
    body = complete.json()
    assert body["baseline_id"] > 0
    assert body["primary_goal"] == "More energy"


def test_intake_conversation_accepts_mixed_units(client, auth_token) -> None:
    headers = {"Authorization": f"Bearer {auth_token}"}
    start = client.post("/intake/conversation/start", headers=headers, json={"top_goals": ["fat loss", "better sleep"]})
    assert start.status_code == 200
    session_id = start.json()["session_id"]

    # age, sex, weight(lbs), waist(in), BP as 120/80, resting hr, sleep in h/m, activity and scales.
    answers = [
        "37",
        "female",
        "185 lbs",
        "34 inches",
        "120/80",
        "63 bpm",
        "7h 30m",
        "light activity",
        "6/10",
        "7",
        "8",
        "6",
        "7",
        "no more",
    ]
    for answer in answers:
        step = client.post(
            "/intake/conversation/answer",
            headers=headers,
            json={"session_id": session_id, "answer": answer},
        )
        assert step.status_code == 200

    complete = client.post("/intake/conversation/complete", headers=headers, json={"session_id": session_id})
    assert complete.status_code == 200
    baseline = client.get("/intake/baseline", headers=headers)
    assert baseline.status_code == 200
    body = baseline.json()
    # Converted and normalized values:
    assert body["activity_level"] == "light"
    assert body["sleep_hours"] >= 7.4


def test_reset_model_usage_only(client, auth_token, db_session) -> None:
    headers = {"Authorization": f"Bearer {auth_token}"}
    session = client.get("/auth/session", headers=headers)
    assert session.status_code == 200
    user_id = session.json()["user_id"]

    row = ModelUsageStat(
        user_id=user_id,
        provider="openai",
        model="gpt-5-mini",
        request_count=3,
        prompt_tokens=300,
        completion_tokens=120,
        total_tokens=420,
        last_used_at=datetime.now(timezone.utc),
    )
    db_session.add(row)
    db_session.commit()

    reset = client.delete("/auth/model-usage", headers=headers)
    assert reset.status_code == 200
    assert reset.json()["deleted_rows"] >= 1

    usage = client.get("/auth/model-usage", headers=headers)
    assert usage.status_code == 200
    assert usage.json()["items"] == []


def test_reset_user_data_keeps_model_usage(client, auth_token, db_session) -> None:
    headers = {"Authorization": f"Bearer {auth_token}"}
    session = client.get("/auth/session", headers=headers)
    assert session.status_code == 200
    user_id = session.json()["user_id"]

    db_session.add(
        Baseline(
            user_id=user_id,
            primary_goal="energy",
            weight=80.0,
            waist=92.0,
            systolic_bp=122,
            diastolic_bp=79,
            resting_hr=61,
            sleep_hours=7.2,
            activity_level="moderate",
            energy=7,
            mood=7,
            stress=4,
            sleep_quality=7,
            motivation=8,
        )
    )
    db_session.add(
        Metric(
            user_id=user_id,
            metric_type="weight_kg",
            value_num=80.2,
            taken_at=datetime.now(timezone.utc),
        )
    )
    db_session.add(
        DomainScore(
            user_id=user_id,
            sleep_score=75,
            metabolic_score=74,
            recovery_score=73,
            behavioral_score=72,
            fitness_score=71,
            computed_at=datetime.now(timezone.utc),
        )
    )
    db_session.add(CompositeScore(user_id=user_id, longevity_score=74, computed_at=datetime.now(timezone.utc)))
    db_session.add(
        ConversationSummary(
            user_id=user_id,
            created_at=datetime.now(timezone.utc),
            question="q",
            answer_summary="a",
            tags="t",
            safety_flags=None,
            agent_trace_json=None,
        )
    )
    db_session.add(
        DailyLog(
            user_id=user_id,
            log_date=date.today(),
            sleep_hours=7.0,
            energy=7,
            mood=7,
            stress=4,
            training_done=True,
            nutrition_on_plan=True,
            notes="note",
        )
    )
    db_session.add(
        ModelUsageStat(
            user_id=user_id,
            provider="openai",
            model="gpt-5-mini",
            request_count=1,
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            last_used_at=datetime.now(timezone.utc),
        )
    )
    db_session.commit()

    reset = client.delete("/auth/data", headers=headers)
    assert reset.status_code == 200
    assert reset.json()["deleted_rows"] >= 6

    intake = client.get("/intake/status", headers=headers)
    assert intake.status_code == 200
    assert intake.json()["baseline_completed"] is False

    usage = client.get("/auth/model-usage", headers=headers)
    assert usage.status_code == 200
    assert len(usage.json()["items"]) == 1
