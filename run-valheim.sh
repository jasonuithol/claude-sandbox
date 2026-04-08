podman run -it --rm \
  -v ~/.claude:/root/.claude:Z \
  -v ~/.claude.json:/root/.claude.json:Z \
  -v ~/ClaudeProjects:/workspace:Z \
  -v "$HOME/.steam/steam/steamapps/common/Valheim dedicated server":/workspace/valheim/server:Z \
  -v "$HOME/.steam/steam/steamapps/common/Valheim":/workspace/valheim/client:Z \
  -v ~/Projects/claude-sandbox/VALHEIM.md:/workspace/VALHEIM.md:Z \
  -v ~/Projects/ValheimRainDance:/workspace/ValheimRainDance:Z \
  -w /workspace \
  claude-sandbox
