from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.workspaces import collection_name
from app.workspace.detector import WORKSPACE_CONFIG_FILE, normalize_workspace_path

DEFAULT_ALLOWED_COMMANDS = ["php", "composer", "npm"]


def workspace_config_path(workspace_root: str) -> Path:
    normalized = normalize_workspace_path(workspace_root)
    return Path(normalized) / WORKSPACE_CONFIG_FILE


def _normalize_config(workspace_root: str, config: dict[str, Any]) -> dict[str, Any]:
    normalized_root = normalize_workspace_path(str(config.get("workspace_root", workspace_root)))
    collection = str(
        config.get("collection")
        or config.get("qdrant_collection")
        or collection_name(normalized_root)
    )
    return {
        "workspace_root": normalized_root,
        "collection": collection,
        "qdrant_collection": collection,  # backward compatible alias for existing code paths
        "trusted": bool(config.get("trusted", True)),
        "allowed_commands": [str(x) for x in config.get("allowed_commands", DEFAULT_ALLOWED_COMMANDS)],
    }


def load_workspace_config(workspace_root: str) -> dict[str, Any] | None:
    path = workspace_config_path(workspace_root)
    if not path.exists():
        return None
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw or "{}")
    if not isinstance(data, dict):
        return None
    return _normalize_config(workspace_root, data)


def ensure_workspace_config(workspace_root: str) -> dict[str, Any]:
    normalized_root = normalize_workspace_path(workspace_root)
    root_path = Path(normalized_root)
    if not root_path.exists() or not root_path.is_dir():
        raise FileNotFoundError(f"Workspace path does not exist or is not a directory: {normalized_root}")

    path = workspace_config_path(normalized_root)
    loaded = load_workspace_config(normalized_root)
    if loaded:
        normalized_loaded = _normalize_config(normalized_root, loaded)
        # Keep collection stable and hash-based.
        normalized_loaded["collection"] = collection_name(normalized_loaded["workspace_root"])
        normalized_loaded["qdrant_collection"] = normalized_loaded["collection"]
        path.write_text(json.dumps(normalized_loaded, indent=2), encoding="utf-8")
        return normalized_loaded

    created = {
        "workspace_root": normalized_root,
        "collection": collection_name(normalized_root),
        "qdrant_collection": collection_name(normalized_root),
        "trusted": True,
        "allowed_commands": list(DEFAULT_ALLOWED_COMMANDS),
    }
    path.write_text(json.dumps(created, indent=2), encoding="utf-8")
    return created
