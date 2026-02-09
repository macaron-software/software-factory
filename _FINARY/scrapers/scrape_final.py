#!/usr/bin/env python3
"""
Final extraction: TR ISINs + IBKR full table + consolidated patrimony.
Connects via CDP, NEVER closes browser.
"""
import asyncio
import json
import re
import os
from datetime import datetime
from playwright.async_api import async_playwright

CDP_URL = "http://localhost:18800"
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
TODAY = datetime.now().strftime("%Y-%m-%d")

# Known TR stock → ISIN mapping (common stocks)
TR_ISIN_MAP = {
    "Amazon.com": "US0231351067",
    "STMicroelectronics": "NL0000226223",
    "L'Oreal": "FR0000120321",
    "BYD": "CNE100000296",
    "Moderna": "US60770K1079",
    "Allianz": "DE0008404005",
    "Exxon Mobil": "US30231G1022",
    "LVMH Moët Hennessy": "FR0000121014",
    "Realty Income": "US7561091049",
    "Intuitive Surgical": "US46120E6023",
    "TotalEnergies": "FR0000120271",
    "Johnson & Johnson": "US4781601046",
    "Enphase Energy": "US29355A1079",
    "Plug Power": "US72919P2020",
    "Sanofi": "FR0000120578",
    "MercadoLibre": "US58733R1023",
    "Soitec": "FR0013227113",
    "Canadian National Railway": "CA1363751027",
    "Sea (ADR)": "US81141R1005",
    "Rheinmetall": "DE0007030009",
    "Intuit": "US4612021034",
    "S&P 500 Information Tech USD (Acc)": "IE00B3WJKG14",
}


def save(name, data):
    os.makedirs(DATA_DIR, exist_ok=True)
    path = os.path.join(DATA_DIR, f"{name}_{TODAY}.json")
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    print(f"  💾 {path}")


def pa(text):
    """Parse French amount"""
    if not text: return 0.0
    text = text.replace("\xa0"," ").replace("€","").replace("$","").replace(",",".").strip()
    text = re.sub(r"\s+","",text)
    try: return float(text)
    except: return 0.0


