from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Any

import requests

from app.config import settings


@dataclass
class RetrievedChunk:
    score: float
    payload: dict[str, Any]


class InMemoryVectorStore:
    def __init__(self) -> None:
        self._store: dict[str, list[tuple[list[float], dict[str, Any]]]] = {}

    def recreate_collection(self, name: str) -> None:
        self._store[name] = []

    def ensure_collection(self, name: str, vector_size: int) -> None:
        self._store.setdefault(name, [])

    def upsert_chunks(self, name: str, vectors: list[list[float]], payloads: list[dict[str, Any]]) -> None:
        self._store.setdefault(name, [])
        for vec, payload in zip(vectors, payloads, strict=True):
            self._store[name].append((vec, payload))

    def search(self, name: str, query_vector: list[float], limit: int) -> list[RetrievedChunk]:
        candidates = self._store.get(name, [])
        scored: list[RetrievedChunk] = []
        for vec, payload in candidates:
            score = cosine_similarity(query_vector, vec)
            scored.append(RetrievedChunk(score=score, payload=payload))
        scored.sort(key=lambda c: c.score, reverse=True)
        return scored[:limit]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a)) or 1.0
    norm_b = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (norm_a * norm_b)


class QdrantVectorStore:
    def __init__(self, url: str | None = None) -> None:
        self.base_url = (url or settings.qdrant_url).rstrip("/")

    def recreate_collection(self, name: str) -> None:
        requests.delete(f"{self.base_url}/collections/{name}", timeout=20)
        self._create_collection(name, settings.vector_size)

    def ensure_collection(self, name: str, vector_size: int) -> None:
        resp = requests.get(f"{self.base_url}/collections/{name}", timeout=20)
        if resp.status_code == 200:
            return
        self._create_collection(name, vector_size)

    def _create_collection(self, name: str, vector_size: int) -> None:
        body = {
            "vectors": {
                "size": vector_size,
                "distance": "Cosine",
            }
        }
        resp = requests.put(f"{self.base_url}/collections/{name}", json=body, timeout=20)
        resp.raise_for_status()

    def upsert_chunks(self, name: str, vectors: list[list[float]], payloads: list[dict[str, Any]]) -> None:
        points = []
        for vec, payload in zip(vectors, payloads, strict=True):
            point_id = int(hashlib.sha1(payload["chunk_hash"].encode("utf-8")).hexdigest()[:15], 16)
            points.append({"id": point_id, "vector": vec, "payload": payload})
        if not points:
            return
        body = {"points": points}
        resp = requests.put(f"{self.base_url}/collections/{name}/points?wait=true", json=body, timeout=60)
        resp.raise_for_status()

    def search(self, name: str, query_vector: list[float], limit: int) -> list[RetrievedChunk]:
        body = {
            "vector": query_vector,
            "limit": limit,
            "with_payload": True,
        }
        resp = requests.post(f"{self.base_url}/collections/{name}/points/search", json=body, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        result = data.get("result", [])
        out: list[RetrievedChunk] = []
        for item in result:
            out.append(RetrievedChunk(score=float(item.get("score", 0.0)), payload=dict(item.get("payload") or {})))
        return out