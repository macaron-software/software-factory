"""Shared rate limiter — Redis-backed when REDIS_URL is set, in-memory fallback.

Multi-node deployments share rate-limit state via Redis so that the effective
limit is per-IP across all nodes, not per-process.
"""
# Ref: feat-settings

from __future__ import annotations

import logging
import os

from slowapi import Limiter
from slowapi.util import get_remote_address

logger = logging.getLogger(__name__)

_redis_url = os.environ.get("REDIS_URL")

if _redis_url:
    try:
        limiter = Limiter(key_func=get_remote_address, storage_uri=_redis_url)
        logger.info("Rate limiter: Redis-backed (%s)", _redis_url.split("@")[-1])
    except Exception as _e:
        logger.warning(
            "Rate limiter: Redis init failed (%s) — falling back to in-memory", _e
        )
        limiter = Limiter(key_func=get_remote_address)
else:
    limiter = Limiter(key_func=get_remote_address)