async def main():
    print("🔌 CDP connect...")
    pw = await async_playwright().start()
    browser = await pw.chromium.connect_over_cdp(CDP_URL)
    ctx = browser.contexts[0]

    tr_page = ibkr_page = None
    for p in ctx.pages:
        url = p.url
        if "traderepublic" in url: tr_page = p
        elif "interactivebrokers" in url: ibkr_page = p

    # ═══════════════════════════════════════
    # TR: Get ISIN by clicking each position
    # ═══════════════════════════════════════
    tr_positions = []
    if tr_page:
        print("\n🟢 TR — Getting ISINs...")
        await tr_page.goto("https://app.traderepublic.com/portfolio?timeframe=1d")
        await tr_page.wait_for_timeout(3000)

        body = await tr_page.inner_text("body")
        # Parse position names from text
        inv_start = body.find("Investissements")
        inv_end = body.find("Mes favoris")
        if inv_start >= 0 and inv_end >= 0:
            inv_text = body[inv_start:inv_end]
            lines = [l.strip() for l in inv_text.split("\n") if l.strip()]

            names = []
            for i, line in enumerate(lines):
                if line in ("Aujourd'hui", "Investissements"):
                    continue
                if re.match(r'^[\d\s.,]+\s*€$', line) or re.match(r'^[\d.,]+\s*%$', line):
                    continue
                # This is a position name
                if i + 1 < len(lines) and re.match(r'^[\d\s.,]+\s*€$', lines[i+1]):
                    amount = pa(lines[i+1])
                    pct = lines[i+2] if i+2 < len(lines) and re.match(r'^[\d.,]+\s*%$', lines[i+2]) else ""
                    names.append({"name": line, "value_eur": amount, "daily_pct": pct})

            print(f"  {len(names)} positions found")

            # Click each to get ISIN from URL
            for pos in names:
                name = pos["name"]
                # First try static ISIN map
                if name in TR_ISIN_MAP:
                    pos["isin"] = TR_ISIN_MAP[name]
                    print(f"  ✓ {name}: {pos['isin']} (mapped)")
                    tr_positions.append(pos)
                    continue

                # Try clicking
                try:
                    await tr_page.goto("https://app.traderepublic.com/portfolio?timeframe=1d")
                    await tr_page.wait_for_timeout(1500)

                    link = tr_page.get_by_text(name, exact=True).first
                    if await link.count() > 0:
                        await link.click()
                        await tr_page.wait_for_timeout(2000)
                        url = tr_page.url
                        isin_m = re.search(r'/asset/([A-Z]{2}[A-Z0-9]{9}\d)', url)
                        if isin_m:
                            pos["isin"] = isin_m.group(1)
                            print(f"  ✓ {name}: {pos['isin']} (clicked)")

                            # Get detail text for shares/avg price
                            detail = await tr_page.inner_text("body")
                            for pat, key in [
                                (r'(\d+[.,]\d+)\s*(?:action|part|pcs)', 'shares'),
                                (r'Prix\s*moyen[^\d]*([\d\s.,]+)\s*€', 'avg_price'),
                                (r'Rendement\s*total[^\d]*([+-]?[\d\s.,]+)\s*€', 'total_return'),
                                (r'Investi[^\d]*([\d\s.,]+)\s*€', 'invested'),
                            ]:
                                m = re.search(pat, detail, re.IGNORECASE)
                                if m:
                                    pos[key] = m.group(1).strip()
                        else:
                            print(f"  ? {name}: URL={url[:60]} (no ISIN in URL)")
                    else:
                        print(f"  ✗ {name}: not clickable")
                except Exception as e:
                    print(f"  ⚠ {name}: {e}")

                tr_positions.append(pos)

    # ═══════════════════════════════════════
    # IBKR: Get full position table with scroll
    # ═══════════════════════════════════════
    ibkr_positions = []
    ibkr_summary = {}
    if ibkr_page:
        print("\n🟠 IBKR — Full extraction...")
        await ibkr_page.goto("https://www.interactivebrokers.ie/portal/#/portfolio")
        await ibkr_page.wait_for_timeout(4000)

        # Dismiss drawer
        await ibkr_page.evaluate("""() => {
            document.querySelectorAll('._drwr-open').forEach(el => {
                el.classList.remove('_drwr-open');
                el.setAttribute('aria-hidden', 'true');
            });
        }""")
        await ibkr_page.wait_for_timeout(1000)

        # Get summary values
        body = await ibkr_page.inner_text("body")
        for pat, key in [
            (r'Liquidité\s*nette\s*\n?\s*([\d\s.,]+)', 'net_liquidation'),
            (r'Pouvoir\s*d\'achat\s*\n?\s*([\d\s.,]+)', 'buying_power'),
            (r'P&L\s*jour\s*\n?\s*([+-]?[\d\s.,]+)', 'daily_pnl'),
            (r'P&L\s*non\s*réalisé\s*\n?\s*([+-]?[\d\s.,]+)', 'unrealized_pnl'),
            (r'Liquidité\s*excédentaire\s*\n?\s*([\d\s.,]+)', 'excess_liquidity'),
        ]:
            m = re.search(pat, body)
            if m:
                ibkr_summary[key] = pa(m.group(1))

        print(f"  Summary: {json.dumps(ibkr_summary)}")

        # Get ALL table rows via JS (handles virtual scrolling)
        table_data = await ibkr_page.evaluate("""() => {
            const rows = [];
            const table = document.querySelector('table');
            if (!table) return rows;
            const trs = table.querySelectorAll('tr');
            for (const tr of trs) {
                const cells = [];
                tr.querySelectorAll('td, th').forEach(td => cells.push(td.innerText.trim()));
                if (cells.length > 3) rows.push(cells);
            }
            return rows;
        }""")
        print(f"  Table rows from JS: {len(table_data)}")

        # Parse table rows
        for row in table_data:
            if len(row) >= 9 and row[0]:
                symbol = row[0].replace("\n", " ").strip()
                if not symbol or symbol.startswith("INSTRUMENT"):
                    continue
                pos = {
                    "symbol": symbol,
                    "quantity": row[1],
                    "last_price": row[2],
                    "change_pct": row[3],
                    "cost_basis": row[4],
                    "market_value": row[5],
                    "avg_price": row[6],
                    "daily_pnl": row[7],
                    "unrealized_pnl": row[8],
                }
                ibkr_positions.append(pos)
                print(f"  {symbol:8s} qty={row[1]:>10s} value={row[5]:>12s} P&L={row[8]:>10s}")

        # Also check for crypto positions (might be in a separate section)
        # Scroll down to see if there are more
        await ibkr_page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await ibkr_page.wait_for_timeout(2000)

        full_text = await ibkr_page.inner_text("body")
        # Look for crypto mentions
        crypto_matches = re.findall(r'(BTC|ETH|SOL|LTC|BCH|XRP)\b.*?(\d[\d.,]*)\s', full_text)
        if crypto_matches:
            print(f"  Crypto mentions: {crypto_matches}")

        # Cash holdings
        cash_section = re.search(r'Cash\s*Holdings(.*?)(?:Interactive|$)', full_text, re.DOTALL)
        if cash_section:
            eur_m = re.search(r'EUR.*?([+-]?[\d\s.,]+)', cash_section.group(1))
            usd_m = re.search(r'USD.*?([+-]?[\d\s.,]+)', cash_section.group(1))
            ibkr_summary["cash_eur"] = pa(eur_m.group(1)) if eur_m else 0
            ibkr_summary["cash_usd"] = pa(usd_m.group(1)) if usd_m else 0
            print(f"  Cash: EUR {ibkr_summary.get('cash_eur',0)}, USD {ibkr_summary.get('cash_usd',0)}")

    # ═══════════════════════════════════════
    # CONSOLIDATED PATRIMONY
    # ═══════════════════════════════════════
    print("\n" + "="*60)
    print("📊 PATRIMOINE CONSOLIDÉ")
    print("="*60)

    patrimony = {
        "date": TODAY,
        "trade_republic": {
            "portfolio_value": sum(p.get("value_eur", 0) for p in tr_positions),
            "cash": 2169.62,
            "positions": tr_positions,
        },
        "ibkr": {
            "summary": ibkr_summary,
            "positions": ibkr_positions,
        },
        "boursobank": {
            "checking": 19.33,
            "pea": 100.00,
            "livret_a_nathael": 7726.18,
            "checking_nathael": 351.74,
            "loans": [
                {"name": "Prêt Personnel 1", "remaining": 1448.78, "source": "boursobank"},
                {"name": "Prêt Personnel 2", "remaining": 6284.35, "source": "boursobank"},
            ],
            "property": {
                "address": "40 chemin de la désirade, 34790 GRABELS",
                "type": "Maison",
                "rooms": 4,
                "surface_m2": 110,
                "purchase_date": "08/2021",
                "purchase_price": 141000,
                "current_estimate": 505254,
                "estimate_high": 565380,
                "estimate_low": 445129,
                "price_per_m2": 4593.22,
                "unrealized_gain": 364254,
                "dpe": "D",
            },
        },
        "credit_agricole": {
            "checking": 2.34,
            "credits": [
                {"name": "PTZ Ministère du Logement", "borrowed": 102000, "remaining": 102000, "monthly": 0, "rate": "0%"},
                {"name": "PAS 1", "borrowed": 10000, "remaining": 10000, "monthly": 0},
                {"name": "PAS 2", "borrowed": 138290, "remaining": 110594.85, "monthly": 90.32},
                {"name": "Prêt Conso Perso (PACP)", "borrowed": 5000, "remaining": 1803.50, "monthly": 73.69},
            ],
        },
    }

    # Compute totals
    tr_total = patrimony["trade_republic"]["portfolio_value"] + patrimony["trade_republic"]["cash"]
    ibkr_net = ibkr_summary.get("net_liquidation", 0)
    bourso_assets = 19.33 + 100.00 + 7726.18 + 351.74
    bourso_loans = 1448.78 + 6284.35
    ca_checking = 2.34
    ca_total_debt = sum(c["remaining"] for c in patrimony["credit_agricole"]["credits"])
    property_val = 505254

    print(f"\n  🏦 TRADE REPUBLIC")
    print(f"     Portfolio:    {patrimony['trade_republic']['portfolio_value']:>12,.2f}€ ({len(tr_positions)} positions)")
    print(f"     Cash:         {patrimony['trade_republic']['cash']:>12,.2f}€")
    print(f"     TOTAL:        {tr_total:>12,.2f}€")

    print(f"\n  🏦 IBKR")
    print(f"     Net Liquidation: {ibkr_net:>12,.2f}€ ({len(ibkr_positions)} positions)")
    for p in ibkr_positions:
        print(f"       {p['symbol']:8s} {p.get('quantity','?'):>8s} × {p.get('last_price','?'):>8s} = {p.get('market_value','?'):>12s}  P&L {p.get('unrealized_pnl','?'):>10s}")
    print(f"     Cash: EUR {ibkr_summary.get('cash_eur',0):>10,.2f} + USD {ibkr_summary.get('cash_usd',0):>10,.2f}")

    print(f"\n  🏦 BOURSOBANK")
    print(f"     Checking:     {19.33:>12,.2f}€")
    print(f"     PEA:          {100.00:>12,.2f}€")
    print(f"     Livret A:     {7726.18:>12,.2f}€ (Nathael)")
    print(f"     Checking:     {351.74:>12,.2f}€ (Nathael)")
    print(f"     Loans:        {-bourso_loans:>12,.2f}€")
    print(f"     🏠 Immobilier: {property_val:>12,}€ (acheté {141000:,}€)")

    print(f"\n  🏦 CRÉDIT AGRICOLE")
    print(f"     Checking:     {ca_checking:>12,.2f}€")
    print(f"     Credits:      {-ca_total_debt:>12,.2f}€ (4 prêts)")
    for c in patrimony["credit_agricole"]["credits"]:
        print(f"       {c['name']:35s} restant: {c['remaining']:>12,.2f}€  mensualité: {c['monthly']:>8,.2f}€")

    total_assets = tr_total + ibkr_net + bourso_assets + ca_checking + property_val
    total_debt = bourso_loans + ca_total_debt
    net_worth = total_assets - total_debt

    print(f"\n  {'='*50}")
    print(f"  TOTAL ACTIFS:        {total_assets:>12,.2f}€")
    print(f"  TOTAL DETTES:        {-total_debt:>12,.2f}€")
    print(f"  ════════════════════════════════════════════")
    print(f"  PATRIMOINE NET:      {net_worth:>12,.2f}€")
    print(f"  {'='*50}")

    patrimony["totals"] = {
        "total_assets": total_assets,
        "total_debt": total_debt,
        "net_worth": net_worth,
    }

    save("patrimoine_consolide", patrimony)

    print("\n✅ Browser left open.")
    await browser.close()
    await pw.stop()


if __name__ == "__main__":
    asyncio.run(main())
