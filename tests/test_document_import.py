"""C03 — safe document import boundaries."""
import io
import json
import os

os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

import pytest
from fastapi.testclient import TestClient

from auth import create_access_token, hash_password
from main import app
from mongo_store import get_store

client = TestClient(app)


def _headers(role: str = "admin") -> dict:
    user = get_store().save_user({
        "id": f"doc-{role}",
        "email": f"doc-{role}@example.com",
        "password_hash": hash_password("doc-password-123"),
        "role": role,
        "status": "active",
    })
    return {"Authorization": f"Bearer {create_access_token(user)}"}


def _upload(name: str, data: bytes, content_type: str = "application/octet-stream", headers: dict | None = None):
    return client.post("/admin/documents", headers=headers or _headers(), files={"file": (name, io.BytesIO(data), content_type)})


def _xlsx_bytes() -> bytes:
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Sheet1"
    sheet.append(["question_text", "difficulty"])
    sheet.append(["List all users", "easy"])
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def test_learner_cannot_upload_documents():
    response = _upload("learner.txt", b"nope", headers=_headers("learner"))
    assert response.status_code == 403


def test_anonymous_cannot_upload_documents():
    response = client.post("/admin/documents", files={"file": ("a.txt", io.BytesIO(b"x"), "text/plain")})
    assert response.status_code == 401


@pytest.mark.parametrize(
    "name,data",
    [
        ("notes.txt", "Câu hỏi SQL\nDòng hai".encode()),
        ("notes.md", b"# Heading\n- item"),
        ("rows.csv", b"question_text,difficulty\nList users,easy\n"),
        ("bank.json", json.dumps({"questions": [{"question_text": "List users"}]}).encode()),
    ],
)
def test_supported_text_formats_are_imported(name, data):
    response = _upload(name, data)
    assert response.status_code == 201 or response.status_code == 200, response.text
    body = response.json()
    assert body["filename"] == name
    assert body["size"] == len(data)
    assert len(body["checksum"]) == 64
    assert body["uploaded_by"] == "doc-admin"
    assert body["status"] == "pending_review"


def test_xlsx_extraction_uses_real_newlines():
    response = _upload("sheet.xlsx", _xlsx_bytes(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    assert response.status_code in (200, 201), response.text
    text = response.json()["text"]
    assert "\\n" not in text, "extraction must not emit literal backslash-n"
    assert "\n" in text
    assert text.splitlines()[0] == "# Sheet1"


def test_unsupported_suffix_is_rejected_before_parsing():
    response = _upload("payload.exe", b"MZ\x00\x00")
    assert response.status_code == 400
    assert "Supported files" in response.json()["detail"]


def test_missing_suffix_is_rejected():
    assert _upload("README", b"text").status_code == 400


def test_oversized_upload_is_rejected(monkeypatch):
    monkeypatch.setenv("MAX_UPLOAD_BYTES", "64")
    response = _upload("big.txt", b"x" * 200)
    assert response.status_code == 413
    assert "limit 64" in response.json()["detail"]


def test_malformed_content_returns_safe_400():
    response = _upload("broken.xlsx", b"not a real spreadsheet")
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "Could not parse .xlsx" in detail
    assert "Traceback" not in detail


def test_non_utf8_text_returns_safe_400():
    response = _upload("latin.txt", b"\xff\xfe\x00binary")
    assert response.status_code == 400
    assert "UTF-8" in response.json()["detail"]


def test_duplicate_checksum_is_rejected_and_not_stored_twice():
    payload = b"duplicate-import-body\n"
    first = _upload("dup-a.txt", payload)
    assert first.status_code in (200, 201)
    second = _upload("dup-b-renamed.txt", payload)

    assert second.status_code == 409
    assert "already imported" in second.json()["detail"]
    stored = [d for d in get_store().documents(limit=1000) if d["checksum"] == first.json()["checksum"]]
    assert len(stored) == 1
    assert stored[0]["filename"] == "dup-a.txt"


def test_stored_text_is_bounded_and_marked_truncated():
    body = ("abcdefghij" * 3000).encode()
    response = _upload("long.txt", body)
    assert response.status_code in (200, 201)
    document = response.json()
    assert len(document["text"]) == 20000
    assert len(document["preview"]) == 500
    assert document["truncated"] is True
    assert document["size"] == len(body)


def test_short_document_is_not_marked_truncated():
    document = _upload("short.txt", b"small body").json()
    assert document["truncated"] is False
