"""C01 — production guard and repository invariants for MongoStore."""
import os

import pytest

from mongo_store import MongoStore, is_production


def _clear_env(monkeypatch):
    for key in ("MONGO_URI", "MONGO_DB_NAME", "ENV", "VERCEL"):
        monkeypatch.delenv(key, raising=False)


def test_local_dev_without_uri_uses_memory(monkeypatch):
    _clear_env(monkeypatch)
    store = MongoStore()
    assert store.mode == "memory"
    assert store.connected is False
    assert store.questions(limit=5)


def test_production_without_uri_fails_closed(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("ENV", "production")
    with pytest.raises(RuntimeError, match="MONGO_URI is required"):
        MongoStore()


def test_vercel_without_uri_fails_closed(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("VERCEL", "1")
    with pytest.raises(RuntimeError, match="MONGO_URI is required"):
        MongoStore()


def test_is_production_detection(monkeypatch):
    _clear_env(monkeypatch)
    assert is_production() is False
    monkeypatch.setenv("VERCEL", "0")
    assert is_production() is False
    monkeypatch.setenv("VERCEL", "1")
    assert is_production() is True
    monkeypatch.delenv("VERCEL")
    monkeypatch.setenv("ENV", "production")
    assert is_production() is True


def test_configured_unreachable_uri_never_silently_falls_back(monkeypatch):
    _clear_env(monkeypatch)
    # Reserved-for-documentation address; connection must fail fast, not fall back.
    monkeypatch.setenv("MONGO_URI", "mongodb://192.0.2.1:27017/?connectTimeoutMS=200")
    store = MongoStore()
    assert store.connected is False
    assert store.mode == "unavailable", "unreachable Mongo must not report memory mode"
    with pytest.raises(RuntimeError):
        store.questions(limit=1)


def test_production_unreachable_uri_raises_at_construction(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("MONGO_URI", "mongodb://192.0.2.1:27017/?connectTimeoutMS=200")
    with pytest.raises(RuntimeError, match="connection required"):
        MongoStore()


def test_error_text_never_contains_uri(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("MONGO_URI", "mongodb://secretuser:secretpass@192.0.2.1:27017/db")
    store = MongoStore()
    assert store.error
    assert "secretpass" not in store.error
    assert "secretuser" not in store.error


def test_duplicate_document_checksum_is_rejected(monkeypatch):
    _clear_env(monkeypatch)
    store = MongoStore()
    first = store.save_document({"filename": "a.csv", "checksum": "abc123", "size": 3})
    assert store.document_by_checksum("abc123")["id"] == first["id"]
    with pytest.raises(ValueError, match="checksum already exists"):
        store.save_document({"filename": "copy.csv", "checksum": "abc123", "size": 3})
    assert len(store.documents()) == 1


def test_settings_and_audit_round_trip(monkeypatch):
    _clear_env(monkeypatch)
    store = MongoStore()
    store.save_setting("llm", {"provider": "anthropic", "model": "claude-sonnet-4-6"})
    assert store.setting("llm")["value"]["provider"] == "anthropic"
    store.save_setting("llm", {"provider": "gemini"})
    assert store.setting("llm")["value"]["provider"] == "gemini", "setting must upsert, not duplicate"

    store.save_audit({"actor_id": "u1", "action": "user.update", "resource_type": "user", "resource_id": "u2", "summary": "role=admin"})
    logs = store.audit_logs()
    assert len(logs) == 1
    assert logs[0]["actor_id"] == "u1"
    assert logs[0]["created_at"]


def test_memory_collections_cover_required_namespaces(monkeypatch):
    _clear_env(monkeypatch)
    store = MongoStore()
    for name in ("users", "questions", "documents", "settings", "audit_logs", "challenges", "jobs", "submissions"):
        assert name in store.memory
