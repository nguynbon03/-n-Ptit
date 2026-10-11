import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

from auth import hash_password
from main import app
from mongo_store import get_store


client = TestClient(app)


def _admin_headers():
    store = get_store()
    store.save_user({
        "id": "test-admin",
        "email": "admin@example.com",
        "password_hash": hash_password("admin-password-123"),
        "role": "admin",
        "status": "active",
    })
    response = client.post("/auth/login", json={"email": "admin@example.com", "password": "admin-password-123"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_frontend_and_static_assets_are_served():
    page = client.get("/")
    styles = client.get("/static/styles.css")

    assert page.status_code == 200
    assert "SQLArena" in page.text
    assert styles.status_code == 200
    legacy_page = Path("pipeline.html").read_text()
    assert all(token not in styles.text + legacy_page for token in ("linear-gradient", "radial-gradient", "conic-gradient"))
    assert all(color in styles.text for color in ("#5C7F71", "#802520", "#BA8530", "#181818", "#F5EDDC", "#B2653B"))


def test_api_auth_and_admin_capability_path():
    assert client.get("/health").status_code == 200
    assert client.get("/questions").status_code == 401
    assert client.get("/stats").status_code == 401

    registered = client.post("/auth/register", json={"email": "learner@example.com", "password": "learner-password-123"})
    assert registered.status_code == 201
    learner_headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}
    assert client.get("/me", headers=learner_headers).json()["role"] == "learner"
    assert client.get("/questions", headers=learner_headers).status_code == 200
    assert client.get("/stats", headers=learner_headers).status_code == 403

    admin_headers = _admin_headers()
    assert client.get("/questions", headers=admin_headers).status_code == 200
    assert client.get("/stats", headers=admin_headers).status_code == 200
    result = client.post(
        "/verify-sql",
        headers=admin_headers,
        json={
            "ddl_sql": "CREATE TABLE users (id INTEGER, name TEXT);",
            "seed_sql": "INSERT INTO users VALUES (1, 'Ada');",
            "answer_sql": "SELECT * FROM users;",
        },
    )
    assert result.status_code == 200
    assert result.json()["valid"] is True
