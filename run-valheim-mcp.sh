#!/usr/bin/env bash
set -euo pipefail

if [ -z "${1:-}" ]; then
    echo "Usage: $0 <project>"
    exit 1
fi

PROJECT="$1"

# Ensure the MCP server is up before starting the container
if ! ss -tnlp | grep -q ':5172'; then
    echo "Error: valheim-mcp.sh does not appear to be running on port 5172."
    echo "Start it with: ~/Projects/claude-sandbox/valheim-mcp.sh"
    exit 1
fi

podman run -it --rm \
  --userns=keep-id \
  --add-host=host.docker.internal:host-gateway \
  -v ~/.claude:/home/jason/.claude:Z \
  -v ~/.claude.json:/home/jason/.claude.json:Z \
  -v ~/ClaudeProjects:/workspace:Z \
  -v "$HOME/.steam/steam/steamapps/common/Valheim dedicated server":/workspace/valheim/server:Z \
  -v "$HOME/.steam/steam/steamapps/common/Valheim":/workspace/valheim/client:Z \
  -v ~/Projects/claude-sandbox/MODDING_WISDOM_MESSAGING.md:/workspace/MODDING_WISDOM_MESSAGING.md:Z \
  -v ~/Projects/claude-sandbox/MODDING_WISDOM_RAINDANCE.md:/workspace/MODDING_WISDOM_RAINDANCE.md:Z \
  -v ~/Projects/claude-sandbox/VALHEIM_MCP.md:/workspace/VALHEIM_MCP.md:Z \
  -v ~/Projects/$PROJECT:/workspace/$PROJECT:Z \
  -w /workspace/$PROJECT \
  claude-sandbox
