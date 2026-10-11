from pathlib import Path

from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


def test_frontend_and_static_assets_are_served():
    page = client.get("/")
    styles = client.get("/static/styles.css")

    assert page.status_code == 200
    assert "SQLArena" in page.text
    assert styles.status_code == 200
    legacy_page = Path("pipeline.html").read_text()
    assert all(token not in styles.text + legacy_page for token in ("gradient", "radial-gradient", "conic-gradient"))
    assert all(color in styles.text for color in ("#5C7F71", "#802520", "#BA8530", "#181818", "#F5EDDC", "#B2653B"))


def test_api_capability_smoke_path():
    assert client.get("/health").status_code == 200
    assert client.get("/questions").status_code == 200
    assert client.get("/stats").status_code == 200
    result = client.post(
        "/verify-sql",
        json={
            "ddl_sql": "CREATE TABLE users (id INTEGER, name TEXT);",
            "seed_sql": "INSERT INTO users VALUES (1, 'Ada');",
            "answer_sql": "SELECT * FROM users;",
        },
    )
    assert result.status_code == 200
    assert result.json()["valid"] is True
