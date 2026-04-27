# claude-sandbox — archived

This repo has been superseded by
[`claude-sandbox-core`](https://github.com/jasonuithol/claude-sandbox-core),
which consolidates all per-domain Claude sandboxes (pygame, valheim, dosre)
behind a single shared image and per-domain conf files.

## Where everything went

| Old location                              | New location |
|-------------------------------------------|--------------|
| `start.sh` / `stop.sh` / orchestrators    | `claude-sandbox-core/bin/` |
| `claude/Dockerfile` + `entrypoint.sh`     | `claude-sandbox-core/core/` |
| `claude/docs/` (Valheim modding)          | `mcp-valheim/docs/` |
| MCP services (valheim-build, valheim-knowledge, valheim-control) | `mcp-valheim/` |
| Steam process control                     | `mcp-steam/` |

## Migrating

```bash
git clone https://github.com/jasonuithol/claude-sandbox-core
git clone https://github.com/jasonuithol/mcp-valheim
git clone https://github.com/jasonuithol/mcp-steam
cd claude-sandbox-core
./bin/start.sh valheim
```

This repository will be archived shortly. No further changes will be
accepted here.
