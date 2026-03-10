"""Context Compressor — summarize old conversation messages to fit LLM context.

When a conversation grows beyond RECENT_WINDOW messages, older messages are
compressed into a concise summary that preserves key decisions, facts, and
context. The summary is cached in the session's config to avoid re-computing.

Flow:
  history = [msg1, msg2, ..., msg50]
  → compressed_summary (1 LLM call) + recent 10 messages
  → fits in context, conversation feels continuous
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Keep this many recent messages verbatim
RECENT_WINDOW = 10
# Compress when history exceeds this count
COMPRESS_THRESHOLD = 16


async def compress_history(
    history: list[dict],
    project_name: str = "",
    cached_summary: Optional[str] = None,
    cached_hash: Optional[str] = None,
) -> tuple[list[dict], Optional[str], Optional[str]]:
    """Compress history if it exceeds threshold.

    Returns:
        (effective_history, new_summary, new_hash)
        - effective_history: list of message dicts to send to LLM
        - new_summary: compressed summary string (or None if not compressed)
        - new_hash: hash of compressed messages (for cache invalidation)
    """
    if len(history) <= COMPRESS_THRESHOLD:
        return history, None, None

    # Split: older messages to compress, recent to keep verbatim
    older = history[:-RECENT_WINDOW]
    recent = history[-RECENT_WINDOW:]

    # Check cache: if we already summarized these exact messages, reuse
    older_hash = _hash_messages(older)
    if cached_hash and cached_hash == older_hash and cached_summary:
        logger.debug("Using cached conversation summary (%d chars)", len(cached_summary))
        summary_msg = {"from_agent": "system", "content": f"[Conversation summary]\n{cached_summary}"}
        return [summary_msg] + recent, cached_summary, older_hash

    # Compress via LLM
    summary = await _summarize_messages(older, project_name)
    if summary:
        logger.info("Compressed %d messages into summary (%d chars)", len(older), len(summary))
        summary_msg = {"from_agent": "system", "content": f"[Conversation summary]\n{summary}"}
        return [summary_msg] + recent, summary, older_hash

    # Fallback: just truncate to recent
    logger.warning("Compression failed, truncating to recent %d messages", RECENT_WINDOW)
    return recent, None, None


async def _summarize_messages(messages: list[dict], project_name: str) -> Optional[str]:
    """Call LLM to summarize a batch of messages."""
    try:
        from ..llm.client import get_llm_client, LLMMessage

        # Build conversation text
        lines = []
        for m in messages:
            sender = m.get("from_agent", "?")
            content = m.get("content", "")
            # Truncate very long messages (tool results, code blocks)
            if len(content) > 600:
                content = content[:500] + f"\n... ({len(content)} chars total)"
            lines.append(f"**{sender}**: {content}")
        conversation = "\n\n".join(lines)

        prompt = (
            f"Summarize this conversation about the project '{project_name}' "
            f"into a concise context summary. Preserve:\n"
            f"- Key decisions made\n"
            f"- Important facts discovered about the codebase\n"
            f"- Questions asked and answers given\n"
            f"- Any tool results or findings\n"
            f"Keep it under 500 words. Use bullet points.\n\n"
            f"Conversation:\n{conversation}"
        )

        llm = get_llm_client()
        resp = await llm.chat(
            messages=[LLMMessage(role="user", content=prompt)],
            provider="minimax",
            model="MiniMax-M2.5",
            temperature=0.2,
            max_tokens=800,
        )
        return resp.content.strip() if resp.content else None

    except Exception as exc:
        logger.error("Failed to compress conversation: %s", exc)
        return None


def _hash_messages(messages: list[dict]) -> str:
    """Hash message contents for cache comparison."""
    h = hashlib.md5()
    for m in messages:
        h.update(m.get("content", "")[:200].encode())
    return h.hexdigest()[:12]
