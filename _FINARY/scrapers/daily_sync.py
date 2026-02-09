#!/usr/bin/env python3
"""daily_sync.py — Connects to existing CDP browser and scrapes all 4 banks.

This script is designed to be run by launchd daily at 08:00.
It connects to Chrome on port 18800 (must already be running with bank sessions).
After scraping, it rebuilds patrimoine_complet.

Usage:
    python3 daily_sync.py            # Full sync
    python3 daily_sync.py --rebuild  # Only rebuild patrimoine from existing data
"""

import asyncio
import json
import sys
from datetime import date
from pathlib import Path

DIR = Path(__file__).parent
DATA_DIR = DIR / "data"
sys.path.insert(0, str(DIR))


async def sync_all():
    """Connect to existing browser via CDP and scrape using existing tabs."""
    import httpx

    # Check browser is accessible
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get("http://127.0.0.1:18800/json", timeout=5)
            tabs = r.json()
            print(f"📡 Connected to Chrome — {len(tabs)} tabs found")
    except Exception as e:
        print(f"❌ Cannot connect to Chrome on :18800 — {e}")
        print("   Start Chrome with: open -a 'Google Chrome' --args --remote-debugging-port=18800")
        return False

    # Use playwright to connect to CDP
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        browser = await pw.chromium.connect_over_cdp("http://127.0.0.1:18800")
        context = browser.contexts[0] if browser.contexts else None
        if not context:
            print("❌ No browser context found")
            return False

        print(f"🌐 Browser context with {len(context.pages)} pages")

        # Map existing tabs to banks by URL
        bank_map = {
            "traderepublic": "Trade Republic",
            "boursobank": "Boursobank",
            "interactivebrokers": "IBKR",
            "credit-agricole": "Crédit Agricole",
            "ca-languedoc": "Crédit Agricole",
            "ca-centrest": "Crédit Agricole",
        }

        # Import scrape functions
        from scrape_all import (
            scrape_tr_details,
            scrape_bourso_details,
            scrape_ibkr_details,
            scrape_ca_details,
        )

        scrape_fns = {
            "Trade Republic": scrape_tr_details,
            "Boursobank": scrape_bourso_details,
            "IBKR": scrape_ibkr_details,
            "Crédit Agricole": scrape_ca_details,
        }

        # Find which banks have open tabs
        found_banks = set()
        for page in context.pages:
            url = page.url.lower()
            for domain, bank_name in bank_map.items():
                if domain in url:
                    found_banks.add(bank_name)
                    break

        print(f"  🏦 Banks with open sessions: {', '.join(found_banks) or 'none'}")

        results = []
        for bank_name, fn in scrape_fns.items():
            if bank_name not in found_banks:
                print(f"  ⚠️  {bank_name}: no open session, skipping")
                continue
            try:
                print(f"  📊 Scraping {bank_name}...")
                page = await fn(context)
                if page:
                    results.append(bank_name)
                    print(f"    ✅ {bank_name} done")
                else:
                    print(f"    ⚠️  {bank_name}: no data returned")
            except Exception as e:
                print(f"    ❌ {bank_name}: {e}")

        print(f"\n✅ Scraped {len(results)}/{len(found_banks)} banks: {', '.join(results)}")

    return len(results) > 0


def rebuild_patrimoine():
    """Rebuild patrimoine_complet from latest scrape data."""
    from build_patrimoine import build
    build(date.today().isoformat())


async def main():
    if "--rebuild" in sys.argv:
        rebuild_patrimoine()
        return

    print(f"🔄 Daily sync — {date.today().isoformat()}")
    success = await sync_all()

    if success:
        print("\n🔨 Rebuilding patrimoine...")
        rebuild_patrimoine()
    else:
        print("\n⚠️  Sync failed — patrimoine not updated")


if __name__ == "__main__":
    asyncio.run(main())
