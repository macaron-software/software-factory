"""SSE streaming consumer — real-time agent output in terminal."""
import json
import os
import signal
import sys
import threading
import time
from typing import Generator

from . import _output as out

try:
    import httpx
except ImportError:
    httpx = None

# ── Spinner ──

_SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
_BRAILLE_PROGRESS = ["⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷"]


class _Spinner:
    """Animated spinner for waiting states."""

    def __init__(self, text: str = "Waiting for agents...", agent: str = ""):
        self._text = text
        self._agent = agent
        self._running = False
        self._thread = None
        self._frame = 0

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()

    def update(self, text: str, agent: str = ""):
        self._text = text
        self._agent = agent

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=1)
        # Clear spinner line
        sys.stderr.write("\r\033[K")
        sys.stderr.flush()

    def _spin(self):
        while self._running:
            frame = _SPINNER_FRAMES[self._frame % len(_SPINNER_FRAMES)]
            if self._agent:
                color = out.agent_color(self._agent)
                label = f"{color}{self._agent}{out._RESET}"
                line = f"\r  {out.c(frame, out._DIM)} {label} {out.dim(self._text)}"
            else:
                line = f"\r  {out.c(frame, out._DIM)} {out.dim(self._text)}"
            sys.stderr.write(f"{line}\033[K")
            sys.stderr.flush()
            self._frame += 1
            time.sleep(0.08)


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
                # Use event: line if present, else "type" from JSON, else "message"
                if event_type:
                    payload["_event"] = event_type
                elif "type" in payload:
                    payload["_event"] = payload["type"]
                else:
                    payload["_event"] = "message"
                yield payload
                data_lines = []
                event_type = None
        # keepalive ": keepalive" lines are ignored


def print_stream(url: str, method: str = "GET", json_body: dict | None = None,
                 headers: dict | None = None) -> None:
    """Stream SSE events and print agent messages with colors and animations."""
    current_agent = None
    spinner = _Spinner()
    spinner.start()
    chunk_buffer = []
    seen_msg_ids = set()  # deduplicate messages

    try:
        for event in stream_sse(url, method, json_body, headers):
            evt = event.get("_event", "message")

            if evt == "agent_status":
                name = event.get("agent_name", event.get("name", event.get("agent_id", "")))
                status = event.get("status", "")
                if status == "thinking":
                    spinner.update("thinking...", name)
                elif status == "idle":
                    spinner.update("waiting...", "")

            elif evt == "stream_start":
                # Agent starts generating — show header, keep spinner for first chunk
                name = event.get("agent_name", event.get("agent_id", ""))
                spinner.update("generating...", name)
                if current_agent is not None:
                    print()  # newline after prev agent
                current_agent = name
                chunk_buffer = []

            elif evt == "stream_delta":
                # LLM chunk — stop spinner on first chunk, print delta
                if spinner._running:
                    spinner.stop()
                delta = event.get("delta", event.get("text", ""))
                agent = event.get("agent_name", event.get("agent_id", current_agent or ""))
                if agent != current_agent or not chunk_buffer:
                    # Print agent header on first chunk
                    if current_agent and chunk_buffer:
                        print()
                    current_agent = agent
                    color = out.agent_color(agent)
                    print(f"\n{out.c(f'[{agent}]', color + out._BOLD)}", end=" ", flush=True)
                    chunk_buffer = []
                print(delta, end="", flush=True)
                chunk_buffer.append(delta)

            elif evt == "stream_end":
                if spinner._running:
                    spinner.stop()
                if chunk_buffer:
                    print()  # newline after streamed content
                    chunk_buffer = []
                # Restart spinner for next agent
                spinner = _Spinner("waiting for next agent...")
                spinner.start()

            elif evt in ("chunk",):
                # Generic chunk event (some endpoints use this)
                if spinner._running:
                    spinner.stop()
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
                if spinner._running:
                    spinner.stop()
                agent = event.get("from_agent", event.get("agent", ""))
                content = event.get("content", event.get("text", ""))
                msg_id = event.get("id", "")
                if not content:
                    continue
                # Deduplicate: skip if already shown (same id or same agent+content hash)
                dedup_key = msg_id or f"{agent}:{hash(content)}"
                if dedup_key in seen_msg_ids:
                    continue
                seen_msg_ids.add(dedup_key)
                # Skip if we already streamed it chunk-by-chunk
                if chunk_buffer:
                    chunk_buffer = []
                    continue
                if agent:
                    color = out.agent_color(agent)
                    print(f"\n{out.c(f'[{agent}]', color + out._BOLD)}")
                    print(out.render_md(content))
                else:
                    print(out.render_md(content))
                current_agent = agent

            elif evt == "delegation":
                if spinner._running:
                    spinner.stop()
                from_a = event.get("from", "")
                to_a = event.get("to", event.get("to_agent", ""))
                task = event.get("task", "")[:60]
                arrow = out.dim("→")
                fc = out.agent_color(from_a) if from_a else ""
                tc = out.agent_color(to_a) if to_a else ""
                label = f"  {fc}{from_a}{out._RESET} {arrow} {tc}{to_a}{out._RESET}"
                if task:
                    label += f" {out.dim(task)}"
                print(label)
                spinner = _Spinner("thinking...", to_a)
                spinner.start()

            elif evt == "conversation_end":
                if spinner._running:
                    spinner.stop()
                rounds = event.get("rounds", "")
                msgs = event.get("messages", "")
                print(f"\n{out.dim(f'── Conversation complete: {rounds} rounds, {msgs} messages ──')}")
                break

            elif evt == "done":
                if spinner._running:
                    spinner.stop()
                html = event.get("html", "")
                text = event.get("text", event.get("content", ""))
                if text:
                    print(f"\n{text}")
                elif html:
                    import re
                    clean = re.sub(r'<[^>]+>', '', html)
                    clean = clean.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
                    if clean.strip():
                        print(f"\n{clean.strip()}")
                current_agent = None
                break

            elif evt == "error":
                if spinner._running:
                    spinner.stop()
                msg = event.get("message", event.get("error", str(event)))
                out.error(msg)
                break

            elif evt == "status":
                status = event.get("status", "")
                phase = event.get("phase", "")
                if phase:
                    spinner.update(f"phase: {phase}", "")
                elif status:
                    spinner.update(status, "")

    except KeyboardInterrupt:
        pass
    finally:
        if spinner._running:
            spinner.stop()

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
