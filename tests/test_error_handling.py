from __future__ import annotations

from fastapi.testclient import TestClient

from app.api import routes
from app.main import app


def test_openai_invalid_workspace_returns_structured_error(tmp_path):
    routes.workspace_session.reset()
    missing = tmp_path / "missing-project"

    client = TestClient(app)
    body = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": f"@path {missing}"}],
    }
    response = client.post("/v1/chat/completions", json=body)
    assert response.status_code == 200
    payload = response.json()
    assert payload["error"] == "workspace_init_failed"
    assert payload["details"]["exception_type"] == "FileNotFoundError"
    assert "traceback" in payload["details"]


def test_openai_qdrant_failure_returns_structured_error(monkeypatch, tmp_path):
    routes.workspace_session.reset()

    def fail_ensure_collection(name: str, vector_size: int):
        raise ConnectionRefusedError("Failed to connect to Qdrant")

    monkeypatch.setattr(routes.vector_store, "ensure_collection", fail_ensure_collection)

    client = TestClient(app)
    body = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": f"@path {tmp_path}"}],
    }
    response = client.post("/v1/chat/completions", json=body)
    assert response.status_code == 200
    payload = response.json()
    assert payload["error"] == "workspace_init_failed"
    assert payload["details"]["exception_type"] == "ConnectionRefusedError"
    assert "traceback" in payload["details"]


def test_openai_ollama_failure_returns_structured_error(monkeypatch, tmp_path):
    routes.workspace_session.reset()

    def fail_run(workspace, messages, tools, local_model=None):
        raise RuntimeError("Failed to connect to Ollama")

    monkeypatch.setattr(routes.agent_runner, "run", fail_run)

    client = TestClient(app)
    body = {
        "model": "gpt-4o-mini",
        "workspace": str(tmp_path),
        "messages": [{"role": "user", "content": "hello"}],
    }
    response = client.post("/v1/chat/completions", json=body)
    assert response.status_code == 200
    payload = response.json()
    assert payload["error"] == "ollama_request_failed"
    assert payload["details"]["exception_type"] == "RuntimeError"
    assert "traceback" in payload["details"]


def test_workspace_tool_file_access_error_is_structured(tmp_path):
    routes.workspace_session.reset()

    client = TestClient(app)
    body = {
        "workspace": str(tmp_path),
        "tool": "read_file",
        "args": {"path": "missing.txt"},
    }
    response = client.post("/workspace/tool", json=body)
    assert response.status_code == 500
    payload = response.json()
    assert payload["error"] == "tool_execution_failed"
    assert payload["details"]["exception_type"] == "FileNotFoundError"
    assert "traceback" in payload["details"]

