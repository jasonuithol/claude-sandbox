# Valheim Development Environment

This document describes how to control the Valheim server and client from inside
the Claude Code container, and where to find relevant files.

## Architecture

Claude Code runs inside a Podman container. Valheim server and client run on the
host. Communication between the container and host is handled via a command
directory watched by `valheim-watcher.sh` on the host.

The host watcher must be running before issuing any commands:

```bash
~/Projects/claude-sandbox/valheim-watcher.sh
```

## Issuing Commands

To control the server, client, or build system, create a file in
`/workspace/valheim/commands/`. The watcher detects it, executes the corresponding
host command, and deletes the file.

### Server and Client Control

These commands are non-blocking — just create an empty file:

```bash
# Start the dedicated server
touch /workspace/valheim/commands/start-server

# Stop the dedicated server gracefully
touch /workspace/valheim/commands/stop-server

# Kill the dedicated server immediately
touch /workspace/valheim/commands/kill-server

# Start the client (via BepInEx)
touch /workspace/valheim/commands/start-client

# Stop the client
touch /workspace/valheim/commands/stop-client
```

### Build and Deploy

These commands are **blocking** — the watcher will not process any further commands
until they complete. Write the project folder name (no path separators) as the
file content:

```bash
# Build the project
echo "ValheimRainDance" > /workspace/valheim/commands/build

# Deploy to server only using deploy-server.sh
echo "ValheimRainDance" > /workspace/valheim/commands/deploy-server

# Deploy to client only using deploy-client.sh
echo "ValheimRainDance" > /workspace/valheim/commands/deploy-client
```

Build always runs `dotnet build -c Release` in the specified project directory.

Deploy scripts (`deploy-server.sh`, `deploy-client.sh`) are
project-specific and must exist in the project directory.

### Checking Build and Deploy Results

When a build or deploy completes, the watcher writes a result file back to the
commands directory. Poll for these files to determine success or failure:

| Command | Success | Failure |
|---------|---------|---------|
| `build` | `build-done` | `build-failed` |
| `deploy-server` | `deploy-server-done` | `deploy-server-failed` |
| `deploy-client` | `deploy-client-done` | `deploy-client-failed` |

Example — wait for build result:

```bash
# Issue the build command
echo "ValheimRainDance" > /workspace/valheim/commands/build

# Poll for result
while [ ! -f /workspace/valheim/commands/build-done ] && \
      [ ! -f /workspace/valheim/commands/build-failed ]; do
    sleep 2
done

if [ -f /workspace/valheim/commands/build-done ]; then
    echo "Build succeeded"
    rm /workspace/valheim/commands/build-done
else
    echo "Build failed — check /workspace/valheim/logs/build.log"
    rm /workspace/valheim/commands/build-failed
fi
```

## Logs

### Build and Deploy Logs

Build and deploy output is written to log files in `/workspace/valheim/logs/`:

| Path | Contents |
|------|----------|
| `/workspace/valheim/logs/build.log` | Output from last build |
| `/workspace/valheim/logs/deploy-server.log` | Output from last deploy-server |
| `/workspace/valheim/logs/deploy-client.log` | Output from last deploy-client |

Each log is overwritten on each run and includes timestamps at start and end.

### Server and Client Logs

| Path | Contents |
|------|----------|
| `/workspace/valheim/server/` | Dedicated server files and logs |
| `/workspace/valheim/client/` | Client files and logs |
| `/workspace/valheim/logs/server.log` | Server stdout/stderr (most useful for startup errors) |
| `/workspace/valheim/logs/client.log` | Client stdout/stderr (most useful for startup errors) |

BepInEx logs are typically found at:

- Server: `/workspace/valheim/server/BepInEx/LogOutput.log`
- Client: `/workspace/valheim/client/BepInEx/LogOutput.log`

## BepInEx

BepInEx is always installed on both the server and client. It is safe to assume
its directory structure is present and plugins can be deployed to:

- Server: `/workspace/valheim/server/BepInEx/plugins/`
- Client: `/workspace/valheim/client/BepInEx/plugins/`

Config files are at:

- Server: `/workspace/valheim/server/BepInEx/config/`
- Client: `/workspace/valheim/client/BepInEx/config/`

## Notes

- Build and deploy commands block the watcher until complete — do not issue
  multiple build/deploy commands simultaneously.
- Server and client start commands are non-blocking — check logs to confirm
  successful startup.
- The container has write access to BepInEx plugin and config directories, so
  deploying a built plugin is as simple as copying the `.dll` to the plugins folder.
- Result files (`build-done`, `build-failed` etc.) are not automatically cleaned
  up — always remove them after reading to avoid confusion on the next run.

  
## Decompiling Assemblies with ilspy

To decompile a DLL and inspect its source, write the container path of the DLL
as the file content of an `ilspy` command:

```bash
echo "/workspace/valheim/server/valheim_server_Data/Managed/assembly_valheim.dll" > /workspace/valheim/commands/ilspy
```

The watcher will translate the container path to the real host path, run
`ilspycmd` against it, and write the output to `/workspace/valheim/logs/ilspy.log`.

Poll for the result file as with build and deploy:

```bash
while [ ! -f /workspace/valheim/commands/ilspy-done ] && \
      [ ! -f /workspace/valheim/commands/ilspy-failed ]; do
    sleep 2
done

if [ -f /workspace/valheim/commands/ilspy-done ]; then
    echo "Decompilation succeeded — see /workspace/valheim/logs/ilspy.log"
    rm /workspace/valheim/commands/ilspy-done
else
    echo "Decompilation failed — see /workspace/valheim/logs/ilspy.log"
    rm /workspace/valheim/commands/ilspy-failed
fi
```

Any DLL path visible from inside the container can be passed — Valheim managed
assemblies, BepInEx core assemblies, or your own built plugins.

### Notes

- The path map is built when the watcher starts. If the container is restarted,
  restart the watcher too to refresh the map.
- Output can be large for complex assemblies — pipe or grep `ilspy.log` as needed.



## Converting SVG to PNG

To convert an SVG to a 256x256 PNG, write the container path of the SVG as the
file content of a `svg-to-png` command:

```bash
echo "/workspace/ValheimRainDance/ThunderstoreAssets/icon.svg" > /workspace/valheim/commands/svg-to-png
```

The output PNG is written to the same directory as the SVG with a `.png` extension.
So `/workspace/ValheimRainDance/ThunderstoreAssets/icon.svg` becomes
`/workspace/ValheimRainDance/ThunderstoreAssets/icon.png`.

Poll for the result file as with other commands:

```bash
while [ ! -f /workspace/valheim/commands/svg-to-png-done ] && \
      [ ! -f /workspace/valheim/commands/svg-to-png-failed ]; do
    sleep 2
done

if [ -f /workspace/valheim/commands/svg-to-png-done ]; then
    echo "Conversion succeeded"
    rm /workspace/valheim/commands/svg-to-png-done
else
    echo "Conversion failed — see /workspace/valheim/logs/svg-to-png.log"
    rm /workspace/valheim/commands/svg-to-png-failed
fi
```

Output is always 256x256 pixels, suitable for Thunderstore mod icons.

