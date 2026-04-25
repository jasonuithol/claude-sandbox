#!/usr/bin/env bash
# stop.sh — shut down all three MCP services
#
# Default: SIGTERM with grace period (docker stop).
# --kill:  SIGKILL immediately (docker kill). Container is left in place
#          either way so the next start.sh can revive it. For full removal,
#          use ./clean.sh.
set -euo pipefail

FORCE=false
if [ "${1:-}" = "--kill" ]; then
    FORCE=true
fi

stop_container() {
    local name="$1"
    echo "Stopping $name container..."
    if [ "$FORCE" = true ]; then
        docker kill "$name" 2>/dev/null && echo "  killed" || echo "  not running"
    else
        docker stop "$name" 2>/dev/null && echo "  stopped" || echo "  not running"
    fi
}

stop_container valheim-mcp-build

# mcp-control is a host process bound to port 5173, not a container.
echo "Stopping mcp-control (port 5173)..."
if [ "$FORCE" = true ]; then
    fuser -k -KILL 5173/tcp 2>/dev/null && echo "  killed" || echo "  not running"
else
    fuser -k -TERM 5173/tcp 2>/dev/null && echo "  stopped" || echo "  not running"
fi

stop_container mcp-knowledge

echo "Done."
