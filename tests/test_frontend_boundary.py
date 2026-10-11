"""C07 — static guard for the frontend trust boundary.

Runs in the existing pytest runner: no JS test framework is installed.
"""
import re
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "frontend" / "src"
_CODE_FILES = sorted(p for p in _SRC.rglob("*.ts*") if p.name != "vite-env.d.ts")


def _code(path: Path) -> str:
    """File text with comments stripped, so prose cannot trip the scanners."""
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return "\n".join(line for line in text.splitlines() if not line.strip().startswith("//"))


def test_frontend_sources_exist():
    names = {p.name for p in _CODE_FILES}
    assert {"api.ts", "auth.tsx", "admin.tsx", "learner.tsx", "main.tsx"} <= names


def test_access_token_is_never_put_in_web_storage():
    for path in _CODE_FILES:
        code = _code(path)
        for forbidden in ("localStorage", "sessionStorage", "document.cookie", "indexedDB"):
            assert forbidden not in code, f"{path.name} must not persist session state via {forbidden}"


def test_learner_code_never_references_answer_fields():
    for path in _CODE_FILES:
        code = _code(path)
        for forbidden in ("answer_sql", "seed_sql", "expected_output", "schema_sql", "blueprint"):
            assert forbidden not in code, f"{path.name} must not reference {forbidden}"


def test_no_fake_refresh_flow():
    joined = "\n".join(_code(p) for p in _CODE_FILES)
    assert "/auth/refresh" not in joined, "backend has no refresh endpoint; do not fake one"
    assert "refresh_token" not in joined


def test_single_api_module_owns_the_token_and_authorization_header():
    api = _code(_SRC / "api.ts")
    assert "Authorization" in api
    for path in _CODE_FILES:
        if path.name == "api.ts":
            continue
        assert "Authorization" not in _code(path), f"{path.name} must send auth through api.ts"
        assert "fetch(" not in _code(path), f"{path.name} must call the API through api.ts"


def test_api_clears_token_on_401():
    api = _code(_SRC / "api.ts")
    assert "res.status === 401" in api
    assert "clearToken()" in api


def test_admin_screens_are_wired():
    main = _code(_SRC / "main.tsx")
    for route in ("/admin/stats", "/admin/users", "/admin/documents", "/admin/generation-jobs", "/admin/settings/llm", "/admin/audit-logs"):
        assert route in main, f"admin shell must load {route}"
    admin = _code(_SRC / "admin.tsx")
    assert "/admin/llm/test" in admin
    assert "review_notes" in admin
    assert "/admin/generation-jobs/${id}" in admin, "job detail must be reachable"


def test_learner_view_has_no_admin_routes():
    learner = _code(_SRC / "learner.tsx")
    assert "/admin" not in learner
    assert "fetch(" not in learner


def test_admin_actions_report_busy_and_error_state():
    admin = _code(_SRC / "admin.tsx")
    assert "busy" in admin and "setError" in admin
    assert "disabled={busy" in admin
