#!/usr/bin/env python3
"""
valheim-mcp.py — MCP server replacing valheim-watcher.sh

Runs on the host. Exposes Valheim dev tools to Claude Code running inside
the Podman container.

Register with Claude Code (run this inside the container):
    claude mcp add valheim --transport http http://host.docker.internal:5172/mcp

Or on the host directly:
    claude mcp add valheim --transport http http://localhost:5172/mcp
"""

import asyncio
import json
import subprocess
from datetime import datetime
from pathlib import Path

from fastmcp import FastMCP

# ── Paths ─────────────────────────────────────────────────────────────────────

HOME        = Path.home()
SERVER_DIR  = HOME / ".steam/steam/steamapps/common/Valheim dedicated server"
CLIENT_DIR  = HOME / ".steam/steam/steamapps/common/Valheim"
PROJECT_DIR = HOME / "Projects"
LOGS_DIR    = HOME / "ClaudeProjects/valheim/logs"

LOGS_DIR.mkdir(parents=True, exist_ok=True)

# ── Container → host path map ─────────────────────────────────────────────────

_path_map: dict[str, str] = {}


def _build_path_map() -> str:
    """
    Inspect the running claude-sandbox Podman container and build a map of
    container mount destinations → host source paths.
    Returns a human-readable summary string.
    """
    global _path_map
    _path_map = {}

    result = subprocess.run(
        ["podman", "ps", "--filter", "ancestor=claude-sandbox", "--format", "{{.ID}}"],
        capture_output=True, text=True,
    )
    container_id = result.stdout.strip().split("\n")[0].strip()

    if not container_id:
        msg = "Warning: no running claude-sandbox container found — path mapping unavailable."
        print(msg)
        return msg

    result = subprocess.run(
        ["podman", "inspect", container_id],
        capture_output=True, text=True,
    )
    data = json.loads(result.stdout)
    mounts = data[0]["Mounts"]

    for mount in mounts:
        _path_map[mount["Destination"]] = mount["Source"]

    lines = [f"  {dst} -> {src}" for dst, src in _path_map.items()]
    summary = (
        f"Path map built from container {container_id} "
        f"({len(_path_map)} mounts):\n" + "\n".join(lines)
    )
    print(summary)
    return summary


def _container_to_host(container_path: str) -> str:
    """
    Translate a container-side path to its host equivalent using the mount map.
    Raises ValueError if no mapping is found.
    """
    best_dst = ""
    best_src = ""

    for dst, src in _path_map.items():
        if container_path.startswith(dst) and len(dst) > len(best_dst):
            best_dst = dst
            best_src = src

    if not best_dst:
        raise ValueError(
            f"No host mapping found for container path: {container_path}\n"
            "If the container was restarted, call refresh_path_map()."
        )

    return best_src + container_path[len(best_dst):]


# ── Subprocess helpers ────────────────────────────────────────────────────────

def _run(cmd: list[str], cwd: str | None, log_path: Path) -> tuple[bool, str]:
    """
    Run a command synchronously, tee stdout+stderr to a log file.
    Returns (success, full_log_content).
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)

    with open(log_path, "w") as log:
        log.write(f"--- Started: {datetime.now()} ---\n")
        log.flush()

        proc = subprocess.run(
            cmd,
            cwd=cwd,
            stdout=log,
            stderr=subprocess.STDOUT,
        )

        status = "succeeded" if proc.returncode == 0 else "failed"
        log.write(f"--- {status.capitalize()}: {datetime.now()} ---\n")

    return proc.returncode == 0, log_path.read_text()


async def _run_async(cmd: list[str], cwd: str | None, log_path: Path) -> tuple[bool, str]:
    """Async wrapper around _run so long builds don't block the MCP event loop."""
    return await asyncio.to_thread(_run, cmd, cwd, log_path)


def _fire_and_forget(cmd: list[str], cwd: str, log_path: Path) -> None:
    """Launch a process detached from this process — for start-server / start-client."""
    with open(log_path, "w") as log:
        subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,   # detach from our session
        )


# ── MCP server ────────────────────────────────────────────────────────────────

mcp = FastMCP(
    name="valheim",
    instructions=(
        "Tools for controlling the Valheim dedicated server, client, and mod "
        "build pipeline from inside the Claude Code container. "
        "All blocking tools (build, deploy, package, decompile, convert) return "
        "the full log output so you can diagnose failures without reading a file."
    ),
)

@mcp.tool()
def steam_status() -> str:
    """Check whether Steam is currently running on the host."""
    result = subprocess.run(["pgrep", "-x", "steam"], capture_output=True)
    if result.returncode == 0:
        pids = result.stdout.decode().strip().replace("\n", ", ")
        return f"Steam is running (PID {pids})."
    return "Steam is not running."




