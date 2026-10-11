"""C05 — admin LLM settings, redaction, and mockable provider test."""
import logging
import os

os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

import httpx
import pytest
from fastapi.testclient import TestClient

import llm_gateway
import main
from auth import create_access_token, hash_password
from main import app
from mongo_store import get_store

client = TestClient(app)

_TOKEN = "sk-test-not-a-real-credential-0000"


def _headers(role: str = "admin") -> dict:
    user = get_store().save_user({
        "id": f"llm-{role}",
        "email": f"llm-{role}@example.com",
        "password_hash": hash_password("llm-password-123"),
        "role": role,
        "status": "active",
    })
    return {"Authorization": f"Bearer {create_access_token(user)}"}


@pytest.fixture(autouse=True)
def _clean_settings(monkeypatch):
    for key in ("AI_PROVIDER", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_API_KEY", "ANTHROPIC_MODEL", "ANTHROPIC_BASE_URL", "ANTHROPIC_DEFAULT_OPUS_MODEL"):
        monkeypatch.delenv(key, raising=False)
    get_store().save_setting("llm", {})
    yield
    get_store().save_setting("llm", {})


def _mock_post(monkeypatch, handler):
    monkeypatch.setattr(llm_gateway.httpx, "post", handler)


def test_learner_cannot_read_or_change_llm_settings():
    headers = _headers("learner")
    assert client.get("/admin/settings/llm", headers=headers).status_code == 403
    assert client.put("/admin/settings/llm", headers=headers, json={"provider": "anthropic"}).status_code == 403
    assert client.post("/admin/llm/test", headers=headers).status_code == 403


def test_anonymous_cannot_touch_llm_settings():
    assert client.get("/admin/settings/llm").status_code == 401
    assert client.post("/admin/llm/test").status_code == 401


def test_get_settings_reports_no_token_when_unconfigured():
    body = client.get("/admin/settings/llm", headers=_headers()).json()
    assert body["provider"] == "anthropic"
    assert body["token_configured"] is False
    assert body["token_source"] == "none"
    assert body["token_hint"] == ""
    assert "api_token" not in body
    assert body["supported_providers"] == ["anthropic", "gemini", "nvidia"]


def test_put_settings_stores_token_but_never_returns_it():
    response = client.put(
        "/admin/settings/llm",
        headers=_headers(),
        json={"provider": "anthropic", "model": "claude-sonnet-4-6", "base_url": "https://api.anthropic.com/v1/messages", "api_token": _TOKEN},
    )

    assert response.status_code == 200
    body = response.json()
    assert _TOKEN not in response.text
    assert "api_token" not in body
    assert body["token_configured"] is True
    assert body["token_source"] == "settings"
    assert body["token_hint"] == "********0000"
    assert body["model"] == "claude-sonnet-4-6"

    reread = client.get("/admin/settings/llm", headers=_headers())
    assert _TOKEN not in reread.text
    assert reread.json()["token_configured"] is True


def test_invalid_provider_is_rejected():
    assert client.put("/admin/settings/llm", headers=_headers(), json={"provider": "openai"}).status_code == 422


def test_put_without_token_keeps_existing_secret_and_empty_clears_it():
    headers = _headers()
    client.put("/admin/settings/llm", headers=headers, json={"provider": "anthropic", "api_token": _TOKEN})

    kept = client.put("/admin/settings/llm", headers=headers, json={"provider": "anthropic", "model": "claude-opus-4-8"}).json()
    assert kept["token_configured"] is True
    assert kept["model"] == "claude-opus-4-8"

    cleared = client.put("/admin/settings/llm", headers=headers, json={"provider": "anthropic", "api_token": ""}).json()
    assert cleared["token_configured"] is False


def test_settings_change_is_audited_without_the_token():
    headers = _headers()
    client.put("/admin/settings/llm", headers=headers, json={"provider": "anthropic", "model": "claude-sonnet-4-6", "api_token": _TOKEN})

    logs = client.get("/admin/audit-logs", headers=headers).json()["logs"]
    entry = next(log for log in logs if log["action"] == "settings.llm.update")
    assert entry["actor_id"] == "llm-admin"
    assert entry["resource_id"] == "llm"
    assert "token_set=True" in entry["summary"]
    assert _TOKEN not in entry["summary"]


def test_llm_test_without_credential_returns_safe_400():
    response = client.post("/admin/llm/test", headers=_headers())
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "not_configured"


def test_llm_test_success_uses_stored_settings(monkeypatch):
    headers = _headers()
    client.put("/admin/settings/llm", headers=headers, json={"provider": "anthropic", "model": "claude-sonnet-4-6", "api_token": _TOKEN})
    seen = {}

    def _handler(url, json=None, headers=None, timeout=None):
        seen["url"] = url
        seen["api_key"] = headers["x-api-key"]
        seen["model"] = json["model"]
        return httpx.Response(200, json={"content": [{"type": "text", "text": "OK"}]}, request=httpx.Request("POST", url))

    _mock_post(monkeypatch, _handler)
    response = client.post("/admin/llm/test", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body == {"ok": True, "provider": "anthropic", "model": "claude-sonnet-4-6", "sample": "OK"}
    assert _TOKEN not in response.text
    assert seen["api_key"] == _TOKEN, "stored token must reach the provider server-side only"
    assert seen["model"] == "claude-sonnet-4-6"


@pytest.mark.parametrize(
    "status,code",
    [(401, "invalid_auth"), (403, "invalid_auth"), (429, "rate_limited"), (500, "provider_unavailable"), (418, "provider_error")],
)
def test_provider_http_failures_map_to_safe_codes(monkeypatch, status, code):
    headers = _headers()
    client.put("/admin/settings/llm", headers=headers, json={"provider": "anthropic", "api_token": _TOKEN})

    def _handler(url, json=None, headers=None, timeout=None):
        request = httpx.Request("POST", url)
        return httpx.Response(status, json={"error": {"message": "provider said something with the token in it"}}, request=request)

    _mock_post(monkeypatch, _handler)
    response = client.post("/admin/llm/test", headers=headers)

    assert response.status_code == 502
    assert response.json()["detail"]["code"] == code
    assert _TOKEN not in response.text
    assert "provider said something" not in response.text, "raw provider body must not leak"


def test_provider_timeout_and_network_errors_map_to_safe_codes(monkeypatch):
    headers = _headers()
    client.put("/admin/settings/llm", headers=headers, json={"provider": "anthropic", "api_token": _TOKEN})

    def _timeout(url, json=None, headers=None, timeout=None):
        raise httpx.ReadTimeout("timed out", request=httpx.Request("POST", url))

    _mock_post(monkeypatch, _timeout)
    assert client.post("/admin/llm/test", headers=headers).json()["detail"]["code"] == "timeout"

    def _network(url, json=None, headers=None, timeout=None):
        raise httpx.ConnectError("no route", request=httpx.Request("POST", url))

    _mock_post(monkeypatch, _network)
    assert client.post("/admin/llm/test", headers=headers).json()["detail"]["code"] == "network_error"


def test_provider_test_never_logs_token_or_prompt(monkeypatch, caplog):
    headers = _headers()
    client.put("/admin/settings/llm", headers=headers, json={"provider": "anthropic", "api_token": _TOKEN})

    def _handler(url, json=None, headers=None, timeout=None):
        return httpx.Response(200, json={"content": [{"type": "text", "text": "OK"}]}, request=httpx.Request("POST", url))

    _mock_post(monkeypatch, _handler)
    with caplog.at_level(logging.DEBUG):
        client.post("/admin/llm/test", headers=headers)

    text = caplog.text
    assert _TOKEN not in text
    assert "Reply with OK" not in text


def test_env_token_is_reported_as_env_source(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", _TOKEN)
    body = client.get("/admin/settings/llm", headers=_headers()).json()
    assert body["token_configured"] is True
    assert body["token_source"] == "env"
    assert _TOKEN not in str(body)


def test_overrides_contain_token_only_in_process(monkeypatch):
    headers = _headers()
    client.put("/admin/settings/llm", headers=headers, json={"provider": "nvidia", "model": "x/y", "api_token": _TOKEN})
    overrides = main.llm_overrides()
    assert overrides["AI_PROVIDER"] == "nvidia"
    assert overrides["NVIDIA_API_KEY"] == _TOKEN
    assert overrides["NVIDIA_MODEL"] == "x/y"
    summary = client.get("/admin/settings/llm", headers=headers).json()
    assert _TOKEN not in str(summary)
