#!/usr/bin/env bash
# entrypoint.sh — register MCP services then launch Claude Code
set -euo pipefail

# Register MCP services (host network, so localhost ports are reachable)
for service in valheim-build valheim-control valheim-knowledge; do
    claude mcp remove "$service" 2>/dev/null || true
done

claude mcp add valheim-build --transport http http://localhost:5172/mcp
claude mcp add valheim-control --transport http http://localhost:5173/mcp
claude mcp add valheim-knowledge --transport http http://localhost:5174/mcp

# Hand off to Claude Code
exec claude --dangerously-skip-permissions "$@"
