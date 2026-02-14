from uuid import uuid4


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


def test_onboarding_page_has_mobile_and_gating_contract(client) -> None:
    response = client.get("/onboarding")
    assert response.status_code == 200
    html = response.text
    assert "Start Intake" in html
    assert "Skip For Now" in html
    assert "disabled" in html
    assert "@media (max-width: 900px)" in html
    assert "Trello" not in html  # style inspiration only, no brand copy.
    assert "Login failed." in html
    assert "Could not save AI settings." in html
    assert "Deep Thinker Model" in html
    assert "Reasoning Model" in html
    assert "Utility Model" in html


def test_model_options_returns_default_best(client, auth_token) -> None:
    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.post("/auth/model-options", headers=headers, json={"ai_provider": "openai"})
    assert response.status_code == 200
    body = response.json()
    assert body["ai_provider"] == "openai"
    assert isinstance(body["models"], list)
    assert body["default_model"] in body["models"]
    assert body["default_deep_thinker_model"] in body["models"]
    assert body["default_reasoning_model"] in body["models"]
    assert body["default_utility_model"] in body["models"]
    assert isinstance(body["model_options"], list)


def test_intake_blocked_without_ai_config(client) -> None:
    email = f"nogate_{uuid4().hex[:8]}@test.com"
    password = "StrongPass123"

    signup = client.post("/auth/signup", json={"email": email, "password": password})
    assert signup.status_code == 201
    login = client.post("/auth/login", data={"username": email, "password": password})
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    intake = client.post("/intake/baseline", headers=headers, json=_baseline_payload())
    assert intake.status_code == 403
    assert "Complete AI provider setup" in intake.json()["detail"]


def test_intake_unlocked_after_ai_config(client, auth_token) -> None:
    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.post("/intake/baseline", headers=headers, json=_baseline_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["baseline_id"] > 0
