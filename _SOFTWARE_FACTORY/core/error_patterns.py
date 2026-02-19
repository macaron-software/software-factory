"""
Error Patterns - Unified error classification
=============================================
Single source of truth for transient/infra/security error detection.

Replaces divergent pattern lists in wiggum_tdd, cycle_worker, wiggum_deploy,
and meta_awareness with a unified classification.

Usage:
    from core.error_patterns import classify_error, is_transient, is_infra

    category = classify_error("Cannot connect to the Docker daemon")
    # Returns "infra"

    if is_transient(error_text):
        # Retry instead of creating feedback task
"""

import re
from typing import Literal

ErrorCategory = Literal["transient", "infra", "security", "code"]

# ============================================================================
# TRANSIENT ERRORS - Should retry, NOT mark as failed
# ============================================================================

TRANSIENT_PATTERNS = [
    # Network/API
    "Unable to connect",
    "connection reset",
    "Connection reset",
    "ETIMEDOUT",
    "ECONNREFUSED",
    "ECONNRESET",

    # LLM/API rate limits
    "rate limit",
    "Rate limit",
    "RATE_LIMIT",
    "rate_limit",
    "too many requests",
    "quota exceeded",
    "requests per minute",

    # MCP/Tools
    "Invalid Tool",
    "Server unavailable",
    "MCP server",
]

# ============================================================================
# INFRA ERRORS - Not code issues, need factory/config fix
# ============================================================================

INFRA_PATTERNS = [
    # Docker (missing in cycle_worker before this module)
    "Cannot connect to the Docker daemon",
    "docker daemon",
    "Docker daemon",
    "docker.sock",
    "No such container",
    "container is not running",
    "OCI runtime",
    "failed to create shim",
    "Error response from daemon",
    "docker: Error",
    "docker build failed",
    "docker-compose",
    "docker: command not found",

    # CLI/command
    "command not found",
    "unrecognized subcommand",
    "missing script",
    "npm error",

    # Environment
    "environment variable",
    "VELIGO_TOKEN",
    "auth required",
    "permission denied",
    "Permission denied",
    "No such file or directory",

    # File/resource locks
    "file lock",
    "Blocking waiting for file lock",

    # Network (infra level)
    "timeout",
    "Timeout",
    "connection refused",
    "Connection refused",
    "network error",

    # System
    "OOM",
    "out of memory",
    "Out of memory",
    "disk full",
    "No space left on device",
    "port already in use",
    "address already in use",
]

# ============================================================================
# SECURITY ERRORS - Must block, never skip
# ============================================================================

SECURITY_PATTERNS = [
    "sql injection",
    "xss",
    "cross-site scripting",
    "command injection",
    "path traversal",
    "secret",
    "hardcoded password",
    "hardcoded key",
    "private key",
]

# Regex versions for meta_awareness compatibility
INFRA_REGEX = [
    re.compile(r"command not found", re.IGNORECASE),
    re.compile(r"unrecognized (subcommand|option|argument)", re.IGNORECASE),
    re.compile(r"No such file or directory", re.IGNORECASE),
    re.compile(r"Permission denied", re.IGNORECASE),
    re.compile(r"Connection refused", re.IGNORECASE),
    re.compile(r"Blocking waiting for file lock", re.IGNORECASE),
    re.compile(r"rate limit", re.IGNORECASE),
    re.compile(r"timeout", re.IGNORECASE),
    re.compile(r"ENOENT|EACCES|ECONNREFUSED", re.IGNORECASE),
    re.compile(r"Cannot connect to the Docker daemon", re.IGNORECASE),
    re.compile(r"No such container", re.IGNORECASE),
    re.compile(r"OCI runtime", re.IGNORECASE),
    re.compile(r"OOM|out of memory", re.IGNORECASE),
    re.compile(r"No space left on device", re.IGNORECASE),
]


def classify_error(error_text: str) -> ErrorCategory:
    """
    Classify an error into a category.

    Priority: transient > infra > security > code
    Transient checked first because infra patterns overlap (e.g., "timeout").

    Args:
        error_text: Error output text

    Returns:
        "transient", "infra", "security", or "code"
    """
    if not error_text:
        return "code"

    if is_transient(error_text):
        return "transient"
    if is_infra(error_text):
        return "infra"
    if is_security(error_text):
        return "security"
    return "code"


def is_transient(error_text: str) -> bool:
    """Check if error is transient (should retry, not fail)."""
    if not error_text:
        return False
    error_lower = error_text.lower()
    for pattern in TRANSIENT_PATTERNS:
        if pattern.lower() in error_lower:
            return True
    return False


def is_infra(error_text: str, use_regex: bool = False) -> bool:
    """
    Check if error is infrastructure-related (not a code issue).

    Args:
        error_text: Error text to check
        use_regex: Use regex patterns (slower but more flexible, for meta_awareness)
    """
    if not error_text:
        return False

    if use_regex:
        for regex in INFRA_REGEX:
            if regex.search(error_text):
                return True
        return False

    error_lower = error_text.lower()
    for pattern in INFRA_PATTERNS:
        if pattern.lower() in error_lower:
            return True
    return False


def is_security(error_text: str) -> bool:
    """Check if error indicates a security issue."""
    if not error_text:
        return False
    error_lower = error_text.lower()
    for pattern in SECURITY_PATTERNS:
        if pattern in error_lower:
            return True
    return False
