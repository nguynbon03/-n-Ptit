"""C06 — audit records for admin mutations, with no secret or answer leakage."""
import io
import os

os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

import pytest
from fastapi.testclient import TestClient

import main
from auth import create_access_token, hash_password
from main import app
from mongo_store import get_store

client = TestClient(app)


def _user(user_id: str, role: str) -> dict:
    return get_store().save_user({
        "id": user_id,
        "email": f"{user_id}@example.com",
        "password_hash": hash_password("audit-password-123"),
        "role": role,
        "status": "active",
    })


def _headers(user: dict) -> dict:
    return {"Authorization": f"Bearer {create_access_token(user)}"}


def _logs(headers: dict, action: str) -> list[dict]:
    return [log for log in client.get("/admin/audit-logs", headers=headers).json()["logs"] if log["action"] == action]


def test_learner_cannot_read_audit_logs():
    assert client.get("/admin/audit-logs", headers=_headers(_user("audit-learner", "learner"))).status_code == 403
    assert client.get("/admin/audit-logs").status_code == 401


def test_user_mutation_is_audited():
    admin = _user("audit-admin", "admin")
    _user("audit-target", "learner")
    headers = _headers(admin)

    client.patch("/admin/users/audit-target", headers=headers, json={"role": "admin", "status": "locked"})
    entry = next(log for log in _logs(headers, "user.update") if log["resource_id"] == "audit-target")

    assert entry["actor_id"] == "audit-admin"
    assert entry["resource_type"] == "user"
    assert entry["summary"] == "role=admin status=locked"
    assert entry["created_at"]
    assert "password_hash" not in entry["summary"]


def test_rejected_self_mutation_is_not_audited():
    admin = _user("audit-admin2", "admin")
    headers = _headers(admin)
    before = len(_logs(headers, "user.update"))
    assert client.patch("/admin/users/audit-admin2", headers=headers, json={"status": "locked"}).status_code == 400
    assert len(_logs(headers, "user.update")) == before


def test_document_upload_is_audited_with_truncated_checksum():
    headers = _headers(_user("audit-admin3", "admin"))
    response = client.post("/admin/documents", headers=headers, files={"file": ("audited.txt", io.BytesIO(b"audit document body"), "text/plain")})
    assert response.status_code in (200, 201)
    document = response.json()

    entry = next(log for log in _logs(headers, "document.upload") if log["resource_id"] == document["id"])
    assert entry["resource_type"] == "document"
    assert "audited.txt" in entry["summary"]
    assert "size=19" in entry["summary"]
    assert document["checksum"][:12] in entry["summary"]
    assert document["checksum"] not in entry["summary"], "only a checksum prefix belongs in the audit summary"
    assert "audit document body" not in entry["summary"]


def test_question_review_is_audited_without_answer_sql():
    headers = _headers(_user("audit-admin4", "admin"))
    get_store().save_question({
        "id": "audit-question-1",
        "question_text": "Audited question",
        "difficulty": "easy",
        "topic": "SELECT",
        "status": "pending_review",
        "answer_sql": "SELECT secret_column FROM secrets;",
    })

    assert client.put("/questions/audit-question-1/status", headers=headers, json={"status": "approved", "review_notes": "ok"}).status_code == 200
    entry = next(log for log in _logs(headers, "question.review") if log["resource_id"] == "audit-question-1")

    assert entry["summary"] == "status=approved"
    assert "secret_column" not in entry["summary"]


def test_generation_lifecycle_is_audited(monkeypatch):
    headers = _headers(_user("audit-admin5", "admin"))
    monkeypatch.setattr(main, "generate_pipeline", lambda **kw: {"generated": 1, "valid": 1, "failed": 0, "question_ids": ["audit-gen-1"], "stats": {}})

    class _Bank:
        def get(self, question_id):
            return {"id": question_id, "question_text": "Generated", "difficulty": "easy", "topic": "SELECT", "answer_sql": "SELECT 1;"}

    monkeypatch.setattr(main, "QuestionBank", lambda *a, **k: _Bank())
    job_id = client.post("/admin/generation-jobs", headers=headers, json={"specs": ["easy"], "document_id": "doc-xyz"}).json()["task_id"]

    assert any(log["resource_id"] == job_id for log in _logs(headers, "generation.start"))
    assert any(log["resource_id"] == job_id for log in _logs(headers, "generation.succeeded"))

    question = get_store().question("audit-gen-1")
    assert question["source"] == "pipeline"
    assert question["source_job_id"] == job_id
    assert question["source_document_id"] == "doc-xyz"
    assert question["legacy_sqlite_id"] == "audit-gen-1"
    assert question["status"] == "pending_review", "generated questions must await review"


def test_failed_generation_is_audited(monkeypatch):
    headers = _headers(_user("audit-admin6", "admin"))

    def _boom(**kwargs):
        raise RuntimeError("ANTHROPIC_AUTH_TOKEN is required when AI_PROVIDER=anthropic")

    monkeypatch.setattr(main, "generate_pipeline", _boom)
    job_id = client.post("/admin/generation-jobs", headers=headers, json={"specs": ["easy"]}).json()["task_id"]

    entry = next(log for log in _logs(headers, "generation.failed") if log["resource_id"] == job_id)
    assert entry["summary"] == "code=configuration_error"


def test_audit_log_listing_is_bounded_and_newest_first():
    headers = _headers(_user("audit-admin7", "admin"))
    _user("audit-target2", "learner")
    for role in ("admin", "learner", "admin"):
        client.patch("/admin/users/audit-target2", headers=headers, json={"role": role})

    response = client.get("/admin/audit-logs?limit=2", headers=headers)
    assert response.status_code == 200
    logs = response.json()["logs"]
    assert len(logs) <= 2
    assert [log["created_at"] for log in logs] == sorted((log["created_at"] for log in logs), reverse=True)
    assert client.get("/admin/audit-logs?limit=0", headers=headers).status_code == 422
    assert client.get("/admin/audit-logs?limit=9999", headers=headers).status_code == 422
