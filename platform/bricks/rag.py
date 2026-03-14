"""RAG brick — retrieval-augmented generation with vector search."""
# Ref: feat-tool-builder

from __future__ import annotations

import asyncio
import logging
import os

from . import BrickDef, BrickRegistry, ToolDef

logger = logging.getLogger(__name__)


async def index_codebase(args: dict, ctx=None) -> str:
    """Index a codebase directory for vector search."""
    path = args.get("path", ".")
    project_id = args.get("project_id", "default")
    try:
        from ..memory.manager import get_memory_manager
        mm = get_memory_manager()
        # Walk source files and store in project memory
        indexed = 0
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in (
                "node_modules", "__pycache__", "target", ".build", "venv")]
            for f in files:
                if not any(f.endswith(ext) for ext in (
                    ".py", ".js", ".ts", ".rs", ".go", ".java", ".swift", ".md")):
                    continue
                fpath = os.path.join(root, f)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="replace") as fh:
                        content = fh.read(4000)
                    rel = os.path.relpath(fpath, path)
                    mm.project_store(
                        project_id, key=f"file:{rel}",
                        value=content[:2000], category="code",
                        source="rag-indexer",
                    )
                    indexed += 1
                except Exception:
                    pass
                if indexed >= 200:
                    break
            if indexed >= 200:
                break
        return f"Indexed {indexed} files for project {project_id}"
    except Exception as e:
        return f"Error: {e}"


async def semantic_search(args: dict, ctx=None) -> str:
    """Search indexed codebase using semantic similarity."""
    query = args.get("query", "")
    project_id = args.get("project_id", "default")
    limit = args.get("limit", 5)
    try:
        from ..memory.manager import get_memory_manager
        mm = get_memory_manager()
        results = mm.project_search(project_id, query, limit=limit)
        if not results:
            return "No results found"
        lines = []
        for r in results:
            key = r.get("key", "")
            value = r.get("value", "")[:500]
            score = r.get("score", 0)
            lines.append(f"[{score:.2f}] {key}\n{value}\n")
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {e}"


async def similar_code(args: dict, ctx=None) -> str:
    """Find code similar to a given snippet."""
    snippet = args.get("snippet", "")
    project_id = args.get("project_id", "default")
    if not snippet:
        return "Error: snippet required"
    return await semantic_search(
        {"query": snippet, "project_id": project_id, "limit": 3}, ctx
    )


BRICK = BrickDef(
    id="rag",
    name="RAG",
    description="Retrieval-Augmented Generation: index codebase, semantic search, find similar code",
    tools=[
        ToolDef(name="rag_index", description="Index a codebase for vector search",
                parameters={"path": "str", "project_id": "str"},
                execute=index_codebase, category="rag"),
        ToolDef(name="rag_search", description="Semantic search in indexed codebase",
                parameters={"query": "str", "project_id": "str", "limit": "int"},
                execute=semantic_search, category="rag"),
        ToolDef(name="rag_similar", description="Find similar code snippets",
                parameters={"snippet": "str", "project_id": "str"},
                execute=similar_code, category="rag"),
    ],
    roles=["developer", "architect", "qa", "cto"],
    requires_env=[],  # Uses platform memory — always available
)


def register(registry: BrickRegistry) -> None:
    registry.register(BRICK)
