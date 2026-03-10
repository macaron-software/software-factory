"""Platform Metrics Collector — in-memory counters + periodic DB flush.

Tracks:
- HTTP requests (method, path, status_code, duration_ms)
- MCP tool calls (tool_name, duration_ms, success/error)
- RLM anonymizations (field_type, count)
- DB queries (table, operation read/write)
- LLM provider costs (provider, model, cost_usd)

All counters are thread-safe (threading.Lock) and flushed to
`platform_metrics_log` every 60s for historical queries.

Usage:
    from platform.metrics.collector import get_collector
    c = get_collector()
    c.track_request("GET", "/api/monitoring/live", 200, 12.5)
    c.track_mcp_call("platform_agents", 45.0, True)
    c.track_anonymization("email", 3)
    snapshot = c.snapshot()
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any


@dataclass
class _Counter:
    count: int = 0
    total_ms: float = 0.0
    errors: int = 0
    last_at: float = 0.0


class MetricsCollector:
    """In-memory metrics with thread-safe counters."""

    def __init__(self):
        self._lock = threading.Lock()
        self._start_time = time.time()

        # HTTP requests: {(method, path_prefix) -> _Counter}
        self._http: dict[tuple[str, str], _Counter] = defaultdict(_Counter)
        self._http_total = _Counter()
        self._http_status: dict[int, int] = defaultdict(int)

        # MCP tool calls: {tool_name -> _Counter}
        self._mcp: dict[str, _Counter] = defaultdict(_Counter)
        self._mcp_total = _Counter()

        # Anonymizations: {field_type -> count}
        self._anon: dict[str, int] = defaultdict(int)
        self._anon_total = 0

        # DB queries: {(table, op) -> count}
        self._db_queries: dict[str, int] = defaultdict(int)
        self._db_total = _Counter()

        # LLM costs by provider: {provider -> {calls, cost_usd, tokens_in, tokens_out}}
        self._llm_costs: dict[str, dict[str, float]] = defaultdict(
            lambda: {"calls": 0, "cost_usd": 0.0, "tokens_in": 0, "tokens_out": 0}
        )

        # Per-endpoint latencies (keep last N for p95)
        self._endpoint_latencies: dict[str, list[float]] = defaultdict(list)
        self._max_latencies = 200  # keep last 200 per endpoint

        # rtk (Rust Token Killer) savings tracking
        # https://github.com/rtk-ai/rtk
        self._rtk_calls: int = 0
        self._rtk_bytes_raw: int = 0
        self._rtk_bytes_compressed: int = 0

    # ── HTTP Tracking ──

    def track_request(
        self, method: str, path: str, status_code: int, duration_ms: float
    ):
        prefix = _path_prefix(path)
        with self._lock:
            c = self._http[(method, prefix)]
            c.count += 1
            c.total_ms += duration_ms
            c.last_at = time.time()
            if status_code >= 400:
                c.errors += 1
            self._http_total.count += 1
            self._http_total.total_ms += duration_ms
            if status_code >= 400:
                self._http_total.errors += 1
            self._http_status[status_code] += 1
            key = f"{method} {prefix}"
            self._endpoint_latencies[key].append(duration_ms)
            if len(self._endpoint_latencies[key]) > self._max_latencies:
                self._endpoint_latencies[key] = self._endpoint_latencies[key][
                    -self._max_latencies :
                ]

    # ── MCP Tracking ──

    def track_mcp_call(self, tool_name: str, duration_ms: float, success: bool):
        with self._lock:
            c = self._mcp[tool_name]
            c.count += 1
            c.total_ms += duration_ms
            c.last_at = time.time()
            if not success:
                c.errors += 1
            self._mcp_total.count += 1
            self._mcp_total.total_ms += duration_ms
            if not success:
                self._mcp_total.errors += 1

    # ── Anonymization Tracking ──

    def track_anonymization(self, field_type: str, count: int = 1):
        with self._lock:
            self._anon[field_type] += count
            self._anon_total += count

    # ── DB Query Tracking ──

    def track_db_query(self, operation: str = "read"):
        with self._lock:
            self._db_queries[operation] += 1
            self._db_total.count += 1

    # ── LLM Cost Tracking ──

    def track_llm_cost(
        self,
        provider: str,
        model: str,
        cost_usd: float,
        tokens_in: int = 0,
        tokens_out: int = 0,
    ):
        key = f"{provider}/{model}"
        with self._lock:
            d = self._llm_costs[key]
            d["calls"] += 1
            d["cost_usd"] += cost_usd
            d["tokens_in"] += tokens_in
            d["tokens_out"] += tokens_out

    # ── rtk Savings Tracking ──

    def track_rtk_call(self, bytes_raw: int, bytes_compressed: int):
        """Track one rtk-wrapped command: original vs compressed output size."""
        with self._lock:
            self._rtk_calls += 1
            self._rtk_bytes_raw += bytes_raw
            self._rtk_bytes_compressed += bytes_compressed

    # ── Snapshot ──

    def snapshot(self) -> dict[str, Any]:
        """Return full metrics snapshot for /api/monitoring/live."""
        with self._lock:
            uptime = time.time() - self._start_time

            # HTTP
            top_endpoints = sorted(
                [
                    (
                        ep,
                        len(lats),
                        round(sum(lats) / len(lats), 1),
                        round(sorted(lats)[int(len(lats) * 0.95)] if lats else 0, 1),
                    )
                    for ep, lats in self._endpoint_latencies.items()
                ],
                key=lambda x: -x[1],
            )[:15]
            http_by_status = dict(sorted(self._http_status.items()))
            # 4xx vs 5xx breakdown
            errors_4xx = sum(v for k, v in self._http_status.items() if 400 <= k < 500)
            errors_5xx = sum(v for k, v in self._http_status.items() if k >= 500)

            # MCP tools
            mcp_tools = {
                name: {
                    "calls": c.count,
                    "avg_ms": round(c.total_ms / c.count, 1) if c.count else 0,
                    "errors": c.errors,
                }
                for name, c in sorted(self._mcp.items(), key=lambda x: -x[1].count)
            }

            # Anonymization
            anon_by_type = dict(sorted(self._anon.items(), key=lambda x: -x[1]))

            # LLM costs
            llm_by_provider = {
                k: dict(v)
                for k, v in sorted(
                    self._llm_costs.items(), key=lambda x: -x[1]["cost_usd"]
                )
            }
            total_llm_cost = sum(v["cost_usd"] for v in self._llm_costs.values())

            return {
                "uptime_seconds": round(uptime),
                "http": {
                    "total_requests": self._http_total.count,
                    "total_errors": self._http_total.errors,
                    "errors_4xx": errors_4xx,
                    "errors_5xx": errors_5xx,
                    "avg_ms": round(
                        self._http_total.total_ms / self._http_total.count, 1
                    )
                    if self._http_total.count
                    else 0,
                    "by_status": http_by_status,
                    "top_endpoints": [
                        {"endpoint": ep, "hits": hits, "avg_ms": avg, "p95_ms": p95}
                        for ep, hits, avg, p95 in top_endpoints
                    ],
                },
                "mcp": {
                    "total_calls": self._mcp_total.count,
                    "total_errors": self._mcp_total.errors,
                    "avg_ms": round(self._mcp_total.total_ms / self._mcp_total.count, 1)
                    if self._mcp_total.count
                    else 0,
                    "by_tool": mcp_tools,
                },
                "anonymization": {
                    "total": self._anon_total,
                    "by_type": anon_by_type,
                },
                "db_queries": {
                    "total": self._db_total.count,
                    "by_operation": dict(self._db_queries),
                },
                "llm_costs": {
                    "total_usd": round(total_llm_cost, 4),
                    "by_provider": llm_by_provider,
                },
                "rtk": {
                    "calls": self._rtk_calls,
                    "bytes_raw": self._rtk_bytes_raw,
                    "bytes_compressed": self._rtk_bytes_compressed,
                    "bytes_saved": self._rtk_bytes_raw - self._rtk_bytes_compressed,
                    "ratio_pct": round(
                        100 * (1 - self._rtk_bytes_compressed / self._rtk_bytes_raw), 1
                    )
                    if self._rtk_bytes_raw > 0
                    else 0,
                    # Estimated tokens saved at ~4 chars/token
                    "tokens_saved_est": (
                        self._rtk_bytes_raw - self._rtk_bytes_compressed
                    )
                    // 4,
                },
            }


def _path_prefix(path: str) -> str:
    """Normalize path to first 2 segments for grouping."""
    parts = [p for p in path.split("/") if p]
    if len(parts) >= 3:
        return "/" + "/".join(parts[:2]) + "/…"
    return path


# Singleton
_collector: MetricsCollector | None = None
_collector_lock = threading.Lock()


def get_collector() -> MetricsCollector:
    global _collector
    if _collector is None:
        with _collector_lock:
            if _collector is None:
                _collector = MetricsCollector()
    return _collector
