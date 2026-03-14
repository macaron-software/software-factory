# Ref: feat-settings
"""
Data retention automation — GDPR Art. 5 + SBD-09.

Purges expired data:
  - Sessions older than 90 days
  - Security logs: pseudonymize IPs after 30 days
  - Orphaned LLM logs after 90 days

Run: python3 -m platform.ops.data_retention
Schedule: daily via cron or platform lifespan bg task
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def run_retention(dry_run: bool = False) -> dict:
    """Execute data retention policies. Returns counts of affected rows."""
    from ..db.adapter import get_db

    db = get_db()
    now = datetime.utcnow()
    results = {}

    cutoff_90d = (now - timedelta(days=90)).isoformat()
    cutoff_30d = (now - timedelta(days=30)).isoformat()

    # 1. Purge sessions older than 90 days
    try:
        if dry_run:
            rows = db.execute("SELECT count(*) FROM sessions WHERE started_at < %s", (cutoff_90d,))
            results["sessions_to_purge"] = rows[0][0] if rows else 0
        else:
            db.execute("DELETE FROM sessions WHERE started_at < %s", (cutoff_90d,))
            results["sessions_purged"] = True
        logger.info("Session retention: cutoff=%s", cutoff_90d)
    except Exception as e:
        logger.warning("Session retention skipped: %s", e)
        results["sessions_error"] = str(e)

    # 2. Pseudonymize IPs in audit logs after 30 days
    try:
        if dry_run:
            rows = db.execute(
                "SELECT count(*) FROM audit_log WHERE created_at < %s AND ip_address IS NOT NULL AND ip_address != 'pseudonymized'",
                (cutoff_30d,),
            )
            results["ips_to_pseudonymize"] = rows[0][0] if rows else 0
        else:
            db.execute(
                "UPDATE audit_log SET ip_address = 'pseudonymized' WHERE created_at < %s AND ip_address IS NOT NULL AND ip_address != 'pseudonymized'",
                (cutoff_30d,),
            )
            results["ips_pseudonymized"] = True
        logger.info("IP pseudonymization: cutoff=%s", cutoff_30d)
    except Exception as e:
        logger.warning("IP pseudonymization skipped: %s", e)
        results["ips_error"] = str(e)

    # 3. Purge old LLM call logs after 90 days
    try:
        if dry_run:
            rows = db.execute("SELECT count(*) FROM llm_calls WHERE created_at < %s", (cutoff_90d,))
            results["llm_logs_to_purge"] = rows[0][0] if rows else 0
        else:
            db.execute("DELETE FROM llm_calls WHERE created_at < %s", (cutoff_90d,))
            results["llm_logs_purged"] = True
        logger.info("LLM log retention: cutoff=%s", cutoff_90d)
    except Exception as e:
        logger.warning("LLM log retention skipped: %s", e)
        results["llm_logs_error"] = str(e)

    return results


if __name__ == "__main__":
    import json
    import sys

    dry = "--dry-run" in sys.argv
    print(f"Data retention {'(DRY RUN)' if dry else '(LIVE)'}")
    result = run_retention(dry_run=dry)
    print(json.dumps(result, indent=2))
