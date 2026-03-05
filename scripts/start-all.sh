#!/usr/bin/env bash
set -e

echo "Starting Local Cursor Agent"

if ! command -v python3 >/dev/null; then
  echo "python3 not installed"
  exit 1
fi

if ! command -v docker >/dev/null; then
  echo "docker not installed or not on PATH"
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "docker daemon is not running"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
RUNTIME_DIR="$PROJECT_DIR/.runtime"
mkdir -p "$RUNTIME_DIR"

cd "$PROJECT_DIR"

AGENT_HOST="${AGENT_HOST:-127.0.0.1}"
AGENT_PORT="${AGENT_PORT:-3210}"
QDRANT_CONTAINER="${QDRANT_CONTAINER:-local-cursor-agent-qdrant}"
if [[ -z "${OLLAMA_BASE_URL:-}" ]]; then
  if grep -qi microsoft /proc/version 2>/dev/null; then
    WSL_GATEWAY="$(ip route | awk '/default/ {print $3; exit}')"
    if [[ -n "$WSL_GATEWAY" ]]; then
      OLLAMA_BASE_URL="http://${WSL_GATEWAY}:11434"
      export OLLAMA_BASE_URL
      echo "Detected WSL. Using OLLAMA_BASE_URL=${OLLAMA_BASE_URL}"
    fi
  fi
fi
OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-http://127.0.0.1:11434}"
export OLLAMA_BASE_URL
export AGENT_HOST
export AGENT_PORT

echo "Starting Qdrant..."
if docker ps --format "{{.Names}}" | grep -Fxq "$QDRANT_CONTAINER"; then
  echo "Qdrant already running: $QDRANT_CONTAINER"
else
  if docker ps -a --format "{{.Names}}" | grep -Fxq "$QDRANT_CONTAINER"; then
    docker start "$QDRANT_CONTAINER" >/dev/null
    echo "Qdrant container started: $QDRANT_CONTAINER"
  else
    docker run -d --name "$QDRANT_CONTAINER" -p 6333:6333 -p 6334:6334 qdrant/qdrant:latest >/dev/null
    echo "Qdrant started in new container: $QDRANT_CONTAINER"
  fi
fi

echo "Waiting for Qdrant to be ready..."
QDRANT_READY=0
for _ in $(seq 1 25); do
  if curl -fsS "http://127.0.0.1:6333/collections" >/dev/null 2>&1; then
    QDRANT_READY=1
    break
  fi
  sleep 1
done
if [[ "$QDRANT_READY" -ne 1 ]]; then
  echo "Qdrant did not become ready in time"
  exit 1
fi
echo "Qdrant is ready."

echo "Checking Ollama..."
if ! curl -fsS "${OLLAMA_BASE_URL}/api/tags" >/dev/null 2>&1; then
  echo "Ollama is not reachable at ${OLLAMA_BASE_URL}"
  echo "Set OLLAMA_BASE_URL explicitly and retry."
  exit 1
fi
echo "Ollama reachable: ${OLLAMA_BASE_URL}"

python3 -m app >"$RUNTIME_DIR/agent.out.log" 2>"$RUNTIME_DIR/agent.err.log" &
echo $! >"$RUNTIME_DIR/agent.pid"

sleep 2

if ! curl -fsS "http://${AGENT_HOST}:${AGENT_PORT}/healthz" >/dev/null 2>&1; then
  echo "Agent health check failed: http://${AGENT_HOST}:${AGENT_PORT}/healthz"
  exit 1
fi
echo
echo "Agent started"
echo "API: http://${AGENT_HOST}:${AGENT_PORT}/v1"
