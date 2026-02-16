import json
from datetime import date, datetime, timezone
from uuid import uuid4

from app.api import intake as intake_api
from app.db.models import (
    Baseline,
    ChatMessage,
    ChatThread,
    CompositeScore,
    ConversationSummary,
    DailyLog,
    DomainScore,
    IntakeConversationSession,
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
        "Lose 10 lbs while keeping strength",
        "3-6 months",
        "Consistency on busy weekdays",
        "42",
        "male",
        "5 ft 10 in",
        "80",
        "92",
        "122",
        "79",
        "61",
        "moderate",
        "intermediate",
        "2 strength + 2 cardio days weekly",
        "gym",
        "none",
        "deadlift 315, bench 205",
        "10:15pm",
        "6:30am",
        "7.2",
        "strong in AM",
        "7",
        "7",
        "4",
        "7",
        "8",
        "none",
        "candesartan 4mg morning",
        "fish oil, magnesium",
        "none",
        "LDL slightly elevated",
        "yes",
        "16:8",
        "experienced",
        "metabolic health",
        "yes, vary by training day",
        "16:8 most weekdays",
        "night walk and breath work",
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

    # Mixed units across intake fields plus optional sections.
    answers = [
        "fat loss with better recovery",
        "4-12 weeks",
        "late-night snacking",
        "37",
        "female",
        "5ft 7in",
        "185 lbs",
        "34 inches",
        "120/80",
        "63 bpm",
        "light activity",
        "beginner",
        "walking only",
        "home bodyweight",
        "knee pain sometimes",
        "unknown",
        "11:00pm",
        "6:30am",
        "7h 30m",
        "afternoon dip",
        "6/10",
        "7",
        "8",
        "6",
        "7",
        "unknown",
        "unknown",
        "multivitamin",
        "unknown",
        "unknown",
        "unsure",
        "flexible",
        "new",
        "schedule",
        "yes",
        "unknown",
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


def test_intake_goal_batch_single_answer_advances_steps(client, auth_token) -> None:
    headers = {"Authorization": f"Bearer {auth_token}"}
    start = client.post("/intake/conversation/start", headers=headers, json={"top_goals": ["Weight loss"]})
    assert start.status_code == 200
    session_id = start.json()["session_id"]
    # A single answer contains target outcome + timeline + challenge.
    step = client.post(
        "/intake/conversation/answer",
        headers=headers,
        json={
            "session_id": session_id,
            "answer": "down to 230lbs, blood pressure normal, timeline 6 months, consistency is the challenge",
        },
    )
    assert step.status_code == 200
    body = step.json()
    # Should skip remaining Batch B fields and move to demographics section.
    assert body["current_step"] == "age_years"


def test_intake_basics_batch_single_answer_advances_steps(client, auth_token) -> None:
    headers = {"Authorization": f"Bearer {auth_token}"}
    start = client.post("/intake/conversation/start", headers=headers, json={"top_goals": ["Weight loss"]})
    assert start.status_code == 200
    session_id = start.json()["session_id"]

    # Complete Batch B in one answer.
    b = client.post(
        "/intake/conversation/answer",
        headers=headers,
        json={
            "session_id": session_id,
            "answer": "down to 230lbs, timeline 6 months, consistency is the challenge",
        },
    )
    assert b.status_code == 200
    assert b.json()["current_step"] == "age_years"

    # Complete most of Batch A in one answer; should move past basics.
    a = client.post(
        "/intake/conversation/answer",
        headers=headers,
        json={
            "session_id": session_id,
            "answer": "52 yrs, male, 270lb, 42inch, 130/80, sedentary",
        },
    )
    assert a.status_code == 200
    assert a.json()["current_step"] != "age_years"
    assert a.json()["current_step"] != "sex_at_birth"
    assert a.json()["current_step"] != "weight"


def test_intake_goal_batch_ai_parser_fills_remaining_fields(monkeypatch, client, auth_token) -> None:
    headers = {"Authorization": f"Bearer {auth_token}"}
    start = client.post("/intake/conversation/start", headers=headers, json={"top_goals": ["Weight loss"]})
    assert start.status_code == 200
    session_id = start.json()["session_id"]

    def fake_ai_parse(*args, **kwargs):
        _ = (args, kwargs)
        return {
            "timeline": "6 months",
            "biggest_challenge": "consistency",
        }

    monkeypatch.setattr(intake_api, "_ai_parse_batch_values", fake_ai_parse)
    step = client.post(
        "/intake/conversation/answer",
        headers=headers,
        json={
            "session_id": session_id,
            "answer": "down to 230lbs and blood pressure normal",
        },
    )
    assert step.status_code == 200
    body = step.json()
    assert body["current_step"] == "age_years"


def test_intake_health_context_single_answer_advances_out_of_batch_e(client, auth_token) -> None:
    headers = {"Authorization": f"Bearer {auth_token}"}
    start = client.post("/intake/conversation/start", headers=headers, json={"top_goals": ["Weight loss"]})
    assert start.status_code == 200
    session_id = start.json()["session_id"]

    answers_by_step = {
        "target_outcome": "down to 230lbs and blood pressure normal",
        "timeline": "6 months",
        "biggest_challenge": "consistency",
        "age_years": "52",
        "sex_at_birth": "male",
        "height_text": "5 ft 10 in",
        "weight": "270 lb",
        "waist": "42 inches",
        "systolic_bp": "130/80",
        "diastolic_bp": "80",
        "activity_level": "sedentary",
        "training_experience": "intermediate",
        "training_history": "2 strength + 2 cardio weekly",
        "equipment_access": "gym",
        "limitations": "none",
        "strength_benchmarks": "deadlift 315",
        "resting_hr": "62",
        "bedtime": "10pm",
        "wake_time": "6am",
        "sleep_hours": "7",
        "sleep_quality": "7",
        "stress": "3",
        "energy": "7",
        "energy_pattern": "strong in AM",
        "mood": "8",
        "motivation": "7",
    }

    step_body = start.json()
    for _ in range(60):
        if step_body.get("current_step") == "health_conditions":
            break
        answer = answers_by_step.get(step_body.get("current_step"), "unknown")
        step = client.post(
            "/intake/conversation/answer",
            headers=headers,
            json={"session_id": session_id, "answer": answer},
        )
        assert step.status_code == 200
        step_body = step.json()

    assert step_body is not None
    assert step_body["current_step"] == "health_conditions"

    e = client.post(
        "/intake/conversation/answer",
        headers=headers,
        json={
            "session_id": session_id,
            "answer": (
                "High blood pressure, high cholesterol, candesartan 4mg am, "
                "ezetimibe 10mg pm, supplements d3 and magnesium and omega 3"
            ),
        },
    )
    assert e.status_code == 200
    body = e.json()
    # Should move out of Batch E after one comprehensive optional health-context answer.
    assert body["current_step"] not in {
        "health_conditions",
        "medication_details",
        "supplement_stack",
        "physician_restrictions",
        "lab_markers",
    }


def test_intake_fasting_single_answer_advances_out_of_batch_f(client, auth_token) -> None:
    headers = {"Authorization": f"Bearer {auth_token}"}
    start = client.post("/intake/conversation/start", headers=headers, json={"top_goals": ["Weight loss"]})
    assert start.status_code == 200
    session_id = start.json()["session_id"]

    answers_by_step = {
        "target_outcome": "down to 230lbs and blood pressure normal",
        "timeline": "6 months",
        "biggest_challenge": "consistency",
        "age_years": "52",
        "sex_at_birth": "male",
        "height_text": "5 ft 10 in",
        "weight": "270 lb",
        "waist": "42 inches",
        "systolic_bp": "130/80",
        "diastolic_bp": "80",
        "activity_level": "sedentary",
        "training_experience": "intermediate",
        "training_history": "2 strength + 2 cardio weekly",
        "equipment_access": "gym",
        "limitations": "none",
        "strength_benchmarks": "deadlift 315",
        "resting_hr": "62",
        "bedtime": "10pm",
        "wake_time": "6am",
        "sleep_hours": "7",
        "sleep_quality": "7",
        "stress": "3",
        "energy": "7",
        "energy_pattern": "strong in AM",
        "mood": "8",
        "motivation": "7",
        "health_conditions": "unknown",
        "medication_details": "unknown",
        "supplement_stack": "unknown",
        "physician_restrictions": "unknown",
        "lab_markers": "unknown",
    }

    step_body = start.json()
    for _ in range(80):
        if step_body.get("current_step") == "fasting_interest":
            break
        answer = answers_by_step.get(step_body.get("current_step"), "unknown")
        step = client.post(
            "/intake/conversation/answer",
            headers=headers,
            json={"session_id": session_id, "answer": answer},
        )
        assert step.status_code == 200
        step_body = step.json()

    assert step_body["current_step"] == "fasting_interest"
    f = client.post(
        "/intake/conversation/answer",
        headers=headers,
        json={
            "session_id": session_id,
            "answer": "fasting yes, flexible, newish, fat loss, metabolic health, willingness yes",
        },
    )
    assert f.status_code == 200
    body = f.json()
    assert body["current_step"] not in {
        "fasting_interest",
        "fasting_style",
        "fasting_experience",
        "fasting_reason",
        "fasting_flexibility",
        "fasting_practices",
        "recovery_practices",
        "goal_notes",
    }


def test_intake_complete_truncates_oversized_optional_strings(client, auth_token, db_session) -> None:
    headers = {"Authorization": f"Bearer {auth_token}"}
    session = client.get("/auth/session", headers=headers)
    assert session.status_code == 200
    user_id = session.json()["user_id"]

    answers = {
        "top_goals": ["Weight loss", "energy"],
        "weight": 100.0,
        "waist": 100.0,
        "systolic_bp": 130,
        "diastolic_bp": 80,
        "resting_hr": 62,
        "sleep_hours": 7.0,
        "activity_level": "moderate",
        "energy": 7,
        "mood": 7,
        "stress": 4,
        "sleep_quality": 7,
        "motivation": 8,
        "training_experience": "Training intermediate, with long narrative that exceeds the 32-char cap.",
        "fasting_style": "fasting yes, flexible, newish, fat loss, metabolic health, willing to vary by day",
    }
    intake_session = IntakeConversationSession(
        user_id=user_id,
        status="active",
        current_step="complete",
        answers_json=json.dumps(answers),
    )
    db_session.add(intake_session)
    db_session.commit()
    db_session.refresh(intake_session)

    complete = client.post(
        "/intake/conversation/complete",
        headers=headers,
        json={"session_id": intake_session.id},
    )
    assert complete.status_code == 200
    body = complete.json()
    assert body["baseline_id"] > 0


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
    thread = ChatThread(
        user_id=user_id,
        title="Chat",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        last_message_at=datetime.now(timezone.utc),
    )
    db_session.add(thread)
    db_session.flush()
    db_session.add(
        ChatMessage(
            thread_id=thread.id,
            user_id=user_id,
            role="user",
            content="hello",
            mode="quick",
            created_at=datetime.now(timezone.utc),
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
    assert reset.json()["deleted_rows"] >= 8

    intake = client.get("/intake/status", headers=headers)
    assert intake.status_code == 200
    assert intake.json()["baseline_completed"] is False

    usage = client.get("/auth/model-usage", headers=headers)
    assert usage.status_code == 200
    assert len(usage.json()["items"]) == 1

    thread_rows = db_session.query(ChatThread).filter(ChatThread.user_id == user_id).all()
    msg_rows = db_session.query(ChatMessage).filter(ChatMessage.user_id == user_id).all()
    assert thread_rows == []
    assert msg_rows == []


def test_reset_daily_data_keeps_intake_baseline_and_chat(client, auth_token, db_session) -> None:
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
    thread = ChatThread(
        user_id=user_id,
        title="Chat",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        last_message_at=datetime.now(timezone.utc),
    )
    db_session.add(thread)
    db_session.flush()
    db_session.add(
        ChatMessage(
            thread_id=thread.id,
            user_id=user_id,
            role="user",
            content="hello",
            mode="quick",
            created_at=datetime.now(timezone.utc),
        )
    )
    db_session.commit()

    reset = client.delete("/auth/daily-data", headers=headers)
    assert reset.status_code == 200
    assert reset.json()["deleted_rows"] >= 5

    intake = client.get("/intake/status", headers=headers)
    assert intake.status_code == 200
    assert intake.json()["baseline_completed"] is True

    thread_rows = db_session.query(ChatThread).filter(ChatThread.user_id == user_id).all()
    msg_rows = db_session.query(ChatMessage).filter(ChatMessage.user_id == user_id).all()
    assert len(thread_rows) == 1
    assert len(msg_rows) == 1

    metric_rows = db_session.query(Metric).filter(Metric.user_id == user_id).all()
    daily_rows = db_session.query(DailyLog).filter(DailyLog.user_id == user_id).all()
    summary_rows = db_session.query(ConversationSummary).filter(ConversationSummary.user_id == user_id).all()
    assert metric_rows == []
    assert daily_rows == []
    assert summary_rows == []


def test_notification_settings_roundtrip(client, auth_token) -> None:
    headers = {"Authorization": f"Bearer {auth_token}"}
    get_default = client.get("/auth/notification-settings", headers=headers)
    assert get_default.status_code == 200
    body = get_default.json()
    assert "enabled" in body
    assert "interval_minutes" in body

    update = client.put(
        "/auth/notification-settings",
        headers=headers,
        json={"enabled": True, "interval_minutes": 90},
    )
    assert update.status_code == 200
    updated = update.json()
    assert updated["enabled"] is True
    assert updated["interval_minutes"] == 90

    get_after = client.get("/auth/notification-settings", headers=headers)
    assert get_after.status_code == 200
    assert get_after.json()["enabled"] is True
    assert get_after.json()["interval_minutes"] == 90
