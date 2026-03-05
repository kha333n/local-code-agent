from __future__ import annotations

import pytest

from app.core.policies import WorkspacePolicy
from app.core.security import SandboxViolation
from app.tools.sandbox_tools import SandboxedTools, ToolPermissionRequired


def test_apply_patch_sandbox_blocks_workspace_escape(tmp_path):
    policy = WorkspacePolicy({"write_paths": ["./"], "allowed_commands": ["pytest"], "allow_git": True})
    tools = SandboxedTools(workspace=str(tmp_path), policy=policy)

    with pytest.raises(SandboxViolation):
        tools.apply_patch("..\\outside.txt", "bad")


def test_write_file_respects_policy(tmp_path):
    (tmp_path / "app").mkdir()
    policy = WorkspacePolicy({"write_paths": ["app/"], "allowed_commands": [], "allow_git": True})
    tools = SandboxedTools(workspace=str(tmp_path), policy=policy)

    with pytest.raises(ToolPermissionRequired):
        tools.write_file("tests/test_sample.py", "content")