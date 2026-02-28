"""Guardrails — critical action interception and audit.

Intercepts tool calls that could have destructive or irreversible effects,
logs them to admin_audit_log, and blocks based on platform settings.

Critical action categories:
  - DESTRUCTIVE_FS: deleting/overwriting production/config files
  - DESTRUCTIVE_GIT: git reset --hard, git push --force, rebase
  - DESTRUCTIVE_INFRA: docker rm, docker system prune, deploy to prod
  - SENSITIVE_DATA: reading .env, secrets, private keys

Configuration (platform_settings table):
  - guardrails_enabled: "1" (default)
  - guardrails_block_destructive: "1" — block destructive git ops
  - guardrails_block_sensitive: "0" — warn only for sensitive reads
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Optional

logger = logging.getLogger(__name__)

# ── Critical pattern definitions ───────────────────────────────────────────────

# Tool + argument patterns that trigger guardrails
_CRITICAL_TOOLS: dict[str, list[dict]] = {
    "git_commit": [
        # git commands that reset/force/destroy history
        {
            "arg": "message",
            "pattern": r"--amend|--force|rebase|--hard",
            "severity": "HIGH",
            "label": "destructive_git",
        },
    ],
    "build": [
        {
            "arg": "command",
            "pattern": r"rm\s+-rf|mkfs|dd\s+if=|wipefs",
            "severity": "CRITICAL",
            "label": "destructive_fs",
        },
        {
            "arg": "command",
            "pattern": r"git\s+(reset\s+--hard|push\s+--force|push\s+-f\b|rebase|clean\s+-fd)",
            "severity": "HIGH",
            "label": "destructive_git",
        },
        {
            "arg": "command",
            "pattern": r"docker\s+(rm|rmi|system\s+prune|volume\s+rm)",
            "severity": "HIGH",
            "label": "destructive_infra",
        },
        {
            "arg": "command",
            "pattern": r"DROP\s+TABLE|TRUNCATE|DELETE\s+FROM\s+(?!.*WHERE)",
            "severity": "CRITICAL",
            "label": "destructive_db",
        },
    ],
    "code_write": [
        {
            "arg": "path",
            "pattern": r"\.(env|pem|key|p12|pfx|jks)$|id_rsa|id_ed25519",
            "severity": "HIGH",
            "label": "sensitive_data",
        },
        {
            "arg": "path",
            "pattern": r"(/etc/|/etc$|/usr/bin/|/usr/local/bin/|/var/|/sys/|/proc/)",
            "severity": "CRITICAL",
            "label": "system_path",
        },
        {
            "arg": "path",
            "pattern": r"(production|prod)\.(?:env|json|yaml|yml|conf|config)$",
            "severity": "HIGH",
            "label": "prod_config",
        },
    ],
    "code_edit": [
        {
            "arg": "path",
            "pattern": r"\.(env|pem|key|p12|pfx|jks)$|id_rsa|id_ed25519",
            "severity": "HIGH",
            "label": "sensitive_data",
        },
        {
            "arg": "path",
            "pattern": r"(production|prod)\.(?:env|json|yaml|yml|conf|config)$",
            "severity": "HIGH",
            "label": "prod_config",
        },
    ],
    "code_read": [
        {
            "arg": "path",
            "pattern": r"id_rsa$|id_ed25519$|\.pem$",
            "severity": "MEDIUM",
            "label": "sensitive_key",
        },
    ],
}

# Severity → action mapping
# CRITICAL: always block + audit
# HIGH: block if guardrails_block_destructive=1, always audit
# MEDIUM: audit only
_DEFAULT_CONFIG = {
    "guardrails_enabled": True,
    "guardrails_block_critical": True,  # block CRITICAL actions
    "guardrails_block_high": True,  # block HIGH severity actions
    "guardrails_block_medium": False,  # medium = warn only
    "guardrails_max_high_per_session": 5,  # max HIGH actions per session before blocking
}

# Module-level config cache (refreshed every 60s)
_config_cache: dict = {}
_config_ts: float = 0.0
_CACHE_TTL = 60.0

# Per-session HIGH-severity counters: {session_id: count}
_session_high_counts: dict[str, int] = {}


def _load_config() -> dict:
    """Load guardrails config from platform_settings. Cached 60s."""
    global _config_cache, _config_ts
    now = time.monotonic()
    if now - _config_ts < _CACHE_TTL and _config_cache:
        return _config_cache

    cfg = dict(_DEFAULT_CONFIG)
    try:
        from ..db.migrations import get_db

        db = get_db()
        rows = db.execute(
            "SELECT key, value FROM platform_settings WHERE key LIKE 'guardrails_%'"
        ).fetchall()
        db.close()
        for row in rows:
            k = row["key"]
            v = row["value"]
            if k in ("guardrails_max_high_per_session",):
                try:
                    cfg[k] = int(v)
                except Exception:
                    pass
            else:
                cfg[k] = v in ("1", "true", "True", True)
    except Exception:
        pass

    _config_cache = cfg
    _config_ts = now
    return cfg


def _audit_log(
    agent_id: str,
    session_id: str,
    tool_name: str,
    label: str,
    severity: str,
    args: dict,
    action_taken: str,
) -> None:
    """Write an entry to admin_audit_log. Never raises."""
    try:
        from ..db.migrations import get_db

        db = get_db()
        args_preview = json.dumps(
            {k: str(v)[:100] for k, v in args.items()}, ensure_ascii=False
        )[:500]
        db.execute(
            """INSERT INTO admin_audit_log (id, event_type, actor_id, target_type,
               target_id, details_json, created_at)
               VALUES (lower(hex(randomblob(8))), ?, ?, 'tool_call', ?, ?, datetime('now'))""",
            (
                f"guardrail_{severity.lower()}",
                agent_id or "unknown",
                tool_name,
                json.dumps(
                    {
                        "label": label,
                        "severity": severity,
                        "action": action_taken,
                        "args": args_preview,
                        "session_id": session_id,
                    }
                ),
            ),
        )
        db.commit()
        db.close()
    except Exception as exc:
        logger.debug("Guardrail audit log failed: %s", exc)


def check_guardrails(
    tool_name: str,
    args: dict,
    agent_id: str = "",
    session_id: str = "",
) -> Optional[str]:
    """
    Check if a tool call triggers guardrails.

    Returns:
      - None: allow execution
      - str: block message (return this instead of executing the tool)
    """
    cfg = _load_config()
    if not cfg.get("guardrails_enabled", True):
        return None

    patterns = _CRITICAL_TOOLS.get(tool_name, [])
    if not patterns:
        return None

    for rule in patterns:
        arg_key = rule["arg"]
        pattern = rule["pattern"]
        severity = rule["severity"]
        label = rule["label"]

        arg_val = str(args.get(arg_key, ""))
        if not arg_val:
            continue
        if not re.search(pattern, arg_val, re.IGNORECASE):
            continue

        # Match found — determine action
        should_block = False
        if severity == "CRITICAL" and cfg.get("guardrails_block_critical", True):
            should_block = True
        elif severity == "HIGH" and cfg.get("guardrails_block_high", True):
            # Check per-session accumulation
            count = _session_high_counts.get(session_id, 0) + 1
            _session_high_counts[session_id] = count
            max_high = cfg.get("guardrails_max_high_per_session", 5)
            if count > max_high:
                should_block = True
            else:
                should_block = True  # block by default for HIGH
        elif severity == "MEDIUM" and cfg.get("guardrails_block_medium", False):
            should_block = True

        action = "BLOCKED" if should_block else "WARNED"
        _audit_log(agent_id, session_id, tool_name, label, severity, args, action)

        logger.warning(
            "GUARDRAIL %s [%s/%s]: agent=%s tool=%s arg=%s pattern=%s",
            action,
            label,
            severity,
            agent_id or "?",
            tool_name,
            arg_key,
            pattern[:40],
        )

        if should_block:
            return (
                f"[GUARDRAIL BLOCKED] Action `{tool_name}` on `{arg_key}` "
                f"matches critical pattern ({label}, severity={severity}). "
                f"This action requires explicit human authorization. "
                f"Set human_input_required=1 or disable guardrails in platform settings."
            )
        else:
            # Warn but don't block — inject warning note into result context
            return None  # allow, audit already done

    return None
