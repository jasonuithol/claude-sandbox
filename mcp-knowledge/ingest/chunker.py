"""Chunking logic for different knowledge source types."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from .extractors import detect_tags, extract_class_name, extract_methods, split_classes


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


_TAG_KEY_RE = re.compile(r"[^a-z0-9_]")


def tag_key(tag: str) -> str:
    """Normalise a tag into a metadata key: 'status-effect' -> 'tag_status_effect'.

    ChromaDB's `where` filter has no $contains operator for metadata — the only
    reliable way to filter by tag is to store each tag as its own boolean key.
    """
    return "tag_" + _TAG_KEY_RE.sub("_", tag.lower())


def tag_flags(tags: list[str]) -> dict:
    """Return a dict of {tag_<name>: True} entries for each tag in the list."""
    return {tag_key(t): True for t in tags if t}


def upsert_chunks(collection, chunks: list[dict]) -> None:
    """Upsert chunks into ChromaDB, expanding the comma-joined `tags` metadata
    into individual `tag_<name>: True` boolean keys so they can be filtered
    via ChromaDB's metadata `where` clause (which has no $contains operator)."""
    if not chunks:
        return
    for c in chunks:
        tag_str = c["metadata"].get("tags", "")
        tag_list = [t.strip() for t in tag_str.split(",") if t.strip()]
        c["metadata"].update(tag_flags(tag_list))
    collection.upsert(
        ids=[c["id"] for c in chunks],
        documents=[c["document"] for c in chunks],
        metadatas=[c["metadata"] for c in chunks],
    )


def chunk_decompile(source: str, dll_name: str = "assembly_valheim") -> list[dict]:
    """Chunk decompiled DLL output by class and method.

    Handles both single-class (ilspycmd -t) and multi-class (full DLL) input.
    Returns list of dicts ready for ChromaDB insertion:
        {id, document, metadata}
    """
    now = _now_iso()
    chunks = []

    for cls in split_classes(source):
        class_name = cls["name"]
        class_source = cls["body"]
        methods = extract_methods(class_source)

        if not methods:
            tags = detect_tags(class_source)
            chunks.append({
                "id": f"decompile/{dll_name}/{class_name}",
                "document": class_source,
                "metadata": {
                    "source": f"decompile/{dll_name}/{class_name}",
                    "type": "class",
                    "class_name": class_name,
                    "method_name": "",
                    "tags": ",".join(tags),
                    "indexed_at": now,
                    "project": "",                },
            })
            continue

        seen: dict[str, int] = {}
        for method in methods:
            tags = detect_tags(method["body"])
            name = method["name"]
            seen[name] = seen.get(name, 0) + 1
            suffix = f"_{seen[name]}" if seen[name] > 1 else ""
            method_id = f"decompile/{dll_name}/{class_name}/{name}{suffix}"
            chunks.append({
                "id": method_id,
                "document": method["body"],
                "metadata": {
                    "source": f"decompile/{dll_name}/{class_name}",
                    "type": "method",
                    "class_name": class_name,
                    "method_name": name,
                    "tags": ",".join(tags),
                    "indexed_at": now,
                    "project": "",                },
            })

    # Deduplicate IDs globally (e.g. generic class variants with the same name)
    seen_ids: dict[str, int] = {}
    for chunk in chunks:
        cid = chunk["id"]
        if cid in seen_ids:
            seen_ids[cid] += 1
            chunk["id"] = f"{cid}_{seen_ids[cid]}"
        else:
            seen_ids[cid] = 1

    return chunks


def chunk_docs(text: str, filename: str) -> list[dict]:
    """Chunk a markdown doc by ## headers.

    Returns list of dicts ready for ChromaDB insertion.
    """
    # Split on ## headers, keeping the header with the content
    sections = re.split(r"(?=^## )", text, flags=re.MULTILINE)
    now = _now_iso()
    chunks = []

    for i, section in enumerate(sections):
        section = section.strip()
        if not section:
            continue

        # Extract section title
        title_match = re.match(r"^##\s+(.+)", section)
        title = title_match.group(1).strip() if title_match else f"section_{i}"
        safe_title = re.sub(r"[^a-zA-Z0-9_-]", "_", title)[:80]

        tags = detect_tags(section)
        # Add a tag from the filename (e.g. MODDING_HARMONY.md -> harmony)
        file_tag = filename.replace("MODDING_", "").replace("VALHEIM_", "").replace(".md", "").lower()
        if file_tag and file_tag not in tags:
            tags.insert(0, file_tag)

        chunk_id = f"docs/{filename}/{safe_title}"
        chunks.append({
            "id": chunk_id,
            "document": section,
            "metadata": {
                "source": f"docs/{filename}",
                "type": "section",
                "class_name": "",
                "method_name": "",
                "tags": ",".join(tags),
                "indexed_at": now,
                "project": "",
                **tag_flags(tags),
            },
        })

    return chunks


def chunk_build_error(error_text: str, project: str) -> dict:
    """Create a single chunk for a build error."""
    tags = ["build-error", project.lower()] + detect_tags(error_text)
    return {
        "id": f"build-error/{project}/{_now_iso()}",
        "document": error_text,
        "metadata": {
            "source": f"build-error/{project}",
            "type": "error",
            "class_name": "",
            "method_name": "",
            "tags": ",".join(tags),
            "indexed_at": _now_iso(),
            "project": project,
            **tag_flags(tags),
        },
    }


def chunk_build_fix(error_text: str, fix_context: str, project: str) -> dict:
    """Create a single chunk for an error->fix pair."""
    combined = f"ERROR:\n{error_text}\n\nFIX (successful build after the above error):\n{fix_context}"
    tags = ["build-fix", project.lower()] + detect_tags(combined)
    return {
        "id": f"build-fix/{project}/{_now_iso()}",
        "document": combined,
        "metadata": {
            "source": f"build-fix/{project}",
            "type": "pattern",
            "class_name": "",
            "method_name": "",
            "tags": ",".join(tags),
            "indexed_at": _now_iso(),
            "project": project,
            **tag_flags(tags),
        },
    }


def chunk_publish(manifest: str, project: str, mod_name: str) -> dict:
    """Create a chunk for a successful publish event."""
    tags = ["publish", project.lower(), mod_name.lower()]
    return {
        "id": f"publish/{project}/{_now_iso()}",
        "document": manifest,
        "metadata": {
            "source": f"publish/{project}",
            "type": "pattern",
            "class_name": "",
            "method_name": "",
            "tags": ",".join(tags),
            "indexed_at": _now_iso(),
            "project": project,
        },
    }


def chunk_mod_source(source: str, project: str, class_name: str) -> list[dict]:
    """Chunk mod source code by class (one chunk per file/class)."""
    tags = ["mod-source", project.lower()] + detect_tags(source)
    now = _now_iso()
    return [{
        "id": f"mod-source/{project}/{class_name}",
        "document": source,
        "metadata": {
            "source": f"mod-source/{project}",
            "type": "class",
            "class_name": class_name,
            "method_name": "",
            "tags": ",".join(tags),
            "indexed_at": now,
            "project": project,
        },
    }]
