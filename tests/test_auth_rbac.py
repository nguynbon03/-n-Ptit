"""C02 — RBAC, lock, and learner projection contract."""
import os

os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

from fastapi.testclient import TestClient

from auth import create_access_token, hash_password
from main import app
from mongo_store import get_store

client = TestClient(app)

_SECRET_FIELDS = ("answer_sql", "seed_sql", "schema_sql", "expected_output", "blueprint", "review_notes", "clarity_score", "metadata", "generation_attempt")


def _user(user_id: str, email: str, role: str, status: str = "active") -> dict:
    return get_store().save_user({
        "id": user_id,
        "email": email,
        "password_hash": hash_password("rbac-password-123"),
        "role": role,
        "status": status,
    })


def _headers(user: dict) -> dict:
    return {"Authorization": f"Bearer {create_access_token(user)}"}


def test_anonymous_requests_are_rejected():
    for path in ("/me", "/questions", "/questions/seed-select-001", "/stats", "/admin/stats", "/admin/users", "/admin/documents", "/admin/generation-jobs", "/weekly/current"):
        assert client.get(path).status_code == 401, path
    assert client.post("/admin/generation-jobs", json={"specs": ["easy"]}).status_code == 401
    assert client.patch("/admin/users/x", json={"role": "admin"}).status_code == 401


def test_learner_is_forbidden_on_admin_routes():
    learner = _user("rbac-learner", "rbac-learner@example.com", "learner")
    headers = _headers(learner)
    for path in ("/stats", "/admin/stats", "/admin/users", "/admin/documents", "/admin/generation-jobs"):
        assert client.get(path, headers=headers).status_code == 403, path
    assert client.post("/admin/generation-jobs", headers=headers, json={"specs": ["easy"]}).status_code == 403
    assert client.patch("/admin/users/rbac-admin", headers=headers, json={"role": "learner"}).status_code == 403
    assert client.put("/questions/seed-select-001/status", headers=headers, json={"status": "approved"}).status_code == 403
    assert client.post("/verify-sql", headers=headers, json={"ddl_sql": "", "seed_sql": "", "answer_sql": "SELECT 1;"}).status_code == 403


def test_locked_user_is_denied_with_previously_issued_token():
    user = _user("rbac-locked", "rbac-locked@example.com", "learner")
    headers = _headers(user)
    assert client.get("/me", headers=headers).status_code == 200

    get_store().save_user({**get_store().user_by_id("rbac-locked"), "status": "locked"})
    assert client.get("/me", headers=headers).status_code == 401
    assert client.get("/questions", headers=headers).status_code == 401
    login = client.post("/auth/login", json={"email": "rbac-locked@example.com", "password": "rbac-password-123"})
    assert login.status_code == 401


def test_locked_admin_token_loses_admin_access():
    admin = _user("rbac-locked-admin", "rbac-locked-admin@example.com", "admin")
    headers = _headers(admin)
    assert client.get("/admin/stats", headers=headers).status_code == 200
    get_store().save_user({**get_store().user_by_id("rbac-locked-admin"), "status": "locked"})
    assert client.get("/admin/stats", headers=headers).status_code == 401


def test_admin_cannot_lock_or_demote_self():
    admin = _user("rbac-admin", "rbac-admin@example.com", "admin")
    headers = _headers(admin)

    locked = client.patch("/admin/users/rbac-admin", headers=headers, json={"status": "locked"})
    demoted = client.patch("/admin/users/rbac-admin", headers=headers, json={"role": "learner"})
    both = client.patch("/admin/users/rbac-admin", headers=headers, json={"role": "learner", "status": "locked"})

    assert locked.status_code == 400
    assert demoted.status_code == 400
    assert both.status_code == 400
    still = get_store().user_by_id("rbac-admin")
    assert still["role"] == "admin" and still["status"] == "active"


def test_admin_can_change_other_users_and_response_hides_password_hash():
    admin = _user("rbac-admin2", "rbac-admin2@example.com", "admin")
    _user("rbac-target", "rbac-target@example.com", "learner")
    response = client.patch("/admin/users/rbac-target", headers=_headers(admin), json={"role": "admin", "status": "locked"})

    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "admin" and body["status"] == "locked"
    assert "password_hash" not in body

    listing = client.get("/admin/users", headers=_headers(admin))
    assert listing.status_code == 200
    assert all("password_hash" not in item for item in listing.json()["users"])
    assert client.patch("/admin/users/does-not-exist", headers=_headers(admin), json={"role": "admin"}).status_code == 404


def test_learner_question_list_and_detail_hide_answer_data():
    learner = _user("rbac-projection", "rbac-projection@example.com", "learner")
    headers = _headers(learner)
    store = get_store()
    store.save_question({
        "id": "rbac-pending-001",
        "question_text": "Pending question must stay hidden from learners.",
        "difficulty": "easy",
        "topic": "SELECT",
        "status": "pending_review",
        "answer_sql": "SELECT 1;",
    })

    listed = client.get("/questions?limit=100", headers=headers)
    assert listed.status_code == 200
    items = listed.json()["questions"]
    assert items, "learner must still see approved questions"
    assert all(item["status"] == "approved" for item in items)
    assert all(field not in item for item in items for field in _SECRET_FIELDS)
    assert all(item["id"] != "rbac-pending-001" for item in items)

    # Learner cannot widen visibility through the status filter.
    filtered = client.get("/questions?status=pending_review&limit=100", headers=headers)
    assert filtered.status_code == 200
    assert all(item["status"] == "approved" for item in filtered.json()["questions"])

    detail = client.get("/questions/seed-select-001", headers=headers)
    assert detail.status_code == 200
    assert all(field not in detail.json() for field in _SECRET_FIELDS)
    assert client.get("/questions/rbac-pending-001", headers=headers).status_code == 404

    weekly = client.get("/weekly/current", headers=headers)
    assert weekly.status_code == 200
    assert all(field not in q for q in weekly.json()["questions"] for field in _SECRET_FIELDS)


def test_admin_still_sees_full_question_record():
    admin = _user("rbac-admin3", "rbac-admin3@example.com", "admin")
    detail = client.get("/questions/seed-select-001", headers=_headers(admin))
    assert detail.status_code == 200
    assert detail.json()["answer_sql"]


def test_invalid_and_malformed_tokens_are_rejected():
    assert client.get("/me", headers={"Authorization": "Bearer not-a-token"}).status_code == 401
    assert client.get("/me", headers={"Authorization": "token-without-scheme"}).status_code == 401
    ghost = create_access_token({"id": "missing-user", "email": "ghost@example.com", "role": "admin"})
    assert client.get("/admin/stats", headers={"Authorization": f"Bearer {ghost}"}).status_code == 401
