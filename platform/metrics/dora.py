"""DORA Metrics — Deployment Frequency, Lead Time, Change Failure Rate, MTTR."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from ..db.migrations import get_db

logger = logging.getLogger(__name__)

_LEVELS = {
    "deploy_freq": [
        (1.0, "elite"),  # ≥1/day
        (0.25, "high"),  # ≥1/week
        (0.033, "medium"),  # ≥1/month
        (0.0, "low"),
    ],
    "lead_time_h": [
        (1, "elite"),  # <1h
        (24, "high"),  # <1 day
        (168, "medium"),  # <1 week
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
    avg = sum(rank.get(lv, 3) for lv in levels) / max(len(levels), 1)
    if avg <= 0.5:
        return "elite"
    if avg <= 1.5:
        return "high"
    if avg <= 2.5:
        return "medium"
    return "low"


class DORAMetrics:
    """Compute DORA metrics from platform DB — uses mission_runs phases as source of truth."""

    def _phase_data(self, project_id: str = "") -> tuple[int, int, int, list]:
        """Get phase counts from mission_runs. Returns (total, done, failed, runs)."""
        import json

        db = get_db()
        try:
            if project_id:
                rows = db.execute(
                    "SELECT phases_json, created_at, updated_at, project_id FROM mission_runs WHERE project_id=?",
                    (project_id,),
                ).fetchall()
            else:
                rows = db.execute(
                    "SELECT phases_json, created_at, updated_at, project_id FROM mission_runs"
                ).fetchall()
            total = done = failed = 0
            runs = []
            for r in rows:
                try:
                    phases = json.loads(r["phases_json"]) if r["phases_json"] else []
                except Exception:
                    phases = []
                t = len(phases)
                d = sum(1 for p in phases if p.get("status") in ("done", "done_with_issues"))
                f = sum(1 for p in phases if p.get("status") == "failed")
                total += t
                done += d
                failed += f
                runs.append(
                    {
                        "total": t,
                        "done": d,
                        "failed": f,
                        "created_at": r["created_at"],
                        "updated_at": r["updated_at"],
                        "project_id": r["project_id"],
                    }
                )
            return total, done, failed, runs
        finally:
            db.close()

    def deployment_frequency(self, project_id: str = "", period_days: int = 30) -> dict:
        """Count completed phases (≈ deployments) — each done phase = one delivery."""
        total, done, failed, runs = self._phase_data(project_id)
        per_day = done / max(period_days, 1)
        level = _classify("deploy_freq", per_day)
        return {
            "count": done,
            "per_day": round(per_day, 2),
            "period_days": period_days,
            "level": level,
        }

    def lead_time_for_changes(self, project_id: str = "", period_days: int = 30) -> dict:
        """Average time from mission start to current progress (hours)."""
        total, done, failed, runs = self._phase_data(project_id)
        if not runs:
            return {"median_hours": 0, "p90_hours": 0, "count": 0, "level": "low"}
        hours = []
        now = datetime.utcnow()
        for r in runs:
            if r["created_at"] and r["done"] > 0:
                try:
                    created = datetime.fromisoformat(
                        r["created_at"].replace("Z", "+00:00").replace("+00:00", "")
                    )
                    updated = (
                        datetime.fromisoformat(
                            r["updated_at"].replace("Z", "+00:00").replace("+00:00", "")
                        )
                        if r["updated_at"]
                        else now
                    )
                    h = (updated - created).total_seconds() / 3600
                    if h >= 0:
                        hours.append(h)
                except Exception:
                    pass
        if not hours:
            return {"median_hours": 0, "p90_hours": 0, "count": 0, "level": "low"}
        hours.sort()
        median = hours[len(hours) // 2]
        p90 = hours[int(len(hours) * 0.9)]
        level = _classify("lead_time_h", median)
        return {
            "median_hours": round(median, 1),
            "p90_hours": round(p90, 1),
            "count": len(hours),
            "level": level,
        }

    def change_failure_rate(self, project_id: str = "", period_days: int = 30) -> dict:
        """Percentage of phases that failed vs total attempted."""
        total, done, failed, runs = self._phase_data(project_id)
        attempted = done + failed
        rate = (failed / attempted * 100) if attempted > 0 else 0
        level = _classify("change_failure_pct", rate)
        return {"rate_pct": round(rate, 1), "failures": failed, "total": attempted, "level": level}

    def mttr(self, project_id: str = "", period_days: int = 30) -> dict:
        """Mean Time To Restore — from incidents."""
        db = get_db()
        try:
            cutoff = (datetime.utcnow() - timedelta(days=period_days)).isoformat()
            rows = db.execute(
                """SELECT (julianday(resolved_at) - julianday(created_at)) * 24 as hours
                   FROM platform_incidents
                   WHERE status='resolved' AND resolved_at IS NOT NULL AND created_at >= ?
                   ORDER BY hours""",
                (cutoff,),
            ).fetchall()
            if not rows:
                return {
                    "median_hours": 0,
                    "count": 0,
                    "level": "high",
                    "note": "no resolved incidents",
                }
            hours = [r["hours"] for r in rows if r["hours"] is not None and r["hours"] >= 0]
            if not hours:
                return {"median_hours": 0, "count": 0, "level": "high"}
            median = hours[len(hours) // 2]
            level = _classify("mttr_h", median)
            return {"median_hours": round(median, 1), "count": len(hours), "level": level}
        finally:
            db.close()

    def velocity_metrics(self, project_id: str = "") -> dict:
        """Phase throughput — phases completed per mission run."""
        total, done, failed, runs = self._phase_data(project_id)
        active_runs = [r for r in runs if r["total"] > 0]
        avg_throughput = done / max(len(active_runs), 1)
        predictability = round(done / max(total, 1) * 100, 1)
        return {
            "sprints": [
                {
                    "sprint": i + 1,
                    "velocity": r["done"],
                    "planned": r["total"],
                    "status": "active",
                    "mission": r["project_id"],
                }
                for i, r in enumerate(active_runs)
            ],
            "total_velocity": done,
            "avg_velocity": round(avg_throughput, 1),
            "predictability_pct": predictability,
            "sprint_count": len(active_runs),
        }

    def llm_cost(self, project_id: str = "", period_days: int = 30) -> dict:
        """LLM usage cost from llm_usage table."""
        db = get_db()
        try:
            cutoff = (datetime.utcnow() - timedelta(days=period_days)).isoformat()
            rows = db.execute(
                "SELECT provider, model, SUM(tokens_in) as tin, SUM(tokens_out) as tout, "
                "SUM(cost_estimate) as cost, COUNT(*) as calls FROM llm_usage "
                "WHERE ts >= ? GROUP BY provider, model ORDER BY cost DESC",
                (cutoff,),
            ).fetchall()
            total_cost = sum(r["cost"] or 0 for r in rows)
            total_calls = sum(r["calls"] or 0 for r in rows)
            total_tokens = sum((r["tin"] or 0) + (r["tout"] or 0) for r in rows)
            by_model = [
                {
                    "provider": r["provider"],
                    "model": r["model"],
                    "calls": r["calls"],
                    "cost": round(r["cost"] or 0, 4),
                    "tokens_in": r["tin"] or 0,
                    "tokens_out": r["tout"] or 0,
                }
                for r in rows
            ]
            return {
                "total_cost_usd": round(total_cost, 2),
                "total_calls": total_calls,
                "total_tokens": total_tokens,
                "by_model": by_model,
            }
        finally:
            db.close()

    def summary(self, project_id: str = "", period_days: int = 30) -> dict:
        """All 4 DORA metrics + velocity + LLM cost + overall level."""
        df = self.deployment_frequency(project_id, period_days)
        lt = self.lead_time_for_changes(project_id, period_days)
        cfr = self.change_failure_rate(project_id, period_days)
        mt = self.mttr(project_id, period_days)
        vel = self.velocity_metrics(project_id)
        llm = self.llm_cost(project_id, period_days)
        overall = _overall_level([df["level"], lt["level"], cfr["level"], mt["level"]])
        return {
            "overall_level": overall,
            "period_days": period_days,
            "project_id": project_id or "all",
            "deployment_frequency": df,
            "lead_time": lt,
            "change_failure_rate": cfr,
            "mttr": mt,
            "velocity": vel,
            "llm_cost": llm,
        }

    def trend(self, project_id: str = "", weeks: int = 12) -> dict:
        """Weekly sparkline data from real platform data."""
        data = {"deploy": [], "lead_time": [], "failure": [], "mttr": []}
        db = get_db()
        try:
            for w in range(weeks - 1, -1, -1):
                end = datetime.utcnow() - timedelta(weeks=w)
                start = end - timedelta(weeks=1)
                start_iso = start.isoformat()
                end_iso = end.isoformat()
                proj_filter = " AND project_id=?" if project_id else ""
                proj_params = (
                    [start_iso, end_iso, project_id] if project_id else [start_iso, end_iso]
                )

                # Deploy: completed sprints in this week
                s_row = db.execute(
                    "SELECT COUNT(*) as cnt FROM sprints WHERE status='completed' AND completed_at >= ? AND completed_at < ?"
                    + (
                        " AND mission_id IN (SELECT id FROM missions WHERE project_id=?)"
                        if project_id
                        else ""
                    ),
                    proj_params,
                ).fetchone()
                data["deploy"].append(s_row["cnt"] if s_row else 0)

                # Lead time: average mission_run duration (hours) for runs completed this week
                lt_rows = db.execute(
                    "SELECT (julianday(updated_at) - julianday(created_at)) * 24 as hours FROM mission_runs "
                    "WHERE status='completed' AND updated_at >= ? AND updated_at < ?" + proj_filter,
                    proj_params,
                ).fetchall()
                avg_lt = (
                    round(sum(r["hours"] for r in lt_rows if r["hours"]) / max(len(lt_rows), 1), 1)
                    if lt_rows
                    else 0
                )
                data["lead_time"].append(avg_lt)

                # Failure: incidents created this week
                f_row = db.execute(
                    "SELECT COUNT(*) as cnt FROM platform_incidents WHERE created_at >= ? AND created_at < ?",
                    (start_iso, end_iso),
                ).fetchone()
                data["failure"].append(f_row["cnt"] if f_row else 0)

                # MTTR: average resolution time (hours) for incidents resolved this week
                mttr_rows = db.execute(
                    "SELECT (julianday(resolved_at) - julianday(created_at)) * 24 as hours "
                    "FROM platform_incidents WHERE status='resolved' AND resolved_at >= ? AND resolved_at < ?",
                    (start_iso, end_iso),
                ).fetchall()
                avg_mttr = (
                    round(
                        sum(r["hours"] for r in mttr_rows if r["hours"]) / max(len(mttr_rows), 1), 1
                    )
                    if mttr_rows
                    else 0
                )
                data["mttr"].append(avg_mttr)
        finally:
            db.close()
        return data


def get_dora_metrics() -> DORAMetrics:
    return DORAMetrics()
