from datetime import date
from uuid import uuid4


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _signup_and_login(client, email: str, password: str) -> str:
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


def test_daily_log_upsert_and_list(client, auth_token) -> None:
    today = date.today().isoformat()
    headers = _auth_headers(auth_token)
    payload = {
        "sleep_hours": 7.4,
        "energy": 8,
        "mood": 7,
        "stress": 4,
        "training_done": True,
        "nutrition_on_plan": True,
        "notes": "Solid day",
    }
    upsert = client.put(f"/daily-log/{today}", headers=headers, json=payload)
    assert upsert.status_code == 200
    body = upsert.json()
    assert body["log_date"] == today
    assert body["sleep_hours"] == payload["sleep_hours"]
    assert body["training_done"] is True

    payload["sleep_hours"] = 6.9
    payload["stress"] = 6
    upsert2 = client.put(f"/daily-log/{today}", headers=headers, json=payload)
    assert upsert2.status_code == 200
    assert upsert2.json()["sleep_hours"] == 6.9
    assert upsert2.json()["stress"] == 6

    listed = client.get("/daily-log", headers=headers)
    assert listed.status_code == 200
    items = listed.json()["items"]
    assert len(items) >= 1
    assert items[0]["log_date"] == today


def test_daily_log_user_isolation(client) -> None:
    password = "StrongPass123"
    token_a = _signup_and_login(client, f"a_{uuid4().hex[:8]}@test.com", password)
    token_b = _signup_and_login(client, f"b_{uuid4().hex[:8]}@test.com", password)
    today = date.today().isoformat()
    payload = {
        "sleep_hours": 7.0,
        "energy": 7,
        "mood": 7,
        "stress": 5,
        "training_done": False,
        "nutrition_on_plan": True,
    }
    save_a = client.put(f"/daily-log/{today}", headers=_auth_headers(token_a), json=payload)
    assert save_a.status_code == 200

    list_b = client.get("/daily-log", headers=_auth_headers(token_b))
    assert list_b.status_code == 200
    assert list_b.json()["items"] == []


def test_overall_summary_contract(client, auth_token) -> None:
    headers = _auth_headers(auth_token)
    summary_empty = client.get("/summary/overall", headers=headers)
    assert summary_empty.status_code == 200
    body = summary_empty.json()
    assert "health_score" in body
    assert "category_scores" in body
    assert "wellness_report" in body
    assert "weekly_personalized_insights" in body
    assert "personalized_journey" in body
    assert "today" in body
    assert "trend_7d" in body
    assert "trend_30d" in body
    assert isinstance(body["health_score"], int)
    assert 0 <= body["health_score"] <= 100
    expected_domains = {"Body Composition", "Nutrition", "Movement", "Sleep", "Stress"}
    assert expected_domains.issubset(set(body["category_scores"].keys()))
    assert isinstance(body["wellness_report"], list)
    assert isinstance(body["weekly_personalized_insights"], list)
    assert isinstance(body["personalized_journey"], dict)
    assert "pattern_signals" in body["personalized_journey"]
    assert "prevention_measures" in body["personalized_journey"]
    assert isinstance(body["top_wins"], list)
    assert isinstance(body["top_risks"], list)
    assert isinstance(body["next_best_action"], str)

    today = date.today().isoformat()
    save = client.put(
        f"/daily-log/{today}",
        headers=headers,
        json={
            "sleep_hours": 7.8,
            "energy": 8,
            "mood": 8,
            "stress": 4,
            "training_done": True,
            "nutrition_on_plan": True,
            "notes": "Good momentum",
        },
    )
    assert save.status_code == 200

    summary_full = client.get("/summary/overall", headers=headers)
    assert summary_full.status_code == 200
    full = summary_full.json()
    assert full["today"]["log_date"] == today
    assert full["trend_7d"]["entries"] >= 1
    assert 0 <= full["health_score"] <= 100
    assert len(full["weekly_personalized_insights"]) >= 1
    assert len(full["personalized_journey"]["pattern_signals"]) >= 1
