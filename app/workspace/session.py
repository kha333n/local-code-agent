from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass
class SessionState:
    workspace: str | None = None
    stateless: bool = False


class WorkspaceSessionStore:
    def __init__(self) -> None:
        self._state = SessionState()
        self._lock = threading.Lock()

    def snapshot(self) -> SessionState:
        with self._lock:
            return SessionState(workspace=self._state.workspace, stateless=self._state.stateless)

    def set_workspace(self, workspace: str) -> None:
        with self._lock:
            self._state.workspace = workspace
            self._state.stateless = False

    def enable_stateless(self) -> None:
        with self._lock:
            self._state.workspace = None
            self._state.stateless = True

    def reset(self) -> None:
        with self._lock:
            self._state.workspace = None
            self._state.stateless = True

