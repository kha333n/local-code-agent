from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.api import routes
from app.main import app


def test_path_command_creates_config_and_initializes_collection(monkeypatch, tmp_path):
    routes.workspace_session.reset()
    called: dict[str, str] = {}

    def fake_ensure_collection(name: str, vector_size: int):
        called["collection"] = name

    monkeypatch.setattr(routes.vector_store, "ensure_collection", fake_ensure_collection)

    client = TestClient(app)
    body = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": f"@path {tmp_path}"}],
    }
    response = client.post("/v1/chat/completions", json=body)
    assert response.status_code == 200
    msg = response.json()["choices"][0]["message"]["content"]
    assert "Workspace set to" in msg

    cfg_file = tmp_path / ".agent-workspace.json"
    assert cfg_file.exists()
    cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
    assert cfg["workspace_root"] == str(tmp_path)
    assert cfg["collection"].startswith("ws_")
    assert cfg["trusted"] is True
    assert called["collection"] == cfg["collection"]


def test_skip_command_sets_stateless_and_bypasses_inference(monkeypatch):
    routes.workspace_session.reset()
    calls = {"count": 0}

    def fake_run(*args, **kwargs):
        calls["count"] += 1
        return "should not run"

    monkeypatch.setattr(routes.agent_runner, "run", fake_run)

    client = TestClient(app)
    body = {"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "@skip"}]}
    response = client.post("/v1/chat/completions", json=body)
    assert response.status_code == 200
    assert calls["count"] == 0
    assert "Stateless mode enabled" in response.json()["choices"][0]["message"]["content"]


def test_index_command_indexes_current_workspace(monkeypatch, tmp_path):
    routes.workspace_session.reset()
    client = TestClient(app)

    set_body = {"model": "gpt-4o-mini", "messages": [{"role": "user", "content": f"@path {tmp_path}"}]}
    client.post("/v1/chat/completions", json=set_body)

    def fake_index_workspace(workspace: str, recreate: bool = False):
        return {"collection": "ws_test", "files_indexed": 2, "chunks_indexed": 5}

    monkeypatch.setattr(routes.indexer, "index_workspace", fake_index_workspace)

    idx_body = {"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "@index"}]}
    idx_res = client.post("/v1/chat/completions", json=idx_body)
    assert idx_res.status_code == 200
    content = idx_res.json()["choices"][0]["message"]["content"]
    assert "Workspace indexed" in content
    assert "files: 2" in content


def test_reset_command_clears_workspace(monkeypatch, tmp_path):
    routes.workspace_session.reset()
    calls = {"workspace": "unset"}

    def fake_run(workspace, messages, tools, local_model=None):
        calls["workspace"] = "none" if workspace is None else str(workspace)
        return "ok"

    monkeypatch.setattr(routes.agent_runner, "run", fake_run)

    client = TestClient(app)
    client.post(
        "/v1/chat/completions",
        json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": f"@path {tmp_path}"}]},
    )
    client.post(
        "/v1/chat/completions",
        json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "@reset"}]},
    )
    client.post(
        "/v1/chat/completions",
        json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "hello"}]},
    )
    assert calls["workspace"] == "none"
