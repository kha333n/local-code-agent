from __future__ import annotations

from app.config import settings
from app.core.workspaces import collection_name
from app.services.embedding import Embedder
from app.services.vector_store import QdrantVectorStore, RetrievedChunk
from app.workspace.config import load_workspace_config


class Retriever:
    def __init__(self, embedder: Embedder, vector_store: QdrantVectorStore) -> None:
        self.embedder = embedder
        self.vector_store = vector_store

    def retrieve(self, workspace: str, query: str, top_k: int | None = None) -> list[RetrievedChunk]:
        top_k = top_k or settings.top_k
        cfg = load_workspace_config(workspace)
        collection = str((cfg or {}).get("collection") or (cfg or {}).get("qdrant_collection") or collection_name(workspace))
        query_vec = self.embedder.embed(query)
        return self.vector_store.search(collection, query_vec, top_k)


def build_context_pack(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return "No indexed workspace context found."
    lines: list[str] = ["Workspace context:"]
    for idx, chunk in enumerate(chunks, start=1):
        payload = chunk.payload
        lines.append(
            f"[{idx}] {payload.get('path')}:{payload.get('start_line')}-{payload.get('end_line')}\n{payload.get('content')}"
        )
    return "\n\n".join(lines)
