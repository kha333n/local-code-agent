from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import settings
from app.core.workspaces import workspace_hash


class WorkspacePolicy:
    def __init__(self, data: dict[str, Any]) -> None:
        self.allowed_commands = [c.lower() for c in data.get("allowed_commands", [])]
        self.allow_git = bool(data.get("allow_git", True))
        self.write_paths = data.get("write_paths", ["./"])

    def can_run(self, command: str) -> bool:
        if not self.allowed_commands:
            return False
        first = (command.strip().split() or [""])[0].lower()
        return first in self.allowed_commands

    def can_write(self, rel_path: str) -> bool:
        normalized = rel_path.replace("\\", "/").lstrip("/")
        if "./" in self.write_paths:
            return True
        for prefix in self.write_paths:
            check = prefix.replace("\\", "/").lstrip("/")
            if normalized.startswith(check):
                return True
        return False


class PolicyStore:
    def __init__(self, policy_dir: Path | None = None) -> None:
        self.policy_dir = policy_dir or (settings.agent_home / "policies")
        self.policy_dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, workspace: str) -> Path:
        return self.policy_dir / f"{workspace_hash(workspace)}.json"

    def load_or_create(self, workspace: str, registry_entry: dict[str, Any] | None) -> WorkspacePolicy:
        path = self._path_for(workspace)
        if not path.exists():
            defaults = {
                "allowed_commands": (registry_entry or {}).get("allowed_commands", []),
                "allow_git": True,
                "write_paths": ["./"],
            }
            path.write_text(json.dumps(defaults, indent=2), encoding="utf-8")
            return WorkspacePolicy(defaults)
        data = json.loads(path.read_text(encoding="utf-8") or "{}")
        if not isinstance(data, dict):
            data = {}
        return WorkspacePolicy(data)

    def update(self, workspace: str, payload: dict[str, Any]) -> WorkspacePolicy:
        path = self._path_for(workspace)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return WorkspacePolicy(payload)