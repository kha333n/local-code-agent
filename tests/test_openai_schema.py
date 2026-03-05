from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.api import routes
from app.main import app


def test_models_endpoint_schema_strict():
    routes.workspace_session.reset()
    client = TestClient(app)
    response = client.get("/v1/models")
    assert response.status_code == 200
    assert response.json() == {
        "object": "list",
        "data": [
            {
                "id": "gpt-4o-mini",
                "object": "model",
                "owned_by": "openai",
            }
        ],
    }


def test_chat_completions_non_streaming_openai_shape_and_model_mapping(monkeypatch):
    routes.workspace_session.reset()
    captured: dict[str, str] = {}

    def fake_run(workspace, messages, tools, local_model=None):
        captured["local_model"] = str(local_model)
        return "stubbed answer"

    monkeypatch.setattr(routes.agent_runner, "run", fake_run)

    client = TestClient(app)
    body = {
        "model": "claude-3.5",
        "messages": [{"role": "user", "content": "hello"}],
    }
    response = client.post("/v1/chat/completions", json=body)
    assert response.status_code == 200

    payload = response.json()
    assert payload["id"] == "chatcmpl-local"
    assert payload["object"] == "chat.completion"
    assert isinstance(payload["created"], int)
    assert payload["model"] == "gpt-4o-mini"
    assert payload["choices"][0]["index"] == 0
    assert payload["choices"][0]["message"]["role"] == "assistant"
    assert payload["choices"][0]["message"]["content"] == "stubbed answer"
    assert payload["choices"][0]["finish_reason"] == "stop"
    assert captured["local_model"] == "qwen2.5-coder:7b"


def test_chat_completions_streaming_sse(monkeypatch):
    routes.workspace_session.reset()
    def fake_run(workspace, messages, tools, local_model=None):
        return "streamed response"

    monkeypatch.setattr(routes.agent_runner, "run", fake_run)

    client = TestClient(app)
    body = {
        "model": "some-unknown-model-name",
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

    assert lines[-1] == "data: [DONE]"
    first = json.loads(lines[0].replace("data: ", "", 1))
    assert first["id"] == "chatcmpl-local"
    assert first["object"] == "chat.completion.chunk"
    assert isinstance(first["created"], int)
    assert first["model"] == "gpt-4o-mini"
    assert first["choices"][0]["index"] == 0
    assert "content" in first["choices"][0]["delta"]
    assert first["choices"][0]["finish_reason"] is None

    final_chunk = json.loads(lines[-2].replace("data: ", "", 1))
    assert final_chunk["id"] == "chatcmpl-local"
    assert final_chunk["object"] == "chat.completion.chunk"
    assert final_chunk["model"] == "gpt-4o-mini"
    assert final_chunk["choices"][0]["index"] == 0
    assert final_chunk["choices"][0]["delta"] == {}
    assert final_chunk["choices"][0]["finish_reason"] == "stop"
