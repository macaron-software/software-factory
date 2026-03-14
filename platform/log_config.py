"""Structured JSON logging with trace_id and secret redaction."""
# Ref: feat-monitoring

from __future__ import annotations

import json
import logging
import os
import re
import time
from contextvars import ContextVar

# Context vars for request tracing
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")
agent_id_var: ContextVar[str] = ContextVar("agent_id", default="")

# Patterns to redact from logs
_SECRET_PATTERNS = [
    re.compile(r"(sk-[a-zA-Z0-9]{20,})"),  # OpenAI keys
    re.compile(r"(Bearer\s+[a-zA-Z0-9._\-]{20,})", re.I),
    re.compile(r'(password["\s:=]+)[^\s,}"\']+', re.I),
    re.compile(r'(api[_-]?key["\s:=]+)[^\s,}"\']+', re.I),
]


def _redact(text: str) -> str:
    for pat in _SECRET_PATTERNS:
        text = pat.sub(r"\1[REDACTED]", text)
    return text


class StructuredFormatter(logging.Formatter):
    """JSON formatter with trace context and secret redaction."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "msg": _redact(record.getMessage()),
        }
        tid = trace_id_var.get("")
        if tid:
            entry["trace_id"] = tid
        aid = agent_id_var.get("")
        if aid:
            entry["agent_id"] = aid
        if record.exc_info and record.exc_info[1]:
            entry["error"] = _redact(str(record.exc_info[1]))
        return json.dumps(entry, ensure_ascii=False)


def setup_logging(level: str = "WARNING", json_format: bool = True):
    """Configure root logger with structured format."""
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.WARNING))
    # Remove existing handlers
    for h in root.handlers[:]:
        root.removeHandler(h)
    handler = logging.StreamHandler()
    if json_format and os.environ.get("LOG_FORMAT") != "text":
        handler.setFormatter(StructuredFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-5s [%(name)s] %(message)s")
        )
    root.addHandler(handler)
    root.addHandler(IncidentLoggingHandler())


# Loggers too noisy to capture as incidents
_INCIDENT_LOGGER_SKIP = {
    "uvicorn",
    "uvicorn.access",
    "uvicorn.error",
    "httpx",
    "httpcore",
    "macaron_platform.llm",  # LLM retries are expected
}

# Error messages that are expected / not actionable
_INCIDENT_MSG_SKIP = (
    "heal_all",  # workspace scan noise
    "Auto-heal",  # auto-heal itself
    "rate: ",  # LLM rate logs
    "REDACTED",
)


class IncidentLoggingHandler(logging.Handler):
    """Capture ERROR+ log records and create platform_incidents (dedup by message)."""

    def __init__(self):
        super().__init__(level=logging.ERROR)

    def emit(self, record: logging.LogRecord):
        # Skip noisy loggers
        if any(record.name.startswith(skip) for skip in _INCIDENT_LOGGER_SKIP):
            return
        msg = record.getMessage()
        if any(s in msg for s in _INCIDENT_MSG_SKIP):
            return
        if record.exc_info and record.exc_info[1]:
            detail = f"{type(record.exc_info[1]).__name__}: {record.exc_info[1]}"
        else:
            detail = msg[:300]
        detail = _redact(detail)
        title = f"[LOG] {record.levelname} — {record.name}: {msg[:80]}"
        self._upsert(title, detail)

    def _upsert(self, title: str, detail: str):
        try:
            from .db.adapter import get_connection

            conn = get_connection()
            existing = conn.execute(
                "SELECT id FROM platform_incidents WHERE error_detail=? AND status='open' LIMIT 1",
                (detail,),
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE platform_incidents SET count=count+1, last_seen_at=CURRENT_TIMESTAMP WHERE id=?",
                    (existing[0],),
                )
            else:
                import uuid

                conn.execute(
                    "INSERT INTO platform_incidents (id, title, severity, status, source, error_type, error_detail, count, last_seen_at) "
                    "VALUES (?, ?, 'P3', 'open', 'log', 'log_error', ?, 1, CURRENT_TIMESTAMP)",
                    (str(uuid.uuid4())[:12], title, detail),
                )
            conn.commit()
            conn.close()
        except Exception:
            pass  # Never raise inside a logging handler
