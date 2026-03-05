from __future__ import annotations

import subprocess
from pathlib import Path

from app.core.policies import WorkspacePolicy
from app.core.security import ensure_within_workspace
from app.utils.platform import IS_WINDOWS, get_shell


class ToolPermissionRequired(PermissionError):
    def __init__(self, tool_request: str, command: str | None = None) -> None:
        self.tool_request = tool_request
        self.command = command
        super().__init__(tool_request)


class SandboxedTools:
    def __init__(self, workspace: str, policy: WorkspacePolicy) -> None:
        self.workspace = workspace
        self.workspace_path = Path(workspace)
        self.policy = policy

    def _resolve_path(self, relative_path: str) -> Path:
        target = (self.workspace_path / relative_path).resolve(strict=False)
        ensure_within_workspace(str(self.workspace_path), str(target))
        return target

    def list_files(self, pattern: str = "**/*") -> list[str]:
        paths: list[str] = []
        for file_path in self.workspace_path.glob(pattern):
            if file_path.is_file():
                paths.append(str(file_path.relative_to(self.workspace_path)).replace("\\", "/"))
        return paths

    def read_file(self, path: str) -> str:
        target = self._resolve_path(path)
        return target.read_text(encoding="utf-8", errors="ignore")

    def write_file(self, path: str, content: str) -> None:
        rel = path.replace("\\", "/")
        if not self.policy.can_write(rel):
            raise ToolPermissionRequired("write_file", path)
        target = self._resolve_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def apply_patch(self, path: str, content: str) -> None:
        rel = path.replace("\\", "/")
        if not self.policy.can_write(rel):
            raise ToolPermissionRequired("apply_patch", path)
        target = self._resolve_path(path)
        target.write_text(content, encoding="utf-8")

    def ripgrep(self, pattern: str) -> str:
        cmd = ["rg", "--line-number", "--no-heading", pattern, str(self.workspace_path)]
        result = subprocess.run(cmd, capture_output=True, text=True, shell=False)
        return result.stdout.strip()

    def git_status(self) -> str:
        if not self.policy.allow_git:
            raise ToolPermissionRequired("git_status", "git status")
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=str(self.workspace_path),
            capture_output=True,
            text=True,
            shell=False,
        )
        return result.stdout.strip()

    def git_diff(self) -> str:
        if not self.policy.allow_git:
            raise ToolPermissionRequired("git_diff", "git diff")
        result = subprocess.run(
            ["git", "diff"],
            cwd=str(self.workspace_path),
            capture_output=True,
            text=True,
            shell=False,
        )
        return result.stdout.strip()

    def run_cmd(self, command: str) -> str:
        if not self.policy.can_run(command):
            raise ToolPermissionRequired("run_cmd", command)

        shell = get_shell()
        if IS_WINDOWS:
            cmd = [*shell, "-NoProfile", "-Command", command]
        else:
            cmd = [*shell, "-lc", command]

        result = subprocess.run(
            cmd,
            cwd=str(self.workspace_path),
            capture_output=True,
            text=True,
            shell=False,
        )
        out = result.stdout + ("\n" + result.stderr if result.stderr else "")
        return out.strip()


def tool_error_response(exc: ToolPermissionRequired) -> dict:
    payload = {"tool_request": exc.tool_request}
    if exc.command:
        payload["command"] = exc.command
    return payload
