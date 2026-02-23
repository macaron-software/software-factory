"""MercatoService — wallet, listing, transfer, draft operations."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from ..db.migrations import get_db

INITIAL_BALANCE = 5000


# ── Dataclasses ──────────────────────────────────────────


@dataclass
class Wallet:
    project_id: str
    balance: int = INITIAL_BALANCE
    total_earned: int = 0
    total_spent: int = 0


@dataclass
class Assignment:
    agent_id: str
    project_id: str
    assignment_type: str = "owned"
    loan_expires_at: str | None = None
    loan_from_project: str | None = None


@dataclass
class Listing:
    id: str
    agent_id: str
    seller_project: str
    listing_type: str = "transfer"
    asking_price: int = 0
    loan_weeks: int | None = None
    buyout_clause: int | None = None
    status: str = "active"
    created_at: str = ""
    expires_at: str | None = None


@dataclass
class Transfer:
    id: str
    listing_id: str | None
    agent_id: str
    from_project: str
    to_project: str
    transfer_type: str
    price: int
    completed_at: str = ""


# ── Service ──────────────────────────────────────────────


class MercatoService:
    # ── Wallet ───────────────────────────────────────────

    def get_wallet(self, project_id: str) -> Wallet:
        conn = get_db()
        row = conn.execute(
            "SELECT * FROM project_wallets WHERE project_id = ?", (project_id,)
        ).fetchone()
        if row:
            conn.close()
            return Wallet(
                project_id=row["project_id"],
                balance=row["balance"],
                total_earned=row["total_earned"],
                total_spent=row["total_spent"],
            )
        conn.execute(
            "INSERT INTO project_wallets (project_id, balance) VALUES (?, ?)",
            (project_id, INITIAL_BALANCE),
        )
        conn.execute(
            "INSERT INTO token_transactions (project_id, amount, reason) VALUES (?, ?, ?)",
            (project_id, INITIAL_BALANCE, "initial"),
        )
        conn.commit()
        conn.close()
        return Wallet(project_id=project_id, balance=INITIAL_BALANCE)

    def adjust_balance(
        self, project_id: str, amount: int, reason: str, reference_id: str | None = None
    ) -> Wallet:
        w = self.get_wallet(project_id)
        new_balance = w.balance + amount
        if new_balance < 0:
            raise ValueError(f"Insufficient funds: {w.balance} + {amount} < 0")
        conn = get_db()
        if amount >= 0:
            conn.execute(
                "UPDATE project_wallets SET balance = balance + ?, total_earned = total_earned + ?, updated_at = CURRENT_TIMESTAMP WHERE project_id = ?",
                (amount, amount, project_id),
            )
        else:
            conn.execute(
                "UPDATE project_wallets SET balance = balance + ?, total_spent = total_spent + ?, updated_at = CURRENT_TIMESTAMP WHERE project_id = ?",
                (amount, abs(amount), project_id),
            )
        conn.execute(
            "INSERT INTO token_transactions (project_id, amount, reason, reference_id) VALUES (?, ?, ?, ?)",
            (project_id, amount, reason, reference_id),
        )
        conn.commit()
        conn.close()
        return self.get_wallet(project_id)

    def get_transactions(self, project_id: str, limit: int = 50) -> list[dict]:
        conn = get_db()
        rows = conn.execute(
            "SELECT * FROM token_transactions WHERE project_id = ? ORDER BY created_at DESC LIMIT ?",
            (project_id, limit),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ── Assignments ──────────────────────────────────────

    def get_assignment(self, agent_id: str) -> Assignment | None:
        conn = get_db()
        row = conn.execute(
            "SELECT * FROM agent_assignments WHERE agent_id = ?", (agent_id,)
        ).fetchone()
        conn.close()
        if not row:
            return None
        return Assignment(
            agent_id=row["agent_id"],
            project_id=row["project_id"],
            assignment_type=row["assignment_type"],
            loan_expires_at=row["loan_expires_at"],
            loan_from_project=row["loan_from_project"],
        )

    def get_project_agents(self, project_id: str) -> list[Assignment]:
        conn = get_db()
        rows = conn.execute(
            "SELECT * FROM agent_assignments WHERE project_id = ?", (project_id,)
        ).fetchall()
        conn.close()
        return [
            Assignment(
                agent_id=r["agent_id"],
                project_id=r["project_id"],
                assignment_type=r["assignment_type"],
                loan_expires_at=r["loan_expires_at"],
                loan_from_project=r["loan_from_project"],
            )
            for r in rows
        ]

    def get_free_agents(self) -> list[str]:
        """Return agent IDs not assigned to any project."""
        from ..agents.store import get_agent_store

        store = get_agent_store()
        all_agents = store.list_all()
        conn = get_db()
        assigned = {
            r["agent_id"] for r in conn.execute("SELECT agent_id FROM agent_assignments").fetchall()
        }
        conn.close()
        return [a.id for a in all_agents if a.id not in assigned]

    def draft_agent(self, agent_id: str, project_id: str) -> Assignment:
        """Recruit a free agent to a project (no cost)."""
        existing = self.get_assignment(agent_id)
        if existing:
            raise ValueError(f"Agent {agent_id} already assigned to {existing.project_id}")
        conn = get_db()
        conn.execute(
            "INSERT INTO agent_assignments (agent_id, project_id, assignment_type) VALUES (?, ?, 'owned')",
            (agent_id, project_id),
        )
        conn.commit()
        conn.close()
        return Assignment(agent_id=agent_id, project_id=project_id)

    # ── Listings ─────────────────────────────────────────

    def list_active(self) -> list[Listing]:
        conn = get_db()
        rows = conn.execute(
            "SELECT * FROM mercato_listings WHERE status = 'active' ORDER BY created_at DESC"
        ).fetchall()
        conn.close()
        return [self._row_to_listing(r) for r in rows]

    def create_listing(
        self,
        agent_id: str,
        seller_project: str,
        listing_type: str = "transfer",
        asking_price: int = 0,
        loan_weeks: int | None = None,
        buyout_clause: int | None = None,
    ) -> Listing:
        assignment = self.get_assignment(agent_id)
        if not assignment or assignment.project_id != seller_project:
            raise ValueError(f"Agent {agent_id} not owned by project {seller_project}")
        lid = uuid.uuid4().hex[:12]
        expires = None
        if listing_type == "loan" and loan_weeks:
            expires = (datetime.now(tz=timezone.utc) + timedelta(weeks=loan_weeks + 2)).isoformat()
        conn = get_db()
        conn.execute(
            "INSERT INTO mercato_listings (id, agent_id, seller_project, listing_type, asking_price, loan_weeks, buyout_clause, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                lid,
                agent_id,
                seller_project,
                listing_type,
                asking_price,
                loan_weeks,
                buyout_clause,
                expires,
            ),
        )
        conn.commit()
        conn.close()
        return Listing(
            id=lid,
            agent_id=agent_id,
            seller_project=seller_project,
            listing_type=listing_type,
            asking_price=asking_price,
            loan_weeks=loan_weeks,
            buyout_clause=buyout_clause,
        )

    def cancel_listing(self, listing_id: str, project_id: str) -> bool:
        conn = get_db()
        cur = conn.execute(
            "UPDATE mercato_listings SET status = 'cancelled' WHERE id = ? AND seller_project = ? AND status = 'active'",
            (listing_id, project_id),
        )
        conn.commit()
        conn.close()
        return cur.rowcount > 0

    # ── Transfers ────────────────────────────────────────

    def execute_transfer(self, listing_id: str, buyer_project: str) -> Transfer:
        conn = get_db()
        listing_row = conn.execute(
            "SELECT * FROM mercato_listings WHERE id = ? AND status = 'active'", (listing_id,)
        ).fetchone()
        if not listing_row:
            conn.close()
            raise ValueError("Listing not found or inactive")
        listing = self._row_to_listing(listing_row)
        if listing.seller_project == buyer_project:
            conn.close()
            raise ValueError("Cannot buy from yourself")

        # Check buyer funds
        buyer_wallet = self.get_wallet(buyer_project)
        if buyer_wallet.balance < listing.asking_price:
            conn.close()
            raise ValueError(f"Insufficient funds: {buyer_wallet.balance} < {listing.asking_price}")

        tid = uuid.uuid4().hex[:12]
        transfer_type = listing.listing_type

        if transfer_type == "transfer":
            # Permanent transfer
            conn.execute(
                "UPDATE agent_assignments SET project_id = ?, assignment_type = 'owned', loan_expires_at = NULL, loan_from_project = NULL WHERE agent_id = ?",
                (buyer_project, listing.agent_id),
            )
        else:
            # Loan
            expires = (datetime.now(tz=timezone.utc) + timedelta(weeks=listing.loan_weeks or 4)).isoformat()
            conn.execute(
                "UPDATE agent_assignments SET project_id = ?, assignment_type = 'loaned', loan_expires_at = ?, loan_from_project = ? WHERE agent_id = ?",
                (buyer_project, expires, listing.seller_project, listing.agent_id),
            )

        conn.execute("UPDATE mercato_listings SET status = 'sold' WHERE id = ?", (listing_id,))
        conn.execute(
            "INSERT INTO mercato_transfers (id, listing_id, agent_id, from_project, to_project, transfer_type, price) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                tid,
                listing_id,
                listing.agent_id,
                listing.seller_project,
                buyer_project,
                transfer_type,
                listing.asking_price,
            ),
        )
        conn.commit()
        conn.close()

        # Adjust balances
        self.adjust_balance(buyer_project, -listing.asking_price, "transfer_buy", tid)
        self.adjust_balance(listing.seller_project, listing.asking_price, "transfer_sell", tid)

        return Transfer(
            id=tid,
            listing_id=listing_id,
            agent_id=listing.agent_id,
            from_project=listing.seller_project,
            to_project=buyer_project,
            transfer_type=transfer_type,
            price=listing.asking_price,
        )

    def get_transfers(self, project_id: str | None = None, limit: int = 50) -> list[Transfer]:
        conn = get_db()
        if project_id:
            rows = conn.execute(
                "SELECT * FROM mercato_transfers WHERE from_project = ? OR to_project = ? ORDER BY completed_at DESC LIMIT ?",
                (project_id, project_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM mercato_transfers ORDER BY completed_at DESC LIMIT ?", (limit,)
            ).fetchall()
        conn.close()
        return [
            Transfer(
                id=r["id"],
                listing_id=r["listing_id"],
                agent_id=r["agent_id"],
                from_project=r["from_project"],
                to_project=r["to_project"],
                transfer_type=r["transfer_type"],
                price=r["price"],
                completed_at=r["completed_at"],
            )
            for r in rows
        ]

    def expire_loans(self) -> int:
        """Return loaned agents whose loan has expired. Returns count of expired."""
        conn = get_db()
        now = datetime.now(tz=timezone.utc).isoformat()
        expired = conn.execute(
            "SELECT * FROM agent_assignments WHERE assignment_type = 'loaned' AND loan_expires_at < ?",
            (now,),
        ).fetchall()
        count = 0
        for row in expired:
            conn.execute(
                "UPDATE agent_assignments SET project_id = ?, assignment_type = 'owned', loan_expires_at = NULL, loan_from_project = NULL WHERE agent_id = ?",
                (row["loan_from_project"], row["agent_id"]),
            )
            count += 1
        if count:
            conn.commit()
        conn.close()
        return count

    # ── Helpers ───────────────────────────────────────────

    def _row_to_listing(self, row) -> Listing:
        return Listing(
            id=row["id"],
            agent_id=row["agent_id"],
            seller_project=row["seller_project"],
            listing_type=row["listing_type"],
            asking_price=row["asking_price"],
            loan_weeks=row["loan_weeks"],
            buyout_clause=row["buyout_clause"],
            status=row["status"],
            created_at=row["created_at"] or "",
            expires_at=row["expires_at"],
        )


# ── Singleton ────────────────────────────────────────────

_service: MercatoService | None = None


def get_mercato_service() -> MercatoService:
    global _service
    if _service is None:
        _service = MercatoService()
    return _service
