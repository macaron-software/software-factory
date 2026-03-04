"""RTK-inspired prompt compressor for SF agent LLM calls.

Reduces token consumption before sending to any LLM provider,
especially useful for local models (Qwen 3.5 via mlx_lm.server)
where throughput is limited by hardware.

Compression strategies (in order):
1. Whitespace normalization — strip trailing spaces, collapse blank lines
2. Code block truncation — keep first+last N lines of long code blocks
3. Tool output truncation — shorten very long tool/user messages
4. History summarization — collapse middle turns when total is too large

Rough token estimate: 1 token ≈ 4 chars (English prose).
For code/JSON, closer to 3 chars/token — we use 3.5 as conservative estimate.

Dual inspiration:
- RTK (https://github.com/macaron-software/rtk) — token compression CLI, same philosophy
- Ralph (https://github.com/frankbria/ralph-claude-code) — context rot prevention in agent loops
  The _summarize_context() function in agents/executor.py is the Ralph-inspired counterpart.
"""

from __future__ import annotations

import re

# Thresholds (chars, not tokens — avoids importing a tokenizer)
_CHARS_PER_TOKEN = 3.5
_MAX_TOTAL_TOKENS = 12_000  # compress when estimated total > this
_MAX_MSG_TOKENS = 3_000  # truncate individual messages above this
_CODE_KEEP_HEAD = 60  # lines to keep at start of a code block
_CODE_KEEP_TAIL = 20  # lines to keep at end of a code block
_HISTORY_KEEP_RECENT = 4  # always keep last N non-system messages intact


def _estimate_tokens(text: str) -> int:
    return max(1, int(len(text) / _CHARS_PER_TOKEN))


def _compress_code_block(block: str) -> str:
    """Truncate a long code block, keeping head + tail."""
    lines = block.splitlines()
    total = len(lines)
    keep = _CODE_KEEP_HEAD + _CODE_KEEP_TAIL
    if total <= keep:
        return block
    head = lines[:_CODE_KEEP_HEAD]
    tail = lines[-_CODE_KEEP_TAIL:]
    omitted = total - keep
    mid = [f"... [{omitted} lines omitted by RTK compressor] ..."]
    return "\n".join(head + mid + tail)


def _compress_message_content(content: str, max_tokens: int = _MAX_MSG_TOKENS) -> str:
    """Apply whitespace normalization + code block truncation to a single message."""
    if not content:
        return content

    # 1. Whitespace normalization
    # Collapse 3+ consecutive blank lines → 2
    content = re.sub(r"\n{3,}", "\n\n", content)
    # Strip trailing spaces on each line
    content = "\n".join(line.rstrip() for line in content.splitlines())

    # 2. Code block truncation (fenced: ```...``` or indented 4-space blocks)
    def _truncate_fenced(m: re.Match) -> str:
        lang = m.group(1) or ""
        body = m.group(2)
        compressed = _compress_code_block(body)
        return f"```{lang}\n{compressed}\n```"

    content = re.sub(
        r"```([^\n]*)\n(.*?)```",
        _truncate_fenced,
        content,
        flags=re.DOTALL,
    )

    # 3. Hard truncation if still too long
    max_chars = int(max_tokens * _CHARS_PER_TOKEN)
    if len(content) > max_chars:
        half = max_chars // 2
        omitted_chars = len(content) - max_chars
        omitted_tokens = _estimate_tokens(content[half : half + omitted_chars])
        content = (
            content[:half]
            + f"\n\n... [~{omitted_tokens} tokens omitted by RTK compressor] ...\n\n"
            + content[-(half):]
        )

    return content


