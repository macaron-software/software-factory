"""
Subprocess Utilities - Unified process management
=================================================
Centralizes subprocess creation, timeout handling, and process group cleanup.

Every subprocess in the Factory MUST use these helpers to ensure:
- start_new_session=True (always, for process group isolation)
- os.killpg() on timeout (kills children too)
- Proper stderr capture even on timeout
- Daemon child process registration/cleanup

Usage:
    from core.subprocess_util import run_subprocess, run_subprocess_streaming

    rc, stdout, stderr = await run_subprocess("cargo build", timeout=300, cwd="/path")
    rc, output = await run_subprocess_streaming("opencode run ...", timeout=900, log_fn=log)
"""

import asyncio
import os
import signal
from typing import Callable, Optional, Tuple


async def run_subprocess(
    cmd: str,
    timeout: int,
    cwd: str = None,
    env: dict = None,
    log_fn: Callable[[str, str], None] = None,
    register_pgroup: bool = False,
) -> Tuple[int, str, str]:
    """
    Run a subprocess with process group isolation and proper cleanup.

    Args:
        cmd: Shell command to run
        timeout: Timeout in seconds
        cwd: Working directory
        env: Environment variables (defaults to os.environ)
        log_fn: Optional log function(msg, level)
        register_pgroup: Register with daemon for shutdown cleanup

    Returns:
        Tuple of (returncode, stdout, stderr)
        On timeout: returncode=-1, stdout=partial, stderr="timeout"
    """
    proc = await asyncio.create_subprocess_shell(
        cmd,
        cwd=cwd,
        env=env or dict(os.environ),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=True,
    )

    if register_pgroup:
        from core.daemon import register_child_pgroup, unregister_child_pgroup
        register_child_pgroup(proc.pid)

    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(), timeout=timeout,
        )
        if register_pgroup:
            unregister_child_pgroup(proc.pid)
        return (
            proc.returncode,
            stdout_bytes.decode(errors="replace"),
            stderr_bytes.decode(errors="replace"),
        )
    except asyncio.TimeoutError:
        _kill_process_group(proc.pid)
        await proc.wait()
        if register_pgroup:
            unregister_child_pgroup(proc.pid)
        if log_fn:
            log_fn(f"Process timeout ({timeout}s) - killed process group: {cmd[:80]}", "WARN")
        return -1, "", f"timeout after {timeout}s"


async def run_subprocess_exec(
    args: list,
    timeout: int,
    cwd: str = None,
    env: dict = None,
    stdin_data: bytes = None,
    merge_stderr: bool = False,
    log_fn: Callable[[str, str], None] = None,
    register_pgroup: bool = False,
) -> Tuple[int, str, str]:
    """
    Run a subprocess with exec (no shell) and process group isolation.

    Args:
        args: Command as list of strings
        timeout: Timeout in seconds
        cwd: Working directory
        env: Environment variables
        stdin_data: Data to send to stdin
        merge_stderr: Merge stderr into stdout stream
        log_fn: Optional log function(msg, level)
        register_pgroup: Register with daemon for shutdown cleanup

    Returns:
        Tuple of (returncode, stdout, stderr)
        When merge_stderr=True, stderr is empty string.
    """
    stderr_target = asyncio.subprocess.STDOUT if merge_stderr else asyncio.subprocess.PIPE

    proc = await asyncio.create_subprocess_exec(
        *args,
        cwd=cwd,
        env=env or dict(os.environ),
        stdin=asyncio.subprocess.PIPE if stdin_data else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=stderr_target,
        start_new_session=True,
    )

    if register_pgroup:
        from core.daemon import register_child_pgroup, unregister_child_pgroup
        register_child_pgroup(proc.pid)

    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(input=stdin_data), timeout=timeout,
        )
        if register_pgroup:
            unregister_child_pgroup(proc.pid)
        return (
            proc.returncode,
            stdout_bytes.decode(errors="replace") if stdout_bytes else "",
            stderr_bytes.decode(errors="replace") if stderr_bytes else "",
        )
    except asyncio.TimeoutError:
        _kill_process_group(proc.pid)
        await proc.wait()
        if register_pgroup:
            unregister_child_pgroup(proc.pid)
        if log_fn:
            log_fn(f"Process timeout ({timeout}s) - killed process group: {args[0]}", "WARN")
        return -1, "", f"timeout after {timeout}s"


