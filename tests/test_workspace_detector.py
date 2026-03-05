from __future__ import annotations

from app.workspace import detector


def test_detect_from_paths_windows():
    messages = [{"role": "user", "content": r"Please edit C:\projects\repo\app\main.py"}]
    assert detector.detect_from_paths(messages) == r"C:\projects\repo\app"


def test_detect_from_paths_linux():
    messages = [{"role": "user", "content": "Fix issue in /home/user/project/src/main.py"}]
    assert detector.detect_from_paths(messages) == "/home/user/project/src"


def test_detect_from_paths_unc_wsl():
    messages = [{"role": "user", "content": r"Open \\wsl$\Ubuntu\home\user\repo\app\api.py"}]
    assert detector.detect_from_paths(messages) == r"\\wsl$\Ubuntu\home\user\repo\app"


def test_detect_workspace_fallback_to_default_workspace_env(monkeypatch):
    monkeypatch.delenv("DEFAULT_WORKSPACE", raising=False)
    monkeypatch.setenv("DEFAULT_WORKSPACE", r"C:\projects\from-env")
    monkeypatch.setattr(detector.os, "getcwd", lambda: (_ for _ in ()).throw(OSError("cwd unavailable")))

    ws = detector.detect_workspace(request_json={}, messages=[])
    assert ws == r"C:\projects\from-env"


def test_detect_workspace_from_header():
    ws = detector.detect_workspace(
        request_json={"x_workspace_path": r"C:\projects\from-header"},
        messages=[],
    )
    assert ws == r"C:\projects\from-header"


def test_detect_workspace_prefers_json_workspace_over_header():
    ws = detector.detect_workspace(
        request_json={
            "workspace": r"C:\projects\from-json",
            "x_workspace_path": r"C:\projects\from-header",
        },
        messages=[],
    )
    assert ws == r"C:\projects\from-json"
