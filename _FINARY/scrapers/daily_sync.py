#!/usr/bin/env python3
"""daily_sync.py — Connects to existing CDP browser and scrapes all 4 banks.

This script is designed to be run by launchd daily at 08:00.
It connects to Chrome on port 9222 (must already be running with bank sessions).
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
    """Connect to existing browser via CDP and scrape all banks."""
    import httpx

    # Check browser is accessible
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get("http://127.0.0.1:9222/json", timeout=5)
            tabs = r.json()
            print(f"📡 Connected to Chrome — {len(tabs)} tabs found")
    except Exception as e:
        print(f"❌ Cannot connect to Chrome on :9222 — {e}")
        print("   Start Chrome with: open -a 'Google Chrome' --args --remote-debugging-port=9222")
        return False

    # Use playwright to connect to CDP
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        browser = await pw.chromium.connect_over_cdp("http://127.0.0.1:9222")
        context = browser.contexts[0] if browser.contexts else None
        if not context:
            print("❌ No browser context found")
            return False

        print(f"🌐 Browser context with {len(context.pages)} pages")

        today = date.today().isoformat()
        results = {}

        # Scrape each bank from its existing tab
        for page in context.pages:
            url = page.url.lower()
            try:
                if "trade.republic" in url or "traderepublic" in url:
                    print("  📊 Scraping Trade Republic...")
                    data = await _scrape_tr(page)
                    if data:
                        results["tr"] = data
                        _save(f"extraction_complete_{today}.json", data, "tr")

                elif "boursobank" in url or "boursorama" in url:
                    print("  🏦 Scraping Boursobank...")
                    data = await _scrape_bourso(page)
                    if data:
                        results["bourso"] = data
                        _save(f"bourso_deep_{today}.json", data)

                elif "ibkr" in url or "interactivebrokers" in url:
                    print("  📈 Scraping IBKR...")
                    data = await _scrape_ibkr(page)
                    if data:
                        results["ibkr"] = data
                        _save(f"extraction_complete_{today}.json", data, "ibkr")

                elif "credit-agricole" in url or "ca-centrest" in url:
                    print("  🏛️  Scraping Crédit Agricole...")
                    data = await _scrape_ca(page)
                    if data:
                        results["ca"] = data
                        _save(f"ca_deep_{today}.json", data)

            except Exception as e:
                print(f"  ⚠️  Error scraping {url[:50]}: {e}")

        print(f"\n✅ Scraped {len(results)} banks: {', '.join(results.keys())}")

    return len(results) > 0


def _save(filename: str, data, section: str = None):
    """Save or merge data into a JSON file."""
    path = DATA_DIR / filename
    existing = {}
    if path.exists():
        with open(path) as f:
            existing = json.load(f)

    if section:
        if section == "tr":
            existing["tr_positions"] = data.get("positions", [])
            existing["tr_cash"] = data.get("cash", 0)
        elif section == "ibkr":
            existing["ibkr_positions"] = data.get("positions", [])
            existing["ibkr_extras"] = data.get("extras", {})
    else:
        existing = data

    with open(path, "w") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False, default=str)
    print(f"    💾 Saved {path.name}")


async def _scrape_tr(page) -> dict:
    """Scrape Trade Republic portfolio from existing page."""
    await page.reload(wait_until="domcontentloaded")
    await page.wait_for_timeout(3000)

    positions = await page.evaluate("""() => {
        const rows = document.querySelectorAll('[class*="portfolio"] [class*="instrument"], [class*="stockList"] li, [data-testid*="instrument"]');
        return Array.from(rows).map(r => ({
            name: r.querySelector('[class*="name"], [class*="title"]')?.textContent?.trim() || '',
            value: r.querySelector('[class*="value"], [class*="price"]')?.textContent?.trim() || '',
        })).filter(r => r.name);
    }""")

    cash_el = await page.query_selector('[class*="cash"], [class*="available"]')
    cash = await cash_el.text_content() if cash_el else "0"

    return {"positions": positions, "cash": cash} if positions else None


async def _scrape_bourso(page) -> dict:
    """Scrape Boursobank from existing page."""
    await page.reload(wait_until="domcontentloaded")
    await page.wait_for_timeout(3000)

    accounts = await page.evaluate("""() => {
        const items = document.querySelectorAll('.account-synthesis__item, [class*="account"]');
        return Array.from(items).map(el => ({
            name: el.querySelector('.account-synthesis__name, [class*="name"]')?.textContent?.trim() || '',
            balance: el.querySelector('.account-synthesis__amount, [class*="amount"]')?.textContent?.trim() || '',
        })).filter(a => a.name);
    }""")

    return {"accounts": accounts} if accounts else None


async def _scrape_ibkr(page) -> dict:
    """Scrape IBKR from existing page."""
    await page.reload(wait_until="domcontentloaded")
    await page.wait_for_timeout(5000)

    data = await page.evaluate("""() => {
        const rows = document.querySelectorAll('tr.pos-row, [class*="position-row"]');
        const positions = Array.from(rows).map(r => {
            const cells = r.querySelectorAll('td');
            return {
                symbol: cells[0]?.textContent?.trim() || '',
                qty: cells[1]?.textContent?.trim() || '',
                price: cells[2]?.textContent?.trim() || '',
                value: cells[3]?.textContent?.trim() || '',
                pnl: cells[4]?.textContent?.trim() || '',
            };
        }).filter(r => r.symbol);
        return { positions };
    }""")

    return data if data.get("positions") else None


async def _scrape_ca(page) -> dict:
    """Scrape Crédit Agricole from existing page."""
    await page.reload(wait_until="domcontentloaded")
    await page.wait_for_timeout(3000)

    accounts = await page.evaluate("""() => {
        const items = document.querySelectorAll('.ca-table tr, [class*="account-line"]');
        return Array.from(items).map(el => ({
            name: el.querySelector('td:first-child, [class*="label"]')?.textContent?.trim() || '',
            balance: el.querySelector('td:last-child, [class*="amount"]')?.textContent?.trim() || '',
        })).filter(a => a.name && a.balance);
    }""")

    return {"accounts": accounts, "credits": []} if accounts else None


def rebuild_patrimoine():
    """Rebuild patrimoine_complet from latest scrape data."""
    from build_patrimoine import build
    build()


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
