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


def test_workspace_page_contract(client) -> None:
    response = client.get("/app")
    assert response.status_code == 200
    html = response.text
    assert "Longevity Workspace" in html
    assert "Baseline Intake" in html
    assert "Default Chat" in html
    assert "Model Token Usage" in html


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
