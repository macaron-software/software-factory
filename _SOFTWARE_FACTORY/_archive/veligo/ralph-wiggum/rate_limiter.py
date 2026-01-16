#!/usr/bin/env python3
"""
Rate Limiter for Minimax M2 API
- 1000 calls / 5h = 200 calls/hour
- File-based tracking for multi-process coordination
"""

import os
import json
import time
import fcntl
from pathlib import Path
from datetime import datetime, timedelta

RATE_LIMIT_FILE = Path(__file__).parent / "status" / "rate_limit.json"
MAX_CALLS_PER_HOUR = 200  # 1000 calls / 5h
WINDOW_SECONDS = 3600    # 1 hour sliding window


def acquire_lock(f):
    """Acquire exclusive lock on file"""
    fcntl.flock(f.fileno(), fcntl.LOCK_EX)


def release_lock(f):
    """Release lock on file"""
    fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def load_rate_data():
    """Load rate limit data from file"""
    RATE_LIMIT_FILE.parent.mkdir(parents=True, exist_ok=True)

    if not RATE_LIMIT_FILE.exists():
        return {"calls": [], "total_calls": 0}

    try:
        with open(RATE_LIMIT_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {"calls": [], "total_calls": 0}


def save_rate_data(data):
    """Save rate limit data to file"""
    with open(RATE_LIMIT_FILE, 'w') as f:
        json.dump(data, f)


def clean_old_calls(calls):
    """Remove calls older than window"""
    cutoff = time.time() - WINDOW_SECONDS
    return [c for c in calls if c > cutoff]


def can_make_call():
    """Check if we can make an API call within rate limit"""
    RATE_LIMIT_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Use lock file for multi-process safety
    lock_file = RATE_LIMIT_FILE.parent / "rate_limit.lock"

    with open(lock_file, 'w') as lock:
        acquire_lock(lock)
        try:
            data = load_rate_data()
            data["calls"] = clean_old_calls(data.get("calls", []))

            current_count = len(data["calls"])
            can_call = current_count < MAX_CALLS_PER_HOUR

            return can_call, current_count, MAX_CALLS_PER_HOUR
        finally:
            release_lock(lock)


def record_call():
    """Record an API call"""
    lock_file = RATE_LIMIT_FILE.parent / "rate_limit.lock"

    with open(lock_file, 'w') as lock:
        acquire_lock(lock)
        try:
            data = load_rate_data()
            data["calls"] = clean_old_calls(data.get("calls", []))
            data["calls"].append(time.time())
            data["total_calls"] = data.get("total_calls", 0) + 1
            save_rate_data(data)
            return len(data["calls"])
        finally:
            release_lock(lock)


def get_wait_time():
    """Get seconds to wait before next call is allowed"""
    lock_file = RATE_LIMIT_FILE.parent / "rate_limit.lock"

    with open(lock_file, 'w') as lock:
        acquire_lock(lock)
        try:
            data = load_rate_data()
            calls = clean_old_calls(data.get("calls", []))

            if len(calls) < MAX_CALLS_PER_HOUR:
                return 0

            # Find oldest call and calculate when it expires
            oldest = min(calls)
            wait = (oldest + WINDOW_SECONDS) - time.time()
            return max(0, wait)
        finally:
            release_lock(lock)


def get_stats():
    """Get current rate limit stats"""
    data = load_rate_data()
    calls = clean_old_calls(data.get("calls", []))

    return {
        "calls_in_window": len(calls),
        "max_calls": MAX_CALLS_PER_HOUR,
        "remaining": MAX_CALLS_PER_HOUR - len(calls),
        "total_calls_ever": data.get("total_calls", 0),
        "window_seconds": WINDOW_SECONDS
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        cmd = sys.argv[1]

        if cmd == "check":
            can_call, current, max_calls = can_make_call()
            print(f"Can call: {can_call} ({current}/{max_calls})")
            sys.exit(0 if can_call else 1)

        elif cmd == "record":
            count = record_call()
            print(f"Recorded call #{count}")

        elif cmd == "wait":
            wait = get_wait_time()
            print(f"Wait time: {wait:.1f}s")

        elif cmd == "stats":
            stats = get_stats()
            print(json.dumps(stats, indent=2))

        else:
            print(f"Unknown command: {cmd}")
            print("Usage: rate_limiter.py [check|record|wait|stats]")
    else:
        stats = get_stats()
        print(f"Rate Limit: {stats['calls_in_window']}/{stats['max_calls']} calls/hour")
        print(f"Remaining: {stats['remaining']}")
