from __future__ import annotations

from app.core.workspaces import collection_name
from app.services.retrieval import Retriever
from app.services.vector_store import InMemoryVectorStore


class DummyEmbedder:
    def embed(self, text: str) -> list[float]:
        mapping = {
            "laravel route": [1.0, 0.0, 0.0],
            "python worker": [0.0, 1.0, 0.0],
            "php route": [0.9, 0.1, 0.0],
        }
        return mapping.get(text, [0.0, 0.0, 1.0])


def test_vector_retrieval_returns_best_match():
    store = InMemoryVectorStore()
    workspace = "C:\\projects\\repo"
    collection = collection_name(workspace)
    store.ensure_collection(collection, 3)

    store.upsert_chunks(
        collection,
        vectors=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
        payloads=[
            {"path": "routes/web.php", "content": "php route", "chunk_hash": "a"},
            {"path": "worker.py", "content": "python worker", "chunk_hash": "b"},
        ],
    )

    retriever = Retriever(embedder=DummyEmbedder(), vector_store=store)  # type: ignore[arg-type]
    results = retriever.retrieve(workspace, "laravel route", top_k=1)

    assert len(results) == 1
    assert results[0].payload["path"] == "routes/web.php"
