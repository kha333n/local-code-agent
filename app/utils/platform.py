from __future__ import annotations

import os
import platform

IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"
IS_WSL = IS_LINUX and (
    "WSL_DISTRO_NAME" in os.environ
    or "microsoft" in platform.release().lower()
    or "microsoft" in platform.version().lower()
)


def get_shell() -> list[str]:
    if IS_WINDOWS:
        return ["powershell"]
    return ["/bin/bash"]
