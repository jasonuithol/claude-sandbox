#!/usr/bin/env python3
"""
mcp-service.py — mcp-build

Runs inside a Docker container. Exposes mod build, deploy, package,
decompile, and SVG conversion tools to Claude Code.

Register with Claude Code (run this inside the claude-sandbox container):
    claude mcp add valheim-build --transport http http://localhost:5172/mcp

Or on the host directly:
    claude mcp add valheim-build --transport http http://localhost:5172/mcp
"""

import asyncio
import json
import subprocess
from datetime import datetime
from pathlib import Path

from fastmcp import FastMCP

# ── Paths ─────────────────────────────────────────────────────────────────────

import os

HOME        = Path.home()
SERVER_DIR  = Path(os.environ.get("VALHEIM_SERVER_DIR",  str(HOME / ".steam/steam/steamapps/common/Valheim dedicated server")))
CLIENT_DIR  = Path(os.environ.get("VALHEIM_CLIENT_DIR",  str(HOME / ".steam/steam/steamapps/common/Valheim")))
PROJECT_DIR = Path(os.environ.get("VALHEIM_PROJECT_DIR", str(HOME / "Projects")))
LOGS_DIR    = Path(os.environ.get("VALHEIM_LOGS_DIR",    str(HOME / "ClaudeProjects/valheim/logs")))

LOGS_DIR.mkdir(parents=True, exist_ok=True)

# ── Container → host path map ─────────────────────────────────────────────────
#
# Translates paths as seen inside claude-sandbox to paths inside this container.
# Built statically from env vars — no docker socket required.
#
# Claude-sandbox mounts              →  This container's paths
#   CLAUDE_SERVER_MOUNT              →  SERVER_DIR
#   CLAUDE_CLIENT_MOUNT              →  CLIENT_DIR
#   CLAUDE_PROJECT_MOUNT/<project>   →  PROJECT_DIR/<project>
#
# Override the CLAUDE_* vars if claude-sandbox uses non-default workspace paths.

_CLAUDE_SERVER_MOUNT  = os.environ.get("CLAUDE_SERVER_MOUNT",  "/workspace/valheim/server")
_CLAUDE_CLIENT_MOUNT  = os.environ.get("CLAUDE_CLIENT_MOUNT",  "/workspace/valheim/client")
_CLAUDE_PROJECT_MOUNT = os.environ.get("CLAUDE_PROJECT_MOUNT", "/workspace")

_path_map: dict[str, str] = {}


def _build_path_map() -> str:
    """
    Build the claude-sandbox → this container path map from known mount points.
    Call refresh_path_map() if the claude-sandbox workspace layout has changed.
    """
    global _path_map
    _path_map = {
        _CLAUDE_SERVER_MOUNT:  str(SERVER_DIR),
        _CLAUDE_CLIENT_MOUNT:  str(CLIENT_DIR),
        _CLAUDE_PROJECT_MOUNT: str(PROJECT_DIR),
    }
    lines = [f"  {dst} -> {src}" for dst, src in _path_map.items()]
    summary = "Path map (static):\n" + "\n".join(lines)
    print(summary)
    return summary


def _container_to_host(container_path: str) -> str:
    """
    Translate a claude-sandbox path to its equivalent inside this container.
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
            f"No mapping found for path: {container_path}\n"
            "Check CLAUDE_SERVER_MOUNT, CLAUDE_CLIENT_MOUNT, CLAUDE_PROJECT_MOUNT env vars."
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


# ── MCP server ────────────────────────────────────────────────────────────────

mcp = FastMCP(
    name="valheim-build",
    instructions=(
        "Tools for building, deploying, and packaging Valheim mods. "
        "All tools (build, deploy, package, decompile, convert) return "
        "the full log output so you can diagnose failures without reading a file. "
        "Server and client control tools are in the separate valheim-control MCP (mcp-control, port 5173)."
    ),
)


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
    import shutil
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

        manifest_path = assets_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        version  = manifest["version_number"]
        modname  = project_dir.name
        zip_name = f"tarbaby-{modname}-{version}.zip"

        staging = project_dir / "staging"
        release = project_dir / "release"
        shutil.rmtree(staging, ignore_errors=True)
        shutil.rmtree(release, ignore_errors=True)
        (staging / "plugins").mkdir(parents=True)
        (staging / "config").mkdir(parents=True)
        release.mkdir()

        for name in ("icon.png", "README.md", "manifest.json"):
            shutil.copy2(assets_dir / name, staging / name)
            lines.append(f"Staged {name}")

        dll_src = project_dir / "bin/Release/netstandard2.1"
        for dll in dll_src.glob("*.dll"):
            shutil.copy2(dll, staging / "plugins" / dll.name)
            lines.append(f"Staged plugins/{dll.name}")

        for cfg in project_dir.glob("*.cfg"):
            shutil.copy2(cfg, staging / "config" / cfg.name)
            lines.append(f"Staged config/{cfg.name}")

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
    Rebuild the claude-sandbox → mcp-build path map from environment variables.
    Only needed if mount paths have changed since startup.
    """
    return _build_path_map()


# ── Entrypoint ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Building initial path map...")
    _build_path_map()
    print("Starting valheim-build MCP on http://0.0.0.0:5172")
    print()
    print("Register with Claude Code:")
    print("  claude mcp add valheim-build --transport http http://localhost:5172/mcp")
    print()
    mcp.run(transport="streamable-http", host="0.0.0.0", port=5172)
