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

MCP_VALHEIM_DIR="$HOME/Projects/mcp-valheim"
if [ ! -d "$MCP_VALHEIM_DIR" ]; then
    echo "Error: $MCP_VALHEIM_DIR not found."
    echo "  git clone https://github.com/jasonuithol/mcp-valheim $MCP_VALHEIM_DIR"
    exit 1
fi

MCP_STEAM_DIR="$HOME/Projects/mcp-steam"
if [ ! -d "$MCP_STEAM_DIR" ]; then
    echo "Error: $MCP_STEAM_DIR not found."
    echo "  git clone https://github.com/jasonuithol/mcp-steam $MCP_STEAM_DIR"
    exit 1
fi

echo "Starting mcp-valheim build..."
"$MCP_VALHEIM_DIR/build/start-container.sh"

echo "Starting mcp-valheim control..."
"$MCP_VALHEIM_DIR/control/start-mcp-service.sh" &
VALHEIM_CONTROL_PID=$!

echo "Starting mcp-steam..."
"$MCP_STEAM_DIR/start-mcp-service.sh" &
STEAM_PID=$!

echo "Starting mcp-valheim knowledge..."
"$MCP_VALHEIM_DIR/knowledge/start-container.sh"

# Give the host services a moment to bind their ports
sleep 2

echo "Launching Claude sandbox for project: $PROJECT"
"$SCRIPT_DIR/claude/start-container.sh" "$PROJECT"

echo "Claude exited. Stopping MCP services..."
kill "$VALHEIM_CONTROL_PID" "$STEAM_PID" 2>/dev/null || true
# Stop (don't remove) so the next start.sh revives the same containers and
# preserves any in-container state. Use ./clean.sh for a full teardown.
docker stop valheim-mcp-build valheim-mcp-knowledge 2>/dev/null || true
