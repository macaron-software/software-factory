"""
RTK Tools — Rust Token Killer integration for context compression.
=================================================================
SOURCE: RTK — Rust Token Killer (bundled at ~/.local/bin/rtk)
        https://github.com/getrtk/rtk

WHY: Agents generating LLM payloads or processing large tool outputs
can use rtk to compress before passing to the next tool, saving 40-90%
of context tokens. RTK strips noise (blank lines, comments, boilerplate)
while preserving semantic signal — especially effective on code and logs.

TOOLS:
  rtk_run   — pipe any shell command through rtk (compressed stdout)
  rtk_wrap  — compress an arbitrary text blob via rtk read -l {mode}
"""
# Ref: feat-tool-builder

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import tempfile
import os
from typing import TYPE_CHECKING

from .registry import BaseTool

if TYPE_CHECKING:
    from ..models import AgentInstance

logger = logging.getLogger(__name__)


def _rtk_path() -> str | None:
    """Return path to rtk binary, or None if not found."""
    return shutil.which("rtk") or (
        os.path.expanduser("~/.local/bin/rtk")
        if os.path.isfile(os.path.expanduser("~/.local/bin/rtk"))
        else None
    )


class RtkRunTool(BaseTool):
    name = "rtk_run"
    description = (
        "Run a shell command through RTK (Rust Token Killer) for compressed output. "
        "params: command (str, e.g. 'git diff' or 'git log -n 10'). "
        "Returns JSON: {stdout (compressed), token_savings, returncode}. "
        "Requires rtk installed at ~/.local/bin/rtk or on PATH."
    )
    category = "productivity"

    async def execute(self, params: dict, agent: "AgentInstance" = None) -> str:
        command = params.get("command", "")
        if not command:
            return json.dumps({"error": "command is required"})

        rtk = _rtk_path()
        if not rtk:
            return json.dumps(
                {
                    "error": (
                        "rtk not found. Install from https://github.com/getrtk/rtk "
                        "or check ~/.local/bin/rtk"
                    )
                }
            )

        full_cmd = f"{rtk} {command}"
        try:
            proc = await asyncio.create_subprocess_shell(
                full_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_b, stderr_b = await proc.communicate()
            stdout = stdout_b.decode(errors="replace")
            stderr = stderr_b.decode(errors="replace")

            # RTK prints savings info to stderr — extract if present
            token_savings = ""
            for line in stderr.splitlines():
                if "%" in line or "token" in line.lower() or "saved" in line.lower():
                    token_savings = line.strip()
                    break

            return json.dumps(
                {
                    "stdout": stdout,
                    "token_savings": token_savings or "n/a",
                    "returncode": proc.returncode,
                }
            )
        except Exception as exc:
            logger.error("rtk_run failed: %s", exc)
            return json.dumps({"error": str(exc)})


class RtkWrapTool(BaseTool):
    name = "rtk_wrap"
    description = (
        "Compress an arbitrary text blob using RTK's read command. "
        "params: text (str), mode (str, default 'aggressive', options: aggressive|normal|minimal). "
        "Returns compressed text via 'rtk read {file} -l {mode}'. "
        "Use to reduce large tool outputs before passing to next LLM step."
    )
    category = "productivity"

    async def execute(self, params: dict, agent: "AgentInstance" = None) -> str:
        text = params.get("text", "")
        mode = params.get("mode", "aggressive")
        if mode not in ("aggressive", "normal", "minimal"):
            mode = "aggressive"

        if not text:
            return json.dumps({"error": "text is required"})

        rtk = _rtk_path()
        if not rtk:
            return json.dumps(
                {
                    "error": (
                        "rtk not found. Install from https://github.com/getrtk/rtk "
                        "or check ~/.local/bin/rtk"
                    )
                }
            )

        tmp = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".txt", delete=False, encoding="utf-8"
            ) as fh:
                fh.write(text)
                tmp = fh.name

            proc = await asyncio.create_subprocess_shell(
                f"{rtk} read {tmp} -l {mode}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_b, _ = await proc.communicate()
            compressed = stdout_b.decode(errors="replace")

            original_len = len(text)
            compressed_len = len(compressed)
            reduction = (
                round((1 - compressed_len / original_len) * 100)
                if original_len > 0
                else 0
            )

            return json.dumps(
                {
                    "compressed": compressed,
                    "original_chars": original_len,
                    "compressed_chars": compressed_len,
                    "reduction_pct": reduction,
                    "mode": mode,
                }
            )
        except Exception as exc:
            logger.error("rtk_wrap failed: %s", exc)
            return json.dumps({"error": str(exc)})
        finally:
            if tmp:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass


def register_rtk_tools(registry) -> None:
    registry.register(RtkRunTool())
    registry.register(RtkWrapTool())
    logger.debug("RTK tools registered (2 tools)")
