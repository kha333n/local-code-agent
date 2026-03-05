from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.api import routes
from app.main import app


def test_chat_completions_non_stream_forced_exception_returns_openai_shape(monkeypatch):
    routes.workspace_session.reset()

    def fail_run(workspace, messages, tools, local_model=None):
        raise RuntimeError("forced failure for non-stream")

    monkeypatch.setattr(routes.agent_runner, "run", fail_run)

    client = TestClient(app)
    body = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": "hello"}],
    }
    response = client.post("/v1/chat/completions", json=body)
    assert response.status_code == 200

    payload = response.json()
    assert payload["id"] == "chatcmpl-local-error"
    assert payload["object"] == "chat.completion"
    assert isinstance(payload["created"], int)
    assert payload["model"] == "gpt-4o-mini"
    assert payload["choices"][0]["index"] == 0
    assert payload["choices"][0]["message"]["role"] == "assistant"
    content = payload["choices"][0]["message"]["content"]
    assert "exception_type: RuntimeError" in content
    assert "forced failure for non-stream" in content
    assert "traceback:" in content
    assert payload["choices"][0]["finish_reason"] == "stop"


def test_chat_completions_stream_forced_exception_returns_error_chunk_stop_done(monkeypatch):
    routes.workspace_session.reset()

    def fail_run(workspace, messages, tools, local_model=None):
        raise RuntimeError("forced failure for stream")

    monkeypatch.setattr(routes.agent_runner, "run", fail_run)

    client = TestClient(app)
    body = {
        "model": "gpt-4o-mini",
        "stream": True,
        "messages": [{"role": "user", "content": "hello"}],
    }

    with client.stream(
        "POST",
        "/v1/chat/completions",
        headers={"Accept": "text/event-stream"},
        json=body,
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        lines = [line for line in response.iter_lines() if line]

    assert len(lines) >= 3
    first = json.loads(lines[0].replace("data: ", "", 1))
    assert first["id"] == "chatcmpl-local-error"
    assert first["object"] == "chat.completion.chunk"
    assert isinstance(first["created"], int)
    assert first["model"] == "gpt-4o-mini"
    assert first["choices"][0]["index"] == 0
    assert first["choices"][0]["finish_reason"] is None
    assert "exception_type: RuntimeError" in first["choices"][0]["delta"]["content"]
    assert "forced failure for stream" in first["choices"][0]["delta"]["content"]

    stop_chunk = json.loads(lines[-2].replace("data: ", "", 1))
    assert stop_chunk["id"] == "chatcmpl-local-error"
    assert stop_chunk["object"] == "chat.completion.chunk"
    assert stop_chunk["choices"][0]["index"] == 0
    assert stop_chunk["choices"][0]["delta"] == {}
    assert stop_chunk["choices"][0]["finish_reason"] == "stop"

    assert lines[-1] == "data: [DONE]"


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


def test_chat_path_error_includes_workspace_diagnostics(tmp_path):
    routes.workspace_session.reset()
    missing = tmp_path / "missing_project"

    client = TestClient(app)
    body = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": f'@path "{missing}"'}],
    }
    response = client.post("/v1/chat/completions", json=body)
    assert response.status_code == 200
    payload = response.json()
    content = payload["choices"][0]["message"]["content"]
    assert "exception_type: FileNotFoundError" in content
    assert "raw=" in content
    assert "normalized=" in content
    assert "exists=False" in content
    assert "is_dir=False" in content
