"""Finnhub provider — enrichment: company profiles, upcoming dividends."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import Decimal

logger = logging.getLogger(__name__)


class FinnhubProvider:
    """Free tier: 60 calls/min. Used for enrichment, not primary quotes."""

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self._client = None

    @property
    def client(self):
        if self._client is None:
            import finnhub
            self._client = finnhub.Client(api_key=self.api_key)
        return self._client

    def get_profile(self, ticker: str) -> dict | None:
        """Get company profile: sector, country, currency, exchange, logo."""
        try:
            p = self.client.company_profile2(symbol=ticker)
            if not p:
                return None
            return {
                "ticker": p.get("ticker", ticker),
                "name": p.get("name"),
                "sector": p.get("finnhubIndustry"),
                "country": p.get("country"),
                "currency": p.get("currency"),
                "exchange": p.get("exchange"),
                "ipo": p.get("ipo"),
                "market_cap": p.get("marketCapitalization"),
                "logo": p.get("logo"),
                "web_url": p.get("weburl"),
            }
        except Exception as e:
            logger.warning("Finnhub profile failed for %s: %s", ticker, e)
            return None

    def get_upcoming_dividends(self, ticker: str) -> list[dict]:
        """Get dividends scheduled for the next 12 months."""
        try:
            today = date.today()
            end = today + timedelta(days=365)
            divs = self.client.stock_dividends(
                ticker, _from=str(today), to=str(end)
            )
            return [
                {
                    "ex_date": d.get("exDate"),
                    "pay_date": d.get("payDate"),
                    "amount": Decimal(str(d["amount"])) if d.get("amount") else None,
                    "currency": d.get("currency", "USD"),
                }
                for d in divs
                if d.get("amount")
            ]
        except Exception as e:
            logger.warning("Finnhub dividends failed for %s: %s", ticker, e)
            return []

    def get_quote(self, ticker: str) -> dict | None:
        """Get real-time quote (US only on free tier)."""
        try:
            q = self.client.quote(ticker)
            if not q or q.get("c") == 0:
                return None
            return {
                "ticker": ticker,
                "price": Decimal(str(q["c"])),
                "high": Decimal(str(q["h"])),
                "low": Decimal(str(q["l"])),
                "open": Decimal(str(q["o"])),
                "previous_close": Decimal(str(q["pc"])),
            }
        except Exception as e:
            logger.warning("Finnhub quote failed for %s: %s", ticker, e)
            return None
