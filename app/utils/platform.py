from __future__ import annotations

import platform

IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"


def get_shell() -> list[str]:
    if IS_WINDOWS:
        return ["powershell"]
    return ["/bin/bash"]

