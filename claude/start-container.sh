if [ -z "${1:-}" ]; then
    echo "Usage: start-container.sh <project>"
    echo "  project: folder name under ~/Projects to mount at /workspace/<project>"
    exit 1
fi

PROJECT="$1"

# Uses podman explicitly: --userns=keep-id and :Z volume labels are required
# for rootless Podman so Claude Code can run as a non-root user in dangerous mode.
podman run -it --rm \
  --userns=keep-id \
  -v ~/.claude:/home/claude/.claude:Z \
  -v ~/.claude.json:/home/claude/.claude.json:Z \
  -v ~/ClaudeProjects:/workspace:Z \
  -v "$HOME/.steam/steam/steamapps/common/Valheim dedicated server":/workspace/valheim/server:Z \
  -v "$HOME/.steam/steam/steamapps/common/Valheim":/workspace/valheim/client:Z \
  -v ~/Projects/claude-sandbox/VALHEIM_MCP.md:/workspace/VALHEIM_MCP.md:Z \
  -v ~/Projects/claude-sandbox/MODDING_TOOLCHAIN.md:/workspace/MODDING_TOOLCHAIN.md:Z \
  -v ~/Projects/claude-sandbox/MODDING_PLUGIN_BASICS.md:/workspace/MODDING_PLUGIN_BASICS.md:Z \
  -v ~/Projects/claude-sandbox/MODDING_HARMONY.md:/workspace/MODDING_HARMONY.md:Z \
  -v ~/Projects/claude-sandbox/MODDING_NETWORKING.md:/workspace/MODDING_NETWORKING.md:Z \
  -v ~/Projects/claude-sandbox/MODDING_ZDO.md:/workspace/MODDING_ZDO.md:Z \
  -v ~/Projects/claude-sandbox/MODDING_MESSAGING.md:/workspace/MODDING_MESSAGING.md:Z \
  -v ~/Projects/claude-sandbox/MODDING_WORLD.md:/workspace/MODDING_WORLD.md:Z \
  -v ~/Projects/claude-sandbox/MODDING_PLAYER.md:/workspace/MODDING_PLAYER.md:Z \
  -v ~/Projects/claude-sandbox/MODDING_CONFIG.md:/workspace/MODDING_CONFIG.md:Z \
  -v ~/Projects/claude-sandbox/MODDING_PACKAGING.md:/workspace/MODDING_PACKAGING.md:Z \
  -v ~/Projects/claude-sandbox/MODDING_GOTCHAS.md:/workspace/MODDING_GOTCHAS.md:Z \
  -v ~/Projects/$PROJECT:/workspace/$PROJECT:Z \
  -w /workspace/$PROJECT \
  claude-sandbox \
  claude --dangerously-skip-permissions
