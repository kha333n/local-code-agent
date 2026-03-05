from __future__ import annotations

from typing import Any

import requests

from app.config import settings


class OllamaClient:
    def __init__(self, base_url: str | None = None, chat_model: str | None = None) -> None:
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.chat_model = chat_model or settings.chat_model

    def chat(self, messages: list[dict[str, str]], model: str | None = None) -> str:
        payload: dict[str, Any] = {
            "model": model or self.chat_model,
            "messages": messages,
            "stream": False,
        }
        response = requests.post(f"{self.base_url}/api/chat", json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()
        msg = data.get("message", {})
        content = msg.get("content", "")
        return str(content)