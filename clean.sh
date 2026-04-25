#!/usr/bin/env bash
# clean.sh — remove the MCP service containers entirely.
#
# Unlike stop.sh (which leaves stopped containers in place so the next
# start.sh can revive them), this force-removes them. Use after rebuilding
# an image, or when a container's state is wedged and revive semantics are
# hurting rather than helping.
#
# Host-mounted state (e.g. mcp-knowledge/knowledge/ ChromaDB data) is NOT
# touched — only the containers themselves. mcp-control is a host process,
# not a container; use ./stop.sh to stop it.
set -euo pipefail

remove_one() {
    local name="$1"
    echo "Removing $name container..."
    docker rm -f "$name" 2>/dev/null && echo "  removed" || echo "  not present"
}

remove_one valheim-mcp-build
remove_one mcp-knowledge

echo "Done."
