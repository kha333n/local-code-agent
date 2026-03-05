from __future__ import annotations

import json

from app.workspace.config import ensure_workspace_config, load_workspace_config


def test_workspace_config_loading(tmp_path):
    cfg_path = tmp_path / ".agent-workspace.json"
    cfg_path.write_text(
        json.dumps(
            {
                "workspace_root": str(tmp_path),
                "qdrant_collection": "ws_custom",
                "trusted": True,
                "allowed_commands": ["php", "composer"],
            }
        ),
        encoding="utf-8",
    )

    cfg = load_workspace_config(str(tmp_path))
    assert cfg is not None
    assert cfg["workspace_root"] == str(tmp_path)
    # Loader normalizes to hash-based collection names.
    assert cfg["qdrant_collection"].startswith("ws_")
    assert cfg["trusted"] is True
    assert cfg["allowed_commands"] == ["php", "composer"]


def test_workspace_initialization_creates_config(tmp_path):
    cfg = ensure_workspace_config(str(tmp_path))
    assert cfg["workspace_root"] == str(tmp_path)
    assert cfg["qdrant_collection"].startswith("ws_")
    assert cfg["trusted"] is True
    assert "php" in cfg["allowed_commands"]

    cfg_file = tmp_path / ".agent-workspace.json"
    assert cfg_file.exists()

