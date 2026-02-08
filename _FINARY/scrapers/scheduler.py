"""Scheduler for CRON-based sync and market data refresh."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)


def create_scheduler() -> AsyncIOScheduler:
    """Create the scheduler with all configured jobs."""
    scheduler = AsyncIOScheduler(timezone="Europe/Paris")

    # Bank sync: 4x/day at 06:00, 12:00, 18:00, 00:00
    scheduler.add_job(
        sync_all_institutions,
        "cron",
        hour="0,6,12,18",
        id="sync_banks",
        name="Sync all bank accounts",
    )

    # Market data: every 5 min during EU market hours (09:00-17:30 CET)
    scheduler.add_job(
        refresh_quotes,
        "cron",
        day_of_week="mon-fri",
        hour="9-17",
        minute="*/5",
        id="refresh_quotes_eu",
        name="Refresh quotes (EU hours)",
    )

    # Market data: every 5 min during US market hours (15:30-22:00 CET)
    scheduler.add_job(
        refresh_quotes,
        "cron",
        day_of_week="mon-fri",
        hour="15-21",
        minute="*/5",
        id="refresh_quotes_us",
        name="Refresh quotes (US hours)",
    )

    # FX rates: daily at 16:30 CET (ECB publication time)
    scheduler.add_job(
        refresh_fx_rates,
        "cron",
        hour=16,
        minute=30,
        id="refresh_fx",
        name="Refresh ECB FX rates",
    )

    # Price history: daily at 23:00 CET
    scheduler.add_job(
        refresh_price_history,
        "cron",
        hour=23,
        minute=0,
        id="refresh_history",
        name="Refresh price history",
    )

    # Net worth snapshot: daily at 23:30 CET
    scheduler.add_job(
        snapshot_networth,
        "cron",
        hour=23,
        minute=30,
        id="snapshot_networth",
        name="Daily net worth snapshot",
    )

    return scheduler


async def sync_all_institutions() -> None:
    """Sync all configured bank/broker accounts."""
    logger.info("Starting scheduled sync of all institutions")
    # Implementation will import and run each scraper
    # For now, placeholder
    logger.info("Sync complete")


async def refresh_quotes() -> None:
    """Refresh current quotes for all held positions."""
    logger.info("Refreshing market quotes at %s", datetime.now(timezone.utc))


async def refresh_fx_rates() -> None:
    """Fetch latest ECB FX rates."""
    logger.info("Refreshing ECB FX rates")
    from scrapers.market_data.ecb_provider import ECBProvider

    provider = ECBProvider()
    rates = await provider.get_daily_rates()
    logger.info("FX rates updated: %d currencies", len(rates))


async def refresh_price_history() -> None:
    """Update daily OHLCV for all held tickers."""
    logger.info("Refreshing price history")


async def snapshot_networth() -> None:
    """Save daily net worth snapshot."""
    logger.info("Saving net worth snapshot")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    scheduler = create_scheduler()
    scheduler.start()
    try:
        asyncio.get_event_loop().run_forever()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
