podman run -it --rm \
  -v ~/.claude:/root/.claude:Z \
  -v ~/.claude.json:/root/.claude.json:Z \
  -v ~/ClaudeProjects:/workspace:Z \
  -w /workspace \
  claude-sandbox
