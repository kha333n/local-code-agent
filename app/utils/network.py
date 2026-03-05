from __future__ import annotations

import subprocess
from urllib.parse import urlsplit, urlunsplit

from app.utils.logger import logger
from app.utils.platform import IS_WSL


def _default_gateway_ip() -> str | None:
    try:
        result = subprocess.run(
            ["ip", "route", "show", "default"],
            capture_output=True,
            text=True,
            shell=False,
            timeout=3,
        )
    except Exception:
        return None

    line = (result.stdout or "").strip().splitlines()
    if not line:
        return None

    parts = line[0].split()
    if "via" not in parts:
        return None
    idx = parts.index("via")
    if idx + 1 >= len(parts):
        return None
    return parts[idx + 1]


def resolve_ollama_base_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    parsed = urlsplit(normalized)
    host = (parsed.hostname or "").lower()

    # Respect explicit non-local host configuration.
    if host and host not in {"127.0.0.1", "localhost", "::1"}:
        return normalized

    # Dynamic host resolution is only needed for WSL -> Windows host networking.
    if not IS_WSL:
        return normalized

    gateway_ip = _default_gateway_ip()
    if not gateway_ip:
        logger.info("WSL detected but no default gateway found; using configured Ollama URL: %s", normalized)
        return normalized

    scheme = parsed.scheme or "http"
    port = parsed.port or 11434
    resolved = urlunsplit((scheme, f"{gateway_ip}:{port}", parsed.path, parsed.query, parsed.fragment)).rstrip("/")
    logger.info("Resolved Ollama URL for WSL: %s -> %s", normalized, resolved)
    return resolved

