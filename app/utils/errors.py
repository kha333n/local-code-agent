from __future__ import annotations

import traceback
from typing import Any


def structured_error(
    error: str,
    message: str,
    *,
    step: str | None = None,
    details: dict[str, Any] | None = None,
    exc: Exception | None = None,
) -> dict[str, Any]:
    payload_details: dict[str, Any] = dict(details or {})
    if step:
        payload_details["step"] = step
    if exc is not None:
        payload_details["exception_type"] = type(exc).__name__
        payload_details["exception_message"] = str(exc)
        payload_details["traceback"] = traceback.format_exc()
    return {
        "error": error,
        "message": message,
        "details": payload_details,
    }

