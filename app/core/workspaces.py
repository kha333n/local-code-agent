from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path
from typing import Any

from app.config import settings
from app.workspace.detector import normalize_workspace_path


def workspace_hash(workspace: str) -> str:
    normalized = normalize_workspace_path(workspace).lower().encode("utf-8")
    return hashlib.sha1(normalized).hexdigest()


def collection_name(workspace: str) -> str:
    return f"ws_{workspace_hash(workspace)[:5]}"


class WorkspaceRegistry:
    def __init__(self, registry_path: Path | None = None) -> None:
        self.registry_path = registry_path or (settings.agent_home / "workspaces.json")
        self._allow_once: set[str] = set()
        self._lock = threading.Lock()
        if not self.registry_path.exists():
            self.registry_path.write_text("{}", encoding="utf-8")

    def _load(self) -> dict[str, Any]:
        raw = self.registry_path.read_text(encoding="utf-8")
        data = json.loads(raw or "{}")
        if not isinstance(data, dict):
            return {}
        return data

    def _save(self, data: dict[str, Any]) -> None:
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        self.registry_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def list(self) -> dict[str, Any]:
        with self._lock:
            return self._load()

    def get(self, workspace: str) -> dict[str, Any] | None:
        workspace = normalize_workspace_path(workspace)
        with self._lock:
            data = self._load()
            return data.get(workspace)

    def is_allowed(self, workspace: str) -> bool:
        workspace = normalize_workspace_path(workspace)
        with self._lock:
            if workspace in self._allow_once:
                return True
            data = self._load()
            entry = data.get(workspace)
            return bool(entry and entry.get("trusted"))

    def allow_once(self, workspace: str) -> dict[str, Any]:
        workspace = normalize_workspace_path(workspace)
        with self._lock:
            self._allow_once.add(workspace)
        return {
            "workspace": workspace,
            "trusted": False,
            "collection": collection_name(workspace),
            "allowed_commands": [],
            "mode": "allow_once",
        }

    def register_always(self, workspace: str, allowed_commands: list[str] | None = None) -> dict[str, Any]:
        workspace = normalize_workspace_path(workspace)
        allowed_commands = allowed_commands or []
        entry = {
            "trusted": True,
            "collection": collection_name(workspace),
            "allowed_commands": allowed_commands,
        }
        with self._lock:
            data = self._load()
            data[workspace] = entry
            self._save(data)
        return entry
