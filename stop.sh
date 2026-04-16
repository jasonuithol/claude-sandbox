#!/usr/bin/env bash
# stop.sh — shut down all three MCP services
set -euo pipefail

FORCE=false
if [ "${1:-}" = "--kill" ]; then
    FORCE=true
fi

echo "Stopping mcp-build container..."
if [ "$FORCE" = true ]; then
    docker rm -f valheim-mcp-build 2>/dev/null && echo "  killed" || echo "  not running"
else
    docker stop valheim-mcp-build 2>/dev/null && echo "  stopped" || echo "  not running"
fi

echo "Stopping mcp-control (port 5173)..."
if [ "$FORCE" = true ]; then
    fuser -k -KILL 5173/tcp 2>/dev/null && echo "  killed" || echo "  not running"
else
    fuser -k -TERM 5173/tcp 2>/dev/null && echo "  stopped" || echo "  not running"
fi

echo "Stopping mcp-knowledge container..."
if [ "$FORCE" = true ]; then
    docker rm -f mcp-knowledge 2>/dev/null && echo "  killed" || echo "  not running"
else
    docker stop mcp-knowledge 2>/dev/null && echo "  stopped" || echo "  not running"
fi

echo "Done."
