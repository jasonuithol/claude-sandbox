# Valheim Development Environment

This document describes how to control the Valheim server and client from inside
the Claude Code container using the MCP tool server.

## Architecture

Claude Code runs inside a Podman container. Valheim server and client run on the
host. The host runs `valheim-mcp.sh`, which exposes all dev tools as MCP tools
that Claude Code can call directly — no shell scripting, no polling, no sentinel files.

```
Podman Container              Host
─────────────────             ──────────────────────────────
Claude Code  ──── HTTP ────►  valheim-mcp.sh (port 5172)
                                    │
                                    ├── start/stop Valheim server
                                    ├── start/stop Valheim client
                                    ├── dotnet build
                                    ├── deploy-server.sh / deploy-client.sh
                                    ├── package.sh
                                    ├── ilspycmd
                                    └── rsvg-convert
```

## Setup

### 1. Start the MCP server on the host

```bash
claude-sandbox/valheim-mcp.sh
```

On first run this creates a `.venv` inside `claude-sandbox/` and installs
dependencies automatically. Leave it running in a terminal.

### 2. Register with Claude Code (once, inside the container)

```bash
claude mcp add valheim --transport http http://host.docker.internal:5172/mcp
```

Verify the connection with `/mcp` inside any Claude Code session.

### 3. Restart the MCP server if the container is restarted

The path map (used for `decompile_dll` and `convert_svg`) is built when the
server starts. If the container is restarted, either restart the MCP server
or call the `refresh_path_map` tool to rebuild it without restarting.

---

## MCP Tools

All tools are available directly to Claude Code. Blocking tools return the full
log output so failures can be diagnosed without reading a file.

### Server and Client Control

These tools are **non-blocking** — they return immediately after issuing the
command. Check the relevant log to confirm successful startup.

| Tool | Description |
|------|-------------|
| `start_server()` | Start the dedicated server via `byawn_start.sh` |
| `stop_server()` | Stop the dedicated server gracefully via `byawn_stop.sh` |
| `kill_server()` | Kill the dedicated server immediately via `byawn_kill.sh` |
| `start_client()` | Start the client via BepInEx (`run_bepinex.sh`) |
| `stop_client()` | Stop the client (`pkill valheim.x86_64`) |

### Build and Deploy

These tools are **blocking** — they run to completion and return the full log.

| Tool | Argument | Description |
|------|----------|-------------|
| `build(project)` | Project folder name | `dotnet build -c Release` |
| `deploy_server(project)` | Project folder name | Run `deploy-server.sh` |
| `deploy_client(project)` | Project folder name | Run `deploy-client.sh` |
| `package(project)` | Project folder name | Run `package.sh`, produces Thunderstore zip |

`project` is a folder name under `~/Projects` with no path separators,
e.g. `"ValheimRainDance"`.

Always build and verify success before deploying or packaging.

### Decompiling Assemblies

```
decompile_dll(container_path)
```

Decompiles a DLL with `ilspycmd` and returns the source. Pass the path as
seen from inside the container:

```
/workspace/valheim/server/valheim_server_Data/Managed/assembly_valheim.dll
```

Output is also written to `logs/ilspy.log`.

### Converting SVG to PNG

```
convert_svg(container_path)
```

Converts an SVG to a 256×256 PNG using `rsvg-convert`. Pass the path as
seen from inside the container:

```
/workspace/ValheimRainDance/ThunderstoreAssets/icon.svg
```

Output PNG is written next to the source SVG with a `.png` extension, suitable
for Thunderstore mod icons.

### Utility

```
refresh_path_map()
```

Rebuilds the container→host path map by re-inspecting the Podman container.
Call this after restarting the container without restarting the MCP server.

---

## Logs

### Build and Deploy Logs

All tool logs are written to `~/ClaudeProjects/valheim/logs/` on the host,
and are also returned directly in the tool response.

| File | Written by |
|------|-----------|
| `logs/build.log` | `build` |
| `logs/deploy-server.log` | `deploy_server` |
| `logs/deploy-client.log` | `deploy_client` |
| `logs/package.log` | `package` |
| `logs/ilspy.log` | `decompile_dll` |
| `logs/svg-to-png.log` | `convert_svg` |

Each log is overwritten on each run and includes timestamps at start and end.

### Server and Client Logs

| Path | Contents |
|------|----------|
| `logs/server.log` | Server stdout/stderr (most useful for startup errors) |
| `logs/client.log` | Client stdout/stderr (most useful for startup errors) |

BepInEx logs are at:

- Server: `/workspace/valheim/server/BepInEx/LogOutput.log`
- Client: `/workspace/valheim/client/BepInEx/LogOutput.log`

---

## BepInEx

BepInEx is always installed on both server and client. Plugin and config
directories are writable from inside the container:

| Location | Path |
|----------|------|
| Server plugins | `/workspace/valheim/server/BepInEx/plugins/` |
| Client plugins | `/workspace/valheim/client/BepInEx/plugins/` |
| Server config | `/workspace/valheim/server/BepInEx/config/` |
| Client config | `/workspace/valheim/client/BepInEx/config/` |

Deploying a built plugin is as simple as copying the `.dll` to the plugins
folder — or use `deploy_server` / `deploy_client` to run the project's own
deploy scripts.

---

## Testing the MCP Server

To test the server from the host command line without Claude Code, use
`mcp-cli` (already installed in the project venv):

```bash
# List all available tools
claude-sandbox/.venv/bin/mcp tools list \
  --transport streamable-http \
  --server-url http://localhost:5172/mcp

# Call a tool
claude-sandbox/.venv/bin/mcp tools call refresh_path_map \
  --transport streamable-http \
  --server-url http://localhost:5172/mcp
```

---

## Notes

- Build and deploy tools block until complete — do not call multiple
  build/deploy tools simultaneously.
- Server and client start tools are non-blocking — check logs to confirm
  successful startup.
- `decompile_dll` output can be large for complex assemblies — Claude can
  grep or filter the returned text as needed.
- The package zip is written to `release/tarbaby-<modname>-<version>.zip`
  inside the project directory.