@mcp.tool()
def start_server() -> str:
    """Start the Valheim dedicated server. Non-blocking — check logs/server.log for startup progress."""
    _fire_and_forget(
        ["setsid", "bash", "byawn_start.sh"],
        cwd=str(SERVER_DIR),
        log_path=LOGS_DIR / "server.log",
    )
    return "Server start initiated. Monitor logs/server.log for startup output."


@mcp.tool()
def stop_server() -> str:
    """Stop the Valheim dedicated server gracefully."""
    subprocess.run(["bash", "byawn_stop.sh"], cwd=str(SERVER_DIR))
    return "Stop-server command issued."


@mcp.tool()
def kill_server() -> str:
    """Kill the Valheim dedicated server immediately (no graceful shutdown)."""
    subprocess.run(["bash", "byawn_kill.sh"], cwd=str(SERVER_DIR))
    return "Kill-server command issued."


@mcp.tool()
def start_client() -> str:
    """Start the Valheim client via BepInEx. Non-blocking — check logs/client.log for startup progress."""
    _fire_and_forget(
        ["setsid", "bash", "run_bepinex.sh", "valheim.x86_64", "-console"],
        cwd=str(CLIENT_DIR),
        log_path=LOGS_DIR / "client.log",
    )
    return "Client start initiated. Monitor logs/client.log for startup output."


@mcp.tool()
def stop_client() -> str:
    """Stop the Valheim client."""
    subprocess.run(["pkill", "-f", "valheim.x86_64"])
    return "Stop-client command issued."


# ── Build, deploy, package (blocking — return full log) ───────────────────────

@mcp.tool()
async def build(project: str) -> str:
    """
    Build a mod project with 'dotnet build -c Release'.

    Args:
        project: Project folder name under ~/Projects (no path separators, e.g. 'ValheimRainDance').

    Returns the full build log. Always check the result before running deploy or package.
    """
    cwd = str(PROJECT_DIR / project)
    success, log = await _run_async(
        ["dotnet", "build", "-c", "Release"],
        cwd=cwd,
        log_path=LOGS_DIR / "build.log",
    )
    header = "BUILD SUCCEEDED ✓" if success else "BUILD FAILED ✗"
    return f"{header}\n\n{log}"


@mcp.tool()
async def deploy_server(project: str) -> str:
    """
    Deploy a mod to the Valheim dedicated server.
    Copies built DLLs to BepInEx/plugins/ and .cfg files to BepInEx/config/.

    Args:
        project: Project folder name under ~/Projects (no path separators).
    """
    return await asyncio.to_thread(_deploy, project, SERVER_DIR, LOGS_DIR / "deploy-server.log")


@mcp.tool()
async def deploy_client(project: str) -> str:
    """
    Deploy a mod to the Valheim client.
    Copies built DLLs to BepInEx/plugins/ and .cfg files to BepInEx/config/.

    Args:
        project: Project folder name under ~/Projects (no path separators).
    """
    return await asyncio.to_thread(_deploy, project, CLIENT_DIR, LOGS_DIR / "deploy-client.log")


def _deploy(project: str, target: Path, log_path: Path) -> str:
    import shutil, glob
    lines = [f"--- Started: {datetime.now()} ---"]
    try:
        project_dir = PROJECT_DIR / project
        dll_src  = project_dir / "bin/Release/netstandard2.1"
        cfg_srcs = list(project_dir.glob("*.cfg"))

        plugins_dst = target / "BepInEx/plugins"
        config_dst  = target / "BepInEx/config"

        dlls = list(dll_src.glob("*.dll"))
        if not dlls:
            raise FileNotFoundError(f"No DLLs found in {dll_src}")

        for dll in dlls:
            shutil.copy2(dll, plugins_dst / dll.name)
            lines.append(f"Copied {dll.name} -> {plugins_dst}")

        for cfg in cfg_srcs:
            shutil.copy2(cfg, config_dst / cfg.name)
            lines.append(f"Copied {cfg.name} -> {config_dst}")

        lines.append(f"--- Succeeded: {datetime.now()} ---")
        result = "\n".join(lines)
        log_path.write_text(result)
        return f"DEPLOY SUCCEEDED ✓\n\n{result}"

    except Exception as e:
        lines.append(f"ERROR: {e}")
        lines.append(f"--- Failed: {datetime.now()} ---")
        result = "\n".join(lines)
        log_path.write_text(result)
        return f"DEPLOY FAILED ✗\n\n{result}"


@mcp.tool()
async def package(project: str) -> str:
    """
    Package a mod for Thunderstore.
    Reads version from ThunderstoreAssets/manifest.json and produces
    release/tarbaby-<modname>-<version>.zip in the project directory.

    Always build successfully before packaging.

    Args:
        project: Project folder name under ~/Projects (no path separators).
    """
    return await asyncio.to_thread(_package, project, LOGS_DIR / "package.log")


