"""ECB FX rates provider — daily EUR/X rates from European Central Bank."""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from xml.etree import ElementTree

import httpx

from scrapers.models import ExchangeRate

logger = logging.getLogger(__name__)

DAILY_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
HIST_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.xml"
NS = {"ecb": "http://www.ecb.int/vocabulary/2002-08-01/eurofxref"}


class ECBProvider:
    """Free, official, daily FX rates from ECB. Published ~16:00 CET."""

    async def get_daily_rates(self) -> dict[str, Decimal]:
        """Fetch today's EUR/X rates. Returns {currency: rate}."""
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(DAILY_URL)
            r.raise_for_status()

        root = ElementTree.fromstring(r.text)
        rates: dict[str, Decimal] = {"EUR": Decimal("1")}

        for cube in root.findall(".//ecb:Cube[@currency]", NS):
            currency = cube.get("currency")
            rate = cube.get("rate")
            if currency and rate:
                rates[currency] = Decimal(rate)

        logger.info("ECB daily rates: %d currencies fetched", len(rates) - 1)
        return rates

    async def get_historical_rates(self) -> list[ExchangeRate]:
        """Fetch historical EUR/X rates (all available history)."""
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(HIST_URL)
            r.raise_for_status()

        root = ElementTree.fromstring(r.text)
        results: list[ExchangeRate] = []

        for time_cube in root.findall(".//ecb:Cube[@time]", NS):
            dt = date.fromisoformat(time_cube.get("time"))
            for rate_cube in time_cube.findall("ecb:Cube[@currency]", NS):
                currency = rate_cube.get("currency")
                rate = rate_cube.get("rate")
                if currency and rate:
                    results.append(
                        ExchangeRate(
                            date=dt,
                            quote_currency=currency,
                            rate=Decimal(rate),
                        )
                    )

        logger.info("ECB historical: %d rate entries fetched", len(results))
        return results

    def convert_to_eur(
        self, amount: Decimal, currency: str, rates: dict[str, Decimal]
    ) -> Decimal:
        """Convert amount from currency to EUR using ECB rates."""
        if currency == "EUR":
            return amount
        rate = rates.get(currency)
        if rate is None or rate == 0:
            raise ValueError(f"No ECB rate for {currency}")
        return (amount / rate).quantize(Decimal("0.01"))

    def convert_from_eur(
        self, amount_eur: Decimal, currency: str, rates: dict[str, Decimal]
    ) -> Decimal:
        """Convert EUR to target currency."""
        if currency == "EUR":
            return amount_eur
        rate = rates.get(currency)
        if rate is None:
            raise ValueError(f"No ECB rate for {currency}")
        return (amount_eur * rate).quantize(Decimal("0.01"))
