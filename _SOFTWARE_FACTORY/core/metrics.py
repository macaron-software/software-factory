#!/usr/bin/env python3
"""
Critic Metrics - Team of Rivals Success Rate Tracking
======================================================
Based on arXiv:2601.14351 "If You Want Coherence, Orchestrate a Team of Rivals"

Tracks catch rates for cascaded critics:
- L0: Fast deterministic (25% target)
- L1a: Code Critic (60% target)
- L1b: Security Critic (15% target)
- L2: Architecture Critic (10% target)
- Final: 90%+ success rate
- Residual: <10% user rejection post-deploy

Usage:
    from core.metrics import CriticMetrics, get_metrics

    metrics = get_metrics("ppz")
    metrics.record_l0_check(rejected=True)
    metrics.record_l1_code(rejected=False)
    print(metrics.summary())
"""

import json
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List


# Singleton storage
_metrics_instances: Dict[str, 'CriticMetrics'] = {}
_lock = threading.Lock()


@dataclass
class CriticStats:
    """Stats for a single critic layer"""
    total: int = 0
    rejected: int = 0
    approved: int = 0

    @property
    def catch_rate(self) -> float:
        """Percentage of issues caught (rejected / total)"""
        return (self.rejected / self.total * 100) if self.total > 0 else 0.0

    @property
    def pass_rate(self) -> float:
        """Percentage that passed (approved / total)"""
        return (self.approved / self.total * 100) if self.total > 0 else 0.0


