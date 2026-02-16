from uuid import uuid4


def _login_token(client, email: str, password: str) -> str:
    login = client.post("/auth/login", data={"username": email, "password": password})
    assert login.status_code == 200
    return login.json()["access_token"]


def test_feedback_submit_export_and_clear_shared(client, auth_token) -> None:
    headers_a = {"Authorization": f"Bearer {auth_token}"}

    email_b = f"fb_{uuid4().hex[:8]}@test.com"
    password_b = "StrongPass123"
    signup_b = client.post("/auth/signup", json={"email": email_b, "password": password_b})
    assert signup_b.status_code == 201
    token_b = _login_token(client, email_b, password_b)
    headers_b = {"Authorization": f"Bearer {token_b}"}

    create_a = client.post(
        "/feedback/entries",
        headers=headers_a,
        json={
            "category": "bug",
            "title": "Chat overlay issue",
            "details": "Chat stayed visible while in settings.",
            "page": "settings",
        },
    )
    assert create_a.status_code == 201
    assert create_a.json()["id"] > 0

    create_b = client.post(
        "/feedback/entries",
        headers=headers_b,
        json={
            "category": "feature",
            "title": "Need daily summary export",
            "details": "Please add weekly and monthly CSV exports.",
            "page": "summary",
        },
    )
    assert create_b.status_code == 201
    assert create_b.json()["id"] > 0

    export = client.get("/feedback/entries/export", headers=headers_a)
    assert export.status_code == 200
    assert export.headers["content-type"].startswith("text/csv")
    csv_text = export.text
    assert "category,title,details,page,user_id,user_email" in csv_text
    assert "Chat overlay issue" in csv_text
    assert "Need daily summary export" in csv_text

    clear = client.delete("/feedback/entries", headers=headers_a)
    assert clear.status_code == 200
    assert clear.json()["deleted_rows"] >= 2

    export_after = client.get("/feedback/entries/export", headers=headers_b)
    assert export_after.status_code == 200
    lines = [line for line in export_after.text.splitlines() if line.strip()]
    assert len(lines) == 1  # header only


def test_feedback_requires_auth(client) -> None:
    response = client.post(
        "/feedback/entries",
        json={
            "category": "idea",
            "title": "Needs auth",
            "details": "This should be rejected without token.",
            "page": "chat",
        },
    )
    assert response.status_code == 401
