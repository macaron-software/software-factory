"""Simple TTL cache for platform data that rarely changes.

Usage:
    from ..cache import ttl_cache, invalidate

    @ttl_cache("agents", ttl=60)
    def list_all(self): ...

    # After mutation:
    invalidate("agents")
"""
from __future__ import annotations

import time
import threading
from typing import Any

_lock = threading.Lock()
_store: dict[str, tuple[float, Any]] = {}  # key → (expires_at, value)

DEFAULT_TTL = 30  # seconds


def get(key: str) -> Any | None:
    """Get cached value if not expired."""
    entry = _store.get(key)
    if entry and entry[0] > time.monotonic():
        return entry[1]
    return None


def put(key: str, value: Any, ttl: int = DEFAULT_TTL):
    """Cache a value with TTL."""
    with _lock:
        _store[key] = (time.monotonic() + ttl, value)


def invalidate(*keys: str):
    """Invalidate one or more cache keys. Pass no args to clear all."""
    with _lock:
        if not keys:
            _store.clear()
        else:
            for k in keys:
                _store.pop(k, None)


def cached(key: str, ttl: int = DEFAULT_TTL):
    """Decorator for caching function results."""
    def decorator(fn):
        def wrapper(*args, **kwargs):
            val = get(key)
            if val is not None:
                return val
            val = fn(*args, **kwargs)
            put(key, val, ttl)
            return val
        wrapper.__wrapped__ = fn
        wrapper.cache_key = key
        return wrapper
    return decorator
