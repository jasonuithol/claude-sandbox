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

# valheim-control and mcp-steam are host processes bound to ports 5173/5174,
# not containers.
stop_host_port() {
    local label="$1"
    local port="$2"
    echo "Stopping $label (port $port)..."
    if [ "$FORCE" = true ]; then
        fuser -k -KILL "$port/tcp" 2>/dev/null && echo "  killed" || echo "  not running"
    else
        fuser -k -TERM "$port/tcp" 2>/dev/null && echo "  stopped" || echo "  not running"
    fi
}

stop_host_port valheim-control 5173
stop_host_port mcp-steam 5174

stop_container valheim-mcp-knowledge

echo "Done."
