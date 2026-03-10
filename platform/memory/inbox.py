"""Inbox file watcher — always-on artifact ingestion.

SOURCE: GoogleCloudPlatform/generative-ai — always-on-memory-agent (IngestAgent)
        https://github.com/GoogleCloudPlatform/generative-ai/tree/main/gemini/agents/always-on-memory-agent

WHY: That agent watches ./inbox/ for files (text, images, audio, video, PDFs) and
     automatically extracts structured memory: summary, entities, topics, importance.
     The key value: agents (or humans) drop artifacts into inbox/ and they become
     searchable platform memory without any manual curation step.
     We saw this as the missing "ambient ingestion" layer — our memory system only
     got data when agents explicitly called memory_store(). Now any file drop works.

ADAPTATION vs always-on-memory-agent:
- Text/structured files only for now (.txt, .md, .json, .yaml, .log, .csv)
  (multimodal — images/audio/video/PDF — requires vision API; can be added later)
- Background asyncio task polling (not inotify) — portable, no Linux-only deps
- Stores in memory_global (category='inbox') — reuses existing memory layer
- LLM extracts: summary + entities + topics + importance (same schema as original)
- Processed files moved to inbox/processed/ to avoid re-ingestion
- INBOX_DIR env var (default: ./inbox relative to SF_ROOT or CWD)
- Also exposes ingest_text() for the HTTP POST /api/memory/ingest endpoint

SUPPORTED FILE TYPES (text tier — same as original's text category):
  .txt .md .log .csv .xml .yaml .yml .json
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

# Poll interval for inbox directory (seconds)
_POLL_INTERVAL = int(os.environ.get("INBOX_POLL_INTERVAL", "10"))

# Max file size to ingest (bytes) — skip binary/huge files
_MAX_FILE_SIZE = int(os.environ.get("INBOX_MAX_FILE_BYTES", str(200 * 1024)))  # 200 KB

# Supported text extensions
_SUPPORTED_EXT = {".txt", ".md", ".log", ".csv", ".xml", ".yaml", ".yml", ".json"}


def _inbox_dir() -> Path:
    """Resolve inbox directory from env or default."""
    sf_root = os.environ.get("SF_ROOT", os.getcwd())
    raw = os.environ.get("INBOX_DIR", os.path.join(sf_root, "inbox"))
    return Path(raw)


# ─────────────────────────────────────────────────────────────────────────────
# LLM extraction
# ─────────────────────────────────────────────────────────────────────────────


async def _extract_memory(filename: str, content: str) -> dict:
    """Use LLM to extract structured memory from raw text.

    SOURCE: always-on-memory-agent IngestAgent extraction schema:
    {summary, entities, topics, importance}
    WHY: Raw text → structured memory makes it queryable and connectable
    by the ConsolidateAgent later.
    """
    # Truncate to ~3000 chars for token budget
    snippet = content[:3000]
    prompt = f"""Extract structured memory from this document fragment.
Filename: {filename}
Content:
---
{snippet}
---

Return JSON only:
{{
  "summary": "1-2 sentence summary",
  "entities": ["list", "of", "key", "named", "entities"],
  "topics": ["list", "of", "topic", "keywords"],
  "importance": 0.0-1.0
}}

importance: 0.3=background info, 0.5=useful reference, 0.7=important, 0.9=critical"""

    try:
        from ..llm.client import LLMClient, LLMMessage

        client = LLMClient()
        resp = await client.chat(
            messages=[LLMMessage(role="user", content=prompt)],
            temperature=0.1,
            max_tokens=512,
        )
        text = resp.content.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)
    except Exception as e:
        logger.warning("inbox._extract_memory failed: %s — using fallback", e)
        # Fallback: simple extraction without LLM
        return {
            "summary": f"File: {filename} ({len(content)} chars)",
            "entities": [],
            "topics": [filename.rsplit(".", 1)[0]],
            "importance": 0.3,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Ingestion
# ─────────────────────────────────────────────────────────────────────────────


async def ingest_text(
    content: str,
    source: str = "api",
    filename: str = "input.txt",
) -> dict:
    """Ingest raw text into platform memory (memory_global, category='inbox').

    This is also the backend for POST /api/memory/ingest.

    Returns: {id, summary, entities, topics, importance, stored: bool}
    """
    extracted = await _extract_memory(filename, content)
    summary = extracted.get("summary", "")
    entities = extracted.get("entities", [])
    topics = extracted.get("topics", [])
    importance = float(extracted.get("importance", 0.3))

    # Build memory value: summary + metadata
    value = json.dumps(
        {
            "summary": summary,
            "entities": entities,
            "topics": topics,
            "source": source,
            "filename": filename,
            "raw_excerpt": content[:500],
        }
    )

    memory_key = f"inbox:{filename}:{uuid.uuid4().hex[:8]}"

    stored = False
    try:
        from ..memory.manager import get_memory_manager

        mm = get_memory_manager()
        mm.global_store(
            key=memory_key,
            value=value,
            category="inbox",
            confidence=importance,
        )
        stored = True
        logger.info(
            "inbox: ingested '%s' (importance=%.1f, %d chars)",
            filename,
            importance,
            len(content),
        )
    except Exception as e:
        logger.error("inbox.ingest_text store error: %s", e)

    return {
        "id": memory_key,
        "summary": summary,
        "entities": entities,
        "topics": topics,
        "importance": importance,
        "stored": stored,
    }


async def _ingest_file(path: Path, processed_dir: Path) -> bool:
    """Read a file, ingest it, move to processed/."""
    if path.stat().st_size > _MAX_FILE_SIZE:
        logger.warning(
            "inbox: skipping %s (too large: %d bytes)", path.name, path.stat().st_size
        )
        # Still move to processed so we don't retry infinitely
        path.rename(processed_dir / path.name)
        return False

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        logger.error("inbox: cannot read %s: %s", path.name, e)
        return False

    result = await ingest_text(content, source="inbox-watcher", filename=path.name)

    # Move to processed/
    try:
        path.rename(processed_dir / path.name)
    except Exception:
        path.unlink(missing_ok=True)

    return result.get("stored", False)


# ─────────────────────────────────────────────────────────────────────────────
# Background watcher task
# ─────────────────────────────────────────────────────────────────────────────


async def start_inbox_watcher() -> None:
    """Background task: watch INBOX_DIR for new files and ingest them.

    SOURCE: always-on-memory-agent — FileWatcher pattern (./inbox/ drop zone).
    WHY: Agents and humans can drop specs, logs, meeting notes, API docs into
         inbox/ and they automatically become searchable platform memory.
    """
    inbox = _inbox_dir()
    try:
        inbox.mkdir(parents=True, exist_ok=True)
        processed = inbox / "processed"
        processed.mkdir(exist_ok=True)
    except Exception as e:
        logger.error("inbox: cannot create inbox dir %s: %s", inbox, e)
        return

    logger.info("inbox watcher started — watching %s (poll=%ds)", inbox, _POLL_INTERVAL)

    while True:
        try:
            for f in inbox.iterdir():
                if f.is_file() and f.suffix.lower() in _SUPPORTED_EXT:
                    logger.info("inbox: detected %s — ingesting", f.name)
                    await _ingest_file(f, processed)
        except Exception as e:
            logger.error("inbox watcher loop error: %s", e)
        await asyncio.sleep(_POLL_INTERVAL)
