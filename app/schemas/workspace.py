from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class WorkspaceIndexRequest(BaseModel):
    workspace: str | None = None
    recreate: bool = False


class WorkspaceAuthorizeRequest(BaseModel):
    workspace: str
    action: Literal["allow_once", "allow_always", "deny"]
    allowed_commands: list[str] = Field(default_factory=list)


class WorkspaceRegisterRequest(BaseModel):
    workspace: str
    trusted: bool = True
    allowed_commands: list[str] = Field(default_factory=list)


class WorkspaceToolRequest(BaseModel):
    workspace: str | None = None
    tool: Literal[
        "read_file",
        "list_files",
        "ripgrep",
        "apply_patch",
        "write_file",
        "git_status",
        "git_diff",
        "run_cmd",
    ]
    args: dict[str, Any] = Field(default_factory=dict)