class CriticMetrics:
    """
    Metrics tracker for Team of Rivals cascaded critics.

    Tracks:
    - L0: Fast deterministic checks (test.skip, @ts-ignore, etc.)
    - L1a: Code Critic (MiniMax M2.5) - syntax, logic, API misuse
    - L1b: Security Critic (GLM-4.7-free) - OWASP, secrets, injections
    - L2: Architecture Critic (Opus) - RBAC, validation, error handling
    - Final: Approved by all critics
    - Residual: User rejection post-deploy (feedback loop)
    """

    def __init__(self, project_id: str, db_path: str = None):
        self.project_id = project_id
        self.db_path = db_path or str(Path(__file__).parent.parent / "data" / "metrics.db")

        # In-memory stats (current session)
        self.l0 = CriticStats()
        self.l1_code = CriticStats()
        self.l1_security = CriticStats()
        self.l2_arch = CriticStats()
        self.final_approved = 0
        self.user_rejected = 0  # Post-deploy feedback

        # Initialize DB
        self._init_db()
        self._load_from_db()

    def _init_db(self):
        """Create metrics table if not exists"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS critic_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    layer TEXT NOT NULL,  -- l0, l1_code, l1_security, l2_arch, final, user_reject
                    result TEXT NOT NULL,  -- approved, rejected
                    details TEXT,  -- JSON with additional info
                    UNIQUE(project_id, timestamp, layer)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_metrics_project
                ON critic_metrics(project_id, layer)
            """)

    def _load_from_db(self):
        """Load cumulative stats from DB"""
        with sqlite3.connect(self.db_path) as conn:
            # Load counts per layer
            for layer, stats in [
                ("l0", self.l0),
                ("l1_code", self.l1_code),
                ("l1_security", self.l1_security),
                ("l2_arch", self.l2_arch),
            ]:
                row = conn.execute("""
                    SELECT
                        COUNT(*) as total,
                        SUM(CASE WHEN result = 'rejected' THEN 1 ELSE 0 END) as rejected,
                        SUM(CASE WHEN result = 'approved' THEN 1 ELSE 0 END) as approved
                    FROM critic_metrics
                    WHERE project_id = ? AND layer = ?
                """, (self.project_id, layer)).fetchone()
                if row:
                    stats.total = row[0] or 0
                    stats.rejected = row[1] or 0
                    stats.approved = row[2] or 0

            # Final approved
            row = conn.execute("""
                SELECT COUNT(*) FROM critic_metrics
                WHERE project_id = ? AND layer = 'final' AND result = 'approved'
            """, (self.project_id,)).fetchone()
            self.final_approved = row[0] if row else 0

            # User rejected
            row = conn.execute("""
                SELECT COUNT(*) FROM critic_metrics
                WHERE project_id = ? AND layer = 'user_reject'
            """, (self.project_id,)).fetchone()
            self.user_rejected = row[0] if row else 0

    def _record(self, layer: str, result: str, details: Dict = None):
        """Record a metric to DB"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO critic_metrics (project_id, timestamp, layer, result, details)
                VALUES (?, ?, ?, ?, ?)
            """, (
                self.project_id,
                datetime.now().isoformat(),
                layer,
                result,
                json.dumps(details) if details else None,
            ))

    # === Recording methods ===

    def record_l0_check(self, rejected: bool, details: Dict = None):
        """Record L0 fast check result"""
        self.l0.total += 1
        if rejected:
            self.l0.rejected += 1
        else:
            self.l0.approved += 1
        self._record("l0", "rejected" if rejected else "approved", details)

    def record_l1_code(self, rejected: bool, details: Dict = None):
        """Record L1 Code Critic result"""
        self.l1_code.total += 1
        if rejected:
            self.l1_code.rejected += 1
        else:
            self.l1_code.approved += 1
        self._record("l1_code", "rejected" if rejected else "approved", details)

    def record_l1_security(self, rejected: bool, details: Dict = None):
        """Record L1 Security Critic result"""
        self.l1_security.total += 1
        if rejected:
            self.l1_security.rejected += 1
        else:
            self.l1_security.approved += 1
        self._record("l1_security", "rejected" if rejected else "approved", details)

    def record_l2_arch(self, rejected: bool, details: Dict = None):
        """Record L2 Architecture Critic result"""
        self.l2_arch.total += 1
        if rejected:
            self.l2_arch.rejected += 1
        else:
            self.l2_arch.approved += 1
        self._record("l2_arch", "rejected" if rejected else "approved", details)

    def record_final_approved(self, details: Dict = None):
        """Record final approval (all critics passed)"""
        self.final_approved += 1
        self._record("final", "approved", details)

    def record_user_rejected(self, details: Dict = None):
        """Record user rejection post-deploy (residual error)"""
        self.user_rejected += 1
        self._record("user_reject", "rejected", details)

    # === Computed metrics ===

    @property
    def success_rate(self) -> float:
        """Overall success rate (final approved / total attempted)"""
        total = self.l0.total
        return (self.final_approved / total * 100) if total > 0 else 0.0

    @property
    def residual_rate(self) -> float:
        """Residual error rate (user rejected / final approved)"""
        return (self.user_rejected / self.final_approved * 100) if self.final_approved > 0 else 0.0

    @property
    def cumulative_catch_rate(self) -> float:
        """
        Cumulative catch rate across all layers.
        = 1 - (final approved / total started)
        """
        total = self.l0.total
        if total == 0:
            return 0.0
        remaining = total - self.l0.rejected
        remaining -= self.l1_code.rejected
        remaining -= self.l1_security.rejected
        remaining -= self.l2_arch.rejected
        caught = total - remaining
        return (caught / total * 100)

    # === Reporting ===

    def summary(self) -> Dict:
        """Get summary metrics"""
        return {
            "project_id": self.project_id,
            "layers": {
                "l0_fast": {
                    "total": self.l0.total,
                    "rejected": self.l0.rejected,
                    "catch_rate": f"{self.l0.catch_rate:.1f}%",
                    "target": "25%",
                },
                "l1_code": {
                    "total": self.l1_code.total,
                    "rejected": self.l1_code.rejected,
                    "catch_rate": f"{self.l1_code.catch_rate:.1f}%",
                    "target": "60%",
                },
                "l1_security": {
                    "total": self.l1_security.total,
                    "rejected": self.l1_security.rejected,
                    "catch_rate": f"{self.l1_security.catch_rate:.1f}%",
                    "target": "15%",
                },
                "l2_arch": {
                    "total": self.l2_arch.total,
                    "rejected": self.l2_arch.rejected,
                    "catch_rate": f"{self.l2_arch.catch_rate:.1f}%",
                    "target": "10%",
                },
            },
            "final": {
                "total_started": self.l0.total,
                "approved": self.final_approved,
                "success_rate": f"{self.success_rate:.1f}%",
                "target": "90%+",
            },
            "residual": {
                "user_rejected": self.user_rejected,
                "residual_rate": f"{self.residual_rate:.1f}%",
                "target": "<10%",
            },
            "cumulative_catch_rate": f"{self.cumulative_catch_rate:.1f}%",
        }

    def print_summary(self):
        """Print formatted summary"""
        s = self.summary()
        print(f"\n{'='*60}")
        print(f"CRITIC METRICS - {self.project_id}")
        print(f"{'='*60}")
        print(f"\nCascaded Critics (Swiss Cheese Model):")
        for layer, data in s["layers"].items():
            status = "✅" if float(data["catch_rate"].rstrip("%")) >= float(data["target"].rstrip("%")) else "⚠️"
            print(f"  {status} {layer}: {data['rejected']}/{data['total']} rejected ({data['catch_rate']} catch, target {data['target']})")
        print(f"\nFinal:")
        print(f"  📊 {s['final']['approved']}/{s['final']['total_started']} approved ({s['final']['success_rate']} success, target {s['final']['target']})")
        print(f"\nResidual (post-deploy feedback):")
        print(f"  {'✅' if float(s['residual']['residual_rate'].rstrip('%')) < 10 else '⚠️'} {s['residual']['user_rejected']} user rejections ({s['residual']['residual_rate']}, target {s['residual']['target']})")
        print(f"\n{'='*60}\n")

    def get_recent(self, limit: int = 100) -> List[Dict]:
        """Get recent metric events"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT * FROM critic_metrics
                WHERE project_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (self.project_id, limit)).fetchall()
            return [dict(row) for row in rows]


def get_metrics(project_id: str) -> CriticMetrics:
    """Get or create metrics instance for project (singleton per project)"""
    with _lock:
        if project_id not in _metrics_instances:
            _metrics_instances[project_id] = CriticMetrics(project_id)
        return _metrics_instances[project_id]


# === CLI ===

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Critic Metrics (Team of Rivals)")
    parser.add_argument("project", nargs="?", default="ppz", help="Project ID")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--recent", type=int, default=0, help="Show N recent events")

    args = parser.parse_args()

    metrics = get_metrics(args.project)

    if args.recent > 0:
        events = metrics.get_recent(args.recent)
        if args.json:
            print(json.dumps(events, indent=2))
        else:
            for e in events:
                print(f"{e['timestamp']} | {e['layer']:15} | {e['result']}")
    elif args.json:
        print(json.dumps(metrics.summary(), indent=2))
    else:
        metrics.print_summary()
