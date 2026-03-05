from __future__ import annotations

from pathlib import Path

from app.config import settings
from app.services.chunker import IGNORED_DIRS, chunk_text
from app.services.embedding import Embedder
from app.services.vector_store import QdrantVectorStore
from app.workspace.config import ensure_workspace_config
from app.workspace.detector import normalize_workspace_path


class WorkspaceIndexer:
    def __init__(self, embedder: Embedder, vector_store: QdrantVectorStore) -> None:
        self.embedder = embedder
        self.vector_store = vector_store

    def index_workspace(self, workspace: str, recreate: bool = False) -> dict[str, int | str]:
        metadata = ensure_workspace_config(workspace)
        normalized_workspace = normalize_workspace_path(metadata["workspace_root"])
        root = Path(normalized_workspace)
        collection = str(metadata.get("collection") or metadata.get("qdrant_collection"))
        if recreate:
            self.vector_store.recreate_collection(collection)
        else:
            self.vector_store.ensure_collection(collection, settings.vector_size)

        files_indexed = 0
        chunks_indexed = 0

        vectors: list[list[float]] = []
        payloads: list[dict] = []

        for file_path in self._iter_files(root):
            try:
                if file_path.stat().st_size > settings.max_file_bytes:
                    continue
                raw = file_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            rel_path = str(file_path.relative_to(root)).replace("\\", "/")
            chunks = chunk_text(raw, rel_path, file_path.stat().st_mtime)
            if not chunks:
                continue
            files_indexed += 1

            for chunk in chunks:
                vectors.append(self.embedder.embed(chunk.content))
                payloads.append(
                    {
                        "path": chunk.path,
                        "start_line": chunk.start_line,
                        "end_line": chunk.end_line,
                        "language": chunk.language,
                        "chunk_hash": chunk.chunk_hash,
                        "file_mtime": chunk.file_mtime,
                        "content": chunk.content,
                    }
                )
                chunks_indexed += 1

            if len(vectors) >= 128:
                self.vector_store.upsert_chunks(collection, vectors, payloads)
                vectors.clear()
                payloads.clear()

        if vectors:
            self.vector_store.upsert_chunks(collection, vectors, payloads)

        return {"collection": collection, "files_indexed": files_indexed, "chunks_indexed": chunks_indexed}

    def _iter_files(self, root: Path):
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            normalized = str(path.relative_to(root)).replace("\\", "/")
            if any(normalized.startswith(skip) for skip in IGNORED_DIRS):
                continue
            yield path
