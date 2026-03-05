from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from app.config import settings
from app.services.indexer import WorkspaceIndexer
from app.services.vector_store import QdrantVectorStore
from app.utils.logger import logger
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
        arg = _extract_path_argument(user_content)
        return WorkspaceCommand(name="path", argument=arg)
    if user_content.lower() == "@skip":
        return WorkspaceCommand(name="skip")
    if user_content.lower() == "@index":
        return WorkspaceCommand(name="index")
    if user_content.lower() == "@reset":
        return WorkspaceCommand(name="reset")
    return None


def _extract_path_argument(user_content: str) -> str:
    remainder = user_content[5:].lstrip()  # remove "@path"
    if not remainder:
        return ""

    # Only parse the first line so extra pasted context does not become path text.
    first_line = remainder.splitlines()[0].strip()
    match = re.match(r'^(?:"([^"]+)"|\'([^\']+)\'|(\S+))', first_line)
    if not match:
        return first_line
    return str(match.group(1) or match.group(2) or match.group(3) or "")


def _normalize_workspace_input(workspace_root: str) -> tuple[str, Path]:
    raw = workspace_root
    norm = raw.strip().strip('"').strip("'")
    p = Path(norm).expanduser()
    if not p.is_absolute():
        p = Path(os.getcwd()) / p
    # Safe canonicalization without strict existence requirement.
    return raw, p.resolve(strict=False)


def execute_workspace_command(
    command: WorkspaceCommand,
    session: WorkspaceSessionStore,
    indexer: WorkspaceIndexer,
    vector_store: QdrantVectorStore,
) -> str:
    logger.info("Workspace command received: %s arg=%s", command.name, command.argument)
    if command.name == "path":
        raw, workspace_path = _normalize_workspace_input(command.argument or "")
        exists = workspace_path.exists()
        is_dir = workspace_path.is_dir()
        has_workspace_config = (workspace_path / ".agent-workspace.json").exists()
        if not ((exists and is_dir) or has_workspace_config):
            raise FileNotFoundError(
                "Invalid workspace path. "
                f"raw={raw!r} normalized={str(workspace_path)!r} "
                f"cwd={os.getcwd()!r} exists={exists} is_dir={is_dir}"
            )

        ws = normalize_workspace_path(str(workspace_path))
        logger.info("Workspace path validated: %s", ws)
        metadata = ensure_workspace_config(ws)
        collection = str(metadata["collection"])
        logger.info("Creating or ensuring Qdrant collection: %s", collection)
        vector_store.ensure_collection(collection, settings.vector_size)
        logger.info("Qdrant collection created/ensured: %s", collection)
        session.set_workspace(str(metadata["workspace_root"]))
        logger.info("Workspace trusted: %s", metadata.get("trusted"))
        return f"Workspace set to {metadata['workspace_root']} (collection: {collection})."

    if command.name == "index":
        state = session.snapshot()
        if state.stateless or not state.workspace:
            return "Please provide project root path to enable project context."
        logger.info("Indexing started: %s", state.workspace)
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
