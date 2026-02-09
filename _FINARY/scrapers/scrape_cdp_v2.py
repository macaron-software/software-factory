#!/usr/bin/env python3
"""
Deep scraper v2 — Connects via CDP, smarter extraction.
Fixes: IBKR drawer, TR text parsing, Bourso session, CA credits.
NEVER closes the browser.
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


def save(name, data):
    os.makedirs(DATA_DIR, exist_ok=True)
    path = os.path.join(DATA_DIR, f"{name}_{TODAY}.json")
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    print(f"  💾 {path}")
    return path


def parse_amount(text):
    if not text:
        return 0.0
    text = text.replace("\xa0", " ").replace("€", "").replace("$", "").replace("USD", "").replace("EUR", "").strip()
    text = re.sub(r"\s+", "", text)
    text = text.replace(",", ".")
    try:
        return float(text)
    except:
        return 0.0


# ─────────────────────────────────────────────
# TRADE REPUBLIC — Parse portfolio text + click each position
# ─────────────────────────────────────────────
async def deep_tr(page):
    print("\n🟢 TRADE REPUBLIC")
    result = {"bank": "trade_republic", "portfolio_total": 0, "cash": 0, "positions": [], "transactions": []}

    await page.goto("https://app.traderepublic.com/portfolio?timeframe=1d")
    await page.wait_for_timeout(3000)
    body = await page.inner_text("body")

    # Parse total portfolio value
    total_match = re.search(r'Portefeuille\s*\n\s*([\d\s.,]+)\s*€', body)
    if total_match:
        result["portfolio_total"] = parse_amount(total_match.group(1))
        print(f"  Portfolio: {result['portfolio_total']}€")

    # Parse positions from text: "Name\nAmount €\nPct %"
    # Find the "Investissements" section
    inv_start = body.find("Investissements")
    inv_end = body.find("Mes favoris")
    if inv_start >= 0 and inv_end >= 0:
        inv_text = body[inv_start:inv_end]
        lines = [l.strip() for l in inv_text.split("\n") if l.strip()]
        # Skip header lines
        i = 0
        while i < len(lines) and not re.match(r'^[\d\s.,]+\s*€$', lines[i] if i + 1 < len(lines) else ""):
            i += 1
            if i > 3:
                i = 1  # Reset — first position name is at index 1 or 2
                break

        # Parse triplets: Name, Amount €, Pct %
        positions_text = []
        idx = i
        while idx < len(lines):
            name = lines[idx]
            # Skip non-name lines
            if re.match(r'^[\d\s.,]+\s*€$', name) or re.match(r'^[\d.,]+\s*%$', name) or name in ("Aujourd'hui", "Investissements"):
                idx += 1
                continue
            # Next should be amount
            if idx + 1 < len(lines):
                amount_text = lines[idx + 1]
                if re.match(r'^[\d\s.,]+\s*€$', amount_text):
                    amount = parse_amount(amount_text)
                    pct = ""
                    if idx + 2 < len(lines) and re.match(r'^[\d.,]+\s*%$', lines[idx + 2]):
                        pct = lines[idx + 2]
                        idx += 3
                    else:
                        idx += 2
                    positions_text.append({"name": name, "value_eur": amount, "daily_pct": pct})
                    continue
            idx += 1

        print(f"  Parsed {len(positions_text)} positions from text")

        # Now click each position to get ISIN, shares, avg price
        for pos in positions_text:
            try:
                await page.goto("https://app.traderepublic.com/portfolio?timeframe=1d")
                await page.wait_for_timeout(1500)

                # Find and click the position by name
                link = page.get_by_text(pos["name"], exact=True).first
                if await link.count() > 0:
                    await link.click()
                    await page.wait_for_timeout(2000)

                    detail_url = page.url
                    detail_text = await page.inner_text("body")

                    # Extract ISIN from URL
                    isin_match = re.search(r'/asset/([A-Z]{2}[A-Z0-9]{9}\d)', detail_url)
                    if isin_match:
                        pos["isin"] = isin_match.group(1)

                    # Extract details from page text
                    for pattern, key in [
                        (r'(\d+[.,]\d+)\s*(?:action|part|pcs|share)', 'shares'),
                        (r'Prix\s*moyen\s*[:\s]*([\d\s.,]+)\s*€', 'avg_price'),
                        (r'Rendement\s*total[^\d]*([+-]?[\d\s.,]+)\s*€', 'total_return_eur'),
                        (r'Rendement\s*total[^\d]*([+-]?[\d.,]+)\s*%', 'total_return_pct'),
                        (r'Valeur\s*actuelle\s*[:\s]*([\d\s.,]+)\s*€', 'current_value'),
                        (r'Investi\s*[:\s]*([\d\s.,]+)\s*€', 'invested'),
                    ]:
                        m = re.search(pattern, detail_text, re.IGNORECASE)
                        if m:
                            pos[key] = m.group(1).strip()

                    print(f"    {pos['name']}: ISIN={pos.get('isin','?')} shares={pos.get('shares','?')} avg={pos.get('avg_price','?')}")
                else:
                    print(f"    {pos['name']}: link not found")
            except Exception as e:
                print(f"    {pos['name']}: ⚠ {e}")

        result["positions"] = positions_text

    # Cash
    await page.goto("https://app.traderepublic.com/profile")
    await page.wait_for_timeout(2000)
    profile = await page.inner_text("body")
    cash_match = re.search(r'Espèces\s*\n?\s*([\d\s.,]+)\s*€', profile)
    if cash_match:
        result["cash"] = parse_amount(cash_match.group(1))
        print(f"  Cash: {result['cash']}€")

    # Transactions
    await page.goto("https://app.traderepublic.com/profile/transactions")
    await page.wait_for_timeout(3000)
    tx_text = await page.inner_text("body")

    # Parse transactions: Date header, then Name + Amount pairs
    tx_lines = [l.strip() for l in tx_text.split("\n") if l.strip()]
    current_date = ""
    txs = []
    for j, line in enumerate(tx_lines):
        # Date headers like "7 févr.", "6 févr."
        if re.match(r'^\d{1,2}\s+\w+\.?$', line):
            current_date = line
            continue
        # Transaction: Name followed by amount on next line
        if j + 1 < len(tx_lines):
            next_line = tx_lines[j + 1]
            amount_m = re.match(r'^([+-]?\s*[\d\s.,]+)\s*€$', next_line)
            if amount_m and not re.match(r'^[+-]?\s*[\d\s.,]+\s*€$', line):
                txs.append({"date": current_date, "name": line, "amount": next_line})

    result["transactions"] = txs[:50]
    print(f"  Transactions: {len(txs)} found")

    # Back to portfolio
    await page.goto("https://app.traderepublic.com/portfolio?timeframe=1d")
    await page.wait_for_timeout(1000)

    save("trade_republic_deep", result)
    return result


# ─────────────────────────────────────────────
# IBKR — Dismiss drawer, extract from dashboard + navigate via hash
# ─────────────────────────────────────────────
async def deep_ibkr(page):
    print("\n🟠 IBKR")
    result = {"bank": "ibkr", "summary": {}, "positions": [], "trades": [], "performance": {}}

    # Dismiss the news drawer that blocks everything
    await page.evaluate("""() => {
        // Close all drawers
        document.querySelectorAll('._drwr-open').forEach(el => {
            el.classList.remove('_drwr-open');
            el.setAttribute('aria-hidden', 'true');
        });
        // Also try clicking close/X buttons in drawers
        document.querySelectorAll('._drwr button[aria-label="Close"], ._drwr .close-btn').forEach(btn => btn.click());
    }""")
    await page.wait_for_timeout(1000)
    print("  Drawer dismissed via JS")

    # Extract dashboard data (42K chars of rich content)
    dash_html = await page.content()
    dash_text = await page.inner_text("body")
    print(f"  Dashboard: {len(dash_text)} chars text, {len(dash_html)} chars HTML")

    # Parse summary values from dashboard
    for pattern, key in [
        (r'Net\s*Liquidation\s*(?:Value)?\s*[:\s]*([\d,]+\.?\d*)', 'net_liquidation'),
        (r'Total\s*Cash\s*(?:Value)?\s*[:\s]*([+-]?[\d,]+\.?\d*)', 'total_cash'),
        (r'Unrealized\s*P&L\s*[:\s]*([+-]?[\d,]+\.?\d*)', 'unrealized_pnl'),
        (r'Realized\s*P&L\s*[:\s]*([+-]?[\d,]+\.?\d*)', 'realized_pnl'),
        (r'Buying\s*Power\s*[:\s]*([\d,]+\.?\d*)', 'buying_power'),
        (r'Maint\.\s*Margin\s*[:\s]*([\d,]+\.?\d*)', 'maintenance_margin'),
        (r'Available\s*Funds\s*[:\s]*([\d,]+\.?\d*)', 'available_funds'),
        (r'Excess\s*Liquidity\s*[:\s]*([\d,]+\.?\d*)', 'excess_liquidity'),
    ]:
        m = re.search(pattern, dash_text, re.IGNORECASE)
        if m:
            result["summary"][key] = m.group(1)

    print(f"  Summary: {json.dumps(result['summary'], indent=2)}")

    # Extract positions from dashboard HTML (usually in a widget)
    # Look for stock symbols and values
    stock_pattern = r'([A-Z]{1,5})\s+(?:[\d,]+)\s+([+-]?[\d,.]+)\s+([+-]?[\d,.]+%?)'
    for m in re.finditer(stock_pattern, dash_text):
        result["positions"].append({"symbol": m.group(1), "value": m.group(2), "change": m.group(3)})

    # Try hash-based navigation (avoids drawer blocking)
    for hash_route, key in [
        ("#/portfolio", "portfolio"),
        ("#/dashboard/performance", "performance"),
    ]:
        try:
            url = f"https://www.interactivebrokers.ie/portal/{hash_route}"
            await page.goto(url)
            await page.wait_for_timeout(3000)
            # Re-dismiss drawer if it reappears
            await page.evaluate("""() => {
                document.querySelectorAll('._drwr-open').forEach(el => {
                    el.classList.remove('_drwr-open');
                    el.setAttribute('aria-hidden', 'true');
                });
            }""")
            await page.wait_for_timeout(500)
            text = await page.inner_text("body")
            result[f"{key}_raw"] = text[:10000]
            print(f"  {key}: {len(text)} chars")
        except Exception as e:
            print(f"  ⚠ {key}: {e}")

    # Navigate to portfolio page and extract position table
    try:
        await page.goto("https://www.interactivebrokers.ie/portal/#/portfolio")
        await page.wait_for_timeout(4000)
        await page.evaluate("""() => {
            document.querySelectorAll('._drwr-open').forEach(el => {
                el.classList.remove('_drwr-open');
                el.setAttribute('aria-hidden', 'true');
            });
        }""")
        await page.wait_for_timeout(1000)

        # Try to get table data
        tables = await page.locator('table').all()
        print(f"  Found {len(tables)} tables on portfolio page")
        for t_idx, table in enumerate(tables[:3]):
            try:
                table_text = await table.inner_text()
                if len(table_text) > 50:
                    print(f"    Table {t_idx}: {table_text[:200]}...")
                    result[f"portfolio_table_{t_idx}"] = table_text[:5000]
            except:
                continue

        # Also get all text for regex extraction
        portfolio_text = await page.inner_text("body")

        # Parse position lines — IBKR shows: Symbol, Qty, Last Price, Market Value, Avg Cost, Unrealized P&L
        position_rows = []
        lines = portfolio_text.split("\n")
        for i, line in enumerate(lines):
            line = line.strip()
            # Look for known symbols
            if re.match(r'^(SPY|VOO|AAPL|AMZN|TSLA|META|MSFT|GOOG|NVDA|BTC|ETH|SOL|LTC|BCH)\b', line):
                # Collect next few lines as data
                data_lines = [lines[j].strip() for j in range(i, min(i+8, len(lines))) if lines[j].strip()]
                position_rows.append(data_lines)

        if position_rows:
            result["positions"] = [{"raw": row} for row in position_rows]
            print(f"  Found {len(position_rows)} position rows")

    except Exception as e:
        print(f"  ⚠ Portfolio extraction: {e}")

    # Try to get Activity/Trades via hash
    try:
        await page.goto("https://www.interactivebrokers.ie/portal/#/activity")
        await page.wait_for_timeout(3000)
        await page.evaluate("""() => {
            document.querySelectorAll('._drwr-open').forEach(el => {
                el.classList.remove('_drwr-open');
                el.setAttribute('aria-hidden', 'true');
            });
        }""")
        activity_text = await page.inner_text("body")
        result["activity_raw"] = activity_text[:10000]
        print(f"  Activity: {len(activity_text)} chars")
    except Exception as e:
        print(f"  ⚠ Activity: {e}")

    # Back to dashboard
    await page.goto("https://www.interactivebrokers.ie/portal/#/dashboard")
    await page.wait_for_timeout(1000)

    save("ibkr_deep", result)
    return result


# ─────────────────────────────────────────────
# BOURSOBANK — Extract from logged-in dashboard
# ─────────────────────────────────────────────
async def deep_bourso(page):
    print("\n🔵 BOURSOBANK")
    result = {"bank": "boursobank", "accounts": [], "pea": [], "loans": [], "insurance": []}

    # Stay on main page — already logged in
    current_url = page.url
    print(f"  Current: {current_url}")

    if "clients.boursobank.com" not in current_url:
        await page.goto("https://clients.boursobank.com/")
        await page.wait_for_timeout(3000)

    # Dashboard
    dash_text = await page.inner_text("body")
    dash_html = await page.content()
    print(f"  Dashboard: {len(dash_text)} chars")

    # Parse accounts from dashboard text
    # Typical: "Compte courant" / "PEA" / "Livret A" with balances
    for pattern, key in [
        (r'Compte\s*courant[^\d]*([\d\s.,]+)\s*€', 'compte_courant'),
        (r'PEA[^\d]*([\d\s.,]+)\s*€', 'pea_total'),
        (r'Livret\s*A[^\d]*([\d\s.,]+)\s*€', 'livret_a'),
        (r'LDD[^\d]*([\d\s.,]+)\s*€', 'ldd'),
        (r'Assurance\s*[Vv]ie[^\d]*([\d\s.,]+)\s*€', 'assurance_vie'),
        (r'Total[^\d]*([\d\s.,]+)\s*€', 'total'),
    ]:
        m = re.search(pattern, dash_text, re.IGNORECASE)
        if m:
            result["accounts"].append({key: parse_amount(m.group(1))})

    print(f"  Accounts: {result['accounts']}")

    # Try /compte/cav/ for checking account details
    for url, label in [
        ("https://clients.boursobank.com/compte/cav/", "Compte courant"),
        ("https://clients.boursobank.com/patrimoine/", "Patrimoine"),
        ("https://clients.boursobank.com/budget/", "Budget"),
    ]:
        try:
            await page.goto(url)
            await page.wait_for_timeout(2000)
            text = await page.inner_text("body")
            if len(text) > 200 and "connexion" not in text.lower()[:200]:
                result[f"{label.lower().replace(' ', '_')}_raw"] = text[:8000]
                print(f"  {label}: {len(text)} chars")
        except Exception as e:
            print(f"  ⚠ {label}: {e}")

    # Try to get PEA details from patrimoine
    try:
        await page.goto("https://clients.boursobank.com/patrimoine/pea/")
        await page.wait_for_timeout(2000)
        pea_text = await page.inner_text("body")
        if len(pea_text) > 200 and "connexion" not in pea_text.lower()[:200]:
            result["pea_raw"] = pea_text[:8000]
            print(f"  PEA: {len(pea_text)} chars")

            # Extract position details
            for pattern, key in [
                (r'([A-Z]{2}\w{9}\d)', 'isin'),
                (r'(\d+)\s*titres?', 'shares'),
                (r'PRU\s*[:\s]*([\d.,]+)\s*€', 'pru'),
                (r'Valorisation\s*[:\s]*([\d\s.,]+)\s*€', 'valorisation'),
                (r'Plus[/-]?value\s*[:\s]*([+-]?[\d\s.,]+)\s*€', 'plus_value'),
            ]:
                matches = re.findall(pattern, pea_text, re.IGNORECASE)
                if matches:
                    result["pea"].append({key: matches})
    except:
        pass

    # Credit/loan details
    try:
        await page.goto("https://clients.boursobank.com/patrimoine/credit/")
        await page.wait_for_timeout(2000)
        credit_text = await page.inner_text("body")
        if len(credit_text) > 200 and "connexion" not in credit_text.lower()[:200]:
            result["credit_raw"] = credit_text[:8000]
            print(f"  Crédits: {len(credit_text)} chars")
    except:
        pass

    # Back to main
    await page.goto("https://clients.boursobank.com/")
    await page.wait_for_timeout(1000)

    save("bourso_deep", result)
    return result


# ─────────────────────────────────────────────
# CRÉDIT AGRICOLE — Synthese + Credits details
# ─────────────────────────────────────────────
async def deep_ca(page):
    print("\n🟤 CRÉDIT AGRICOLE")
    result = {"bank": "credit_agricole", "accounts": [], "credits": [], "insurance": []}

    # Navigate to synthese
    await page.goto("https://www.credit-agricole.fr/ca-languedoc/particulier/operations/synthese.html")
    await page.wait_for_timeout(5000)

    synth_text = await page.inner_text("body")
    synth_html = await page.content()
    print(f"  Synthese: {len(synth_text)} chars")

    # Parse account balance
    balance_match = re.search(r'Compte\s*(?:courant|de\s*dépôt)[^\d]*([\d\s.,]+)\s*€', synth_text, re.IGNORECASE)
    if balance_match:
        result["accounts"].append({"checking": parse_amount(balance_match.group(1))})
        print(f"  Checking: {balance_match.group(1)}€")

    # Expand credits section
    try:
        expand_btn = page.locator('text="Afficher mes crédits"')
        if await expand_btn.count() > 0:
            await expand_btn.click()
            await page.wait_for_timeout(2000)
            synth_text = await page.inner_text("body")
            print(f"  After expanding credits: {len(synth_text)} chars")
    except:
        pass

    # Parse credits from expanded synthese (same logic as run_scrape.py)
    credit_section = synth_text[synth_text.find("crédits"):] if "crédits" in synth_text.lower() else ""
    if credit_section:
        # Extract credit blocks
        credit_lines = credit_section.split("\n")
        current_credit = {}
        credits = []
        for line in credit_lines:
            line = line.strip()
            if not line:
                continue
            # Credit name usually starts with uppercase and is not a number
            if "Echéance" in line or "Échéance" in line:
                continue
            if "Montant emprunté" in line:
                continue
            if "Restant dû" in line:
                continue

            amount_m = re.match(r'^([\d\s.,]+)\s*€', line)
            if amount_m:
                val = parse_amount(amount_m.group(1))
                if "monthly_payment" not in current_credit:
                    current_credit["monthly_payment"] = val
                elif "borrowed" not in current_credit:
                    current_credit["borrowed"] = val
                elif "remaining" not in current_credit:
                    current_credit["remaining"] = val
                    credits.append(current_credit)
                    current_credit = {}
            elif re.match(r'^\d{11}$', line):
                current_credit["account_number"] = line
            elif len(line) > 5 and not re.match(r'^[\d.,]+$', line) and "Mensuelle" not in line:
                if current_credit and "name" in current_credit:
                    if current_credit.get("remaining") is not None:
                        credits.append(current_credit)
                    current_credit = {"name": line}
                elif not current_credit:
                    current_credit = {"name": line}

        if current_credit and "name" in current_credit:
            credits.append(current_credit)

        result["credits"] = credits
        print(f"  Credits: {len(credits)} found")
        for c in credits:
            print(f"    {c.get('name','?')}: borrowed={c.get('borrowed','?')}€ remaining={c.get('remaining','?')}€ monthly={c.get('monthly_payment','?')}€")

    # Navigate to credits detail page
    try:
        await page.goto("https://www.credit-agricole.fr/ca-languedoc/particulier/operations/credits.html")
        await page.wait_for_timeout(5000)
        credits_text = await page.inner_text("body")
        credits_html = await page.content()
        print(f"  Credits page: {len(credits_text)} chars")

        # Extract rate info from credits page
        for pattern, key in [
            (r'Taux\s*(?:nominal|fixe|variable)?[^\d]*(\d+[.,]\d+)\s*%', 'taux'),
            (r'TEG[^\d]*(\d+[.,]\d+)\s*%', 'teg'),
            (r'TAEG[^\d]*(\d+[.,]\d+)\s*%', 'taeg'),
            (r'Assurance[^\d]*([\d.,]+)\s*€', 'assurance_mensuelle'),
            (r'Durée[^\d]*(\d+)\s*(mois|ans)', 'duree'),
            (r'Date\s*(?:de\s*)?(?:début|souscription)[^\d]*(\d{2}/\d{2}/\d{4})', 'date_debut'),
        ]:
            matches = re.findall(pattern, credits_text, re.IGNORECASE)
            if matches:
                result[f"credits_{key}"] = matches
                print(f"    {key}: {matches}")

        # Try to download amortization table
        amort_link = page.locator('a:has-text("amortissement")')
        if await amort_link.count() > 0:
            href = await amort_link.first.get_attribute("href")
            print(f"    Amortization table link: {href}")
            result["amortissement_link"] = href
    except Exception as e:
        print(f"  ⚠ Credits page: {e}")

    # Insurance page
    try:
        await page.goto("https://www.credit-agricole.fr/ca-languedoc/particulier/operations/assurances.html")
        await page.wait_for_timeout(4000)
        ins_text = await page.inner_text("body")
        print(f"  Assurances: {len(ins_text)} chars")
        if len(ins_text) > 500:
            result["assurances_raw"] = ins_text[:5000]
            for pattern, key in [
                (r'Cotisation[^\d]*([\d.,]+)\s*€', 'cotisation'),
                (r'Prime[^\d]*([\d.,]+)\s*€', 'prime'),
                (r'Contrat\s*n°?\s*(\d+)', 'contrat_num'),
            ]:
                matches = re.findall(pattern, ins_text, re.IGNORECASE)
                if matches:
                    result["insurance"].append({key: matches})
    except Exception as e:
        print(f"  ⚠ Assurances: {e}")

    # Back to synthese
    await page.goto("https://www.credit-agricole.fr/ca-languedoc/particulier/operations/synthese.html")
    await page.wait_for_timeout(1000)

    save("ca_deep", result)
    return result


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
async def main():
    print("🔌 Connecting to browser via CDP...")
    pw = await async_playwright().start()
    browser = await pw.chromium.connect_over_cdp(CDP_URL)

    ctx = browser.contexts[0]
    pages = ctx.pages
    print(f"  {len(pages)} pages open")

    tr_page = ibkr_page = bourso_page = ca_page = None
    for p in pages:
        url = p.url
        title = await p.title()
        print(f"    {title[:40]:40s} {url[:60]}")
        if "traderepublic" in url:
            tr_page = p
        elif "interactivebrokers" in url:
            ibkr_page = p
        elif "boursobank" in url or "boursorama" in url:
            bourso_page = p
        elif "credit-agricole" in url:
            ca_page = p

    all_results = {}

    for name, page_obj, func in [
        ("trade_republic", tr_page, deep_tr),
        ("ibkr", ibkr_page, deep_ibkr),
        ("boursobank", bourso_page, deep_bourso),
        ("credit_agricole", ca_page, deep_ca),
    ]:
        if page_obj:
            try:
                all_results[name] = await func(page_obj)
            except Exception as e:
                print(f"  ❌ {name}: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"  ⚠ No tab for {name}")

    save("all_banks_deep", all_results)

    # Summary
    print("\n" + "="*60)
    print("📊 RÉSUMÉ PATRIMOINE")
    print("="*60)

    total = 0
    tr = all_results.get("trade_republic", {})
    if tr:
        tr_total = tr.get("portfolio_total", 0) + tr.get("cash", 0)
        print(f"  Trade Republic: {tr.get('portfolio_total',0):>10,.2f}€ portfolio + {tr.get('cash',0):>10,.2f}€ cash = {tr_total:>10,.2f}€")
        print(f"    {len(tr.get('positions',[]))} positions")
        total += tr_total

    ibkr = all_results.get("ibkr", {})
    if ibkr and ibkr.get("summary"):
        nlv = ibkr["summary"].get("net_liquidation", "?")
        print(f"  IBKR: Net Liquidation = {nlv}")

    bourso = all_results.get("boursobank", {})
    if bourso:
        print(f"  Boursobank: {len(bourso.get('accounts',[]))} accounts")

    ca = all_results.get("credit_agricole", {})
    if ca:
        print(f"  Crédit Agricole: {len(ca.get('credits',[]))} crédits")
        for c in ca.get("credits", []):
            print(f"    {c.get('name','?')}: {c.get('remaining','?')}€ restant")

    print(f"\n  Browser left open ✅")

    await browser.close()  # Disconnects CDP only
    await pw.stop()


if __name__ == "__main__":
    asyncio.run(main())
