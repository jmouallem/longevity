from datetime import date

from conftest import FakeScenario
from app.db.models import ConversationSummary, FeedbackEntry


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


def test_coach_unauthorized(client) -> None:
    response = client.post("/coach/question", json={"question": "What should I do?"})
    assert response.status_code == 401


def test_coach_baseline_missing_safe_shape(client, auth_token, override_llm) -> None:
    override_llm(FakeScenario.OK_LUNCH_PLAN)
    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.post("/coach/question", headers=headers, json={"question": "I feel tired lately."})
    assert response.status_code == 200
    body = response.json()
    assert "complete baseline" in body["answer"].lower()
    assert "baseline_missing" in body["safety_flags"]
    assert len(body["suggested_questions"]) >= 3


def test_coach_ok_fixture_response(client, auth_token, override_llm) -> None:
    headers = {"Authorization": f"Bearer {auth_token}"}
    baseline = client.post("/intake/baseline", headers=headers, json=_baseline_payload())
    assert baseline.status_code == 200
    override_llm(FakeScenario.OK_LUNCH_PLAN)

    response = client.post(
        "/coach/question",
        headers=headers,
        json={"question": "What should I eat for lunch today?", "mode": "quick"},
    )
    assert response.status_code == 200
    body = response.json()
    for key in [
        "answer",
        "rationale_bullets",
        "recommended_actions",
        "suggested_questions",
        "safety_flags",
        "disclaimer",
        "thread_id",
        "agent_trace",
    ]:
        assert key in body
    assert body["thread_id"] is not None
    assert isinstance(body["agent_trace"], list)
    assert len(body["suggested_questions"]) >= 3
    assert any("daily" in q.lower() and "log" in q.lower() for q in body["suggested_questions"])
    assert "daily log hint" in body["answer"].lower()
    assert "energy and recovery" in body["answer"].lower()


def test_coach_malformed_json_fixture_fallback(client, auth_token, override_llm) -> None:
    headers = {"Authorization": f"Bearer {auth_token}"}
    baseline = client.post("/intake/baseline", headers=headers, json=_baseline_payload())
    assert baseline.status_code == 200
    override_llm(FakeScenario.MALFORMED_JSON)

    response = client.post("/coach/question", headers=headers, json={"question": "How can I improve energy?"})
    assert response.status_code == 200
    body = response.json()
    assert "llm_unavailable" in body["safety_flags"]
    assert len(body["suggested_questions"]) >= 3


def test_coach_safety_phrase_escalates(client, auth_token, override_llm) -> None:
    headers = {"Authorization": f"Bearer {auth_token}"}
    override_llm(FakeScenario.TIMEOUT)

    response = client.post(
        "/coach/question",
        headers=headers,
        json={"question": "I have chest pain and feel faint."},
    )
    assert response.status_code == 200
    body = response.json()
    assert "urgent_symptom_language" in body["safety_flags"]


def test_coach_persists_agent_trace(client, auth_token, override_llm, db_session) -> None:
    headers = {"Authorization": f"Bearer {auth_token}"}
    baseline = client.post("/intake/baseline", headers=headers, json=_baseline_payload())
    assert baseline.status_code == 200
    override_llm(FakeScenario.OK_LUNCH_PLAN)

    response = client.post(
        "/coach/question",
        headers=headers,
        json={"question": "Build a supplement plan based on my current stack.", "mode": "deep", "deep_think": True},
    )
    assert response.status_code == 200

    row = db_session.query(ConversationSummary).order_by(ConversationSummary.created_at.desc()).first()
    assert row is not None
    assert row.agent_trace_json
    assert "nutritionist" in row.agent_trace_json


