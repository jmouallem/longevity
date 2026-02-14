from conftest import FakeScenario


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
    ]:
        assert key in body
    assert len(body["suggested_questions"]) >= 3


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
