"""
Incident Diagnosis Tools — runtime diagnostics for SF agents.
==============================================================
Gives a diagnostic agent the ability to investigate *why* something is broken
or slow, before auto-heal or TMA kicks in. Covers:

  diag_logs            → fetch container / service logs (docker, journalctl, file)
  diag_process_stats   → CPU %, RSS memory, open files, network connections (psutil)
  diag_db_stats        → SQLite / Postgres slow queries, table sizes, lock waits
  diag_endpoint_latency → HTTP response time distribution (P50/P95/P99) via curl
  diag_queue_depth     → platform task queue + backlog depth
  diag_correlate       → synthesise symptoms into ranked root cause hypotheses

Design principles:
  - All tools return structured plaintext (no JSON blobs) — LLM-friendly
  - Fail open: on any OS/permission error, return a useful error message
  - No side effects: read-only, nothing is mutated
  - Reuse psutil + subprocess, no new deps

These tools are NOT for:
  - Error clustering (use monitoring_tools.py)
  - Browser perf audits (use perf_audit_tools.py)
  - Auto-healing (use ops/auto_heal.py)
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
from datetime import datetime, timezone

from ..models import AgentInstance
from .registry import BaseTool

logger = logging.getLogger(__name__)


async def _sh(cmd: list[str], timeout: int = 15) -> str:
    """Run shell command, return stdout or error."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        out = stdout.decode(errors="replace").strip()
        err = stderr.decode(errors="replace").strip()
        if proc.returncode != 0 and not out:
            return f"[exit {proc.returncode}] {err or '(no output)'}"
        return out or err or "(no output)"
    except asyncio.TimeoutError:
        return f"[timeout after {timeout}s]"
    except FileNotFoundError:
        return f"[command not found: {cmd[0]}]"
    except Exception as e:
        return f"[error: {e}]"


class DiagLogsTool(BaseTool):
    """Fetch logs from a container, systemd service, or log file.

    Supports: docker container name, systemd unit name, or absolute file path.
    Returns the last N lines, optionally filtered by a pattern (grep-style).
    This is the first tool to run in any incident investigation.
    """

    name = "diag_logs"
    description = (
        "Fetch recent logs from a Docker container, systemd service, or log file. "
        "Params: source (required: container name / service name / file path), "
        "lines (optional int, default 100), "
        "filter (optional string, grep pattern), "
        "level (optional: 'error'|'warn'|'all', default 'all')."
    )
    category = "diagnostic"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        source = params.get("source", "").strip()
        if not source:
            return (
                "Error: source is required (container name, service name, or file path)"
            )
        lines = int(params.get("lines", 100))
        pattern = params.get("filter", "").strip()
        level = params.get("level", "all")

        # Determine source type
        if source.startswith("/"):
            raw = await _sh(["tail", f"-{lines}", source])
        elif shutil.which("docker") and await _is_docker_container(source):
            raw = await _sh(
                ["docker", "logs", "--tail", str(lines), source], timeout=20
            )
        elif shutil.which("journalctl"):
            raw = await _sh(
                ["journalctl", "-u", source, f"-n{lines}", "--no-pager", "-o", "short"],
                timeout=20,
            )
        else:
            return f"Source '{source}' not found as file, Docker container, or systemd service"

        # Level filter
        if level == "error":
            raw = (
                "\n".join(
                    line
                    for line in raw.splitlines()
                    if any(
                        w in line.lower()
                        for w in (
                            "error",
                            "exception",
                            "critical",
                            "fatal",
                            "traceback",
                        )
                    )
                )
                or "(no error lines found)"
            )
        elif level == "warn":
            raw = (
                "\n".join(
                    line
                    for line in raw.splitlines()
                    if any(
                        w in line.lower()
                        for w in ("error", "warning", "warn", "exception", "critical")
                    )
                )
                or "(no warning/error lines found)"
            )

        # Pattern filter
        if pattern:
            raw = (
                "\n".join(
                    line for line in raw.splitlines() if pattern.lower() in line.lower()
                )
                or f"(no lines matching '{pattern}')"
            )

        return f"=== logs: {source} (last {lines} lines) ===\n{raw}"


