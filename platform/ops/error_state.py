"""
Error signature state management — SQLite-backed.

WHY
---
auto_heal.py groupait les incidents par simple `error_type` et relançait un TMA
epic à chaque cycle, sans mémoire : un même bug connu pouvait déclencher des dizaines
d'epics et de notifications. Ce module apporte la mémoire qui manquait.

WHAT
----
Persiste l'historique de chaque "signature d'erreur" (empreinte naturelle d'un cluster)
pour permettre trois décisions intelligentes :

  NEW        → première occurrence → on alerte et on lance le heal
  REGRESSION → le bug était résolu (ticket fermé) et revient → on ré-alerte
  ONGOING    → bug connu avec ticket ouvert → on supprime le spam

Règles de suppression (méthode should_alert) :
  1. Signature mutée → toujours supprimer
  2. Sévérité S1/S2 → toujours alerter (override tout)
  3. NEW ou REGRESSION → alerter
  4. ONGOING + ticket ouvert → supprimer
  5. Alerté depuis < 24h → supprimer
  6. Sinon → alerter

SOURCE
------
Porté et adapté de airweave-ai/error-monitoring-agent (MIT License)
https://github.com/airweave-ai/error-monitoring-agent/blob/main/backend/state.py

ADAPTATIONS
-----------
- Stockage JSON → SQLite (platform.db, tables error_signatures + error_mutes)
- Suppression de la dépendance filelock
- Matching sémantique des mutes délégué à monitoring-ops agent (tool loop)
- Typage Python natif, pas de Pydantic PreviousErrorState
"""
# Ref: feat-ops

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from ..db.adapter import get_connection

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            return None
    return None


