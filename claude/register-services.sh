#!/usr/bin/env bash
# register-services.sh — register MCP services with Claude Code inside the container
set -euo pipefail

for service in valheim-build valheim-control valheim-knowledge; do
    claude mcp remove "$service" 2>/dev/null || true
done

claude mcp add valheim-build --transport http http://localhost:5172/mcp
claude mcp add valheim-control --transport http http://localhost:5173/mcp
claude mcp add valheim-knowledge --transport http http://localhost:5184/mcp

echo "Done. Verify with: /mcp"
