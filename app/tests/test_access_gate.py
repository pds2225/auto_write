from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from auto_write.operator_main import app


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_local_console_stays_open_without_password(monkeypatch):
    monkeypatch.delenv("AUTO_WRITE_ACCESS_PASSWORD", raising=False)
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.setenv("AUTO_WRITE_HOST", "127.0.0.1")
    client = TestClient(app)
    response = client.get("/console")
    assert response.status_code == 200
    health = client.get("/health")
    assert health.status_code == 200


def test_render_without_password_locks_console_and_keeps_health(monkeypatch):
    monkeypatch.delenv("AUTO_WRITE_ACCESS_PASSWORD", raising=False)
    monkeypatch.setenv("RENDER", "true")
    client = TestClient(app)
    locked = client.get("/console")
    assert locked.status_code == 503
    assert "AUTO_WRITE_ACCESS_PASSWORD" in locked.text
    assert client.get("/health").status_code == 200


def test_password_login_opens_console_and_rejects_external_next(monkeypatch):
    monkeypatch.setenv("AUTO_WRITE_ACCESS_PASSWORD", "secret-pass")
    monkeypatch.delenv("RENDER", raising=False)
    client = TestClient(app)
    denied = client.get("/console", follow_redirects=False)
    assert denied.status_code == 303
    assert denied.headers["location"].startswith("/login?next=")

    bad = client.post("/login", data={"password": "nope", "next": "/console"}, follow_redirects=False)
    assert bad.status_code == 401

    external = client.post(
        "/login",
        data={"password": "secret-pass", "next": "https://evil.example/phish"},
        follow_redirects=False,
    )
    assert external.status_code == 303
    assert external.headers["location"] == "/console"

    page = client.get("/console")
    assert page.status_code == 200
    assert "문서 작업" in page.text


def test_render_blocks_git_write_after_login(monkeypatch):
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("AUTO_WRITE_ACCESS_PASSWORD", "secret-pass")
    client = TestClient(app)
    logged_in = client.post("/login", data={"password": "secret-pass", "next": "/console"}, follow_redirects=False)
    assert logged_in.status_code == 303
    blocked = client.post("/console/git/sync", follow_redirects=False)
    assert blocked.status_code == 303
    assert "Render" in blocked.headers["location"]


def test_render_blueprint_keeps_disk_and_password():
    text = (REPO_ROOT / "render.yaml").read_text(encoding="utf-8")
    assert "mountPath: /var/data" in text
    assert "AUTO_WRITE_WORKSPACE_ROOT" in text
    assert "AUTO_WRITE_RESULTS_ROOT" in text
    assert "AUTO_WRITE_ACCESS_PASSWORD" in text
    assert "sync: false" in text
    assert "healthCheckPath: /health" in text