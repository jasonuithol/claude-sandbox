#!/usr/bin/env bash
# start.sh — spin up all three MCP services, then launch the sandboxed Claude instance
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -z "${1:-}" ]; then
    echo "Usage: start.sh <project>"
    echo "  project: folder name under ~/Projects to mount at /workspace/<project>"
    exit 1
fi

PROJECT="$1"

if [ ! -d "$HOME/Projects/$PROJECT" ]; then
    echo "Error: ~/Projects/$PROJECT does not exist"
    exit 1
fi

echo "Starting mcp-build..."
"$SCRIPT_DIR/mcp-build/start-container.sh"

echo "Starting mcp-control..."
"$SCRIPT_DIR/mcp-control/start-mcp-service.sh" &
CONTROL_PID=$!

echo "Starting mcp-knowledge..."
"$SCRIPT_DIR/mcp-knowledge/start-container.sh"

# Give the host services a moment to bind their ports
sleep 2

echo "Launching Claude sandbox for project: $PROJECT"
"$SCRIPT_DIR/claude/start-container.sh" "$PROJECT"

echo "Claude exited. Stopping MCP services..."
kill "$CONTROL_PID" 2>/dev/null || true
# Stop (don't remove) so the next start.sh revives the same containers and
# preserves any in-container state. Use ./clean.sh for a full teardown.
docker stop valheim-mcp-build mcp-knowledge 2>/dev/null || true
