#!/usr/bin/env bash
# start-mcp-service.sh — run the valheim MCP client server directly on the host
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$SCRIPT_DIR/../.venv"

if [ ! -f "$VENV/bin/activate" ]; then
    echo "Error: virtualenv not found at $VENV"
    echo "Set up with: python3 -m venv $VENV && $VENV/bin/pip install fastmcp psutil"
    exit 1
fi

source "$VENV/bin/activate"
exec python "$SCRIPT_DIR/mcp-service.py"
