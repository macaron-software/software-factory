"""SSE streaming consumer — real-time agent output in terminal."""
import json
import os
import signal
import sys
import time
from typing import Generator

from . import _output as out

try:
    import httpx
except ImportError:
    httpx = None


def stream_sse(url: str, method: str = "GET", json_body: dict | None = None,
               headers: dict | None = None, timeout: float = 600) -> Generator[dict, None, None]:
    """Connect to an SSE endpoint and yield parsed events."""
    if httpx is None:
        out.error("httpx required for streaming")
        return
    h = {"Accept": "text/event-stream", **(headers or {})}
    with httpx.Client(timeout=httpx.Timeout(timeout, connect=10)) as client:
        if method == "POST":
            with client.stream("POST", url, json=json_body, headers=h) as resp:
                yield from _parse_sse(resp)
        else:
            with client.stream("GET", url, headers=h) as resp:
                yield from _parse_sse(resp)


def _parse_sse(resp) -> Generator[dict, None, None]:
    """Parse SSE text/event-stream into dicts."""
    event_type = None
    data_lines = []
    for line in resp.iter_lines():
        if line.startswith("event:"):
            event_type = line[6:].strip()
        elif line.startswith("data:"):
            data_lines.append(line[5:].strip())
        elif line == "" or line.startswith(":"):
            if data_lines:
                raw = "\n".join(data_lines)
                try:
                    payload = json.loads(raw)
                except (json.JSONDecodeError, ValueError):
                    payload = {"text": raw}
                payload["_event"] = event_type or "message"
                yield payload
                data_lines = []
                event_type = None
        # keepalive ": keepalive" lines are ignored


def print_stream(url: str, method: str = "GET", json_body: dict | None = None,
                 headers: dict | None = None) -> None:
    """Stream SSE events and print agent messages with colors."""
    current_agent = None
    for event in stream_sse(url, method, json_body, headers):
        evt = event.get("_event", "message")

        if evt == "chunk":
            # Streaming delta from LLM
            agent = event.get("agent", event.get("from_agent", ""))
            text = event.get("text", event.get("delta", event.get("content", "")))
            if agent and agent != current_agent:
                if current_agent is not None:
                    print()
                color = out.agent_color(agent)
                print(f"\n{out.c(f'[{agent}]', color + out._BOLD)}", end=" ", flush=True)
                current_agent = agent
            print(text, end="", flush=True)

        elif evt == "message":
            agent = event.get("from_agent", event.get("agent", ""))
            content = event.get("content", event.get("text", ""))
            if not content:
                continue
            if agent:
                color = out.agent_color(agent)
                print(f"\n{out.c(f'[{agent}]', color + out._BOLD)} {content}")
            else:
                print(content)
            current_agent = None

        elif evt == "done":
            html = event.get("html", "")
            text = event.get("text", event.get("content", ""))
            if text:
                print(f"\n{text}")
            elif html:
                # Strip HTML tags for terminal
                import re
                clean = re.sub(r'<[^>]+>', '', html)
                clean = clean.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
                if clean.strip():
                    print(f"\n{clean.strip()}")
            current_agent = None

        elif evt == "error":
            msg = event.get("message", event.get("error", str(event)))
            out.error(msg)
            break

        elif evt == "status":
            status = event.get("status", "")
            phase = event.get("phase", "")
            if phase:
                print(f"\n{out.dim(f'── Phase: {phase} ({status}) ──')}")
            elif status:
                print(f"\n{out.dim(f'── {status} ──')}")

        elif evt == "agent_status":
            # Agent loop status update
            name = event.get("name", "")
            status = event.get("status", "")
            if name:
                print(f"  {out.agent_color(name)}{name}{out._RESET}: {out.status_color(status)}")

    print()  # final newline


def run_headless(cmd_args: list[str], log_dir: str | None = None) -> int:
    """Fork the CLI command as a background process, return PID."""
    log_dir = log_dir or os.path.expanduser("~/.sf/runs")
    os.makedirs(log_dir, exist_ok=True)
    run_id = f"{int(time.time())}"
    log_file = os.path.join(log_dir, f"{run_id}.log")

    pid = os.fork()
    if pid > 0:
        # Parent
        out.info(f"Background run started — PID {pid}, log: {log_file}")
        out.info(f"  sf runs tail {run_id}")
        # Write PID file
        with open(os.path.join(log_dir, f"{run_id}.pid"), "w") as f:
            f.write(str(pid))
        with open(os.path.join(log_dir, f"{run_id}.cmd"), "w") as f:
            f.write(" ".join(cmd_args))
        return pid

    # Child — redirect stdout/stderr to log file
    os.setsid()
    with open(log_file, "w") as lf:
        os.dup2(lf.fileno(), sys.stdout.fileno())
        os.dup2(lf.fileno(), sys.stderr.fileno())
    # Re-exec without --headless
    args_clean = [a for a in cmd_args if a != "--headless"]
    os.execvp(sys.executable, [sys.executable] + args_clean)
    return 0  # unreachable


def list_runs(log_dir: str | None = None) -> list[dict]:
    """List active headless runs."""
    log_dir = log_dir or os.path.expanduser("~/.sf/runs")
    if not os.path.isdir(log_dir):
        return []
    runs = []
    for f in os.listdir(log_dir):
        if f.endswith(".pid"):
            run_id = f[:-4]
            pid_file = os.path.join(log_dir, f)
            cmd_file = os.path.join(log_dir, f"{run_id}.cmd")
            log_file = os.path.join(log_dir, f"{run_id}.log")
            try:
                with open(pid_file) as pf:
                    pid = int(pf.read().strip())
                cmd = ""
                if os.path.exists(cmd_file):
                    with open(cmd_file) as cf:
                        cmd = cf.read().strip()
                # Check if still running
                try:
                    os.kill(pid, 0)
                    alive = True
                except OSError:
                    alive = False
                runs.append({
                    "id": run_id, "pid": pid, "cmd": cmd,
                    "status": "running" if alive else "stopped",
                    "log": log_file,
                })
            except (ValueError, FileNotFoundError):
                continue
    return sorted(runs, key=lambda r: r["id"], reverse=True)


def tail_run(run_id: str, log_dir: str | None = None, lines: int = 50) -> None:
    """Tail a headless run log."""
    log_dir = log_dir or os.path.expanduser("~/.sf/runs")
    log_file = os.path.join(log_dir, f"{run_id}.log")
    if not os.path.exists(log_file):
        out.error(f"Run {run_id} not found")
        return
    import subprocess
    subprocess.run(["tail", "-f", "-n", str(lines), log_file])


def stop_run(run_id: str, log_dir: str | None = None) -> None:
    """Stop a headless run."""
    log_dir = log_dir or os.path.expanduser("~/.sf/runs")
    pid_file = os.path.join(log_dir, f"{run_id}.pid")
    if not os.path.exists(pid_file):
        out.error(f"Run {run_id} not found")
        return
    with open(pid_file) as f:
        pid = int(f.read().strip())
    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
        out.info(f"Stopped run {run_id} (PID {pid})")
    except (ProcessLookupError, PermissionError) as e:
        out.warn(f"Process {pid} already stopped: {e}")
