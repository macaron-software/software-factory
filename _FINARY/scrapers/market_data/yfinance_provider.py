"""Yahoo Finance provider — primary source for quotes, history, dividends."""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

import httpx
import yfinance as yf

from scrapers.models import PricePoint

logger = logging.getLogger(__name__)


class YFinanceProvider:
    """Free, unlimited. Delayed ~15min for US, real-time for EU."""

    def get_quote(self, ticker: str) -> dict:
        """Get current quote + metadata for a ticker."""
        t = yf.Ticker(ticker)
        info = t.info
        return {
            "ticker": ticker,
            "price": Decimal(str(info.get("currentPrice") or info.get("regularMarketPrice") or 0)),
            "previous_close": Decimal(str(info.get("previousClose", 0))),
            "currency": info.get("currency", "USD"),
            "name": info.get("longName") or info.get("shortName") or ticker,
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "country": info.get("country"),
            "exchange": info.get("exchange"),
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE"),
            "dividend_yield": info.get("dividendYield"),
            "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
            "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
        }

    def get_history(self, ticker: str, period: str = "5y") -> list[PricePoint]:
        """Get daily OHLCV history."""
        t = yf.Ticker(ticker)
        df = t.history(period=period)
        if df.empty:
            return []

        currency = (t.info or {}).get("currency", "USD")
        points = []
        for idx, row in df.iterrows():
            points.append(
                PricePoint(
                    ticker=ticker,
                    date=idx.date(),
                    open=Decimal(str(round(row["Open"], 4))),
                    high=Decimal(str(round(row["High"], 4))),
                    low=Decimal(str(round(row["Low"], 4))),
                    close=Decimal(str(round(row["Close"], 4))),
                    volume=int(row["Volume"]),
                    currency=currency,
                )
            )
        return points

    def get_dividends(self, ticker: str) -> list[dict]:
        """Get dividend history."""
        t = yf.Ticker(ticker)
        divs = t.dividends
        if divs.empty:
            return []
        return [
            {
                "date": idx.date(),
                "amount": Decimal(str(round(val, 6))),
            }
            for idx, val in divs.items()
        ]

    def search(self, query: str) -> list[dict]:
        """Search for tickers by name, ISIN, or keyword."""
        try:
            r = httpx.get(
                "https://query2.finance.yahoo.com/v1/finance/search",
                params={"q": query, "quotesCount": 10, "newsCount": 0},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10,
            )
            r.raise_for_status()
            results = r.json().get("quotes", [])
            return [
                {
                    "ticker": q["symbol"],
                    "name": q.get("longname") or q.get("shortname", ""),
                    "exchange": q.get("exchange"),
                    "type": q.get("quoteType"),
                }
                for q in results
                if "symbol" in q
            ]
        except Exception as e:
            logger.warning("Yahoo search failed for '%s': %s", query, e)
            return []
