"""DORA Metrics — Deployment Frequency, Lead Time, Change Failure Rate, MTTR."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from ..db.migrations import get_db

logger = logging.getLogger(__name__)

_LEVELS = {
    "deploy_freq": [
        (1.0, "elite"),     # ≥1/day
        (0.25, "high"),     # ≥1/week
        (0.033, "medium"),  # ≥1/month
        (0.0, "low"),
    ],
    "lead_time_h": [
        (1, "elite"),       # <1h
        (24, "high"),       # <1 day
        (168, "medium"),    # <1 week
        (999999, "low"),
    ],
    "change_failure_pct": [
        (5, "elite"),
        (10, "high"),
        (15, "medium"),
        (100, "low"),
    ],
    "mttr_h": [
        (1, "elite"),
        (24, "high"),
        (168, "medium"),
        (999999, "low"),
    ],
}


def _classify(metric: str, value: float) -> str:
    for threshold, level in _LEVELS[metric]:
        if metric in ("deploy_freq",):
            if value >= threshold:
                return level
        else:
            if value <= threshold:
                return level
    return "low"


def _overall_level(levels: list[str]) -> str:
    rank = {"elite": 0, "high": 1, "medium": 2, "low": 3}
    avg = sum(rank.get(l, 3) for l in levels) / max(len(levels), 1)
    if avg <= 0.5:
        return "elite"
    if avg <= 1.5:
        return "high"
    if avg <= 2.5:
        return "medium"
    return "low"


class DORAMetrics:
    """Compute DORA metrics from platform DB."""

    def deployment_frequency(self, project_id: str = "", period_days: int = 30) -> dict:
        """Count completed workflow sessions (≈ deployments) over the period."""
        db = get_db()
        try:
            cutoff = (datetime.utcnow() - timedelta(days=period_days)).isoformat()
            if project_id:
                rows = db.execute(
                    """SELECT COUNT(*) as cnt FROM sessions
                       WHERE status='completed' AND project_id=?
                       AND completed_at >= ?""",
                    (project_id, cutoff),
                ).fetchone()
            else:
                rows = db.execute(
                    """SELECT COUNT(*) as cnt FROM sessions
                       WHERE status='completed' AND completed_at >= ?""",
                    (cutoff,),
                ).fetchone()
            count = rows["cnt"] if rows else 0
            per_day = count / max(period_days, 1)
            level = _classify("deploy_freq", per_day)
            return {"count": count, "per_day": round(per_day, 2), "period_days": period_days, "level": level}
        finally:
            db.close()

    def lead_time_for_changes(self, project_id: str = "", period_days: int = 30) -> dict:
        """Median time from session creation to completion (hours)."""
        db = get_db()
        try:
            cutoff = (datetime.utcnow() - timedelta(days=period_days)).isoformat()
            q = """SELECT
                       (julianday(completed_at) - julianday(created_at)) * 24 as hours
                   FROM sessions
                   WHERE status='completed' AND completed_at >= ?
                     AND completed_at IS NOT NULL AND created_at IS NOT NULL"""
            params: list = [cutoff]
            if project_id:
                q += " AND project_id=?"
                params.append(project_id)
            q += " ORDER BY hours"
            rows = db.execute(q, params).fetchall()
            if not rows:
                return {"median_hours": 0, "p90_hours": 0, "count": 0, "level": "low"}
            hours = [r["hours"] for r in rows if r["hours"] is not None and r["hours"] >= 0]
            if not hours:
                return {"median_hours": 0, "p90_hours": 0, "count": 0, "level": "low"}
            median = hours[len(hours) // 2]
            p90 = hours[int(len(hours) * 0.9)]
            level = _classify("lead_time_h", median)
            return {"median_hours": round(median, 1), "p90_hours": round(p90, 1), "count": len(hours), "level": level}
        finally:
            db.close()

    def change_failure_rate(self, project_id: str = "", period_days: int = 30) -> dict:
        """Percentage of sessions that failed."""
        db = get_db()
        try:
            cutoff = (datetime.utcnow() - timedelta(days=period_days)).isoformat()
            base = "FROM sessions WHERE created_at >= ?"
            params: list = [cutoff]
            if project_id:
                base += " AND project_id=?"
                params.append(project_id)

            total = db.execute(f"SELECT COUNT(*) as cnt {base} AND status IN ('completed','failed')", params).fetchone()["cnt"]
            failed = db.execute(f"SELECT COUNT(*) as cnt {base} AND status='failed'", params).fetchone()["cnt"]
            rate = (failed / total * 100) if total > 0 else 0
            level = _classify("change_failure_pct", rate)
            return {"rate_pct": round(rate, 1), "failures": failed, "total": total, "level": level}
        finally:
            db.close()

    def mttr(self, project_id: str = "", period_days: int = 30) -> dict:
        """Mean Time To Restore — duration of corrective missions (parent_mission_id != null)."""
        db = get_db()
        try:
            cutoff = (datetime.utcnow() - timedelta(days=period_days)).isoformat()
            q = """SELECT
                       (julianday(completed_at) - julianday(created_at)) * 24 as hours
                   FROM missions
                   WHERE parent_mission_id IS NOT NULL
                     AND status='completed' AND completed_at IS NOT NULL
                     AND created_at >= ?"""
            params: list = [cutoff]
            if project_id:
                q += " AND project_id=?"
                params.append(project_id)
            q += " ORDER BY hours"
            rows = db.execute(q, params).fetchall()
            if not rows:
                # Fallback: use failed→completed session pairs
                return {"median_hours": 0, "count": 0, "level": "high", "note": "no corrective missions"}
            hours = [r["hours"] for r in rows if r["hours"] is not None and r["hours"] >= 0]
            if not hours:
                return {"median_hours": 0, "count": 0, "level": "high"}
            median = hours[len(hours) // 2]
            level = _classify("mttr_h", median)
            return {"median_hours": round(median, 1), "count": len(hours), "level": level}
        finally:
            db.close()

    def summary(self, project_id: str = "", period_days: int = 30) -> dict:
        """All 4 DORA metrics + overall level."""
        df = self.deployment_frequency(project_id, period_days)
        lt = self.lead_time_for_changes(project_id, period_days)
        cfr = self.change_failure_rate(project_id, period_days)
        mt = self.mttr(project_id, period_days)
        overall = _overall_level([df["level"], lt["level"], cfr["level"], mt["level"]])
        return {
            "overall_level": overall,
            "period_days": period_days,
            "project_id": project_id or "all",
            "deployment_frequency": df,
            "lead_time": lt,
            "change_failure_rate": cfr,
            "mttr": mt,
        }

    def trend(self, project_id: str = "", weeks: int = 12) -> dict:
        """Weekly sparkline data for each metric."""
        data = {"deploy": [], "lead_time": [], "failure": [], "mttr": []}
        for w in range(weeks - 1, -1, -1):
            end = datetime.utcnow() - timedelta(weeks=w)
            start = end - timedelta(weeks=1)
            # simplified: just count completions per week
            db = get_db()
            try:
                params: list = [start.isoformat(), end.isoformat()]
                pfilter = ""
                if project_id:
                    pfilter = " AND project_id=?"
                    params.append(project_id)

                completed = db.execute(
                    f"SELECT COUNT(*) as cnt FROM sessions WHERE status='completed' AND completed_at >= ? AND completed_at < ?{pfilter}",
                    params,
                ).fetchone()["cnt"]
                data["deploy"].append(completed)

                failed = db.execute(
                    f"SELECT COUNT(*) as cnt FROM sessions WHERE status='failed' AND created_at >= ? AND created_at < ?{pfilter}",
                    params,
                ).fetchone()["cnt"]
                total = completed + failed
                data["failure"].append(round(failed / total * 100, 1) if total > 0 else 0)

                lt_rows = db.execute(
                    f"""SELECT AVG((julianday(completed_at)-julianday(created_at))*24) as h
                        FROM sessions WHERE status='completed' AND completed_at >= ? AND completed_at < ?{pfilter}""",
                    params,
                ).fetchone()
                data["lead_time"].append(round(lt_rows["h"] or 0, 1))

                data["mttr"].append(0)  # requires corrective mission tracking
            finally:
                db.close()

        return data


def get_dora_metrics() -> DORAMetrics:
    return DORAMetrics()
