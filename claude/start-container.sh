if [ -z "${1:-}" ]; then
    echo "Usage: start-container.sh <project>"
    echo "  project: folder name under ~/Projects to mount at /workspace/<project>"
    exit 1
fi

PROJECT="$1"
DIR="$(dirname "$0")"

# Uses podman explicitly: --userns=keep-id and :Z volume labels are required
# for rootless Podman so Claude Code can run as a non-root user in dangerous mode.
podman run -it --rm \
  --userns=keep-id \
  -v ~/.claude:/home/claude/.claude:Z \
  -v ~/.claude.json:/home/claude/.claude.json:Z \
  -v ~/ClaudeProjects:/workspace:Z \
  -v "$HOME/.steam/steam/steamapps/common/Valheim dedicated server":/workspace/valheim/server:Z \
  -v "$HOME/.steam/steam/steamapps/common/Valheim":/workspace/valheim/client:Z \
  -v "$DIR/docs":/workspace/docs:Z \
  -v ~/Projects/$PROJECT:/workspace/$PROJECT:Z \
  -w /workspace/$PROJECT \
  claude-sandbox \
  claude --dangerously-skip-permissions
