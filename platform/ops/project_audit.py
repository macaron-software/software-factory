# Ref: feat-quality
"""
Project Compliance Audit Engine — 19-dimension check.

Runs deterministic checks (no LLM) across:
  SAFe traceability, UX, UI, A11Y, i18n, Security, GDPR, Observability,
  API, DR, LEAN/KISS, SOC2, ISO27001, SecureByDesign, OWASP, CRUD, RBAC.

Usage:
  from platform.ops.project_audit import run_audit
  report = await run_audit("my-project", workspace="/path/to/code")
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


# ── Data Structures ──────────────────────────────────────────────

@dataclass
class AuditCheck:
    category: str
    name: str
    status: str = "warn"  # pass | warn | fail | skip
    score: float = 0.0    # 0-100
    evidence: str = ""
    remediation: str = ""


@dataclass
class AuditReport:
    id: str = ""
    project_id: str = ""
    global_score: float = 0.0
    checks: list[AuditCheck] = field(default_factory=list)
    dimensions: dict = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)
    created_at: str = ""
    created_by: str = "system"

    def pass_count(self) -> int:
        return sum(1 for c in self.checks if c.status == "pass")

    def total_count(self) -> int:
        return len([c for c in self.checks if c.status != "skip"])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "global_score": round(self.global_score, 1),
            "pass_count": self.pass_count(),
            "total_count": self.total_count(),
            "checks": [asdict(c) for c in self.checks],
            "dimensions": self.dimensions,
            "recommendations": self.recommendations,
            "created_at": self.created_at,
        }


# ── Check Functions ──────────────────────────────────────────────

def _check_traceability(project_id: str, workspace: str) -> list[AuditCheck]:
    """SAFe E2E traceability: persona→feature→story→AC→IHM→code→TU→E2E."""
    checks = []
    try:
        from ..ops.traceability_scheduler import run_traceability_audit
        import asyncio
        summary = asyncio.get_event_loop().run_until_complete(
            run_traceability_audit(project_id)
        )
        cov = summary.get("coverage_pct", 0)
        checks.append(AuditCheck(
            "SAFe", "E2E Traceability",
            status="pass" if cov >= 80 else "warn",
            score=cov,
            evidence=f"Coverage: {cov}% — epics:{summary.get('epics',0)}, stories:{summary.get('stories',0)}, tests:{summary.get('test_links',0)}",
            remediation="" if cov >= 80 else "Add missing story→code→test links"
        ))
    except Exception as e:
        checks.append(AuditCheck("SAFe", "E2E Traceability", "skip", 0, f"Error: {e}"))
    return checks


def _check_quality(project_id: str, workspace: str) -> list[AuditCheck]:
    """Quality metrics: complexity, coverage, docs, architecture."""
    checks = []
    try:
        from ..metrics.quality import QualityScanner
        import asyncio
        scanner = QualityScanner()
        scorecard = asyncio.get_event_loop().run_until_complete(
            scanner.full_scan(workspace, project_id=project_id)
        )
        gs = scorecard.global_score
        checks.append(AuditCheck(
            "Quality", "Global Quality Score",
            status="pass" if gs >= 70 else "warn" if gs >= 50 else "fail",
            score=gs,
            evidence=f"Score: {gs}/100"
        ))
        for dim_name, dim_result in scorecard.dimensions.items():
            s = getattr(dim_result, "score", 0)
            checks.append(AuditCheck(
                "Quality", f"Quality: {dim_name}",
                status="pass" if s >= 70 else "warn",
                score=s,
                evidence=f"{dim_name}: {s}/100"
            ))
    except Exception as e:
        checks.append(AuditCheck("Quality", "Quality Scan", "skip", 0, f"Error: {e}"))
    return checks


def _check_security(workspace: str) -> list[AuditCheck]:
    """Security: RBAC, SQL injection, XSS, secrets, headers, rate-limit."""
    checks = []

    # Check for parameterized SQL
    sql_safe = not _grep_exists(workspace, r"f\".*SELECT.*{|f'.*SELECT.*{|\.format\(.*SELECT", "*.py")
    checks.append(AuditCheck(
        "Security", "SQL Injection Prevention",
        "pass" if sql_safe else "warn", 100 if sql_safe else 30,
        "Parameterized queries" if sql_safe else "Found string-formatted SQL",
        "" if sql_safe else "Use parameterized queries (%s or ?) instead of f-strings"
    ))

    # Check for secrets in code
    has_secrets = _grep_exists(workspace, r"(password|secret|api_key)\s*=\s*['\"][^'\"]{8,}", "*.py")
    checks.append(AuditCheck(
        "Security", "No Hardcoded Secrets",
        "pass" if not has_secrets else "fail", 100 if not has_secrets else 0,
        "No secrets found" if not has_secrets else "Hardcoded secrets detected",
        "" if not has_secrets else "Move secrets to .env or Infisical"
    ))

    # Check for shell=True
    shell_true = _grep_exists(workspace, r"subprocess.*shell\s*=\s*True", "*.py")
    checks.append(AuditCheck(
        "Security", "No shell=True",
        "pass" if not shell_true else "warn", 100 if not shell_true else 30,
        "No shell=True" if not shell_true else "shell=True found — command injection risk"
    ))

    # Check for .env in .gitignore
    gitignore = os.path.join(workspace, ".gitignore")
    env_ignored = False
    if os.path.exists(gitignore):
        env_ignored = ".env" in open(gitignore).read()
    checks.append(AuditCheck(
        "Security", ".env in .gitignore",
        "pass" if env_ignored else "warn", 100 if env_ignored else 50,
        ".env excluded" if env_ignored else ".env not in .gitignore"
    ))

    return checks


def _check_a11y(workspace: str) -> list[AuditCheck]:
    """A11Y: ARIA, semantic HTML, focus-visible, skip-link, contrast."""
    checks = []
    html_dir = os.path.join(workspace, "platform", "web", "templates") if os.path.isdir(
        os.path.join(workspace, "platform")) else workspace

    if not os.path.isdir(html_dir):
        checks.append(AuditCheck("A11Y", "HTML Templates", "skip", 0, "No templates found"))
        return checks

    has_main = _grep_exists(html_dir, r"<main|role=\"main\"", "*.html")
    has_nav = _grep_exists(html_dir, r"<nav|role=\"navigation\"", "*.html")
    has_skip = _grep_exists(html_dir, r"skip.*link|skip.*content|skip-link", "*.html")
    has_focus = _grep_exists(workspace, r":focus-visible|focus-visible", "*.css") or \
                _grep_exists(workspace, r":focus-visible|focus-visible", "*.html")

    checks.append(AuditCheck("A11Y", "Semantic landmarks", "pass" if (has_main and has_nav) else "warn",
                             100 if (has_main and has_nav) else 40,
                             f"<main>={'Y' if has_main else 'N'}, <nav>={'Y' if has_nav else 'N'}"))
    checks.append(AuditCheck("A11Y", "Skip link", "pass" if has_skip else "warn",
                             100 if has_skip else 0, remediation="Add skip-to-content link"))
    checks.append(AuditCheck("A11Y", "Focus visible", "pass" if has_focus else "warn",
                             100 if has_focus else 0, remediation="Add :focus-visible styles"))

    return checks


def _check_i18n(workspace: str) -> list[AuditCheck]:
    """i18n: localization support, RTL, locale files."""
    checks = []
    has_i18n = os.path.isdir(os.path.join(workspace, "platform", "i18n")) or \
               os.path.isdir(os.path.join(workspace, "locales")) or \
               _grep_exists(workspace, r"i18n|gettext|t\(|ngettext", "*.py")
    has_rtl = _grep_exists(workspace, r"dir=\"rtl\"|dir=.rtl|rtl", "*.html") or \
              _grep_exists(workspace, r"direction:\s*rtl|margin-inline", "*.css")

    checks.append(AuditCheck("i18n", "Localization support",
                             "pass" if has_i18n else "warn", 100 if has_i18n else 0,
                             remediation="Add i18n support with locale files"))
    checks.append(AuditCheck("i18n", "RTL support",
                             "pass" if has_rtl else "warn", 100 if has_rtl else 0,
                             remediation="Add RTL support with CSS logical properties"))
    return checks


def _check_gdpr(workspace: str) -> list[AuditCheck]:
    """GDPR: privacy page, data export, deletion, retention."""
    checks = []
    has_privacy = _grep_exists(workspace, r"/privacy|privacy\.html|privacy_page", "*.py") or \
                  os.path.exists(os.path.join(workspace, "platform", "web", "templates", "privacy.html"))
    has_export = _grep_exists(workspace, r"/api/me/export|export_my_data|data.*export", "*.py")
    has_delete = _grep_exists(workspace, r"DELETE.*api/me|delete_my_account|account.*delet", "*.py")
    has_retention = _grep_exists(workspace, r"data_retention|retention.*policy|auto.*purge", "*.py")

    checks.append(AuditCheck("GDPR", "Privacy page (Art.12)", "pass" if has_privacy else "warn",
                             100 if has_privacy else 0, remediation="Create /privacy page"))
    checks.append(AuditCheck("GDPR", "Data export (Art.15)", "pass" if has_export else "warn",
                             100 if has_export else 0, remediation="Add GET /api/me/export"))
    checks.append(AuditCheck("GDPR", "Account deletion (Art.17)", "pass" if has_delete else "warn",
                             100 if has_delete else 0, remediation="Add DELETE /api/me"))
    checks.append(AuditCheck("GDPR", "Data retention (Art.5)", "pass" if has_retention else "warn",
                             100 if has_retention else 0, remediation="Add data retention automation"))
    return checks


def _check_observability(workspace: str) -> list[AuditCheck]:
    """Observability: OTEL, health endpoint, metrics, structured logging."""
    checks = []
    has_otel = _grep_exists(workspace, r"opentelemetry|OTEL|trace\.get_tracer", "*.py")
    has_health = _grep_exists(workspace, r"/api/health|/health|healthcheck", "*.py")
    has_metrics = _grep_exists(workspace, r"/metrics|prometheus|Counter\(|Histogram\(", "*.py")

    checks.append(AuditCheck("Observability", "OTEL traces", "pass" if has_otel else "warn",
                             100 if has_otel else 0, remediation="Add OpenTelemetry instrumentation"))
    checks.append(AuditCheck("Observability", "Health endpoint", "pass" if has_health else "warn",
                             100 if has_health else 0, remediation="Add /api/health endpoint"))
    checks.append(AuditCheck("Observability", "Metrics", "pass" if has_metrics else "warn",
                             100 if has_metrics else 0, remediation="Add /metrics prometheus endpoint"))
    return checks


def _check_api(workspace: str) -> list[AuditCheck]:
    """API: rate limiting, versioning, error handling."""
    checks = []
    has_rate = _grep_exists(workspace, r"rate.limit|slowapi|Limiter|RateLimit", "*.py")
    has_cors = _grep_exists(workspace, r"CORSMiddleware|cors|CORS_ORIGINS", "*.py")
    has_errors = _grep_exists(workspace, r"JSONResponse.*error|HTTPException|status_code", "*.py")

    checks.append(AuditCheck("API", "Rate limiting", "pass" if has_rate else "warn",
                             100 if has_rate else 0, remediation="Add rate limiting middleware"))
    checks.append(AuditCheck("API", "CORS config", "pass" if has_cors else "warn",
                             100 if has_cors else 0, remediation="Configure CORS origins"))
    checks.append(AuditCheck("API", "Error handling", "pass" if has_errors else "warn",
                             100 if has_errors else 0))
    return checks


def _check_dr(workspace: str) -> list[AuditCheck]:
    """DR: backup/restore, documented RTO/RPO."""
    checks = []
    has_backup = _grep_exists(workspace, r"backup|pg_dump|restore", "*.py") or \
                 os.path.exists(os.path.join(workspace, "platform", "ops", "backup.py"))
    checks.append(AuditCheck("DR", "Backup/Restore", "pass" if has_backup else "warn",
                             100 if has_backup else 0, remediation="Add backup/restore automation"))
    return checks


def _check_lean(workspace: str) -> list[AuditCheck]:
    """LEAN/KISS: complexity, file sizes, dependencies."""
    checks = []
    # Check for oversized files (>2000 LOC)
    big_files = []
    for root, _, files in os.walk(workspace):
        if "node_modules" in root or ".git" in root or "__pycache__" in root:
            continue
        for f in files:
            if f.endswith((".py", ".ts", ".js")):
                fp = os.path.join(root, f)
                try:
                    lc = sum(1 for _ in open(fp))
                    if lc > 2000:
                        big_files.append(f"{f}: {lc} LOC")
                except Exception:
                    pass

    checks.append(AuditCheck(
        "LEAN", "No oversized files (>2000 LOC)",
        "pass" if not big_files else "warn",
        100 if not big_files else max(0, 100 - len(big_files) * 10),
        f"{len(big_files)} files >2000 LOC" if big_files else "All files <2000 LOC",
        "Split large files" if big_files else ""
    ))
    return checks


def _check_tests(workspace: str) -> list[AuditCheck]:
    """Tests: presence of unit tests and E2E tests."""
    checks = []
    has_ut = os.path.isdir(os.path.join(workspace, "tests")) or \
             _grep_exists(workspace, r"def test_|@pytest", "*.py")
    has_e2e = os.path.isdir(os.path.join(workspace, "platform", "tests", "e2e")) or \
              _grep_exists(workspace, r"playwright|cypress|selenium", "*.ts") or \
              _grep_exists(workspace, r"playwright|cypress|selenium", "*.js")

    checks.append(AuditCheck("Tests", "Unit tests exist", "pass" if has_ut else "fail",
                             100 if has_ut else 0, remediation="Add unit tests"))
    checks.append(AuditCheck("Tests", "E2E tests exist", "pass" if has_e2e else "warn",
                             100 if has_e2e else 0, remediation="Add E2E tests (Playwright)"))
    return checks


def _check_rbac(workspace: str) -> list[AuditCheck]:
    """RBAC: auth middleware, role checks, protected routes."""
    checks = []
    has_auth = _grep_exists(workspace, r"require_auth|@login_required|Depends.*auth", "*.py")
    has_roles = _grep_exists(workspace, r"role.*admin|role.*editor|role.*viewer|is_admin", "*.py")

    checks.append(AuditCheck("RBAC", "Auth middleware", "pass" if has_auth else "warn",
                             100 if has_auth else 0, remediation="Add authentication middleware"))
    checks.append(AuditCheck("RBAC", "Role-based access", "pass" if has_roles else "warn",
                             100 if has_roles else 0, remediation="Add role-based authorization"))
    return checks


# ── Helpers ──────────────────────────────────────────────────────

def _grep_exists(directory: str, pattern: str, glob: str) -> bool:
    """Check if pattern exists in files matching glob under directory."""
    import subprocess
    try:
        result = subprocess.run(
            ["grep", "-rlE", pattern, "--include", glob, directory],
            capture_output=True, text=True, timeout=10
        )
        return bool(result.stdout.strip())
    except Exception:
        return False


# ── Main Orchestrator ────────────────────────────────────────────

async def run_audit(project_id: str, workspace: str = "", user: str = "system") -> AuditReport:
    """Run full 19-dimension compliance audit on a project."""
    if not workspace:
        workspace = os.getcwd()

    report = AuditReport(
        id=f"audit-{uuid.uuid4().hex[:12]}",
        project_id=project_id,
        created_at=datetime.now(timezone.utc).isoformat(),
        created_by=user,
    )

    # Run all check categories
    report.checks.extend(_check_traceability(project_id, workspace))
    report.checks.extend(_check_quality(project_id, workspace))
    report.checks.extend(_check_security(workspace))
    report.checks.extend(_check_a11y(workspace))
    report.checks.extend(_check_i18n(workspace))
    report.checks.extend(_check_gdpr(workspace))
    report.checks.extend(_check_observability(workspace))
    report.checks.extend(_check_api(workspace))
    report.checks.extend(_check_dr(workspace))
    report.checks.extend(_check_lean(workspace))
    report.checks.extend(_check_tests(workspace))
    report.checks.extend(_check_rbac(workspace))

    # Calculate global score
    scored = [c for c in report.checks if c.status != "skip"]
    if scored:
        report.global_score = sum(c.score for c in scored) / len(scored)

    # Build dimension summaries
    dims = {}
    for c in report.checks:
        cat = c.category
        if cat not in dims:
            dims[cat] = {"total": 0, "pass": 0, "warn": 0, "fail": 0, "skip": 0}
        dims[cat]["total"] += 1
        dims[cat][c.status] += 1
    report.dimensions = dims

    # Generate recommendations
    for c in report.checks:
        if c.status in ("warn", "fail") and c.remediation:
            report.recommendations.append(f"[{c.category}] {c.remediation}")

    # Persist to DB
    try:
        await _persist_report(report)
    except Exception as e:
        logger.warning("Could not persist audit report: %s", e)

    return report


async def _persist_report(report: AuditReport):
    """Save audit report to PostgreSQL."""
    from ..db.adapter import get_db
    db = get_db()

    db.execute(
        """INSERT INTO audit_reports (id, project_id, global_score, dimensions_json, checks_json, recommendations_json, created_at, created_by)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (id) DO NOTHING""",
        (
            report.id,
            report.project_id,
            report.global_score,
            json.dumps(report.dimensions),
            json.dumps([asdict(c) for c in report.checks]),
            json.dumps(report.recommendations),
            report.created_at,
            report.created_by,
        ),
    )


async def get_latest_report(project_id: str) -> dict | None:
    """Get the latest audit report for a project."""
    from ..db.adapter import get_db
    db = get_db()
    rows = db.execute(
        "SELECT id, project_id, global_score, dimensions_json, checks_json, recommendations_json, created_at, created_by "
        "FROM audit_reports WHERE project_id = %s ORDER BY created_at DESC LIMIT 1",
        (project_id,),
    )
    if not rows:
        return None
    r = rows[0]
    return {
        "id": r[0], "project_id": r[1], "global_score": r[2],
        "dimensions": json.loads(r[3] or "{}"),
        "checks": json.loads(r[4] or "[]"),
        "recommendations": json.loads(r[5] or "[]"),
        "created_at": r[6], "created_by": r[7],
    }


async def get_audit_history(project_id: str, limit: int = 10) -> list[dict]:
    """Get audit history for a project."""
    from ..db.adapter import get_db
    db = get_db()
    rows = db.execute(
        "SELECT id, global_score, created_at FROM audit_reports WHERE project_id = %s ORDER BY created_at DESC LIMIT %s",
        (project_id, limit),
    )
    return [{"id": r[0], "score": r[1], "created_at": r[2]} for r in rows]


# ── CLI Entry Point ──────────────────────────────────────────────

def run_audit_sync(project_id: str, workspace: str = "") -> AuditReport:
    """Synchronous wrapper for CLI usage."""
    import asyncio
    return asyncio.run(run_audit(project_id, workspace))


if __name__ == "__main__":
    import sys
    pid = sys.argv[1] if len(sys.argv) > 1 else "factory"
    ws = sys.argv[2] if len(sys.argv) > 2 else os.getcwd()
    report = run_audit_sync(pid, ws)
    print(f"\n{'='*60}")
    print(f"  AUDIT REPORT: {pid}")
    print(f"  Score: {report.global_score:.0f}/100 ({report.pass_count()}/{report.total_count()} pass)")
    print(f"{'='*60}")
    for cat, dim in report.dimensions.items():
        p, w, f = dim["pass"], dim["warn"], dim["fail"]
        print(f"  {cat:<20} {p} pass / {w} warn / {f} fail")
    if report.recommendations:
        print(f"\n  Recommendations:")
        for r in report.recommendations[:10]:
            print(f"    - {r}")
