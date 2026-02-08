"""Tests for Trade Republic scraper — validates scraper instantiation and config."""

from __future__ import annotations

import pytest

from scrapers.trade_republic.scraper import TradeRepublicScraper


class TestTradeRepublicScraper:
    def test_init(self):
        scraper = TradeRepublicScraper(phone="+33612345678", pin="1234")
        assert scraper.institution_name == "trade_republic"
        assert scraper.display_name == "Trade Republic"
        assert scraper.scraper_type == "websocket"
        assert scraper.phone == "+33612345678"

    def test_default_locale(self):
        scraper = TradeRepublicScraper()
        assert scraper.locale == "fr"
