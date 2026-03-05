from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.config import settings
from app.services.indexer import WorkspaceIndexer
from app.services.vector_store import QdrantVectorStore
from app.workspace.config import ensure_workspace_config
from app.workspace.detector import normalize_workspace_path
from app.workspace.session import WorkspaceSessionStore


@dataclass
class WorkspaceCommand:
    name: str
    argument: str | None = None


def parse_workspace_command(messages: list[dict[str, str]]) -> WorkspaceCommand | None:
    user_content = ""
    for message in reversed(messages):
        if message.get("role") == "user":
            user_content = message.get("content", "").strip()
            break

    if not user_content.startswith("@"):
        return None

    if user_content.lower().startswith("@path "):
        arg = user_content[6:].strip().strip("'\"")
        return WorkspaceCommand(name="path", argument=arg)
    if user_content.lower() == "@skip":
        return WorkspaceCommand(name="skip")
    if user_content.lower() == "@index":
        return WorkspaceCommand(name="index")
    if user_content.lower() == "@reset":
        return WorkspaceCommand(name="reset")
    return None


def execute_workspace_command(
    command: WorkspaceCommand,
    session: WorkspaceSessionStore,
    indexer: WorkspaceIndexer,
    vector_store: QdrantVectorStore,
) -> str:
    if command.name == "path":
        ws = normalize_workspace_path(command.argument or "")
        root = Path(ws)
        if not ws or not root.exists() or not root.is_dir():
            return "Invalid workspace path. Please provide an existing project directory."

        metadata = ensure_workspace_config(ws)
        collection = str(metadata["collection"])
        vector_store.ensure_collection(collection, settings.vector_size)
        session.set_workspace(str(metadata["workspace_root"]))
        return f"Workspace set to {metadata['workspace_root']} (collection: {collection})."

    if command.name == "index":
        state = session.snapshot()
        if state.stateless or not state.workspace:
            return "Please provide project root path to enable project context."
        result = indexer.index_workspace(state.workspace, recreate=False)
        return (
            f"Workspace indexed: {state.workspace} | collection: {result['collection']} | "
            f"files: {result['files_indexed']} | chunks: {result['chunks_indexed']}"
        )

    if command.name == "skip":
        session.enable_stateless()
        return "Stateless mode enabled. Project context and RAG are disabled."

    if command.name == "reset":
        session.reset()
        return "Workspace cleared. Stateless mode enabled."

    return "Unknown workspace command."