class ErrorStateManager:
    """
    Persists error signature history and mutes in platform.db.

    Tables: error_signatures, error_mutes (created by migrations).
    """

    # ------------------------------------------------------------------
    # Signatures
    # ------------------------------------------------------------------

    def get_signature(self, signature: str) -> Optional[dict]:
        """Return stored state for a signature, or None if unseen."""
        db = get_connection()
        try:
            row = db.execute(
                "SELECT * FROM error_signatures WHERE signature = ?", (signature,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            db.close()

    def upsert_signature(self, signature: str, updates: dict) -> None:
        """Create or update a signature record."""
        db = get_connection()
        try:
            existing = db.execute(
                "SELECT times_seen FROM error_signatures WHERE signature = ?",
                (signature,),
            ).fetchone()
            now_iso = _now().isoformat()
            if existing is None:
                db.execute(
                    """INSERT INTO error_signatures
                       (signature, first_seen, last_seen, times_seen)
                       VALUES (?, ?, ?, 1)""",
                    (signature, now_iso, now_iso),
                )
            else:
                db.execute(
                    """UPDATE error_signatures
                       SET last_seen = ?, times_seen = times_seen + 1
                       WHERE signature = ?""",
                    (now_iso, signature),
                )
            # Apply field updates
            allowed = {
                "last_alerted",
                "last_severity",
                "last_status",
                "last_summary",
                "linked_mission_id",
                "linked_ticket_url",
                "linked_ticket_status",
                "muted_until",
                "muted_by",
                "mute_reason",
            }
            for key, val in updates.items():
                if key in allowed:
                    db.execute(
                        f"UPDATE error_signatures SET {key} = ? WHERE signature = ?",
                        (val, signature),
                    )
            db.commit()
        finally:
            db.close()

    def mark_alerted(self, signature: str) -> None:
        """Record that an alert was sent for this signature."""
        self.upsert_signature(signature, {"last_alerted": _now().isoformat()})

    # ------------------------------------------------------------------
    # Status determination
    # ------------------------------------------------------------------

    CLOSED_TICKET_STATUSES = {
        "completed",
        "done",
        "closed",
        "canceled",
        "cancelled",
        "finished",
        "resolved",
        "fixed",
        "wontfix",
        "archived",
        "rejected",
    }

    def determine_status(self, signature: str, has_open_ticket: bool = False) -> str:
        """
        Determine NEW / REGRESSION / ONGOING for a signature.

        - NEW: never seen before
        - REGRESSION: was seen + had a closed ticket → came back
        - ONGOING: known open issue
        """
        state = self.get_signature(signature)
        if state is None:
            return "NEW"

        ticket_status = (state.get("linked_ticket_status") or "").lower()
        if ticket_status in self.CLOSED_TICKET_STATUSES:
            return "REGRESSION"

        if has_open_ticket:
            return "ONGOING"

        last_alerted = _parse_dt(state.get("last_alerted"))
        if last_alerted is None:
            return "NEW"

        return "ONGOING"

    # ------------------------------------------------------------------
    # Suppression
    # ------------------------------------------------------------------

    def should_alert(
        self,
        signature: str,
        status: str,
        severity: str,
        has_open_ticket: bool = False,
        suppress_window_hours: int = 24,
    ) -> tuple[bool, Optional[str]]:
        """
        Returns (should_alert, suppression_reason).

        Rules (in priority order):
        1. Muted (exact) → suppress
        2. S1/S2 → always alert
        3. NEW → alert
        4. REGRESSION → alert
        5. ONGOING + open ticket → suppress
        6. Alerted within suppress_window_hours → suppress
        7. Default → alert

        For semantic mute matching, use the monitoring_should_alert tool via the monitoring-ops agent.
        """
        if self.is_muted(signature):
            mute = self.get_mute_info(signature)
            return False, f"Muted until {mute.get('muted_until', '?')}"

        if severity in ("S1", "S2"):
            return True, None

        if status == "NEW":
            return True, None

        if status == "REGRESSION":
            return True, None

        if status == "ONGOING" and has_open_ticket:
            return False, "Has open ticket — suppressing spam"

        state = self.get_signature(signature)
        if state:
            last_alerted = _parse_dt(state.get("last_alerted"))
            if last_alerted:
                elapsed = _now() - last_alerted
                if elapsed < timedelta(hours=suppress_window_hours):
                    h = elapsed.total_seconds() / 3600
                    return (
                        False,
                        f"Alerted {h:.1f}h ago (within {suppress_window_hours}h window)",
                    )

        return True, None

    # ------------------------------------------------------------------
    # Mutes
    # ------------------------------------------------------------------

    def is_muted(self, signature: str) -> bool:
        db = get_connection()
        try:
            row = db.execute(
                "SELECT muted_until FROM error_mutes WHERE signature = ?",
                (signature,),
            ).fetchone()
            if row is None:
                return False
            until = _parse_dt(row["muted_until"])
            return until is not None and until > _now()
        finally:
            db.close()

    def get_mute_info(self, signature: str) -> Optional[dict]:
        db = get_connection()
        try:
            row = db.execute(
                "SELECT * FROM error_mutes WHERE signature = ?", (signature,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            db.close()

    def add_mute(
        self,
        signature: str,
        duration_hours: int,
        muted_by: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> None:
        muted_until = (_now() + timedelta(hours=duration_hours)).isoformat()
        db = get_connection()
        try:
            db.execute(
                """INSERT OR REPLACE INTO error_mutes
                   (signature, muted_until, muted_at, muted_by, reason, duration_hours)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    signature,
                    muted_until,
                    _now().isoformat(),
                    muted_by,
                    reason,
                    duration_hours,
                ),
            )
            db.commit()
        finally:
            db.close()
        self.upsert_signature(
            signature,
            {
                "muted_until": muted_until,
                "muted_by": muted_by,
                "mute_reason": reason,
            },
        )

    def remove_mute(self, signature: str) -> None:
        db = get_connection()
        try:
            db.execute("DELETE FROM error_mutes WHERE signature = ?", (signature,))
            db.commit()
        finally:
            db.close()

    def get_active_mutes(self) -> dict[str, dict]:
        db = get_connection()
        try:
            rows = db.execute("SELECT * FROM error_mutes").fetchall()
            now = _now()
            active = {}
            for row in rows:
                until = _parse_dt(row["muted_until"])
                if until and until > now:
                    active[row["signature"]] = dict(row)
            return active
        finally:
            db.close()

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        db = get_connection()
        try:
            total = db.execute("SELECT COUNT(*) as n FROM error_signatures").fetchone()[
                "n"
            ]
            with_ticket = db.execute(
                "SELECT COUNT(*) as n FROM error_signatures WHERE linked_ticket_url IS NOT NULL"
            ).fetchone()["n"]
            active_mutes = len(self.get_active_mutes())
            return {
                "total_signatures": total,
                "signatures_with_tickets": with_ticket,
                "active_mutes": active_mutes,
            }
        finally:
            db.close()


# Singleton
_state_manager: Optional[ErrorStateManager] = None


def get_error_state_manager() -> ErrorStateManager:
    global _state_manager
    if _state_manager is None:
        _state_manager = ErrorStateManager()
    return _state_manager
