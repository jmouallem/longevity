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


def test_chat_threads_created_by_coach_calls(client, auth_token, override_llm) -> None:
    headers = {"Authorization": f"Bearer {auth_token}"}
    baseline = client.post("/intake/baseline", headers=headers, json=_baseline_payload())
    assert baseline.status_code == 200
    override_llm(FakeScenario.OK_LUNCH_PLAN)

    q1 = client.post("/coach/question", headers=headers, json={"question": "How do I improve energy this week?"})
    assert q1.status_code == 200
    body1 = q1.json()
    thread_id = body1["thread_id"]
    assert thread_id is not None

    q2 = client.post(
        "/coach/question",
        headers=headers,
        json={"question": "Add a simple meal template.", "thread_id": thread_id},
    )
    assert q2.status_code == 200
    assert q2.json()["thread_id"] == thread_id

    threads = client.get("/chat/threads", headers=headers)
    assert threads.status_code == 200
    items = threads.json()["items"]
    assert len(items) == 1
    assert items[0]["thread_id"] == thread_id
    assert items[0]["message_count"] == 4

    messages = client.get(f"/chat/threads/{thread_id}/messages", headers=headers)
    assert messages.status_code == 200
    rows = messages.json()["messages"]
    assert len(rows) == 4
    assert rows[0]["role"] == "user"
    assert rows[1]["role"] == "assistant"


def test_chat_thread_create_endpoint(client, auth_token) -> None:
    headers = {"Authorization": f"Bearer {auth_token}"}
    create = client.post("/chat/threads", headers=headers, json={"title": "Supplements"})
    assert create.status_code == 201
    body = create.json()
    assert body["title"] == "Supplements"
    assert body["message_count"] == 0

    listing = client.get("/chat/threads", headers=headers)
    assert listing.status_code == 200
    assert any(item["thread_id"] == body["thread_id"] for item in listing.json()["items"])