def test_daily_checkin_plan_is_specialist_and_time_aligned(client, auth_token) -> None:
    headers = {"Authorization": f"Bearer {auth_token}"}
    baseline = client.post("/intake/baseline", headers=headers, json=_baseline_payload())
    assert baseline.status_code == 200

    response = client.post(
        "/coach/daily-checkin-plan",
        headers=headers,
        json={"local_hour": 8, "timezone_offset_minutes": -300, "generate_with_ai": False},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["time_bucket"] == "morning"
    assert body["goal_focus"] == "energy"
    assert len(body["questions"]) >= 8
    keys = {item["key"] for item in body["questions"]}
    assert {"sleep_hours", "energy", "stress", "tracked_signals", "notes"} <= keys
    assert all(item.get("specialist") for item in body["questions"])
    nutrition_q = next((item["question"] for item in body["questions"] if item["key"] == "nutrition_on_plan"), "")
    assert "on-plan" not in nutrition_q.lower()


def test_daily_checkin_plan_skips_already_captured_weight_signal(client, auth_token) -> None:
    headers = {"Authorization": f"Bearer {auth_token}"}
    baseline = client.post("/intake/baseline", headers=headers, json=_baseline_payload())
    assert baseline.status_code == 200
    metric = client.post(
        "/metrics",
        headers=headers,
        json={"metric_type": "weight_kg", "value": 119.2},
    )
    assert metric.status_code == 201

    response = client.post(
        "/coach/daily-checkin-plan",
        headers=headers,
        json={"local_hour": 8, "timezone_offset_minutes": -300, "generate_with_ai": False},
    )
    assert response.status_code == 200
    body = response.json()
    keys = {item["key"] for item in body["questions"]}
    assert "weight_kg" not in keys
    assert "weigh_in_done" not in keys


def test_runtime_specialist_gap_creates_feedback_entry(client, auth_token, override_llm, db_session) -> None:
    headers = {"Authorization": f"Bearer {auth_token}"}
    baseline = client.post("/intake/baseline", headers=headers, json=_baseline_payload())
    assert baseline.status_code == 200
    override_llm(FakeScenario.OK_LUNCH_PLAN)

    response = client.post(
        "/coach/question",
        headers=headers,
        json={
            "question": "Please audit my supplement stack for interactions and optimize timing.",
            "mode": "deep",
            "deep_think": True,
        },
    )
    assert response.status_code == 200
    rows = (
        db_session.query(FeedbackEntry)
        .filter(FeedbackEntry.page == "coach_runtime")
        .order_by(FeedbackEntry.created_at.desc())
        .all()
    )
    assert rows
    assert any("Supplement Auditor" in row.title for row in rows)
    assert any(str(row.user_email).startswith("system:") for row in rows)


def test_daily_checkin_answer_parser_accepts_free_text_with_details(client, auth_token, override_llm) -> None:
    headers = {"Authorization": f"Bearer {auth_token}"}
    # Force heuristic path to verify resilient parsing when utility model is unavailable.
    override_llm(FakeScenario.TIMEOUT)
    response = client.post(
        "/coach/daily-checkin/parse-answer",
        headers=headers,
        json={
            "key": "nutrition_on_plan",
            "question": "Have you logged what you ate so far today?",
            "answer_text": "no, but I ate two pieces of pizza for breakfast",
            "value_type": "bool",
            "goal_focus": "weight",
            "time_bucket": "morning",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["parsed_bool"] is False
    assert "pizza" in (body.get("captured_text") or "").lower()


def test_daily_checkin_answer_parser_accepts_yes_no_short_form(client, auth_token, override_llm) -> None:
    headers = {"Authorization": f"Bearer {auth_token}"}
    override_llm(FakeScenario.TIMEOUT)
    response = client.post(
        "/coach/daily-checkin/parse-answer",
        headers=headers,
        json={
            "key": "hydration_done",
            "question": "Have you started hydration today?",
            "answer_text": "yes",
            "value_type": "bool",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["parsed_bool"] is True


def test_daily_checkin_food_log_summary_returns_markdown(client, auth_token, override_llm) -> None:
    headers = {"Authorization": f"Bearer {auth_token}"}
    # Force fallback formatter path; should still return rich markdown.
    override_llm(FakeScenario.TIMEOUT)
    response = client.post(
        "/coach/daily-checkin/food-log-summary",
        headers=headers,
        json={
            "entry_text": "Supper was ramen, 2 eggs, homemade broth, smoked duck breast",
            "local_time_label": "6:45 PM",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert "markdown" in body
    assert "logged your meal" in body["markdown"].lower()


def test_daily_checkin_step_summary_returns_markdown(client, auth_token, override_llm) -> None:
    headers = {"Authorization": f"Bearer {auth_token}"}
    override_llm(FakeScenario.TIMEOUT)
    response = client.post(
        "/coach/daily-checkin/step-summary",
        headers=headers,
        json={
            "key": "hydration_done",
            "label": "Hydration",
            "specialist": "Recovery & Stress Regulator",
            "raw_answer": "just drank a cup of water",
            "parsed_value": True,
            "time_bucket": "evening",
            "current_payload": {"hydration_done": True, "stress": 3, "energy": 7},
            "current_extras": {},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert "markdown" in body
    assert "logged update" in body["markdown"].lower()


def test_proactive_card_returns_markdown_from_daily_weekly_monthly_inputs(client, auth_token, override_llm) -> None:
    headers = {"Authorization": f"Bearer {auth_token}"}
    baseline = client.post("/intake/baseline", headers=headers, json=_baseline_payload())
    assert baseline.status_code == 200
    today = date.today().isoformat()
    upsert = client.put(
        f"/daily-log/{today}",
        headers=headers,
        json={
            "sleep_hours": 7.3,
            "energy": 7,
            "mood": 7,
            "stress": 4,
            "training_done": True,
            "nutrition_on_plan": True,
        },
    )
    assert upsert.status_code == 200
    override_llm(FakeScenario.TIMEOUT)
    response = client.post(
        "/coach/proactive-card",
        headers=headers,
        json={"card_type": "daily_summary"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["card_type"] == "daily_summary"
    assert "daily summary" in body["markdown"].lower()
    assert "daily totals snapshot" in body["markdown"].lower()
    assert "remaining today vs goal" in body["markdown"].lower()


def test_proactive_card_daily_summary_estimates_free_text_food_log(client, auth_token, override_llm) -> None:
    headers = {"Authorization": f"Bearer {auth_token}"}
    baseline = client.post("/intake/baseline", headers=headers, json=_baseline_payload())
    assert baseline.status_code == 200

    today = date.today().isoformat()
    upsert = client.put(
        f"/daily-log/{today}",
        headers=headers,
        json={
            "sleep_hours": 7.0,
            "energy": 7,
            "mood": 8,
            "stress": 2,
            "nutrition_on_plan": True,
            "checkin_payload_json": {
                "answers": {
                    "nutrition_on_plan": {
                        "raw_answer": (
                            "I ate to pieces of chicken pizza for breakfast, "
                            "2 pieces of sour dough toast with peanut butter and banana for lunch"
                        )
                    }
                },
                "extras": {},
            },
        },
    )
    assert upsert.status_code == 200

    override_llm(FakeScenario.TIMEOUT)
    response = client.post(
        "/coach/proactive-card",
        headers=headers,
        json={"card_type": "daily_summary"},
    )
    assert response.status_code == 200
    markdown = response.json()["markdown"].lower()
    assert "- calories: ~" in markdown
    assert "- protein: ~" in markdown
    assert "- carbs: ~" in markdown
    assert "- fat: ~" in markdown
    assert "estimate requires more detailed meal logging" not in markdown


def test_proactive_card_uses_notes_chat_progress_for_food_details(client, auth_token, override_llm) -> None:
    headers = {"Authorization": f"Bearer {auth_token}"}
    baseline = client.post("/intake/baseline", headers=headers, json=_baseline_payload())
    assert baseline.status_code == 200
    today = date.today().isoformat()
    upsert = client.put(
        f"/daily-log/{today}",
        headers=headers,
        json={
            "sleep_hours": 0.0,
            "energy": 5,
            "mood": 5,
            "stress": 5,
            "nutrition_on_plan": False,
            "notes": "chat_progress: woke up at 4:30am, had coffee with cream, and two pieces of chicken pizza for breakfast",
        },
    )
    assert upsert.status_code == 200
    override_llm(FakeScenario.TIMEOUT)
    response = client.post(
        "/coach/proactive-card",
        headers=headers,
        json={"card_type": "daily_summary"},
    )
    assert response.status_code == 200
    markdown = response.json()["markdown"].lower()
    assert "food log details:" in markdown
    assert "chicken pizza" in markdown


def test_proactive_card_rejects_invalid_card_type(client, auth_token) -> None:
    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.post(
        "/coach/proactive-card",
        headers=headers,
        json={"card_type": "invalid"},
    )
    assert response.status_code == 422


def test_chat_progress_signal_is_captured_into_daily_log_and_metrics(client, auth_token, override_llm) -> None:
    headers = {"Authorization": f"Bearer {auth_token}"}
    baseline = client.post("/intake/baseline", headers=headers, json=_baseline_payload())
    assert baseline.status_code == 200
    override_llm(FakeScenario.TIMEOUT)

    question = (
        "I ate 2 slices of pizza for breakfast, drank 4 cups of water, "
        "my weight is 264.8 lb, bp 122/82, hr 56, and took candesartan."
    )
    response = client.post("/coach/question", headers=headers, json={"question": question})
    assert response.status_code == 200

    today = date.today().isoformat()
    log_resp = client.get(f"/daily-log?from={today}&to={today}", headers=headers)
    assert log_resp.status_code == 200
    items = log_resp.json().get("items") or []
    assert items
    first = items[0]
    assert first["nutrition_on_plan"] is True
    payload_blob = first.get("checkin_payload_json") or {}
    extras = payload_blob.get("extras") or {}
    assert "pizza" in str(extras.get("nutrition_food_details", "")).lower()
    assert "water" in str(extras.get("hydration_progress", "")).lower()
    assert "candesartan" in str(extras.get("meds_taken", "")).lower()

    weight_metrics = client.get("/metrics?metric_type=weight_kg", headers=headers)
    assert weight_metrics.status_code == 200
    metric_items = weight_metrics.json().get("items") or []
    assert metric_items


def test_chat_progress_no_schema_still_updates_food_details(client, auth_token, override_llm) -> None:
    headers = {"Authorization": f"Bearer {auth_token}"}
    baseline = client.post("/intake/baseline", headers=headers, json=_baseline_payload())
    assert baseline.status_code == 200
    override_llm(FakeScenario.NO_SCHEMA)

    question = "I ate a bran muffin for breakfast"
    response = client.post("/coach/question", headers=headers, json={"question": question})
    assert response.status_code == 200

    today = date.today().isoformat()
    log_resp = client.get(f"/daily-log?from={today}&to={today}", headers=headers)
    assert log_resp.status_code == 200
    items = log_resp.json().get("items") or []
    assert items
    first = items[0]
    assert first["nutrition_on_plan"] is True
    payload_blob = first.get("checkin_payload_json") or {}
    extras = payload_blob.get("extras") or {}
    assert "bran muffin" in str(extras.get("nutrition_food_details", "")).lower()


def test_chat_progress_no_schema_meds_only_does_not_mark_food_logged(client, auth_token, override_llm) -> None:
    headers = {"Authorization": f"Bearer {auth_token}"}
    baseline = client.post("/intake/baseline", headers=headers, json=_baseline_payload())
    assert baseline.status_code == 200
    override_llm(FakeScenario.NO_SCHEMA)

    question = "I took candesartan at 6:30am"
    response = client.post("/coach/question", headers=headers, json={"question": question})
    assert response.status_code == 200

    today = date.today().isoformat()
    log_resp = client.get(f"/daily-log?from={today}&to={today}", headers=headers)
    assert log_resp.status_code == 200
    items = log_resp.json().get("items") or []
    assert items
    first = items[0]
    assert first["nutrition_on_plan"] is False
    payload_blob = first.get("checkin_payload_json") or {}
    extras = payload_blob.get("extras") or {}
    assert not extras.get("nutrition_food_details")
    assert "candesartan" in str(extras.get("meds_taken", "")).lower()


def test_chat_progress_no_schema_food_fragment_excludes_sleep_and_meds_clauses(client, auth_token, override_llm) -> None:
    headers = {"Authorization": f"Bearer {auth_token}"}
    baseline = client.post("/intake/baseline", headers=headers, json=_baseline_payload())
    assert baseline.status_code == 200
    override_llm(FakeScenario.NO_SCHEMA)

    question = "woke up at 4:30am, took blood pressure meds, had coffee with cream, and two pieces of chicken pizza for breakfast"
    response = client.post("/coach/question", headers=headers, json={"question": question})
    assert response.status_code == 200

    today = date.today().isoformat()
    log_resp = client.get(f"/daily-log?from={today}&to={today}", headers=headers)
    assert log_resp.status_code == 200
    items = log_resp.json().get("items") or []
    assert items
    payload_blob = (items[0].get("checkin_payload_json") or {})
    extras = payload_blob.get("extras") or {}
    food = str(extras.get("nutrition_food_details", "")).lower()
    assert "pizza" in food
    assert "woke up" not in food
    assert "blood pressure meds" not in food


def test_chat_progress_no_schema_separates_food_and_meds_fields(client, auth_token, override_llm) -> None:
    headers = {"Authorization": f"Bearer {auth_token}"}
    baseline = client.post("/intake/baseline", headers=headers, json=_baseline_payload())
    assert baseline.status_code == 200
    override_llm(FakeScenario.NO_SCHEMA)

    question = "woke up at 4:30am, took blood pressure meds, had coffee with cream, and two pieces of chicken pizza for breakfast"
    response = client.post("/coach/question", headers=headers, json={"question": question})
    assert response.status_code == 200

    today = date.today().isoformat()
    log_resp = client.get(f"/daily-log?from={today}&to={today}", headers=headers)
    assert log_resp.status_code == 200
    items = log_resp.json().get("items") or []
    assert items
    payload_blob = (items[0].get("checkin_payload_json") or {})
    extras = payload_blob.get("extras") or {}
    food = str(extras.get("nutrition_food_details", "")).lower()
    meds = str(extras.get("meds_taken", "")).lower()
    assert "pizza" in food
    assert "blood pressure med" not in food
    assert "blood pressure med" in meds
    assert "pizza" not in meds


def test_chat_progress_mixed_rollup_is_sanitized_by_category(client, auth_token, override_llm) -> None:
    headers = {"Authorization": f"Bearer {auth_token}"}
    baseline = client.post("/intake/baseline", headers=headers, json=_baseline_payload())
    assert baseline.status_code == 200
    override_llm(FakeScenario.MIXED_ROLLUP)

    question = "woke up at 4:30am, took blood pressure meds, had coffee with cream, and two pieces of chicken pizza for breakfast"
    response = client.post("/coach/question", headers=headers, json={"question": question})
    assert response.status_code == 200

    today = date.today().isoformat()
    log_resp = client.get(f"/daily-log?from={today}&to={today}", headers=headers)
    assert log_resp.status_code == 200
    items = log_resp.json().get("items") or []
    assert items
    payload_blob = (items[0].get("checkin_payload_json") or {})
    extras = payload_blob.get("extras") or {}

    food = str(extras.get("nutrition_food_details", "")).lower()
    meds = str(extras.get("meds_taken", "")).lower()
    assert "pizza" in food
    assert "blood pressure med" not in food
    assert "woke up" not in food
    assert "blood pressure med" in meds
    assert "pizza" not in meds
