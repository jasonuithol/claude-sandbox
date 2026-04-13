# mcp-knowledge Usage

## Quick Start

```bash
# Build
./build-container.sh

# Run
./start-container.sh

# Register with Claude Code
claude mcp add valheim-knowledge --transport http http://localhost:5174/mcp
```

Requires mcp-build (port 5172) to be running if you plan to use `seed_decompile`.

---

## Endpoints

| Endpoint | Protocol | Purpose |
|----------|----------|---------|
| `http://localhost:5174/mcp` | MCP (JSON-RPC) | Claude queries and maintenance |
| `http://localhost:5174/ingest` | Plain HTTP POST | Service-to-service tool reporting |

---

## MCP Tools

### Query

**`ask(question)`** — Semantic search across all knowledge. Returns top 5 chunks with source, tags, and similarity score.

```
ask("How does ZRoutedRpc register custom RPCs?")
```

**`ask_class(class_name)`** — Find everything indexed about a specific Valheim class. Returns up to 10 chunks.

```
ask_class("Player")
```

**`ask_tagged(question, tags)`** — Semantic search filtered by tags. Useful for narrowing results to a specific system.

```
ask_tagged("how to sync custom data", ["rpc", "zdo"])
```

### Maintenance

**`stats()`** — Total chunk count, source breakdown, type distribution, top tags.

**`list_sources()`** — All indexed sources with chunk counts.

**`forget(source)`** — Delete all chunks from a source. Use `list_sources()` to find the exact source string.

```
forget("decompile/assembly_valheim/Player")
```

**`seed_docs(docs_path)`** — Index the curated MODDING_*.md / VALHEIM_*.md docs. Run once on first setup.

```
seed_docs("/opt/projects/claude-sandbox/claude/docs")
```

**`seed_decompile(class_name)`** — Decompile a class via mcp-build and index the output. Requires mcp-build to be running.

```
seed_decompile("Player")
seed_decompile("ZRoutedRpc")
```

---

## Automatic Ingest

mcp-build and mcp-control report every tool execution to `/ingest` automatically. No action needed — knowledge accumulates as you work.

### What gets indexed

| Event | What's stored |
|-------|--------------|
| Build failure | Error message with CS error codes |
| Build success after failure | Error + fix pair |
| Decompile | Each method as a separate chunk |
| Publish success | Manifest metadata |
| Publish failure | Error details |

### What gets skipped

Routine operations: deploy, package, start/stop server, start/stop client, successful builds with no prior failure.

### Reporter setup (mcp-build / mcp-control)

Add this to each service:

```python
import httpx
from datetime import datetime

_KNOWLEDGE_URL = "http://localhost:5174/ingest"

def _report(tool: str, args: dict, result: str, success: bool):
    """Fire-and-forget report to mcp-knowledge. Never raises."""
    try:
        httpx.post(_KNOWLEDGE_URL, json={
            "tool": tool,
            "args": args,
            "result": result,
            "success": success,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "service": "mcp-build",  # or "mcp-control"
        }, timeout=2)
    except Exception:
        pass
```

Call `_report(...)` at the end of every tool function. If mcp-knowledge is down, nothing breaks.

---

## Seed Workflow

First time after starting the service:

```
1. seed_docs("/opt/projects/claude-sandbox/claude/docs")
2. seed_decompile("Player")
3. seed_decompile("ZRoutedRpc")
4. seed_decompile("ZDOVars")
5. seed_decompile("EnvMan")
6. seed_decompile("ZNetPeer")
7. seed_decompile("Bed")
8. seed_decompile("RandEventSystem")
9. seed_decompile("VisEquipment")
10. seed_decompile("ZSyncAnimation")
```

Run `stats()` afterwards to confirm everything was indexed.

---

## Tags

Tags are auto-detected from content. Use them with `ask_tagged` to narrow searches.

Common tags: `rpc`, `zdo`, `networking`, `inventory`, `status-effect`, `harmony`, `weather`, `emote`, `animation`, `teleport`, `minimap`, `building`, `raid`, `visual-equip`, `bepinex`, `build-error`, `build-fix`, `publish`.

**Case sensitivity:** ChromaDB's `$contains` filter is case-sensitive. Tags
are stored lowercase, so always pass lowercase tags to `ask_tagged`. The
`ask()` tool (pure semantic search) is unaffected.

---

## Volumes

| Mount | Container path | Purpose |
|-------|---------------|---------|
| `mcp-knowledge/knowledge` | `/opt/knowledge` | ChromaDB storage (persists across rebuilds) |
| `~/Projects` | `/opt/projects` (read-only) | Access to mod source and docs |
