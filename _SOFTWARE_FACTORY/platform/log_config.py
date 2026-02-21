"""Structured JSON logging with trace_id and secret redaction."""
from __future__ import annotations

import json
import logging
import os
import re
import time
import uuid
from contextvars import ContextVar

# Context vars for request tracing
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")
agent_id_var: ContextVar[str] = ContextVar("agent_id", default="")

# Patterns to redact from logs
_SECRET_PATTERNS = [
    re.compile(r'(sk-[a-zA-Z0-9]{20,})'),  # OpenAI keys
    re.compile(r'(Bearer\s+[a-zA-Z0-9._\-]{20,})', re.I),
    re.compile(r'(password["\s:=]+)[^\s,}"\']+', re.I),
    re.compile(r'(api[_-]?key["\s:=]+)[^\s,}"\']+', re.I),
]


def _redact(text: str) -> str:
    for pat in _SECRET_PATTERNS:
        text = pat.sub(r'\1[REDACTED]', text)
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
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)-5s [%(name)s] %(message)s"
        ))
    root.addHandler(handler)
