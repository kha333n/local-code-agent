from __future__ import annotations

import hashlib
from typing import Any

import requests

from app.config import settings


class Embedder:
    def __init__(self, base_url: str | None = None, model: str | None = None) -> None:
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.model = model or settings.embedding_model

    def embed(self, text: str) -> list[float]:
        payload = {"model": self.model, "prompt": text}
        try:
            resp = requests.post(f"{self.base_url}/api/embeddings", json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            emb = data.get("embedding")
            if isinstance(emb, list) and emb:
                return [float(x) for x in emb]
        except requests.RequestException:
            pass
        return self._fallback_embedding(text)

    def _fallback_embedding(self, text: str) -> list[float]:
        # Deterministic local fallback so tests can run without external services.
        size = settings.vector_size
        vec = [0.0] * size
        tokens = text.lower().split()
        if not tokens:
            return vec
        for tok in tokens:
            digest = hashlib.sha1(tok.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:2], "big") % size
            sign = 1.0 if digest[2] % 2 == 0 else -1.0
            vec[idx] += sign
        norm = sum(v * v for v in vec) ** 0.5 or 1.0
        return [v / norm for v in vec]