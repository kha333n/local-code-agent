from __future__ import annotations

import json
import time
from collections.abc import Iterator

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

from app.agents.pipeline import AgentRunner
from app.core.policies import WorkspacePolicy
from app.core.security import SandboxViolation
from app.core.workspaces import WorkspaceRegistry, normalize_workspace_path
from app.schemas.openai import ChatCompletionRequest
from app.schemas.workspace import (
    WorkspaceAuthorizeRequest,
    WorkspaceIndexRequest,
    WorkspaceRegisterRequest,
    WorkspaceToolRequest,
)
from app.services.embedding import Embedder
from app.services.indexer import WorkspaceIndexer
from app.services.ollama import OllamaClient
from app.services.retrieval import Retriever
from app.services.vector_store import QdrantVectorStore
from app.tools.sandbox_tools import SandboxedTools, ToolPermissionRequired, tool_error_response
from app.workspace.commands import execute_workspace_command, parse_workspace_command
from app.workspace.config import ensure_workspace_config
from app.workspace.detector import detect_workspace
from app.workspace.session import WorkspaceSessionStore

router = APIRouter()

registry = WorkspaceRegistry()
embedder = Embedder()
vector_store = QdrantVectorStore()
indexer = WorkspaceIndexer(embedder=embedder, vector_store=vector_store)
retriever = Retriever(embedder=embedder, vector_store=vector_store)
ollama = OllamaClient()
agent_runner = AgentRunner(retriever=retriever, ollama=ollama)
workspace_session = WorkspaceSessionStore()

LOCAL_OLLAMA_MODEL = "qwen2.5-coder:7b"
OPENAI_PUBLIC_MODEL = "gpt-4o-mini"
SUPPORTED_MODEL_ALIASES = {
    "gpt-4",
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-3.5-turbo",
    "claude-3",
    "claude-3.5",
}


def _resolve_workspace_or_error(request_json: dict, messages: list[dict] | None = None) -> tuple[str | None, JSONResponse | None]:
    workspace = detect_workspace(request_json=request_json, messages=messages or [])
    if not workspace:
        return (
            None,
            JSONResponse(
                status_code=400,
                content={
                    "error": "workspace_required",
                    "message": "Workspace not detected. Please provide project root path.",
                },
            ),
        )
    return workspace, None


def _load_workspace_metadata(workspace: str) -> dict:
    return ensure_workspace_config(workspace)


def _workspace_not_registered_response(workspace: str) -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content={"error": "workspace_not_registered", "workspace": workspace},
    )


def _workspace_policy_from_config(config: dict) -> WorkspacePolicy:
    return WorkspacePolicy(
        {
            "allowed_commands": config.get("allowed_commands", []),
            "allow_git": True,
            "write_paths": ["./"],
        }
    )


def _map_model_to_local(_requested_model: str | None) -> str:
    requested = (_requested_model or "").lower()
    if requested in SUPPORTED_MODEL_ALIASES:
        return LOCAL_OLLAMA_MODEL
    # Unknown model names are accepted and still routed to the local model.
    return LOCAL_OLLAMA_MODEL


def _is_stream_request(payload: ChatCompletionRequest, accept_header: str | None) -> bool:
    if payload.stream:
        return True
    if not accept_header:
        return False
    return "text/event-stream" in accept_header.lower()


def _chunk_text(text: str, chunk_size: int = 48) -> list[str]:
    if not text:
        return [""]
    return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]


def _stream_chunks(content: str) -> Iterator[str]:
    created = int(time.time())
    for part in _chunk_text(content):
        payload = {
            "id": "chatcmpl-local",
            "object": "chat.completion.chunk",
            "created": created,
            "model": OPENAI_PUBLIC_MODEL,
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": part},
                    "finish_reason": None,
                }
            ],
        }
        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
    done_payload = {
        "id": "chatcmpl-local",
        "object": "chat.completion.chunk",
        "created": created,
        "model": OPENAI_PUBLIC_MODEL,
        "choices": [
            {
                "index": 0,
                "delta": {},
                "finish_reason": "stop",
            }
        ],
    }
    yield f"data: {json.dumps(done_payload, ensure_ascii=False)}\n\n"
    yield "data: [DONE]\n\n"


def _non_stream_response(content: str) -> dict:
    return {
        "id": "chatcmpl-local",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": OPENAI_PUBLIC_MODEL,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
    }


@router.get("/health")
def health() -> dict:
    return {"ok": True}


@router.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@router.post("/workspace/register")
def workspace_register(payload: WorkspaceRegisterRequest) -> dict:
    ws = normalize_workspace_path(payload.workspace)
    if payload.trusted:
        entry = registry.register_always(ws, payload.allowed_commands)
    else:
        entry = registry.allow_once(ws)
    return {"workspace": ws, **entry}


@router.post("/workspace/authorize")
def workspace_authorize(payload: WorkspaceAuthorizeRequest) -> dict:
    ws = normalize_workspace_path(payload.workspace)
    if payload.action == "deny":
        return {"workspace": ws, "status": "denied"}
    if payload.action == "allow_once":
        entry = registry.allow_once(ws)
        return {"workspace": ws, "status": "allow_once", **entry}
    entry = registry.register_always(ws, payload.allowed_commands)
    return {"workspace": ws, "status": "allow_always", **entry}


