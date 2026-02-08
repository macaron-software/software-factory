"""ISIN ↔ Ticker resolver. Unifies identifiers from different scrapers."""

from __future__ import annotations

import logging
import re

from scrapers.market_data.yfinance_provider import YFinanceProvider

logger = logging.getLogger(__name__)

# Common ISIN → ticker overrides (well-known instruments)
KNOWN_MAPPINGS: dict[str, dict] = {
    "IE00B4L5Y983": {"ticker": "IWDA.AS", "name": "iShares Core MSCI World", "exchange": "XAMS"},
    "IE00BK5BQT80": {"ticker": "VWCE.DE", "name": "Vanguard FTSE All-World", "exchange": "XETR"},
    "LU1681043599": {"ticker": "CW8.PA", "name": "Amundi MSCI World", "exchange": "XPAR"},
    "FR0010315770": {"ticker": "CW8.PA", "name": "Amundi MSCI World", "exchange": "XPAR"},
    "IE00B5BMR087": {"ticker": "CSPX.L", "name": "iShares Core S&P 500", "exchange": "XLON"},
    "LU0392494562": {"ticker": "XMWO.DE", "name": "Xtrackers MSCI World", "exchange": "XETR"},
    "FR0007052782": {"ticker": "LVC.PA", "name": "Lyxor CAC 40 (DR)", "exchange": "XPAR"},
    "US0378331005": {"ticker": "AAPL", "name": "Apple Inc.", "exchange": "XNAS"},
    "US5949181045": {"ticker": "MSFT", "name": "Microsoft Corp.", "exchange": "XNAS"},
}

ISIN_REGEX = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")


class ISINResolver:
    """Resolves ISIN ↔ ticker using local cache, known mappings, and Yahoo search."""

    def __init__(self, yfinance: YFinanceProvider | None = None) -> None:
        self._yfinance = yfinance or YFinanceProvider()
        self._cache: dict[str, dict] = dict(KNOWN_MAPPINGS)

    def is_isin(self, identifier: str) -> bool:
        return bool(ISIN_REGEX.match(identifier))

    def resolve(self, identifier: str) -> dict:
        """
        Resolve an identifier (ISIN or ticker) to a standardized dict.
        Returns: {ticker, name, exchange, isin?}
        """
        identifier = identifier.strip().upper()

        # 1. Check local cache
        if identifier in self._cache:
            result = self._cache[identifier]
            logger.debug("Cache hit for %s → %s", identifier, result.get("ticker"))
            return result

        # 2. If it's a ticker (not ISIN), return as-is
        if not self.is_isin(identifier):
            return {"ticker": identifier, "name": identifier, "exchange": None}

        # 3. Yahoo Finance search for ISIN
        results = self._yfinance.search(identifier)
        if results:
            best = results[0]
            resolved = {
                "ticker": best["ticker"],
                "name": best.get("name", ""),
                "exchange": best.get("exchange"),
                "isin": identifier,
            }
            self._cache[identifier] = resolved
            logger.info("Resolved ISIN %s → %s", identifier, best["ticker"])
            return resolved

        logger.warning("Could not resolve: %s", identifier)
        raise ValueError(f"Cannot resolve identifier: {identifier}")

    def add_mapping(self, isin: str, ticker: str, name: str = "", exchange: str = "") -> None:
        """Manually add a mapping to the cache."""
        self._cache[isin] = {
            "ticker": ticker,
            "name": name,
            "exchange": exchange,
            "isin": isin,
        }
