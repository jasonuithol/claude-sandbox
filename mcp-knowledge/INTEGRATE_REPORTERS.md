# Integrate Knowledge Reporting into mcp-build and mcp-control

This document tells you exactly what to change so that mcp-build and mcp-control
report every tool execution to mcp-knowledge. Follow it step by step.

---

## What you're doing

Adding a fire-and-forget HTTP POST to the end of every `@mcp.tool()` function
in both services. The POST sends the tool name, args, result, and success/failure
to `http://localhost:5174/ingest`. If the knowledge service is down, nothing
breaks — the POST silently fails.

---

## Step 1: Add the reporter helper

Add this function to the main Python file of **each** service (the file that
defines the `@mcp.tool()` functions). Put it near the top, after imports.

### For mcp-build

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
            "service": "mcp-build",
        }, timeout=2)
    except Exception:
        pass
```

### For mcp-control

Identical, except change `"service": "mcp-build"` to `"service": "mcp-control"`.

---

## Step 2: Add `_report()` calls to every tool function

Add a single `_report(...)` call **at the end** of each `@mcp.tool()` function,
just before the `return`. Do not change the return value. Do not await the report.
Do not wrap existing logic in try/except for reporting purposes.

### Pattern

Before:
```python
@mcp.tool()
async def build(project: str) -> str:
    cwd = str(PROJECT_DIR / project)
    success, log = await _run_async(...)
    header = "BUILD SUCCEEDED ✓" if success else "BUILD FAILED ✗"
    result = f"{header}\n\n{log}"
    return result
```

After:
```python
@mcp.tool()
async def build(project: str) -> str:
    cwd = str(PROJECT_DIR / project)
    success, log = await _run_async(...)
    header = "BUILD SUCCEEDED ✓" if success else "BUILD FAILED ✗"
    result = f"{header}\n\n{log}"
    _report("build", {"project": project}, result, success)
    return result
```

That's it. One line added per tool.

### What to pass

| Argument | Value |
|----------|-------|
| `tool` | The function name as a string: `"build"`, `"decompile_dll"`, `"publish"`, etc. |
| `args` | A dict of the meaningful arguments. Don't include large blobs — just the identifiers (project name, class name, dll name, etc.) |
| `result` | The return value string (the same thing being returned to the caller) |
| `success` | `True` if the operation succeeded, `False` if it failed. Most tools already track this. If a tool doesn't have a clear success/failure, pass `True`. |

---

## Step 3: Make sure httpx is available

Check `requirements.txt` in each service. If `httpx` is not already listed, add it.
Both services likely already have it since they make HTTP calls, but verify.

---

## Step 4: Rebuild the containers

After making the changes:

```bash
# Rebuild mcp-build
cd ~/Projects/claude-sandbox/mcp-build   # or wherever it lives
./build-container.sh

# Rebuild mcp-control (if containerized)
# mcp-control runs on the host, so just restart it
```

---

## Every tool needs a report call

Do not skip any tools. The knowledge service decides what's interesting — the
reporters send everything. Here's what mcp-knowledge does with each tool:

| Tool | Knowledge service action |
|------|------------------------|
| `build` (failure) | Indexes the error |
| `build` (success after failure) | Indexes the error→fix pair |
| `build` (routine success) | Skips it |
| `decompile_dll` | Chunks by method and indexes each one |
| `publish` (success) | Indexes manifest metadata |
| `publish` (failure) | Indexes the error |
| `deploy_server` / `deploy_client` | Skips |
| `package` | Skips |
| `start_server` / `stop_server` | Skips |
| `start_client` / `stop_client` | Skips |

Even the skipped ones should be reported — the knowledge service may learn to
use them later.

---

## Checklist

- [ ] `_report()` helper added to mcp-build main file
- [ ] `_report()` helper added to mcp-control main file
- [ ] Every `@mcp.tool()` in mcp-build has a `_report(...)` call before its return
- [ ] Every `@mcp.tool()` in mcp-control has a `_report(...)` call before its return
- [ ] `httpx` is in requirements.txt for both services
- [ ] Containers rebuilt / services restarted
- [ ] Verified: `curl -X POST http://localhost:5174/ingest -H 'Content-Type: application/json' -d '{"tool":"test","args":{},"result":"hello","success":true,"timestamp":"2026-04-12T00:00:00Z","service":"test"}'` returns `{"action":"skipped_unknown","chunks":0}`
