from __future__ import annotations

import subprocess
import time
from pathlib import Path

from app.core.policies import WorkspacePolicy
from app.core.security import ensure_within_workspace
from app.utils.logger import logger
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

    def _log_tool_start(self, tool_name: str, args: dict) -> float:
        started = time.perf_counter()
        logger.info("Tool start: tool=%s workspace=%s args=%s", tool_name, self.workspace, args)
        return started

    def _log_tool_done(self, tool_name: str, started: float, result_summary: str) -> None:
        duration_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "Tool done: tool=%s workspace=%s duration_ms=%s result=%s",
            tool_name,
            self.workspace,
            duration_ms,
            result_summary,
        )

    def _log_tool_error(self, tool_name: str, started: float, exc: Exception) -> None:
        duration_ms = int((time.perf_counter() - started) * 1000)
        logger.exception(
            "Tool failed: tool=%s workspace=%s duration_ms=%s exception=%s",
            tool_name,
            self.workspace,
            duration_ms,
            type(exc).__name__,
        )

    def list_files(self, pattern: str = "**/*") -> list[str]:
        started = self._log_tool_start("list_files", {"pattern": pattern})
        paths: list[str] = []
        try:
            for file_path in self.workspace_path.glob(pattern):
                if file_path.is_file():
                    paths.append(str(file_path.relative_to(self.workspace_path)).replace("\\", "/"))
            self._log_tool_done("list_files", started, f"files={len(paths)}")
            return paths
        except Exception as exc:
            self._log_tool_error("list_files", started, exc)
            raise

    def read_file(self, path: str) -> str:
        started = self._log_tool_start("read_file", {"path": path})
        try:
            target = self._resolve_path(path)
            content = target.read_text(encoding="utf-8", errors="ignore")
            self._log_tool_done("read_file", started, f"chars={len(content)}")
            return content
        except Exception as exc:
            self._log_tool_error("read_file", started, exc)
            raise

    def write_file(self, path: str, content: str) -> None:
        started = self._log_tool_start("write_file", {"path": path, "chars": len(content)})
        rel = path.replace("\\", "/")
        if not self.policy.can_write(rel):
            raise ToolPermissionRequired("write_file", path)
        try:
            target = self._resolve_path(path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            self._log_tool_done("write_file", started, "ok")
        except Exception as exc:
            self._log_tool_error("write_file", started, exc)
            raise

    def apply_patch(self, path: str, content: str) -> None:
        started = self._log_tool_start("apply_patch", {"path": path, "chars": len(content)})
        rel = path.replace("\\", "/")
        if not self.policy.can_write(rel):
            raise ToolPermissionRequired("apply_patch", path)
        try:
            target = self._resolve_path(path)
            target.write_text(content, encoding="utf-8")
            self._log_tool_done("apply_patch", started, "ok")
        except Exception as exc:
            self._log_tool_error("apply_patch", started, exc)
            raise

    def ripgrep(self, pattern: str) -> str:
        started = self._log_tool_start("ripgrep", {"pattern": pattern})
        cmd = ["rg", "--line-number", "--no-heading", pattern, str(self.workspace_path)]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, shell=False)
            output = result.stdout.strip()
            self._log_tool_done("ripgrep", started, f"chars={len(output)}")
            return output
        except Exception as exc:
            self._log_tool_error("ripgrep", started, exc)
            raise

    def git_status(self) -> str:
        started = self._log_tool_start("git_status", {})
        if not self.policy.allow_git:
            raise ToolPermissionRequired("git_status", "git status")
        try:
            result = subprocess.run(
                ["git", "status", "--short"],
                cwd=str(self.workspace_path),
                capture_output=True,
                text=True,
                shell=False,
            )
            output = result.stdout.strip()
            self._log_tool_done("git_status", started, f"chars={len(output)}")
            return output
        except Exception as exc:
            self._log_tool_error("git_status", started, exc)
            raise

    def git_diff(self) -> str:
        started = self._log_tool_start("git_diff", {})
        if not self.policy.allow_git:
            raise ToolPermissionRequired("git_diff", "git diff")
        try:
            result = subprocess.run(
                ["git", "diff"],
                cwd=str(self.workspace_path),
                capture_output=True,
                text=True,
                shell=False,
            )
            output = result.stdout.strip()
            self._log_tool_done("git_diff", started, f"chars={len(output)}")
            return output
        except Exception as exc:
            self._log_tool_error("git_diff", started, exc)
            raise

    def run_cmd(self, command: str) -> str:
        started = self._log_tool_start("run_cmd", {"command": command})
        if not self.policy.can_run(command):
            raise ToolPermissionRequired("run_cmd", command)

        shell = get_shell()
        if IS_WINDOWS:
            cmd = [*shell, "-NoProfile", "-Command", command]
        else:
            cmd = [*shell, "-lc", command]

        try:
            result = subprocess.run(
                cmd,
                cwd=str(self.workspace_path),
                capture_output=True,
                text=True,
                shell=False,
            )
            out = result.stdout + ("\n" + result.stderr if result.stderr else "")
            output = out.strip()
            self._log_tool_done("run_cmd", started, f"chars={len(output)}")
            return output
        except Exception as exc:
            self._log_tool_error("run_cmd", started, exc)
            raise


def tool_error_response(exc: ToolPermissionRequired) -> dict:
    payload = {"tool_request": exc.tool_request}
    if exc.command:
        payload["command"] = exc.command
    return payload
