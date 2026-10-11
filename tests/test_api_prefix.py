"""C08 — single /api prefix layer and deployment boundary."""
import os
import re
from pathlib import Path

os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

from fastapi.testclient import TestClient

import api.index as vercel_entry
from main import app

client = TestClient(app)
_ROOT = Path(__file__).resolve().parents[1]


def test_health_answers_on_both_bare_and_api_paths():
    bare = client.get("/health")
    prefixed = client.get("/api/health")

    assert bare.status_code == 200
    assert prefixed.status_code == 200
    assert bare.json() == prefixed.json()
    assert prefixed.json()["persistence"] in ("mongo", "memory")


def test_prefix_is_stripped_exactly_once():
    assert client.get("/api/api/health").status_code == 404
    assert client.get("/api").status_code == 200, "/api must map to the app root"


def test_similar_paths_are_not_rewritten():
    # `/apifoo` shares the first four characters but is not an /api route.
    assert client.get("/apifoo").status_code == 404


def test_vercel_entry_adds_no_second_strip_layer():
    source = (_ROOT / "api" / "index.py").read_text()
    assert "StripApiPrefix" not in source
    assert vercel_entry.app is app, "Vercel must serve the same ASGI app, unwrapped"


def test_vercel_routes_forward_api_with_prefix():
    config = (_ROOT / "vercel.json").read_text()
    assert '"/api/(.*)"' in config
    assert '"dest": "/api/index.py"' in config


def test_env_example_documents_production_persistence_contract():
    env = (_ROOT / ".env.example").read_text()
    for key in ("MONGO_URI", "MONGO_DB_NAME", "JWT_SECRET_KEY", "MAX_UPLOAD_BYTES", "ALLOW_BACKGROUND_JOBS"):
        assert key in env, f"{key} must be documented"
    assert "ENV=production" in env


def test_no_credentials_are_committed_in_tracked_config():
    # Matches a URI carrying an inline user:password, ignoring placeholders.
    credential_uri = re.compile(r"mongodb(\+srv)?://(?!<)[^\s:/]+:(?!<)[^\s@/]+@")
    for name in (".env.example", "vercel.json", "docker-compose.yml", "README.md", "Dockerfile"):
        text = (_ROOT / name).read_text()
        assert not credential_uri.search(text), f"{name} must not contain Mongo credentials"
        assert "sk-ant-" not in text, f"{name} must not contain a provider token"


def test_env_template_keeps_every_secret_slot_empty():
    for line in (_ROOT / ".env.example").read_text().splitlines():
        if "=" not in line or line.strip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        if key.strip() in ("ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "NVIDIA_API_KEY", "JWT_SECRET_KEY", "MONGO_URI"):
            assert value.strip() == "", f".env.example:{key} must stay empty"


def test_dotenv_is_git_ignored():
    ignore = (_ROOT / ".gitignore").read_text()
    assert ".env" in ignore