@router.post("/workspace/index")
def workspace_index(
    payload: WorkspaceIndexRequest,
    x_workspace_path: str | None = Header(default=None, alias="X-Workspace-Path"),
):
    request_json = payload.model_dump(exclude_none=True)
    if x_workspace_path:
        request_json["x_workspace_path"] = x_workspace_path

    ws, err = _resolve_workspace_or_error(request_json=request_json)
    if err:
        return err
    assert ws is not None

    try:
        metadata = _load_workspace_metadata(ws)
        if not metadata.get("trusted", False):
            return _workspace_not_registered_response(ws)
        result = indexer.index_workspace(ws, recreate=payload.recreate)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {
        "workspace": str(metadata["workspace_root"]),
        "collection": str(metadata.get("collection") or metadata.get("qdrant_collection")),
        **result,
    }


@router.post("/workspace/tool")
def workspace_tool(
    payload: WorkspaceToolRequest,
    x_workspace_path: str | None = Header(default=None, alias="X-Workspace-Path"),
):
    request_json = payload.model_dump(exclude_none=True)
    if x_workspace_path:
        request_json["x_workspace_path"] = x_workspace_path

    ws, err = _resolve_workspace_or_error(request_json=request_json)
    if err:
        return err
    assert ws is not None

    try:
        metadata = _load_workspace_metadata(ws)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not metadata.get("trusted", False):
        return _workspace_not_registered_response(ws)

    policy = _workspace_policy_from_config(metadata)
    tools = SandboxedTools(workspace=ws, policy=policy)

    try:
        if payload.tool == "read_file":
            return {"result": tools.read_file(payload.args["path"])}
        if payload.tool == "list_files":
            return {"result": tools.list_files(payload.args.get("pattern", "**/*"))}
        if payload.tool == "ripgrep":
            return {"result": tools.ripgrep(payload.args["pattern"])}
        if payload.tool == "apply_patch":
            tools.apply_patch(payload.args["path"], payload.args["content"])
            return {"result": "ok"}
        if payload.tool == "write_file":
            tools.write_file(payload.args["path"], payload.args["content"])
            return {"result": "ok"}
        if payload.tool == "git_status":
            return {"result": tools.git_status()}
        if payload.tool == "git_diff":
            return {"result": tools.git_diff()}
        if payload.tool == "run_cmd":
            return {"result": tools.run_cmd(payload.args["command"])}
    except ToolPermissionRequired as exc:
        return JSONResponse(status_code=403, content=tool_error_response(exc))
    except SandboxViolation as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    raise HTTPException(status_code=400, detail="unsupported tool")


@router.get("/v1/models")
def list_models() -> dict:
    return {
        "object": "list",
        "data": [
            {
                "id": "gpt-4o-mini",
                "object": "model",
                "owned_by": "openai",
            }
        ],
    }


@router.post("/v1/chat/completions")
def chat_completions(
    payload: ChatCompletionRequest,
    x_workspace_path: str | None = Header(default=None, alias="X-Workspace-Path"),
    accept: str | None = Header(default=None),
):
    messages = [m.model_dump() for m in payload.messages]
    command = parse_workspace_command(messages)
    request_json = payload.model_dump(exclude_none=True)
    if x_workspace_path:
        request_json["x_workspace_path"] = x_workspace_path

    # Execute workspace control commands before normal LLM inference.
    if command is not None:
        if command.name == "index":
            candidate = detect_workspace(request_json=request_json, messages=messages)
            if candidate:
                workspace_session.set_workspace(candidate)
        try:
            response_text = execute_workspace_command(
                command=command,
                session=workspace_session,
                indexer=indexer,
                vector_store=vector_store,
            )
        except Exception:
            response_text = "Workspace command failed. Please verify the path and local services."
        if _is_stream_request(payload, accept):
            headers = {"Cache-Control": "no-cache", "Connection": "keep-alive"}
            return StreamingResponse(_stream_chunks(response_text), media_type="text/event-stream", headers=headers)
        return _non_stream_response(response_text)

    session_state = workspace_session.snapshot()
    if session_state.stateless:
        ws = None
    elif session_state.workspace and "workspace" not in request_json and "x_workspace_path" not in request_json:
        ws = session_state.workspace
    else:
        ws = detect_workspace(request_json=request_json, messages=messages)
    resolved_workspace: str | None = None
    tools: SandboxedTools | None = None

    if ws:
        try:
            metadata = _load_workspace_metadata(ws)
            if metadata.get("trusted", False):
                resolved_workspace = str(metadata["workspace_root"])
                policy = _workspace_policy_from_config(metadata)
                tools = SandboxedTools(workspace=resolved_workspace, policy=policy)
                workspace_session.set_workspace(resolved_workspace)
        except FileNotFoundError:
            # Invalid workspace path falls back to stateless mode for OpenAI compatibility.
            resolved_workspace = None
            tools = None

    local_model = _map_model_to_local(payload.model)
    try:
        response_text = agent_runner.run(
            workspace=resolved_workspace,
            messages=messages,
            tools=tools,
            local_model=local_model,
        )
    except Exception:
        # Keep API-compatible behavior for IDE integrations.
        response_text = "Local model is temporarily unavailable. Please retry."

    if _is_stream_request(payload, accept):
        headers = {"Cache-Control": "no-cache", "Connection": "keep-alive"}
        return StreamingResponse(_stream_chunks(response_text), media_type="text/event-stream", headers=headers)

    return _non_stream_response(response_text)