async def run_subprocess_streaming(
    cmd: list,
    timeout: int,
    cwd: str = None,
    env: dict = None,
    progress_interval: int = 60,
    stuck_timeout: int = 600,
    stale_timeout: int = 180,
    log_fn: Callable[[str, str], None] = None,
) -> Tuple[int, str]:
    """
    Run subprocess with streaming output and stuck/stale detection.

    Used for long-running LLM agent calls (opencode, claude).

    Args:
        cmd: Command as list of strings (exec, not shell)
        timeout: Max absolute timeout in seconds
        cwd: Working directory
        env: Environment variables
        progress_interval: Seconds between progress logs
        stuck_timeout: Seconds with 0 output before declaring stuck
        stale_timeout: Seconds with no new output (after producing some) before declaring stale
        log_fn: Optional log function(msg, level)

    Returns:
        Tuple of (returncode, output)
        returncode: -2 for stuck, -3 for stale, -1 for max timeout
    """
    from core.daemon import register_child_pgroup, unregister_child_pgroup

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=cwd,
        env=env or dict(os.environ),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        start_new_session=True,
    )

    register_child_pgroup(proc.pid)
    output_chunks = []
    start_time = asyncio.get_event_loop().time()
    last_progress_time = start_time
    last_progress_len = 0
    last_output_time = start_time
    exit_reason = None

    async def read_stream():
        nonlocal last_progress_time, last_progress_len, last_output_time, exit_reason
        while True:
            try:
                chunk = await asyncio.wait_for(
                    proc.stdout.read(4096), timeout=progress_interval,
                )
                if not chunk:
                    break
                output_chunks.append(chunk.decode(errors="replace"))

                now = asyncio.get_event_loop().time()
                current_len = sum(len(c) for c in output_chunks)
                if current_len > last_progress_len:
                    last_output_time = now

                if now - last_progress_time >= progress_interval:
                    elapsed = int(now - start_time)
                    delta = current_len - last_progress_len
                    if log_fn:
                        log_fn(f"[STREAM] {elapsed}s | +{delta} chars | total {current_len} chars", "DEBUG")
                    last_progress_time = now
                    last_progress_len = current_len

            except asyncio.TimeoutError:
                if proc.returncode is not None:
                    break
                now = asyncio.get_event_loop().time()
                elapsed = int(now - start_time)
                current_len = sum(len(c) for c in output_chunks)
                stale_duration = int(now - last_output_time)

                if log_fn:
                    log_fn(f"[STREAM] {elapsed}s | waiting... | {current_len} chars | stale {stale_duration}s", "DEBUG")

                if current_len == 0 and elapsed > stuck_timeout:
                    exit_reason = "stuck"
                    return
                if current_len > 0 and stale_duration > stale_timeout:
                    exit_reason = "stale"
                    return
                if elapsed > timeout:
                    exit_reason = "max_timeout"
                    return

    try:
        await read_stream()
        if exit_reason:
            raise asyncio.TimeoutError(exit_reason)
        await proc.wait()
        unregister_child_pgroup(proc.pid)
        return proc.returncode, "".join(output_chunks)

    except asyncio.TimeoutError:
        _kill_process_group(proc.pid)
        await proc.wait()
        unregister_child_pgroup(proc.pid)
        elapsed = int(asyncio.get_event_loop().time() - start_time)
        current_len = sum(len(c) for c in output_chunks)

        if exit_reason == "stuck":
            if log_fn:
                log_fn(f"STUCK: {elapsed}s with 0 chars - likely rate limited", "WARN")
            return -2, "".join(output_chunks)
        elif exit_reason == "stale":
            if log_fn:
                log_fn(f"STALE: No new output for {int(asyncio.get_event_loop().time() - last_output_time)}s after {current_len} chars", "WARN")
            return -3, "".join(output_chunks)
        else:
            if log_fn:
                log_fn(f"MAX TIMEOUT {elapsed}s - killed process group", "ERROR")
            return -1, "".join(output_chunks)


def _kill_process_group(pid: int, max_retries: int = 3):
    """
    Kill an entire process group with verification and retry.

    Ensures the process is actually dead before returning, preventing
    orphaned processes from being reparented to init (parent=1).
    """
    import time

    for attempt in range(max_retries):
        try:
            pgid = os.getpgid(pid)
            os.killpg(pgid, signal.SIGKILL)

            # Verify process is dead (check 5 times over 500ms)
            for check in range(5):
                time.sleep(0.1)
                try:
                    os.getpgid(pid)  # If this succeeds, process still alive
                except ProcessLookupError:
                    # Process dead, success
                    return

            # Still alive after 500ms, retry kill
            if attempt < max_retries - 1:
                continue

        except ProcessLookupError:
            # Process already dead = success
            return
        except OSError as e:
            # Permission error or other OS error
            if attempt < max_retries - 1:
                time.sleep(0.2)
                continue
            # Final attempt failed, log but don't crash
            return

    # Failed to kill after retries (process may be stuck in D state)
    # Log but don't crash - watchdog will clean up later