def _package(project: str, log_path: Path) -> str:
    import shutil, zipfile
    lines = [f"--- Started: {datetime.now()} ---"]
    try:
        project_dir = PROJECT_DIR / project
        assets_dir  = project_dir / "ThunderstoreAssets"

        # Read version from manifest
        manifest_path = assets_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        version  = manifest["version_number"]
        modname  = project_dir.name
        zip_name = f"tarbaby-{modname}-{version}.zip"

        # Clean and prepare staging
        staging = project_dir / "staging"
        release = project_dir / "release"
        shutil.rmtree(staging, ignore_errors=True)
        shutil.rmtree(release, ignore_errors=True)
        (staging / "plugins").mkdir(parents=True)
        (staging / "config").mkdir(parents=True)
        release.mkdir()

        # Copy Thunderstore assets
        for name in ("icon.png", "README.md", "manifest.json"):
            shutil.copy2(assets_dir / name, staging / name)
            lines.append(f"Staged {name}")

        # Copy DLLs
        dll_src = project_dir / "bin/Release/netstandard2.1"
        for dll in dll_src.glob("*.dll"):
            shutil.copy2(dll, staging / "plugins" / dll.name)
            lines.append(f"Staged plugins/{dll.name}")

        # Copy configs
        for cfg in project_dir.glob("*.cfg"):
            shutil.copy2(cfg, staging / "config" / cfg.name)
            lines.append(f"Staged config/{cfg.name}")

        # Zip staging into release
        zip_path = release / zip_name
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in staging.rglob("*"):
                if f.is_file():
                    zf.write(f, f.relative_to(staging))

        lines.append(f"Created {zip_path}")
        lines.append(f"--- Succeeded: {datetime.now()} ---")
        result = "\n".join(lines)
        log_path.write_text(result)
        return f"PACKAGE SUCCEEDED ✓\n\n{result}"

    except Exception as e:
        lines.append(f"ERROR: {e}")
        lines.append(f"--- Failed: {datetime.now()} ---")
        result = "\n".join(lines)
        log_path.write_text(result)
        return f"PACKAGE FAILED ✗\n\n{result}"


# ── Path-translated tools (blocking) ─────────────────────────────────────────

@mcp.tool()
async def decompile_dll(container_path: str) -> str:
    """
    Decompile a DLL with ilspycmd and return the source output.
    Output is also written to logs/ilspy.log.

    Args:
        container_path: Path to the DLL as seen from inside the container,
                        e.g. '/workspace/valheim/server/valheim_server_Data/Managed/assembly_valheim.dll'
    """
    try:
        host_path = _container_to_host(container_path)
    except ValueError as e:
        return f"PATH TRANSLATION FAILED\n\n{e}"

    success, log = await _run_async(
        ["ilspycmd", host_path],
        cwd=None,
        log_path=LOGS_DIR / "ilspy.log",
    )
    header = "DECOMPILE SUCCEEDED ✓" if success else "DECOMPILE FAILED ✗"
    return f"{header}\n\n{log}"


@mcp.tool()
async def convert_svg(container_path: str) -> str:
    """
    Convert an SVG to a 256x256 PNG using rsvg-convert.
    Output PNG is written next to the source SVG with a .png extension.

    Args:
        container_path: Path to the .svg as seen from inside the container,
                        e.g. '/workspace/ValheimRainDance/ThunderstoreAssets/icon.svg'
    """
    try:
        host_svg = _container_to_host(container_path)
    except ValueError as e:
        return f"PATH TRANSLATION FAILED\n\n{e}"

    host_png = str(Path(host_svg).with_suffix(".png"))

    success, log = await _run_async(
        ["rsvg-convert", "-w", "256", "-h", "256", host_svg, "-o", host_png],
        cwd=None,
        log_path=LOGS_DIR / "svg-to-png.log",
    )
    header = "CONVERT SUCCEEDED ✓" if success else "CONVERT FAILED ✗"
    return f"{header}\n\n{log}"


# ── Utility ───────────────────────────────────────────────────────────────────

@mcp.tool()
def refresh_path_map() -> str:
    """
    Rebuild the container→host path map by re-inspecting the Podman container.
    Call this whenever the container has been restarted since the MCP server started.
    """
    return _build_path_map()


# ── Entrypoint ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Building initial path map...")
    _build_path_map()
    print("Starting Valheim MCP server on http://0.0.0.0:5172")
    print()
    print("Register with Claude Code inside the container:")
    print("  claude mcp add valheim --transport http http://host.docker.internal:5172/mcp")
    print()
    mcp.run(transport="streamable-http", host="0.0.0.0", port=5172)
