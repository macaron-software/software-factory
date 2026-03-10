"""Shared low-level helpers for tool modules."""

from __future__ import annotations

import asyncio
import json
import urllib.request

_TIMEOUT = 10


def get_json(url: str) -> dict:
    """HTTP GET → parsed JSON. Raises on non-2xx or timeout."""
    req = urllib.request.Request(url, headers={"User-Agent": "sf-agent/1.0"})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return json.loads(resp.read().decode())


async def run_proc(
    cmd: list[str], cwd: str | None = None, timeout: float = 30.0
) -> tuple[int, str]:
    """Run a subprocess, return (returncode, combined stdout+stderr)."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        output = (
            stdout.decode(errors="replace") + stderr.decode(errors="replace")
        ).strip()
        return proc.returncode, output
    except FileNotFoundError:
        return -1, f"{cmd[0]}: command not found"
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except Exception:
            pass
        return -2, f"Timeout ({timeout}s) exceeded running {cmd[0]}"
    except Exception as exc:
        return 1, str(exc)
