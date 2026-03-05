#!/usr/bin/env bash
set -e

echo "Starting Local Cursor Agent"

if ! command -v python3 >/dev/null; then
  echo "python3 not installed"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
RUNTIME_DIR="$PROJECT_DIR/.runtime"
mkdir -p "$RUNTIME_DIR"

cd "$PROJECT_DIR"

AGENT_HOST="${AGENT_HOST:-127.0.0.1}"
AGENT_PORT="${AGENT_PORT:-3210}"
export AGENT_HOST
export AGENT_PORT

python3 -m app >"$RUNTIME_DIR/agent.out.log" 2>"$RUNTIME_DIR/agent.err.log" &
echo $! >"$RUNTIME_DIR/agent.pid"

sleep 2

curl -s "http://${AGENT_HOST}:${AGENT_PORT}/healthz" || true
echo
echo "Agent started"
echo "API: http://${AGENT_HOST}:${AGENT_PORT}/v1"
