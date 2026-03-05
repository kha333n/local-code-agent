from __future__ import annotations

from pathlib import Path


class SandboxViolation(ValueError):
    pass


def is_path_within_workspace(workspace: str, target: str) -> bool:
    ws = Path(workspace).resolve(strict=False)
    tg = Path(target).resolve(strict=False)
    try:
        return tg == ws or ws in tg.parents
    except RuntimeError:
        return False


def ensure_within_workspace(workspace: str, target: str) -> None:
    if not is_path_within_workspace(workspace, target):
        raise SandboxViolation(f"Path '{target}' escapes workspace '{workspace}'")
