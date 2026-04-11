#!/usr/bin/env bash
# register-services.sh — register MCP services with Claude Code inside the container
set -euo pipefail

claude mcp add valheim-build --transport http http://localhost:5172/mcp
claude mcp add valheim-control --transport http http://localhost:5173/mcp

echo "Done. Verify with: /mcp"
