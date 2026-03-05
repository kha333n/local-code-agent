# local-cursor-agent

Cross-platform local Cursor-style coding agent (Windows, Linux, and WSL) using Ollama + Qdrant + LangGraph.

## Architecture
- FastAPI server (`app/main.py`)
- LangGraph pipeline (`plan -> retrieve -> propose_patch -> apply_patch -> run_tests -> fix_loop -> summarize`)
- Per-workspace Qdrant collections (`ws_<hash>`)
- Local Ollama chat + embeddings
- Platform helper (`app/utils/platform.py`) for shell execution

## Environment Configuration
The app loads configuration from `.env`.

Example (`.env`):
```env
AGENT_PORT=3210
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen2.5-coder:7b
QDRANT_URL=http://127.0.0.1:6333
RAG_TOP_K=10
```

`python -m app` defaults to `http://127.0.0.1:3210`.

## Dynamic Workspaces
Workspace is resolved automatically in this priority order:
1. JSON body field `workspace`
2. HTTP header `X-Workspace-Path`
3. Path detection from chat message content
4. Current working directory (`os.getcwd()`)
5. Workspace config in current directory (`.agent-workspace.json`)
6. Environment variable `DEFAULT_WORKSPACE`
7. If none found: stateless chat mode or `workspace_required` (tool/index endpoints)

Supported path formats for auto-detection:
- Windows: `C:\projects\repo`
- Linux: `/home/user/project`
- WSL UNC: `\\wsl$\Ubuntu\home\user\project`

The detector lives in: `app/workspace/detector.py`

## Project Workspace Config
Each workspace can contain:
- `.agent-workspace.json`

Example:
```json
{
  "workspace_root": "C:\\projects\\repo",
  "collection": "ws_a93fd12",
  "trusted": true,
  "allowed_commands": ["php", "composer", "npm"]
}
```

Behavior:
- If workspace is detected and config does not exist, the server auto-creates it.
- `collection` is normalized to `ws_<workspace_hash>`.
- If `trusted` is `false`, endpoints return `workspace_not_registered`.
- Allowed commands from config are applied to sandboxed `run_cmd`.

## Workspace Control Commands
The chat endpoint supports control commands parsed before LLM inference:

- `@path <directory>`
  - Validates the path exists
  - Sets workspace root
  - Creates/updates `<workspace>/.agent-workspace.json`
  - Initializes the workspace Qdrant collection
  - Returns confirmation
- `@index`
  - Indexes the active workspace
- `@skip`
  - Enables stateless mode (workspace = null, RAG/tools disabled)
- `@reset`
  - Clears current workspace and returns to stateless mode

If workspace is not trusted, API returns:
```json
{"error":"workspace_not_registered","workspace":"<path>"}
```

If workspace cannot be detected:
```json
{"error":"workspace_required","message":"Workspace not detected. Please provide project root path."}
```

Stateless mode:
- `POST /v1/chat/completions` still works without a detected workspace.
- RAG retrieval, file tools, and command tools are disabled in stateless mode.
- The assistant responds: `Please provide project root path to enable project context.`

## Workspace Authorization Flow
Client can call:
- `POST /workspace/authorize` with `action`:
  - `allow_once`
  - `allow_always`
  - `deny`

## Policies
Per-workspace policy file:
- `~/.local-agent/policies/<workspace_hash>.json`

Fields:
- `allowed_commands`
- `allow_git`
- `write_paths`

If a tool call is blocked by policy, API returns:
```json
{"tool_request":"run_cmd","command":"php artisan test"}
```

## Endpoints
- `GET /health`
- `GET /healthz`
- `GET /debug`
- `POST /workspace/register`
- `POST /workspace/authorize`
- `POST /workspace/index`
- `POST /workspace/tool`
- `GET /v1/models`
- `POST /v1/chat/completions`

## Debugging
Structured error responses are returned with full details and traceback for local debugging.

Example shape:
```json
{
  "error": "workspace_init_failed",
  "message": "Workspace command failed",
  "details": {
    "workspace_root": "/home/user/project",
    "step": "qdrant_collection_create",
    "exception_type": "ConnectionRefusedError",
    "exception_message": "Failed to connect to Qdrant",
    "traceback": "<full python traceback>"
  }
}
```

## OpenAI Model ID
- `gpt-4o-mini` (OpenAI-compatible public model id)

## Local Run
1. `pip install -e .[dev]`
   - or `pip install -r requirements.txt`
2. `./scripts/start-qdrant.ps1`
3. Ensure Ollama is running with `qwen2.5-coder:7b`
4. `python -m app` (default `http://127.0.0.1:3210`)

Or use orchestrated startup:
- `./scripts/start-all.ps1` (default `http://127.0.0.1:3210`)
- `./scripts/stop-all.ps1`

## Startup (Windows)
```powershell
.\scripts\start-all.ps1
```

## Startup (Linux / WSL)
```bash
chmod +x scripts/*.sh
./scripts/start-all.sh
```

## PowerShell Scripts
- `scripts/start-qdrant.ps1`
- `scripts/stop-qdrant.ps1`
- `scripts/run-agent.ps1`
- `scripts/start-all.ps1`
- `scripts/stop-all.ps1`
- `scripts/index-workspace.ps1`
- `scripts/curl-chat.ps1`

## Linux/WSL Scripts
- `scripts/start-all.sh`
- `scripts/stop-all.sh`

## Tests
- `tests/test_chunker.py`
- `tests/test_vector_retrieval.py`
- `tests/test_patch_sandbox.py`
- `tests/test_openai_schema.py`
