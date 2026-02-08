"""Abstract base scraper. All institution scrapers inherit from this."""

from __future__ import annotations

import abc
import logging
from datetime import datetime, timezone

from scrapers.models import Account, Position, SyncResult, SyncStatus, Transaction

logger = logging.getLogger(__name__)


class BaseScraper(abc.ABC):
    """Base class for all bank/broker scrapers."""

    institution_name: str
    display_name: str
    scraper_type: str  # 'api', 'playwright', 'websocket'

    def __init__(self) -> None:
        self.logger = logging.getLogger(f"scraper.{self.institution_name}")

    async def sync(self) -> SyncResult:
        """Run a full sync: login → fetch accounts → fetch transactions/positions → logout."""
        result = SyncResult(
            institution_name=self.institution_name,
            status=SyncStatus.SYNCING,
            started_at=datetime.now(timezone.utc),
        )
        try:
            await self.login()
            accounts = await self.fetch_accounts()
            result.accounts_synced = len(accounts)

            total_tx = 0
            total_pos = 0
            for account in accounts:
                transactions = await self.fetch_transactions(account)
                total_tx += len(transactions)
                positions = await self.fetch_positions(account)
                total_pos += len(positions)

            result.transactions_added = total_tx
            result.positions_updated = total_pos
            result.status = SyncStatus.SUCCESS

        except OTPRequiredError as e:
            result.status = SyncStatus.OTP_REQUIRED
            result.error_message = str(e)
            self.logger.warning("OTP required for %s", self.institution_name)

        except Exception as e:
            result.status = SyncStatus.ERROR
            result.error_message = str(e)
            self.logger.exception("Sync failed for %s", self.institution_name)

        finally:
            try:
                await self.logout()
            except Exception:
                pass
            result.finished_at = datetime.now(timezone.utc)

        return result

    @abc.abstractmethod
    async def login(self) -> None:
        """Authenticate with the institution."""
        ...

    @abc.abstractmethod
    async def logout(self) -> None:
        """Close the session."""
        ...

    @abc.abstractmethod
    async def fetch_accounts(self) -> list[Account]:
        """Fetch all accounts from the institution."""
        ...

    @abc.abstractmethod
    async def fetch_transactions(self, account: Account) -> list[Transaction]:
        """Fetch recent transactions for an account."""
        ...

    async def fetch_positions(self, account: Account) -> list[Position]:
        """Fetch investment positions (override for brokers)."""
        return []


class OTPRequiredError(Exception):
    """Raised when the institution requires OTP verification."""

    def __init__(self, method: str = "sms"):
        self.method = method
        super().__init__(f"OTP required via {method}")
