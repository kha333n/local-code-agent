#!/usr/bin/env bash
set -e

echo "Stopping agent..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PID_FILE="$PROJECT_DIR/.runtime/agent.pid"
QDRANT_CONTAINER="${QDRANT_CONTAINER:-local-cursor-agent-qdrant}"

if [[ -f "$PID_FILE" ]]; then
  PID="$(cat "$PID_FILE")"
  kill "$PID" 2>/dev/null || true
  rm -f "$PID_FILE"
fi

pkill -f "python3 -m app" || true
echo "Stopping Qdrant..."

if ! command -v docker >/dev/null; then
  echo "docker not installed or not on PATH"
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "docker daemon is not running"
  exit 1
fi

if docker ps --format "{{.Names}}" | grep -Fxq "$QDRANT_CONTAINER"; then
  docker stop "$QDRANT_CONTAINER" >/dev/null
  echo "Qdrant stopped: $QDRANT_CONTAINER"
else
  echo "Qdrant not running: $QDRANT_CONTAINER"
fi

echo "Stopped"
