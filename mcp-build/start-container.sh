#!/usr/bin/env bash
# start-container.sh — run the valheim-build MCP container
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Load .env if present (for THUNDERSTORE_TOKEN etc.)
if [ -f "$SCRIPT_DIR/.env" ]; then
    set -a
    source "$SCRIPT_DIR/.env"
    set +a
fi

docker run --rm -d \
    --name valheim-mcp-build \
    --network host \
    -v "$HOME/.steam/steam/steamapps/common/Valheim dedicated server:/opt/valheim-server" \
    -v "$HOME/.steam/steam/steamapps/common/Valheim:/opt/valheim-client" \
    -v "$HOME/Projects:/opt/projects" \
    -v "$HOME/ClaudeProjects:/opt/claudeprojects" \
    -e VALHEIM_SERVER_DIR=/opt/valheim-server \
    -e VALHEIM_CLIENT_DIR=/opt/valheim-client \
    -e VALHEIM_PROJECT_DIR=/opt/projects \
    -e VALHEIM_LOGS_DIR=/opt/claudeprojects/valheim/logs \
    ${THUNDERSTORE_TOKEN:+-e THUNDERSTORE_TOKEN="$THUNDERSTORE_TOKEN"} \
    valheim-mcp-build