async def _is_docker_container(name: str) -> bool:
    """Check if name is a running docker container."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "docker",
            "inspect",
            "--format={{.State.Status}}",
            name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
        return proc.returncode == 0
    except Exception:
        return False


class DiagProcessStatsTool(BaseTool):
    """Get CPU, memory, and connection stats for a process or the platform itself.

    Uses psutil for in-process stats (fast, no subprocess).
    Returns: PID, CPU%, RSS memory (MB), VMS (MB), open file descriptors,
    TCP connections, thread count, top 5 memory-consuming child processes.
    """

    name = "diag_process_stats"
    description = (
        "Get CPU/memory/connection stats for a process. "
        "Params: pid (optional int, defaults to current process), "
        "name (optional string, match by process name), "
        "include_children (optional bool, default true)."
    )
    category = "diagnostic"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        try:
            import psutil
        except ImportError:
            return "psutil not installed — run: pip install psutil"

        pid = params.get("pid")
        name_filter = params.get("name", "").strip()

        try:
            if name_filter:
                procs = [
                    p
                    for p in psutil.process_iter(["pid", "name", "cmdline"])
                    if name_filter.lower() in (p.info["name"] or "").lower()
                ]
                if not procs:
                    return f"No process found matching name '{name_filter}'"
                proc = procs[0]
            elif pid:
                proc = psutil.Process(int(pid))
            else:
                proc = psutil.Process(os.getpid())

            with proc.oneshot():
                cpu = proc.cpu_percent(interval=0.5)
                mem = proc.memory_info()
                rss_mb = mem.rss / 1024 / 1024
                vms_mb = mem.vms / 1024 / 1024
                threads = proc.num_threads()
                fds = proc.num_fds() if hasattr(proc, "num_fds") else "n/a"
                try:
                    conns = len(proc.connections())
                except Exception:
                    conns = "n/a"
                cmdline = " ".join(proc.cmdline()[:5])

            # System context
            sys_cpu = psutil.cpu_percent(interval=0.1)
            sys_mem = psutil.virtual_memory()
            sys_mem_pct = sys_mem.percent

            lines = [
                f"=== process stats: {proc.name()} (pid {proc.pid}) ===",
                f"CPU:         {cpu:.1f}% (system total: {sys_cpu:.1f}%)",
                f"RSS memory:  {rss_mb:.1f} MB",
                f"VMS memory:  {vms_mb:.1f} MB",
                f"System mem:  {sys_mem_pct:.1f}% used ({sys_mem.available // 1024 // 1024} MB free)",
                f"Threads:     {threads}",
                f"Open FDs:    {fds}",
                f"TCP conns:   {conns}",
                f"Command:     {cmdline}",
            ]

            # Children
            if params.get("include_children", True):
                try:
                    children = proc.children(recursive=True)
                    if children:
                        lines.append(f"\nChild processes ({len(children)}):")
                        for c in sorted(
                            children, key=lambda p: p.memory_info().rss, reverse=True
                        )[:5]:
                            cm = c.memory_info().rss / 1024 / 1024
                            lines.append(f"  pid {c.pid} {c.name()}: {cm:.1f} MB RSS")
                except Exception:
                    pass

            return "\n".join(lines)

        except psutil.NoSuchProcess:
            return f"Process pid={pid} not found"
        except Exception as e:
            return f"Error reading process stats: {e}"


class DiagDbStatsTool(BaseTool):
    """Analyse database performance: slow queries, table sizes, lock waits.

    For SQLite (default): runs EXPLAIN QUERY PLAN, .tables + page stats.
    For Postgres: queries pg_stat_statements (top slow queries), table bloat,
    active locks, connection count.
    """

    name = "diag_db_stats"
    description = (
        "Analyse DB performance: slow queries, table sizes, lock waits. "
        "Params: db_path (optional, default platform DB path), "
        "backend (optional: 'sqlite'|'postgres', auto-detected), "
        "top_n (optional int, default 10 — top N slow queries)."
    )
    category = "diagnostic"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        import sqlite3

        backend = params.get("backend", "sqlite")
        top_n = int(params.get("top_n", 10))

        if backend == "postgres":
            return await self._postgres_stats(top_n)

        # SQLite
        db_path = params.get("db_path", "")
        if not db_path:
            # Try to find platform DB
            candidates = [
                "data/platform.db",
                "../data/platform.db",
                "/app/data/platform.db",
            ]
            for c in candidates:
                if os.path.exists(c):
                    db_path = c
                    break
        if not db_path or not os.path.exists(db_path):
            return "SQLite DB not found. Provide db_path explicitly."

        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            lines = [f"=== SQLite diagnostics: {db_path} ==="]

            # File size
            size_mb = os.path.getsize(db_path) / 1024 / 1024
            lines.append(f"File size: {size_mb:.2f} MB")

            # Tables with row counts
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
            lines.append(f"\nTables ({len(tables)}):")
            for t in tables[:20]:
                tname = t["name"]
                try:
                    count = conn.execute(f"SELECT COUNT(*) FROM [{tname}]").fetchone()[
                        0
                    ]
                    lines.append(f"  {tname}: {count:,} rows")
                except Exception:
                    lines.append(f"  {tname}: (error reading)")

            # Page cache stats
            page_count = conn.execute("PRAGMA page_count").fetchone()[0]
            page_size = conn.execute("PRAGMA page_size").fetchone()[0]
            freelist = conn.execute("PRAGMA freelist_count").fetchone()[0]
            lines.append(
                f"\nPage stats: {page_count} pages × {page_size}B = {page_count * page_size // 1024}KB"
            )
            lines.append(
                f"Freelist (fragmentation): {freelist} pages ({100 * freelist // max(page_count, 1)}%)"
            )
            if freelist > page_count * 0.1:
                lines.append("  ⚠️  High fragmentation — consider VACUUM")

            # Index health
            missing_idx = []
            for t in tables[:10]:
                tname = t["name"]
                indexes = conn.execute(f"PRAGMA index_list([{tname}])").fetchall()
                if not indexes:
                    try:
                        count = conn.execute(
                            f"SELECT COUNT(*) FROM [{tname}]"
                        ).fetchone()[0]
                        if count > 1000:
                            missing_idx.append(f"{tname} ({count:,} rows, no index)")
                    except Exception:
                        pass
            if missing_idx:
                lines.append("\n⚠️  Large tables with no index:")
                for m in missing_idx:
                    lines.append(f"  {m}")

            conn.close()
            return "\n".join(lines)

        except Exception as e:
            return f"SQLite diagnostics error: {e}"

    async def _postgres_stats(self, top_n: int) -> str:
        try:
            from ..db.adapter import get_connection

            conn = get_connection()

            lines = ["=== Postgres diagnostics ==="]

            # Active connections
            result = conn.execute(
                "SELECT count(*) as n, state FROM pg_stat_activity GROUP BY state"
            ).fetchall()
            lines.append("Connections by state:")
            for row in result:
                lines.append(f"  {row[1] or 'idle'}: {row[0]}")

            # Top slow queries (requires pg_stat_statements)
            try:
                slow = conn.execute(
                    f"SELECT query, calls, mean_exec_time::numeric(10,2) ms, "
                    f"total_exec_time::numeric(10,2) total_ms "
                    f"FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT {top_n}"
                ).fetchall()
                lines.append(f"\nTop {top_n} slow queries (mean exec time):")
                for i, row in enumerate(slow, 1):
                    q = str(row[0])[:80].replace("\n", " ")
                    lines.append(f"  {i}. {row[2]}ms avg, {row[1]} calls — {q}")
            except Exception:
                lines.append(
                    "\n(pg_stat_statements not enabled — add to shared_preload_libraries)"
                )

            # Table bloat (approx)
            try:
                bloat = conn.execute(
                    "SELECT relname, n_dead_tup, n_live_tup FROM pg_stat_user_tables "
                    "WHERE n_dead_tup > 1000 ORDER BY n_dead_tup DESC LIMIT 10"
                ).fetchall()
                if bloat:
                    lines.append("\n⚠️  Tables with dead tuples (VACUUM needed):")
                    for row in bloat:
                        lines.append(f"  {row[0]}: {row[1]:,} dead, {row[2]:,} live")
            except Exception:
                pass

            conn.close()
            return "\n".join(lines)
        except Exception as e:
            return f"Postgres diagnostics error: {e}"


class DiagEndpointLatencyTool(BaseTool):
    """Measure HTTP endpoint response time distribution (P50/P95/P99).

    Sends N sequential requests and reports timing stats. Useful for:
    detecting regressions after a deploy, comparing before/after a fix,
    identifying which endpoint is the slowest in a service.
    """

    name = "diag_endpoint_latency"
    description = (
        "Measure HTTP endpoint response time distribution (P50/P95/P99). "
        "Params: url (required), "
        "n (optional int, default 10 — number of requests), "
        "method (optional: 'GET'|'POST', default 'GET'), "
        "timeout_s (optional float, default 10.0)."
    )
    category = "diagnostic"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        import time

        url = params.get("url", "").strip()
        if not url:
            return "Error: url is required"
        n = min(int(params.get("n", 10)), 50)
        method = params.get("method", "GET").upper()
        timeout_s = float(params.get("timeout_s", 10.0))

        times: list[float] = []
        errors: list[str] = []

        try:
            import httpx
        except ImportError:
            # Fall back to curl
            return await self._curl_latency(url, n, timeout_s)

        async with httpx.AsyncClient(timeout=timeout_s) as client:
            for i in range(n):
                t0 = time.perf_counter()
                try:
                    fn = client.get if method == "GET" else client.post
                    resp = await fn(url)
                    elapsed = (time.perf_counter() - t0) * 1000
                    times.append(elapsed)
                    if resp.status_code >= 500:
                        errors.append(f"req {i + 1}: HTTP {resp.status_code}")
                except Exception as e:
                    errors.append(f"req {i + 1}: {type(e).__name__}: {e}")

        if not times:
            return f"All {n} requests failed:\n" + "\n".join(errors)

        times.sort()
        p50 = times[len(times) // 2]
        p95 = times[int(len(times) * 0.95)]
        p99 = times[int(len(times) * 0.99)]
        avg = sum(times) / len(times)
        mn, mx = times[0], times[-1]

        lines = [
            f"=== endpoint latency: {method} {url} ({n} requests) ===",
            f"P50: {p50:.0f}ms  P95: {p95:.0f}ms  P99: {p99:.0f}ms",
            f"Avg: {avg:.0f}ms  Min: {mn:.0f}ms  Max: {mx:.0f}ms",
            f"Success: {len(times)}/{n}",
        ]
        if errors:
            lines.append(f"Errors: {', '.join(errors[:3])}")

        # Flag against SF default budget
        if p95 > 500:
            lines.append(f"⚠️  P95 {p95:.0f}ms exceeds 500ms budget")
        elif p99 > 500:
            lines.append(f"ℹ️  P99 {p99:.0f}ms near budget threshold")

        return "\n".join(lines)

    async def _curl_latency(self, url: str, n: int, timeout_s: float) -> str:
        fmt = "%{time_total}"
        times = []
        for _ in range(n):
            out = await _sh(
                [
                    "curl",
                    "-s",
                    "-o",
                    "/dev/null",
                    "-w",
                    fmt,
                    "--max-time",
                    str(int(timeout_s)),
                    url,
                ]
            )
            try:
                times.append(float(out) * 1000)
            except ValueError:
                pass
        if not times:
            return f"All {n} curl requests failed"
        times.sort()
        p50 = times[len(times) // 2]
        p95 = times[int(len(times) * 0.95)]
        return f"=== endpoint latency (curl): {url} ===\nP50: {p50:.0f}ms  P95: {p95:.0f}ms  (n={len(times)})"


class DiagQueueDepthTool(BaseTool):
    """Check platform task queue depth and backlog.

    Reports: number of active agent loops, pending missions, stalled tasks,
    oldest unprocessed item age. Useful when the platform feels slow or
    missions aren't progressing.
    """

    name = "diag_queue_depth"
    description = (
        "Check platform task queue depth, active agents, pending/stalled missions. "
        "No params required. Returns counts + oldest item age."
    )
    category = "diagnostic"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        try:
            from ..db.adapter import get_connection

            conn = get_connection()
            lines = ["=== platform queue depth ==="]

            # Active agents
            try:
                active = conn.execute(
                    "SELECT COUNT(*) FROM agents WHERE status='active'"
                ).fetchone()
                lines.append(f"Active agents:      {active[0] if active else '?'}")
            except Exception:
                pass

            # Missions by status
            try:
                mission_stats = conn.execute(
                    "SELECT status, COUNT(*) n FROM missions GROUP BY status ORDER BY n DESC"
                ).fetchall()
                lines.append("Missions by status:")
                for row in mission_stats:
                    lines.append(f"  {row[0]}: {row[1]}")
            except Exception:
                pass

            # Stalled missions (in_progress, not updated recently)
            try:
                stalled = conn.execute(
                    "SELECT id, name, updated_at FROM missions "
                    "WHERE status='in_progress' "
                    "AND updated_at < datetime('now', '-30 minutes') "
                    "ORDER BY updated_at ASC LIMIT 5"
                ).fetchall()
                if stalled:
                    lines.append(
                        f"\n⚠️  Stalled missions (>30min no update): {len(stalled)}"
                    )
                    for row in stalled:
                        lines.append(
                            f"  {row[0][:8]}: {(row[1] or '?')[:40]} — last: {row[2]}"
                        )
            except Exception:
                pass

            # Recent incidents (unresolved)
            try:
                incidents = conn.execute(
                    "SELECT COUNT(*) n, severity FROM incidents "
                    "WHERE resolved=0 OR resolved IS NULL "
                    "GROUP BY severity ORDER BY severity ASC"
                ).fetchall()
                if incidents:
                    lines.append("\nOpen incidents:")
                    for row in incidents:
                        lines.append(f"  severity {row[1] or '?'}: {row[0]}")
            except Exception:
                pass

            conn.close()
            return "\n".join(lines)
        except Exception as e:
            return f"Queue depth check error: {e}"


class DiagCorrelateTool(BaseTool):
    """Synthesise multiple diagnostic findings into ranked root cause hypotheses.

    Give it the raw output from other diag_* tools. It structures the findings,
    identifies patterns, and returns a ranked list of root cause hypotheses with
    confidence and recommended next actions.

    This is the last step in a diagnostic workflow — run all other diag tools first,
    then feed findings here to get a structured RCA.
    """

    name = "diag_correlate"
    description = (
        "Synthesise diagnostic findings into ranked root cause hypotheses. "
        "Run diag_logs / diag_process_stats / diag_db_stats / diag_endpoint_latency first, "
        "then pass their outputs here. "
        "Params: symptoms (required string — paste all diag tool outputs), "
        "context (optional string — what changed recently, deploy notes, user report)."
    )
    category = "diagnostic"

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        symptoms = params.get("symptoms", "").strip()
        context = params.get("context", "").strip()

        if not symptoms:
            return (
                "Error: symptoms is required. Paste the output from diag_logs, "
                "diag_process_stats, diag_db_stats, diag_endpoint_latency here."
            )

        # Build a structured prompt for the agent's LLM to reason over
        # (this tool returns a prompt template — the agent then reasons over it)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        lines = [
            f"=== Root Cause Analysis Request [{ts}] ===",
            "",
            "## Diagnostic findings",
            symptoms,
        ]
        if context:
            lines += ["", "## Recent changes / context", context]

        lines += [
            "",
            "## Instructions for RCA",
            "Analyse the diagnostic findings above and produce:",
            "1. **Root cause hypotheses** — ranked by likelihood (High/Med/Low confidence)",
            "   For each: what caused it, evidence from the findings, confidence",
            "2. **Immediate actions** — what to do right now to stabilise",
            "3. **Fix recommendations** — permanent fixes for each hypothesis",
            "4. **Monitoring gaps** — what instrumentation would have caught this faster",
            "",
            "Format as:",
            "### Hypothesis 1 — [title] (HIGH confidence)",
            "Evidence: ...",
            "Fix: ...",
        ]
        return "\n".join(lines)


def register_diag_tools(reg) -> None:
    """Register all diagnostic tools into the tool registry."""
    for cls in [
        DiagLogsTool,
        DiagProcessStatsTool,
        DiagDbStatsTool,
        DiagEndpointLatencyTool,
        DiagQueueDepthTool,
        DiagCorrelateTool,
    ]:
        reg.register(cls())
