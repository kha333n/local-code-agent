from __future__ import annotations

import os
import re
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

WORKSPACE_CONFIG_FILE = ".agent-workspace.json"

WINDOWS_PATH_RE = re.compile(
    r"(?<!\w)([A-Za-z]:[\\/](?:[^\\/:*?\"<>|\r\n\t '`\[\]\(\)\{\},;]+[\\/]?)*)"
)
LINUX_PATH_RE = re.compile(r"(?<![\w:])(/(?:[^/\r\n\t '\"`]+/)*[^/\r\n\t '\"`]+/?)+")
UNC_WSL_PATH_RE = re.compile(
    r"(\\\\wsl\$\\[^\\/:*?\"<>|\r\n\t ]+\\(?:[^\\/:*?\"<>|\r\n\t '`\[\]\(\)\{\},;]+\\?)*)",
    re.IGNORECASE,
)


def _is_wsl_unc(path: str) -> bool:
    return path.lower().startswith("\\\\wsl$\\")


def _is_windows_path(path: str) -> bool:
    return bool(re.match(r"^[A-Za-z]:[\\/]", path))


def _trim_path_noise(raw: str) -> str:
    candidate = raw.strip().strip("'\"")
    return candidate.rstrip(".,;:)]}")


def _finalize_windows_path(raw: str) -> str:
    pure = PureWindowsPath(raw.replace("/", "\\"))
    normalized = str(pure)
    if re.fullmatch(r"[A-Za-z]:\\?", normalized):
        return f"{normalized[0]}:\\"
    return normalized.rstrip("\\/")


def _finalize_posix_path(raw: str) -> str:
    pure = PurePosixPath(raw.replace("\\", "/"))
    normalized = str(pure)
    if normalized == ".":
        return ""
    if normalized == "/":
        return normalized
    return normalized.rstrip("/")


def normalize_workspace_path(path: str) -> str:
    cleaned = _trim_path_noise(path or "")
    if not cleaned:
        return ""

    if _is_wsl_unc(cleaned) or _is_windows_path(cleaned):
        return _finalize_windows_path(cleaned)
    return _finalize_posix_path(cleaned)


def _extract_message_content(msg: Any) -> str:
    if isinstance(msg, str):
        return msg
    if isinstance(msg, dict):
        content = msg.get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict) and isinstance(item.get("text"), str):
                    parts.append(item["text"])
                elif isinstance(item, str):
                    parts.append(item)
            return "\n".join(parts)
    return ""


def _find_git_root(path: Path) -> Path | None:
    current = path
    for candidate in [current, *current.parents]:
        try:
            if (candidate / ".git").exists():
                return candidate
        except OSError:
            continue
    return None


def _looks_like_file_path(path: str) -> bool:
    if _is_wsl_unc(path) or _is_windows_path(path):
        name = PureWindowsPath(path).name
    else:
        name = PurePosixPath(path).name
    return "." in name and not name.startswith(".")


def _workspace_from_path_candidate(candidate: str) -> str:
    normalized = normalize_workspace_path(candidate)
    if not normalized:
        return ""

    concrete = Path(normalized)
    try:
        if concrete.exists():
            base = concrete if concrete.is_dir() else concrete.parent
            git_root = _find_git_root(base)
            return normalize_workspace_path(str(git_root or base))
    except OSError:
        pass

    if _looks_like_file_path(normalized):
        pure = PureWindowsPath(normalized) if (_is_wsl_unc(normalized) or _is_windows_path(normalized)) else PurePosixPath(normalized)
        return normalize_workspace_path(str(pure.parent))
    return normalized


def detect_from_paths(messages: list[Any]) -> str | None:
    for msg in messages:
        text = _extract_message_content(msg)
        if not text:
            continue

        candidates: list[str] = []
        for pattern in (UNC_WSL_PATH_RE, WINDOWS_PATH_RE, LINUX_PATH_RE):
            candidates.extend(match.group(1) for match in pattern.finditer(text))

        for candidate in candidates:
            if candidate.startswith("//"):
                continue
            workspace = _workspace_from_path_candidate(candidate)
            if workspace:
                return workspace
    return None


def detect_workspace(request_json: dict[str, Any] | None, messages: list[Any] | None) -> str | None:
    request_json = request_json or {}
    messages = messages or []

    explicit = normalize_workspace_path(str(request_json.get("workspace", "")))
    if explicit:
        return explicit

    header_workspace = normalize_workspace_path(
        str(request_json.get("x_workspace_path") or request_json.get("X-Workspace-Path") or "")
    )
    if header_workspace:
        return header_workspace

    detected_from_msgs = detect_from_paths(messages)
    if detected_from_msgs:
        return detected_from_msgs

    try:
        cwd = normalize_workspace_path(os.getcwd())
    except OSError:
        cwd = ""
    if cwd:
        return cwd

    try:
        cwd_path = Path(os.getcwd())
    except OSError:
        cwd_path = None
    if cwd_path:
        cfg = cwd_path / WORKSPACE_CONFIG_FILE
        if cfg.exists():
            try:
                import json

                data = json.loads(cfg.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    cfg_root = normalize_workspace_path(str(data.get("workspace_root", "")))
                    if cfg_root:
                        return cfg_root
            except (OSError, ValueError):
                pass

    env_workspace = normalize_workspace_path(os.getenv("DEFAULT_WORKSPACE", ""))
    if env_workspace:
        return env_workspace

    return None
