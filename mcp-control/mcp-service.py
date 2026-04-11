#!/usr/bin/env python3
"""
mcp-service.py — mcp-control

Runs directly on the host (NOT in a container). Exposes tools that control
host processes and containers: Steam status, Valheim client and server lifecycle.

Register with Claude Code (run this inside the claude-sandbox container):
    claude mcp add valheim-control --transport http http://localhost:5173/mcp

Or on the host directly:
    claude mcp add valheim-control --transport http http://localhost:5173/mcp
"""

import os
import subprocess
from pathlib import Path

import psutil
from fastmcp import FastMCP

# ── Paths ─────────────────────────────────────────────────────────────────────

HOME       = Path.home()
SERVER_DIR = Path(os.environ.get("VALHEIM_SERVER_DIR", str(HOME / ".steam/steam/steamapps/common/Valheim dedicated server")))
CLIENT_DIR = Path(os.environ.get("VALHEIM_CLIENT_DIR", str(HOME / ".steam/steam/steamapps/common/Valheim")))
LOGS_DIR   = Path(os.environ.get("VALHEIM_LOGS_DIR",   str(HOME / "ClaudeProjects/valheim/logs")))

VALHEIM_SERVER_CONTAINER = "valheim_server"
VALHEIM_SERVER_IMAGE     = "valheim_server"

LOGS_DIR.mkdir(parents=True, exist_ok=True)

# ── MCP server ────────────────────────────────────────────────────────────────

mcp = FastMCP(
    name="valheim-control",
    instructions=(
        "Tools for controlling the Valheim server container and client process on the host. "
        "Runs directly on the host — use these for anything that requires visibility into "
        "host processes or container management. "
        "Build tools are in the separate valheim-build MCP (mcp-build, port 5172)."
    ),
)


# ── Steam ─────────────────────────────────────────────────────────────────────

@mcp.tool()
def steam_status() -> str:
    """Check whether Steam is currently running on the host."""
    procs = [p for p in psutil.process_iter(["name"])
             if p.info["name"] in ("steam", "steam.exe")]
    if procs:
        pids = ", ".join(str(p.pid) for p in procs)
        return f"Steam is running (PID {pids})."
    return "Steam is not running."


@mcp.tool()
def start_steam() -> str:
    """Start Steam on the host. Non-blocking — use steam_status() to confirm startup."""
    subprocess.Popen(["steam"], start_new_session=True)
    return "Steam launch initiated."


# ── Server lifecycle ──────────────────────────────────────────────────────────

@mcp.tool()
def start_server(script: str = "start_server.sh") -> str:
    """
    Start the Valheim dedicated server in a Docker container.
    Builds the image first if it doesn't exist.

    Args:
        script: Script to run inside the container (default: 'start_server.sh').
                Must exist in the Valheim dedicated server directory.
    """
    inspect = subprocess.run(
        ["docker", "inspect", VALHEIM_SERVER_IMAGE],
        capture_output=True,
    )
    if inspect.returncode != 0:
        build = subprocess.run(
            ["docker", "build", "docker", "-t", VALHEIM_SERVER_IMAGE],
            cwd=str(SERVER_DIR),
            capture_output=True, text=True,
        )
        if build.returncode != 0:
            return f"IMAGE BUILD FAILED ✗\n\n{build.stderr}"

    log_path = LOGS_DIR / "server.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    with open(log_path, "w") as log:
        subprocess.Popen(
            ["docker", "run", "--rm",
             "--name", VALHEIM_SERVER_CONTAINER,
             "-v", "valheim_server_data:/root/.config/unity3d/IronGate/Valheim",
             "-v", f"{SERVER_DIR}:/irongate",
             VALHEIM_SERVER_IMAGE, script],
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    return f"Server container starting (script: {script}). Monitor logs/server.log for output."


@mcp.tool()
def stop_server() -> str:
    """Stop the Valheim server container gracefully (SIGTERM)."""
    result = subprocess.run(
        ["docker", "stop", VALHEIM_SERVER_CONTAINER],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return f"STOP FAILED ✗\n\n{result.stderr}"
    return "Server container stopped."


@mcp.tool()
def kill_server() -> str:
    """Kill the Valheim server container immediately (SIGKILL)."""
    result = subprocess.run(
        ["docker", "kill", VALHEIM_SERVER_CONTAINER],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return f"KILL FAILED ✗\n\n{result.stderr}"
    return "Server container killed."


# ── Client lifecycle ──────────────────────────────────────────────────────────

@mcp.tool()
def start_client() -> str:
    """Start the Valheim client via BepInEx. Non-blocking — check logs/client.log for startup progress."""
    log_path = LOGS_DIR / "client.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    with open(log_path, "w") as log:
        subprocess.Popen(
            ["./run_bepinex.sh", "valheim.x86_64", "-console"],
            cwd=str(CLIENT_DIR),
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    return "Client start initiated. Monitor logs/client.log for startup output."


@mcp.tool()
def stop_client() -> str:
    """Stop the Valheim client."""
    targets = [p for p in psutil.process_iter(["cmdline"])
               if "valheim.x86_64" in " ".join(p.info.get("cmdline") or [])]
    if not targets:
        return "No valheim.x86_64 process found."
    for p in targets:
        p.kill()
    psutil.wait_procs(targets, timeout=5)
    return "Client stopped."


# ── Entrypoint ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Starting valheim-control MCP on http://0.0.0.0:5173")
    print()
    print("Register with Claude Code:")
    print("  claude mcp add valheim-control --transport http http://localhost:5173/mcp")
    print()
    mcp.run(transport="streamable-http", host="0.0.0.0", port=5173)
