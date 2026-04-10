#!/usr/bin/env bash
# valheim-mcp.sh — launch the Valheim MCP server on the host
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$SCRIPT_DIR/.venv"

# Create venv on first run
if [ ! -d "$VENV" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV"
fi

# Install/upgrade fastmcp if missing
if ! "$VENV/bin/python" -c "import fastmcp" 2>/dev/null; then
    echo "Installing fastmcp..."
    "$VENV/bin/pip" install --quiet fastmcp
fi

exec "$VENV/bin/python" "$SCRIPT_DIR/valheim-mcp.py"