def compress_messages(
    messages: list,
    system_prompt: str = "",
    provider: str = "",
    force: bool = False,
) -> tuple[list, str, dict]:
    """Compress messages + system_prompt before LLM call.

    Args:
        messages: list of LLMMessage (or dicts with role/content)
        system_prompt: separate system prompt string
        provider: provider name (used for logging / selective compression)
        force: apply even if under threshold

    Returns:
        (compressed_messages, compressed_system_prompt, stats)
        stats = {"original_tokens": int, "compressed_tokens": int, "savings_pct": float}
    """
    # Calculate original size
    orig_chars = sum(
        len(getattr(m, "content", "") or m.get("content", "")) for m in messages
    ) + len(system_prompt)
    orig_tokens = _estimate_tokens(orig_chars)

    # Skip compression if under threshold and not forced
    if orig_tokens <= _MAX_TOTAL_TOKENS and not force:
        return (
            messages,
            system_prompt,
            {
                "original_tokens": orig_tokens,
                "compressed_tokens": orig_tokens,
                "savings_pct": 0.0,
            },
        )

    # Compress system prompt
    new_system = _compress_message_content(system_prompt, max_tokens=2000)

    # Split messages: always keep system + last N user/assistant messages intact
    # Middle messages get compressed more aggressively
    non_system = [
        m for m in messages if (getattr(m, "role", None) or m.get("role")) != "system"
    ]
    system_msgs = [
        m for m in messages if (getattr(m, "role", None) or m.get("role")) == "system"
    ]

    recent = non_system[-_HISTORY_KEEP_RECENT:] if non_system else []
    middle = (
        non_system[:-_HISTORY_KEEP_RECENT]
        if len(non_system) > _HISTORY_KEEP_RECENT
        else []
    )

    def _compress_msg(m, max_tokens: int):
        content = getattr(m, "content", None)
        if content is None:
            content = m.get("content", "")
        compressed_content = _compress_message_content(content, max_tokens=max_tokens)
        # Return same type
        if hasattr(m, "content"):
            # LLMMessage dataclass — create copy with compressed content
            import dataclasses

            return dataclasses.replace(m, content=compressed_content)
        else:
            return {**m, "content": compressed_content}

    # Middle messages: aggressive compression (1500 tokens max each)
    compressed_middle = [_compress_msg(m, max_tokens=1500) for m in middle]

    # Recent messages: light compression only (3000 tokens max each)
    compressed_recent = [_compress_msg(m, max_tokens=_MAX_MSG_TOKENS) for m in recent]

    # If middle is very long, replace with a summary placeholder
    if len(compressed_middle) > 8:
        n = len(compressed_middle)
        # Keep first 2 for context, summarize the rest
        first_two = compressed_middle[:2]
        omitted_count = n - 2
        placeholder_content = (
            f"[RTK compressor: {omitted_count} earlier messages omitted to save tokens. "
            f"Focus on the recent context below.]"
        )
        # Build a synthetic assistant message as the placeholder
        if middle and hasattr(middle[0], "role"):
            from .client import LLMMessage

            placeholder = LLMMessage(role="assistant", content=placeholder_content)
        else:
            placeholder = {"role": "assistant", "content": placeholder_content}
        compressed_middle = first_two + [placeholder]

    new_messages = system_msgs + compressed_middle + compressed_recent

    # Recalculate
    new_chars = sum(
        len(getattr(m, "content", "") or m.get("content", "")) for m in new_messages
    ) + len(new_system)
    new_tokens = _estimate_tokens(new_chars)
    savings = (
        max(0.0, (orig_tokens - new_tokens) / orig_tokens * 100) if orig_tokens else 0.0
    )

    return (
        new_messages,
        new_system,
        {
            "original_tokens": orig_tokens,
            "compressed_tokens": new_tokens,
            "savings_pct": round(savings, 1),
        },
    )


def record_compression_stats(
    provider: str, original_tokens: int, compressed_tokens: int, savings_pct: float
) -> None:
    """Persist compression stats to DB (fire-and-forget, no exception propagation)."""
    try:
        from ..db.migrations import get_db

        db = get_db()
        try:
            db.execute(
                "INSERT INTO rtk_compression_stats (provider, original_tokens, compressed_tokens, savings_pct) VALUES (?,?,?,?)",
                (provider, original_tokens, compressed_tokens, savings_pct),
            )
            db.commit()
        finally:
            db.close()
    except Exception:
        pass
