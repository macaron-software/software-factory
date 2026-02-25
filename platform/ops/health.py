#!/usr/bin/env python3
"""Macaron Platform — Health Monitor.

Usage:
    python3 -m platform.ops.health           # Run all checks
    python3 -m platform.ops.health --watch   # Run every 5min
    python3 -m platform.ops.health --json    # JSON output for alerting

Checks:
  1. VM HTTP response (basic auth)
  2. PostgreSQL connectivity + row counts
  3. Container status on VM
  4. Disk space on VM
  5. Backup freshness (last backup age)
  6. SSL cert expiry (if HTTPS)
"""

import argparse
import datetime
import json
import os
import subprocess
import sys
import time
from pathlib import Path

VM_HOST = os.getenv("AZURE_VM_IP", "localhost")
VM_USER = "azureadmin"
STORAGE_ACCOUNT = "macaronbackups"


def _load_env():
    """Load secrets from ~/.config/factory/.env if not in environment."""
    env_file = Path.home() / ".config" / "factory" / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


_load_env()
PG_URL = os.environ.get("DATABASE_URL", "")


def _run(cmd: str, timeout: int = 15) -> tuple[int, str]:
    try:
        r = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return r.returncode, r.stdout + r.stderr
    except subprocess.TimeoutExpired:
        return -1, "TIMEOUT"


def check_vm_http() -> dict:
    """Check VM HTTP 200."""
    code, out = _run(
        f"curl -s -o /dev/null -w '%{{http_code}}' -u macaron:macaron http://{VM_HOST}/ --connect-timeout 10"
    )
    status = out.strip()
    ok = status == "200"
    return {"name": "vm_http", "ok": ok, "detail": f"HTTP {status}"}


def check_pg_connectivity() -> dict:
    """Check PostgreSQL connection + basic row counts."""
    try:
        import psycopg

        pg_url = PG_URL
        if "connect_timeout" not in pg_url:
            sep = "&" if "?" in pg_url else "?"
            pg_url += f"{sep}connect_timeout=10"
        conn = psycopg.connect(pg_url)
        cur = conn.execute(
            "SELECT COUNT(*) FROM agents UNION ALL "
            "SELECT COUNT(*) FROM missions UNION ALL "
            "SELECT COUNT(*) FROM messages"
        )
        rows = [r[0] for r in cur.fetchall()]
        conn.close()
        detail = f"agents={rows[0]} missions={rows[1]} messages={rows[2]}"
        return {"name": "pg_connectivity", "ok": True, "detail": detail}
    except Exception as e:
        return {"name": "pg_connectivity", "ok": False, "detail": str(e)[:200]}


def check_vm_containers() -> dict:
    """Check Docker containers on VM."""
    vm_pass = os.environ.get("VM_PASS", "")
    if not vm_pass:
        return {"name": "vm_containers", "ok": False, "detail": "VM_PASS not set"}
    code, out = _run(
        f"sshpass -p '{vm_pass}' ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 "
        f"{VM_USER}@{VM_HOST} 'docker ps --format \"{{{{.Names}}}} {{{{.Status}}}}\"'",
        timeout=20,
    )
    containers = (
        [line for line in out.strip().split("\n") if line.strip()] if code == 0 else []
    )
    platform_up = any("platform" in c and "Up" in c for c in containers)
    return {
        "name": "vm_containers",
        "ok": platform_up,
        "detail": f"{len(containers)} containers, platform={'UP' if platform_up else 'DOWN'}",
    }


def check_vm_disk() -> dict:
    """Check disk usage on VM."""
    vm_pass = os.environ.get("VM_PASS", "")
    if not vm_pass:
        return {"name": "vm_disk", "ok": False, "detail": "VM_PASS not set"}
    code, out = _run(
        f"sshpass -p '{vm_pass}' ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 "
        f"{VM_USER}@{VM_HOST} 'df -h / --output=pcent | tail -1'",
        timeout=15,
    )
    usage = out.strip().replace("%", "") if code == 0 else "?"
    try:
        pct = int(usage)
        ok = pct < 85
    except ValueError:
        pct = -1
        ok = False
    return {"name": "vm_disk", "ok": ok, "detail": f"{pct}% used"}


def check_backup_freshness() -> dict:
    """Check last backup age."""
    code, out = _run(
        f"az storage blob list --account-name {STORAGE_ACCOUNT} "
        f"--container-name db-backups --prefix daily/ "
        f'--query "sort_by([],&properties.lastModified)[-1].properties.lastModified" '
        f"-o tsv --only-show-errors",
        timeout=20,
    )
    if code != 0 or not out.strip():
        return {"name": "backup_freshness", "ok": False, "detail": "No backups found"}

    try:
        last_backup = datetime.datetime.fromisoformat(
            out.strip().replace("Z", "+00:00")
        )
        age_hours = (
            datetime.datetime.now(datetime.timezone.utc) - last_backup
        ).total_seconds() / 3600
        ok = age_hours < 26  # Should be daily
        return {"name": "backup_freshness", "ok": ok, "detail": f"{age_hours:.1f}h ago"}
    except Exception as e:
        return {"name": "backup_freshness", "ok": False, "detail": str(e)[:100]}


def run_all_checks() -> list[dict]:
    """Run all health checks."""
    checks = [
        check_vm_http,
        check_pg_connectivity,
        check_vm_containers,
        check_vm_disk,
        check_backup_freshness,
    ]
    results = []
    for check_fn in checks:
        try:
            result = check_fn()
        except Exception as e:
            result = {"name": check_fn.__name__, "ok": False, "detail": f"ERROR: {e}"}
        results.append(result)
    return results


def print_results(results: list[dict], as_json: bool = False):
    """Print health check results."""
    if as_json:
        print(
            json.dumps(
                {
                    "timestamp": datetime.datetime.now(
                        datetime.timezone.utc
                    ).isoformat(),
                    "checks": results,
                }
            )
        )
        return

    all_ok = all(r["ok"] for r in results)
    status = "✅ HEALTHY" if all_ok else "❌ DEGRADED"
    print(f"\n{'=' * 50}")
    print(f"  MACARON HEALTH — {status}")
    print(
        f"  {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
    )
    print(f"{'=' * 50}")
    for r in results:
        icon = "✅" if r["ok"] else "❌"
        print(f"  {icon} {r['name']:20s} {r['detail']}")
    print()


def main():
    parser = argparse.ArgumentParser(description="Macaron Health Monitor")
    parser.add_argument(
        "--watch", action="store_true", help="Run continuously every 5min"
    )
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument(
        "--interval", type=int, default=300, help="Watch interval (seconds)"
    )
    args = parser.parse_args()

    if args.watch:
        print("🔍 Health monitor started (Ctrl+C to stop)")
        while True:
            results = run_all_checks()
            print_results(results, args.json)
            failed = [r for r in results if not r["ok"]]
            if failed:
                print(f"  ⚠ {len(failed)} check(s) failed!")
            time.sleep(args.interval)
    else:
        results = run_all_checks()
        print_results(results, args.json)
        sys.exit(0 if all(r["ok"] for r in results) else 1)


if __name__ == "__main__":
    main()
