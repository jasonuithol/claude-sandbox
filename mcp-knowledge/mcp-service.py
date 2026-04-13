"""mcp-knowledge: RAG-backed Valheim modding knowledge service.

FastMCP server (query + maintenance tools) with a plain HTTP /ingest endpoint
for fire-and-forget reporting from mcp-build and mcp-control.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import chromadb
import httpx
from fastmcp import FastMCP

from ingest.chunker import chunk_decompile, chunk_docs, chunk_mod_source
from ingest.router import IngestRouter

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

KNOWLEDGE_DIR = os.environ.get("KNOWLEDGE_DIR", "/opt/knowledge")
PROJECTS_DIR = os.environ.get("PROJECTS_DIR", "/opt/projects")
MCP_BUILD_URL = os.environ.get("MCP_BUILD_URL", "http://localhost:5172")
PORT = int(os.environ.get("PORT", "5174"))

logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s %(message)s")
logger = logging.getLogger("mcp-knowledge")

# ---------------------------------------------------------------------------
# ChromaDB setup
# ---------------------------------------------------------------------------

chroma_client = chromadb.PersistentClient(path=KNOWLEDGE_DIR)
collection = chroma_client.get_or_create_collection(
    name="valheim_knowledge",
    metadata={"hnsw:space": "cosine"},
)

# ---------------------------------------------------------------------------
# Ingest router
# ---------------------------------------------------------------------------

router = IngestRouter(collection)

# ---------------------------------------------------------------------------
# FastMCP server
# ---------------------------------------------------------------------------

mcp = FastMCP("mcp-knowledge")

# ---- Query tools ---------------------------------------------------------


@mcp.tool()
def ask(question: str) -> str:
    """Semantic search — returns the top 5 most relevant knowledge chunks."""
    results = collection.query(query_texts=[question], n_results=5)
    return _format_results(results)


@mcp.tool()
def ask_class(class_name: str) -> str:
    """Find all indexed knowledge about a specific Valheim class."""
    results = collection.query(
        query_texts=[class_name],
        n_results=10,
        where={"class_name": class_name},
    )
    return _format_results(results)


@mcp.tool()
def ask_tagged(question: str, tags: list[str]) -> str:
    """Filtered semantic search — restrict results by tags like 'rpc', 'zdo', 'weather'."""
    # ChromaDB $contains does substring match on metadata fields
    # We filter by checking each tag appears in the comma-separated tags field
    if len(tags) == 1:
        where = {"tags": {"$contains": tags[0]}}
    else:
        where = {"$and": [{"tags": {"$contains": t}} for t in tags]}

    results = collection.query(
        query_texts=[question],
        n_results=5,
        where=where,
    )
    return _format_results(results)


# ---- Maintenance tools ---------------------------------------------------


@mcp.tool()
def list_sources() -> str:
    """List all indexed sources with chunk counts."""
    all_meta = collection.get(include=["metadatas"])
    sources: dict[str, int] = {}
    for meta in all_meta["metadatas"]:
        src = meta.get("source", "unknown")
        sources[src] = sources.get(src, 0) + 1

    if not sources:
        return "No sources indexed yet."

    lines = [f"  {src}: {count} chunks" for src, count in sorted(sources.items())]
    return f"Indexed sources ({len(sources)}):\n" + "\n".join(lines)


@mcp.tool()
def forget(source: str) -> str:
    """Remove all chunks from a source."""
    # Get IDs matching this source
    results = collection.get(where={"source": source}, include=[])
    ids = results["ids"]
    if not ids:
        return f"No chunks found for source: {source}"
    collection.delete(ids=ids)
    return f"Deleted {len(ids)} chunks from source: {source}"


@mcp.tool()
def stats() -> str:
    """Collection size, source breakdown, tag distribution."""
    count = collection.count()
    if count == 0:
        return "Knowledge base is empty."

    all_meta = collection.get(include=["metadatas"])

    # Source breakdown
    sources: dict[str, int] = {}
    tags_count: dict[str, int] = {}
    types: dict[str, int] = {}

    for meta in all_meta["metadatas"]:
        src = meta.get("source", "unknown")
        sources[src] = sources.get(src, 0) + 1

        chunk_type = meta.get("type", "unknown")
        types[chunk_type] = types.get(chunk_type, 0) + 1

        for tag in meta.get("tags", "").split(","):
            tag = tag.strip()
            if tag:
                tags_count[tag] = tags_count.get(tag, 0) + 1

    lines = [f"Total chunks: {count}", ""]

    lines.append(f"Sources ({len(sources)}):")
    for src, c in sorted(sources.items(), key=lambda x: -x[1])[:20]:
        lines.append(f"  {src}: {c}")

    lines.append(f"\nTypes:")
    for t, c in sorted(types.items(), key=lambda x: -x[1]):
        lines.append(f"  {t}: {c}")

    lines.append(f"\nTop tags:")
    for tag, c in sorted(tags_count.items(), key=lambda x: -x[1])[:20]:
        lines.append(f"  {tag}: {c}")

    return "\n".join(lines)


@mcp.tool()
def seed_docs(docs_path: str) -> str:
    """One-time: index the curated MODDING_*.md and VALHEIM_*.md docs."""
    docs_dir = Path(docs_path)
    if not docs_dir.is_dir():
        return f"Directory not found: {docs_path}"

    total_chunks = 0
    files_indexed = []

    for md_file in sorted(docs_dir.glob("*.md")):
        name = md_file.name
        if not (name.startswith("MODDING_") or name.startswith("VALHEIM_")):
            continue

        text = md_file.read_text(encoding="utf-8")
        chunks = chunk_docs(text, name)
        if chunks:
            collection.upsert(
                ids=[c["id"] for c in chunks],
                documents=[c["document"] for c in chunks],
                metadatas=[c["metadata"] for c in chunks],
            )
            total_chunks += len(chunks)
            files_indexed.append(f"  {name}: {len(chunks)} chunks")

    if not files_indexed:
        return f"No MODDING_*.md or VALHEIM_*.md files found in {docs_path}"

    return (
        f"Indexed {total_chunks} chunks from {len(files_indexed)} files:\n"
        + "\n".join(files_indexed)
    )


@mcp.tool()
def seed_decompile(decompiled_source: str) -> str:
    """Index decompiled source. Accepts output from a single class or an entire DLL.

    Splits by class automatically, then chunks each class by method.

    Args:
        decompiled_source: The decompiled source text (from ilspycmd).
    """
    if not decompiled_source.strip():
        return "Empty decompile output"

    chunks = chunk_decompile(decompiled_source)
    if chunks:
        BATCH = 5000
        for i in range(0, len(chunks), BATCH):
            batch = chunks[i:i + BATCH]
            collection.upsert(
                ids=[c["id"] for c in batch],
                documents=[c["document"] for c in batch],
                metadatas=[c["metadata"] for c in batch],
            )

    # Summarise what was indexed
    classes = {c["metadata"]["class_name"] for c in chunks}
    return f"Indexed {len(chunks)} chunks from {len(classes)} classes: {', '.join(sorted(classes))}"


# ---------------------------------------------------------------------------
# Result formatting
# ---------------------------------------------------------------------------


def _format_results(results: dict) -> str:
    """Format ChromaDB query results into readable text."""
    if not results["ids"] or not results["ids"][0]:
        return "No results found."

    lines = []
    for i, (doc, meta, dist) in enumerate(
        zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        )
    ):
        source = meta.get("source", "unknown")
        tags = meta.get("tags", "")
        class_name = meta.get("class_name", "")
        method_name = meta.get("method_name", "")
        similarity = 1 - dist  # cosine distance -> similarity

        header_parts = [f"[{i + 1}] {source}"]
        if class_name:
            header_parts.append(f"class={class_name}")
        if method_name:
            header_parts.append(f"method={method_name}")
        header_parts.append(f"similarity={similarity:.2f}")
        if tags:
            header_parts.append(f"tags=[{tags}]")

        lines.append(" | ".join(header_parts))
        lines.append(doc[:1500])  # cap chunk display length
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Plain HTTP /ingest endpoint (non-MCP, for service-to-service reporting)
# ---------------------------------------------------------------------------

from starlette.requests import Request
from starlette.responses import JSONResponse


async def ingest_endpoint(request: Request) -> JSONResponse:
    """Receive tool execution payloads from mcp-build / mcp-control."""
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)

    tool = payload.get("tool")
    if not tool:
        return JSONResponse({"error": "missing 'tool' field"}, status_code=400)

    try:
        result = router.route(payload)
        logger.info("Ingested %s -> %s (%d chunks)", tool, result["action"], result["chunks"])
        return JSONResponse(result, status_code=200)
    except Exception as e:
        logger.exception("Ingest error for tool=%s", tool)
        return JSONResponse({"error": str(e)}, status_code=500)


# ---------------------------------------------------------------------------
# Mount /ingest on the FastMCP app and run
# ---------------------------------------------------------------------------

from starlette.applications import Starlette
from starlette.routing import Route, Mount

mcp_app = mcp.http_app("/mcp")

# Build a Starlette app that serves both /ingest and /mcp
app = Starlette(
    routes=[
        Route("/ingest", ingest_endpoint, methods=["POST"]),
        Mount("/", app=mcp_app),
    ],
    lifespan=mcp_app.lifespan,
)

if __name__ == "__main__":
    import uvicorn

    logger.info("Starting mcp-knowledge on port %d", PORT)
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
