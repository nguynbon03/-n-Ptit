"""C04/C06 — generation job status, persistence, and production gate."""
import os

os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

import pytest
from fastapi.testclient import TestClient

import main
from auth import create_access_token, hash_password
from main import app
from mongo_store import get_store

client = TestClient(app)


def _admin_headers(user_id: str = "job-admin") -> dict:
    user = get_store().save_user({
        "id": user_id,
        "email": f"{user_id}@example.com",
        "password_hash": hash_password("job-password-123"),
        "role": "admin",
        "status": "active",
    })
    return {"Authorization": f"Bearer {create_access_token(user)}"}


def _learner_headers() -> dict:
    user = get_store().save_user({
        "id": "job-learner",
        "email": "job-learner@example.com",
        "password_hash": hash_password("job-password-123"),
        "role": "learner",
        "status": "active",
    })
    return {"Authorization": f"Bearer {create_access_token(user)}"}


@pytest.fixture
def fake_pipeline(monkeypatch):
    calls = {}

    def _fake(specs, questions_per_spec, excel_id=None, llm_overrides=None):
        calls["specs"] = specs
        calls["questions_per_spec"] = questions_per_spec
        calls["excel_id"] = excel_id
        calls["llm_overrides"] = llm_overrides
        return {"generated": 1, "valid": 1, "failed": 0, "question_ids": ["gen-q-1"], "stats": {}, "excel_id": excel_id}

    monkeypatch.setattr(main, "generate_pipeline", _fake)

    class _Bank:
        def get(self, question_id):
            return {
                "id": question_id,
                "question_text": "Generated question",
                "difficulty": "easy",
                "topic": "SELECT",
                "status": "pending_review",
                "answer_sql": "SELECT 1;",
                "metadata": {"excel_source": {"id": "E1"}},
                "blueprint": {"intent": "x"},
            }

    monkeypatch.setattr(main, "QuestionBank", lambda *a, **k: _Bank())
    return calls


def test_learner_cannot_create_or_read_jobs():
    headers = _learner_headers()
    assert client.post("/admin/generation-jobs", headers=headers, json={"specs": ["easy"]}).status_code == 403
    assert client.get("/admin/generation-jobs/anything", headers=headers).status_code == 403
    assert client.get("/tasks/anything", headers=headers).status_code == 403


def test_job_detail_404_for_unknown_id():
    assert client.get("/admin/generation-jobs/not-a-job", headers=_admin_headers()).status_code == 404


def test_create_job_succeeds_and_persists_questions_with_source(fake_pipeline):
    headers = _admin_headers()
    created = client.post("/admin/generation-jobs", headers=headers, json={"specs": ["easy"], "questions_per_spec": 1})

    assert created.status_code == 202
    body = created.json()
    assert body["status"] == "queued"
    assert body["durable"] is False
    job_id = body["task_id"]

    # TestClient runs BackgroundTasks synchronously before the response closes.
    detail = client.get(f"/admin/generation-jobs/{job_id}", headers=headers)
    assert detail.status_code == 200
    job = detail.json()
    assert job["status"] == "succeeded"
    assert job["status"] in main.JOB_STATUSES
    assert job["durable"] is False
    assert job["executor"] == "background_tasks"
    assert job["persisted_question_ids"] == ["gen-q-1"]
    assert job["requested_by"] == "job-admin"

    question = get_store().question("gen-q-1")
    assert question is not None, "generated question must land in Mongo"
    assert question["source_job_id"] == job_id
    assert question["status"] == "pending_review"
    assert question["metadata"]["excel_source"]["id"] == "E1", "Excel metadata must survive"

    listed = client.get("/admin/generation-jobs", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["durable_executor"] is False
    assert any(j["id"] == job_id for j in listed.json()["jobs"])


def test_legacy_tasks_route_matches_job_detail(fake_pipeline):
    headers = _admin_headers()
    job_id = client.post("/admin/generation-jobs", headers=headers, json={"specs": ["easy"]}).json()["task_id"]
    assert client.get(f"/tasks/{job_id}", headers=headers).json()["status"] == client.get(f"/admin/generation-jobs/{job_id}", headers=headers).json()["status"]


def test_job_survives_loss_of_process_memory(fake_pipeline):
    headers = _admin_headers()
    job_id = client.post("/admin/generation-jobs", headers=headers, json={"specs": ["easy"]}).json()["task_id"]

    main._tasks.clear()  # simulate API process restart
    detail = client.get(f"/admin/generation-jobs/{job_id}", headers=headers)

    assert detail.status_code == 200
    assert detail.json()["status"] == "succeeded", "Mongo job record must answer after restart"


def test_provider_failure_marks_job_failed_with_error_code(monkeypatch):
    def _boom(**kwargs):
        raise ValueError("LLM generation failed: ERROR: Anthropic LLM failed after retries")

    monkeypatch.setattr(main, "generate_pipeline", lambda **kw: _boom(**kw))
    headers = _admin_headers()
    job_id = client.post("/admin/generation-jobs", headers=headers, json={"specs": ["easy"]}).json()["task_id"]

    job = client.get(f"/admin/generation-jobs/{job_id}", headers=headers).json()
    assert job["status"] == "failed"
    assert job["error_code"] == "provider_error"
    assert "LLM generation failed" in job["error"]


def test_production_blocks_generation_without_durable_worker(monkeypatch, fake_pipeline):
    headers = _admin_headers()
    monkeypatch.setenv("ENV", "production")
    monkeypatch.delenv("ALLOW_BACKGROUND_JOBS", raising=False)

    blocked = client.post("/admin/generation-jobs", headers=headers, json={"specs": ["easy"]})
    assert blocked.status_code == 503
    assert "not a durable worker" in blocked.json()["detail"]

    monkeypatch.setenv("ALLOW_BACKGROUND_JOBS", "1")
    allowed = client.post("/admin/generation-jobs", headers=headers, json={"specs": ["easy"]})
    assert allowed.status_code == 202
    assert allowed.json()["durable"] is False


def test_legacy_generate_route_shares_the_gate(monkeypatch, fake_pipeline):
    headers = _admin_headers()
    monkeypatch.setenv("ENV", "production")
    monkeypatch.delenv("ALLOW_BACKGROUND_JOBS", raising=False)
    assert client.post("/generate", headers=headers, json={"specs": ["easy"]}).status_code == 503
