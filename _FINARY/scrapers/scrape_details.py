#!/usr/bin/env python3
"""
Deep scraper — connects to already-open browser tabs.
Login manually in each tab first, then run this to extract details.

Usage:
  1. Browser is already open from scrape_all.py
  2. Login manually in each tab (TR, Bourso, IBKR, CA)
  3. Run: python scrape_details.py [tr|bourso|ibkr|ca|all]
"""
import asyncio
import json
import os
import re
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

STATE_DIR = Path("data/.browser_state")
DATA_DIR = Path("data")


def save(name, data):
    p = DATA_DIR / f"{name}_details_{date.today().isoformat()}.json"
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str))
    print(f"  ✅ Saved {p}")


async def find_tab(context, url_pattern):
    """Find existing tab matching URL pattern."""
    for page in context.pages:
        if url_pattern in page.url:
            return page
    return None


# ─── TRADE REPUBLIC DETAILS ─────────────────────────────────────
async def deep_tr(context):
    print("\n═══ TRADE REPUBLIC — DEEP SCRAPE ═══")
    page = await find_tab(context, "traderepublic")
    if not page:
        print("  No TR tab found. Open https://app.traderepublic.com/portfolio in browser.")
        return

    # Make sure we're on portfolio
    if "portfolio" not in page.url:
        await page.goto("https://app.traderepublic.com/portfolio", wait_until="domcontentloaded")
        await page.wait_for_timeout(5000)

    await page.wait_for_timeout(3000)
    body = await page.inner_text("body")

    # Parse positions
    lines = body.split('\n')
    positions = []
    idx = 0
    in_inv = False
    while idx < len(lines):
        l = lines[idx].strip()
        if l == "Investissements":
            in_inv = True
            idx += 1; continue
        if l in ("Mes favoris", "Découvrez"):
            break
        if in_inv and l and not l.startswith(('1J','1S','1M','1A','Max','Aujourd','Ouvrez')):
            if idx+2 < len(lines):
                val = lines[idx+1].strip()
                pct = lines[idx+2].strip()
                if re.match(r'^[\d\s\xa0,.]+\s*€$', val) and re.match(r'^[\d,.]+\s*%$', pct):
                    positions.append({"name": l, "current_value": val.replace('\xa0',' ')})
                    idx += 3; continue
        idx += 1

    total_match = re.search(r'Portefeuille\s*\n\s*([\d\s\xa0,.]+)\s*€', body)
    total = total_match.group(1).replace('\xa0',' ').strip() if total_match else "?"
    print(f"  Portfolio: {total} € — {len(positions)} positions")

    # Click each position for detail (ISIN, shares, avg price, P&L)
    for pos in positions:
        try:
            # Use page.get_by_text for React SPA
            el = page.get_by_text(pos["name"], exact=True)
            await el.click(timeout=3000)
            await page.wait_for_timeout(3000)

            detail = await page.inner_text("body")

            # ISIN
            m = re.search(r'\b([A-Z]{2}[A-Z0-9]{9}\d)\b', detail)
            if m: pos["isin"] = m.group(1)

            # Shares
            m = re.search(r'([\d,.]+)\s*(?:parts?|actions?|shares?|pcs|Anteile)', detail, re.I)
            if m: pos["shares"] = m.group(1)

            # Average price
            m = re.search(r'(?:Prix moyen|Avg|Durchschnitt|prix d.achat)[^\d]*([\d\s\xa0,.]+)\s*€', detail, re.I)
            if m: pos["avg_price"] = m.group(1).replace('\xa0',' ').strip() + " €"

            # P&L
            m = re.search(r'([\+\-][\d\s\xa0,.]+)\s*€\s*\n\s*([\+\-]?[\d,.]+\s*%)', detail)
            if m:
                pos["pnl"] = m.group(1).replace('\xa0',' ').strip() + " €"
                pos["pnl_pct"] = m.group(2).strip()

            # Total invested
            m = re.search(r'(?:Investi|Invested|Investiert)[^\d]*([\d\s\xa0,.]+)\s*€', detail, re.I)
            if m: pos["invested"] = m.group(1).replace('\xa0',' ').strip() + " €"

            # Fees
            m = re.search(r'(?:Frais|Fees|Gebühren)[^\d]*([\d\s\xa0,.]+)\s*€', detail, re.I)
            if m: pos["fees"] = m.group(1).replace('\xa0',' ').strip() + " €"

            # Save raw
            safe = re.sub(r'[^a-zA-Z0-9]', '_', pos["name"])[:25]
            Path(f"/tmp/tr_detail_{safe}.txt").write_text(detail[:5000])

            print(f"    ✓ {pos['name']}: ISIN={pos.get('isin','?')} qty={pos.get('shares','?')} avg={pos.get('avg_price','?')} P&L={pos.get('pnl','?')}")

            await page.go_back()
            await page.wait_for_timeout(2000)
        except Exception as e:
            print(f"    ✗ {pos['name']}: {e}")
            try:
                await page.goto("https://app.traderepublic.com/portfolio", wait_until="domcontentloaded")
                await page.wait_for_timeout(3000)
            except Exception:
                pass

    # Activity / Transactions
    print("  Fetching transactions...")
    activity = []
    try:
        await page.goto("https://app.traderepublic.com/profile/transactions", wait_until="domcontentloaded")
        await page.wait_for_timeout(5000)

        # Scroll to load all
        for _ in range(12):
            await page.evaluate("window.scrollBy(0, 1000)")
            await page.wait_for_timeout(500)

        activity_text = await page.inner_text("body")
        Path("/tmp/tr_activity_deep.txt").write_text(activity_text)
        print(f"  Activity: {len(activity_text)} chars saved")
    except Exception as e:
        print(f"  Activity error: {e}")

    # Cash
    cash = ""
    try:
        prof = await page.inner_text("body")
        m = re.search(r'Espèces\s*\n?\s*([\d\s\xa0,.]+)\s*€', prof)
        if m: cash = m.group(1).replace('\xa0',' ').strip()
    except Exception:
        pass

    data = {
        "scraped_at": datetime.now().isoformat(),
        "source": "trade_republic",
        "total_value": total,
        "cash": cash,
        "positions": positions,
    }
    save("trade_republic", data)
    return page


# ─── IBKR DETAILS ───────────────────────────────────────────────
async def deep_ibkr(context):
    print("\n═══ IBKR — DEEP SCRAPE ═══")
    page = await find_tab(context, "interactivebrokers")
    if not page:
        print("  No IBKR tab found.")
        return

    # Dismiss any modals
    try:
        btn = await page.query_selector('button:has-text("Close")')
        if btn and await btn.is_visible():
            await btn.click()
            await page.wait_for_timeout(1000)
    except Exception:
        pass

    body = await page.inner_text("body")

    # Parse account summary
    summary = {}
    for kw in ['Trésorerie','P&L non réalisé','P&L réalisé','Marge de maintien',
                'Liquidité excédentaire','Pouvoir d\'achat','Dividendes']:
        m = re.search(kw + r'\s*\n\s*([\-\d\s\xa0,.]+)', body)
        if m: summary[kw] = m.group(1).replace('\xa0',' ').strip()

    total_m = re.search(r'EUR\s*\n\s*([\d\s\xa0,.]+)', body)
    if total_m: summary["total"] = total_m.group(1).replace('\xa0',' ').strip()
    print(f"  Account: {summary}")

    # Navigate to Portfolio
    print("  Loading portfolio positions...")
    positions = []
    try:
        await page.click('text="Portefeuille"', timeout=5000)
        await page.wait_for_timeout(5000)
        await page.screenshot(path="/tmp/ibkr_deep_portfolio.png")

        ptf_text = await page.inner_text("body")
        Path("/tmp/ibkr_deep_portfolio.txt").write_text(ptf_text)

        # Parse: SYMBOL lines with values
        pos_blocks = re.findall(
            r'([A-Z]{1,6})\n(?:SS )?(.+?)\n\t([\d,.]+)\t([\-\d,.]+\s*%)',
            ptf_text
        )
        for symbol, name, price, change in pos_blocks:
            positions.append({
                "symbol": symbol,
                "name": name.strip(),
                "last_price": price,
                "change": change.strip(),
            })
        print(f"  Found {len(positions)} positions")

        # Try to click each position for details (cost basis, quantity, fees)
        for pos in positions:
            try:
                await page.click(f'text="{pos["symbol"]}"', timeout=3000)
                await page.wait_for_timeout(3000)
                detail = await page.inner_text("body")

                # Quantity
                m = re.search(r'(?:Position|Quantity|Quantité|Qty)[:\s]*([\-\d,.]+)', detail, re.I)
                if m: pos["quantity"] = m.group(1)

                # Cost basis / avg cost
                m = re.search(r'(?:Cost Basis|Prix de revient|Avg Cost|Coût moyen)[:\s]*([\d\s,.]+)', detail, re.I)
                if m: pos["cost_basis"] = m.group(1).strip()

                # Market value
                m = re.search(r'(?:Market Value|Valeur de marché|Valeur)[:\s]*([\d\s,.]+)', detail, re.I)
                if m: pos["market_value"] = m.group(1).strip()

                # Unrealized P&L
                m = re.search(r'(?:Unrealized P&L|P&L non réalisé)[:\s]*([\-\d\s,.]+)', detail, re.I)
                if m: pos["unrealized_pnl"] = m.group(1).strip()

                Path(f"/tmp/ibkr_pos_{pos['symbol']}.txt").write_text(detail[:3000])
                print(f"    ✓ {pos['symbol']}: qty={pos.get('quantity','?')} cost={pos.get('cost_basis','?')} P&L={pos.get('unrealized_pnl','?')}")

                await page.go_back()
                await page.wait_for_timeout(2000)
            except Exception:
                pass

    except Exception as e:
        print(f"  Portfolio error: {e}")

    # Navigate to Ordres & Transactions
    print("  Loading trades...")
    trades_text = ""
    try:
        await page.click('text="Ordres & transactions"', timeout=5000)
        await page.wait_for_timeout(5000)
        await page.screenshot(path="/tmp/ibkr_deep_trades.png")
        trades_text = await page.inner_text("body")
        Path("/tmp/ibkr_deep_trades.txt").write_text(trades_text)
        print(f"  Trades: {len(trades_text)} chars")
    except Exception as e:
        print(f"  Trades error: {e}")

    # Navigate to Performance & Rapports
    print("  Loading reports...")
    try:
        await page.click('text="Performance & Rapports"', timeout=5000)
        await page.wait_for_timeout(5000)
        await page.screenshot(path="/tmp/ibkr_deep_reports.png")
        reports_text = await page.inner_text("body")
        Path("/tmp/ibkr_deep_reports.txt").write_text(reports_text)
        print(f"  Reports: {len(reports_text)} chars")
    except Exception as e:
        print(f"  Reports error: {e}")

    # Relevés (statements) — flex query for fees
    print("  Loading statements...")
    try:
        await page.click('text="Relevés"', timeout=5000)
        await page.wait_for_timeout(5000)
        await page.screenshot(path="/tmp/ibkr_deep_statements.png")
        stmts = await page.inner_text("body")
        Path("/tmp/ibkr_deep_statements.txt").write_text(stmts)
        print(f"  Statements: {len(stmts)} chars")
    except Exception as e:
        print(f"  Statements error: {e}")

    data = {
        "scraped_at": datetime.now().isoformat(),
        "source": "ibkr",
        "account": "U15999905",
        "summary": summary,
        "positions": positions,
    }
    save("ibkr", data)
    return page


# ─── BOURSOBANK DETAILS ─────────────────────────────────────────
async def deep_bourso(context):
    print("\n═══ BOURSOBANK — DEEP SCRAPE ═══")
    page = await find_tab(context, "bourso")
    if not page:
        print("  No Bourso tab found.")
        return

    body = await page.inner_text("body")
    if "connexion" in page.url.lower():
        print("  Not logged in. Login manually in the browser tab.")
        return

    print(f"  Logged in: {page.url}")

    # Accounts overview
    print("  Loading accounts...")
    try:
        await page.click('a:has-text("Mes comptes")', timeout=5000)
        await page.wait_for_timeout(5000)
        accounts_text = await page.inner_text("body")
        Path("/tmp/bourso_deep_accounts.txt").write_text(accounts_text)
        await page.screenshot(path="/tmp/bourso_deep_accounts.png")
        print(f"  Accounts: {len(accounts_text)} chars")
    except Exception as e:
        print(f"  Accounts error: {e}")

    # PEA / Bourse
    print("  Loading PEA/Bourse...")
    positions = []
    try:
        await page.goto("https://clients.boursobank.com/bourse/portefeuille/", wait_until="domcontentloaded")
        await page.wait_for_timeout(5000)
        await page.screenshot(path="/tmp/bourso_deep_pea.png")
        pea_text = await page.inner_text("body")
        Path("/tmp/bourso_deep_pea.txt").write_text(pea_text)

        # Find ISIN codes and position data
        for m in re.finditer(r'([A-Z]{2}[A-Z0-9]{9}\d)', pea_text):
            isin = m.group(1)
            # Get surrounding context
            start = max(0, m.start()-200)
            end = min(len(pea_text), m.end()+200)
            ctx = pea_text[start:end]
            positions.append({"isin": isin, "context": ctx[:300]})
        print(f"  Found {len(positions)} positions with ISIN")
    except Exception as e:
        print(f"  PEA error: {e}")

    # Loans
    print("  Loading loans...")
    loans = []
    try:
        await page.goto("https://clients.boursobank.com/credit/", wait_until="domcontentloaded")
        await page.wait_for_timeout(5000)
        loans_page = await page.inner_text("body")
        Path("/tmp/bourso_deep_loans.txt").write_text(loans_page)
        await page.screenshot(path="/tmp/bourso_deep_loans.png")

        # Click each loan for details
        loan_links = await page.query_selector_all('a[href*="credit/detail"], a[href*="credit/pret"]')
        for link in loan_links:
            try:
                txt = await link.inner_text()
                await link.click()
                await page.wait_for_timeout(3000)
                detail = await page.inner_text("body")

                loan = {"name": txt.strip()[:100]}
                for pattern, key in [
                    (r'Taux\s*(?:nominal|fixe|d.intérêt)?[:\s]*([\d,.]+)\s*%', "rate"),
                    (r'TAEG[:\s]*([\d,.]+)\s*%', "taeg"),
                    (r'TEG[:\s]*([\d,.]+)\s*%', "teg"),
                    (r'(?:Mensualité|Échéance)[:\s]*([\d\s,.]+)\s*€', "monthly"),
                    (r'(?:Capital restant|Restant dû|CRD)[:\s]*([\d\s,.]+)\s*€', "remaining"),
                    (r'(?:Montant emprunté|Capital initial)[:\s]*([\d\s,.]+)\s*€', "borrowed"),
                    (r'(?:Assurance|Coût assurance)[:\s]*([\d\s,.]+)\s*€', "insurance"),
                    (r'(?:Frais de dossier)[:\s]*([\d\s,.]+)\s*€', "fees"),
                    (r'(?:Durée)[:\s]*(\d+)\s*(?:mois|ans)', "duration"),
                    (r'(?:Date.+?souscription)[:\s]*(\d{2}/\d{2}/\d{4})', "start_date"),
                ]:
                    m = re.search(pattern, detail, re.I)
                    if m: loan[key] = m.group(1).strip()

                Path(f"/tmp/bourso_loan_{len(loans)}.txt").write_text(detail[:5000])
                loans.append(loan)
                print(f"    ✓ {loan['name'][:40]}: rate={loan.get('rate','?')}% TAEG={loan.get('taeg','?')}%")

                await page.go_back()
                await page.wait_for_timeout(2000)
            except Exception:
                pass
        print(f"  Found {len(loans)} loans with details")
    except Exception as e:
        print(f"  Loans error: {e}")

    # Fees (frais bancaires)
    print("  Loading fees...")
    try:
        await page.goto("https://clients.boursobank.com/compte/frais/", wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        fees_text = await page.inner_text("body")
        Path("/tmp/bourso_deep_fees.txt").write_text(fees_text)
    except Exception:
        pass

    data = {
        "scraped_at": datetime.now().isoformat(),
        "source": "boursobank",
        "positions": positions,
        "loans": loans,
    }
    save("boursobank", data)
    return page


# ─── CRÉDIT AGRICOLE DETAILS ────────────────────────────────────
async def deep_ca(context):
    print("\n═══ CRÉDIT AGRICOLE — DEEP SCRAPE ═══")
    page = await find_tab(context, "credit-agricole")
    if not page:
        page = await find_tab(context, "ca-languedoc")
    if not page:
        print("  No CA tab found.")
        return

    region = os.environ.get("CA_REGION", "languedoc")
    base = f"https://www.credit-agricole.fr/ca-{region}/particulier"

    body = await page.inner_text("body")
    if "particulier.html" in page.url and "synthese" not in page.url:
        print("  Not logged in. Login manually in the browser tab.")
        return

    print(f"  Logged in: {page.url}")

    # Credits page
    print("  Loading Crédits page...")
    credits = []
    try:
        await page.goto(f"{base}/operations/credits.html", wait_until="domcontentloaded")
        await page.wait_for_timeout(5000)
        await page.screenshot(path="/tmp/ca_deep_credits.png")
        credits_text = await page.inner_text("body")
        Path("/tmp/ca_deep_credits.txt").write_text(credits_text)

        # Click each loan link for details
        loan_links = await page.query_selector_all('a[href*="credit"], a[href*="pret"]')
        seen_urls = set()
        for link in loan_links:
            try:
                href = await link.get_attribute("href")
                if not href or href in seen_urls or "simulateur" in href.lower():
                    continue
                seen_urls.add(href)
                txt = await link.inner_text()
                if len(txt.strip()) < 3:
                    continue

                await link.click()
                await page.wait_for_timeout(3000)
                detail = await page.inner_text("body")

                loan = {"name": txt.strip()[:100], "url": href}
                for pattern, key in [
                    (r'Taux\s*(?:nominal|fixe|d.intérêt)?[:\s]*([\d,.]+)\s*%', "rate"),
                    (r'TAEG[:\s]*([\d,.]+)\s*%', "taeg"),
                    (r'TEG[:\s]*([\d,.]+)\s*%', "teg"),
                    (r'(?:Mensualité|Échéance|échéance)[:\s]*([\d\s,.]+)\s*€', "monthly"),
                    (r'(?:Capital restant|Restant dû|CRD)[:\s]*([\d\s,.]+)\s*€', "remaining"),
                    (r'(?:Montant emprunté|Capital initial|Montant du prêt)[:\s]*([\d\s,.]+)\s*€', "borrowed"),
                    (r'(?:Assurance|Coût assurance|Prime assurance)[:\s]*([\d\s,.]+)\s*€', "insurance"),
                    (r'(?:Frais de dossier|Frais)[:\s]*([\d\s,.]+)\s*€', "fees"),
                    (r'(?:Durée)\s*[:\s]*(\d+)\s*(?:mois|ans)', "duration"),
                    (r'(?:Date.+?(?:souscription|effet|mise en place))[:\s]*(\d{2}/\d{2}/\d{4})', "start_date"),
                    (r'(?:Date.+?fin|Échéance finale)[:\s]*(\d{2}/\d{2}/\d{4})', "end_date"),
                    (r'(?:Numéro|N°)[:\s]*(\d{10,})', "account_number"),
                ]:
                    m = re.search(pattern, detail, re.I)
                    if m: loan[key] = m.group(1).strip()

                safe = re.sub(r'[^a-zA-Z0-9]', '_', txt)[:25]
                Path(f"/tmp/ca_loan_{safe}.txt").write_text(detail[:5000])
                credits.append(loan)
                print(f"    ✓ {loan['name'][:40]}: rate={loan.get('rate','?')}% TAEG={loan.get('taeg','?')}%")

                await page.go_back()
                await page.wait_for_timeout(2000)
            except Exception:
                pass
        print(f"  Found {len(credits)} loan details")
    except Exception as e:
        print(f"  Credits error: {e}")

    # Assurances
    print("  Loading assurances...")
    try:
        await page.goto(f"{base}/operations/assurances.html", wait_until="domcontentloaded")
        await page.wait_for_timeout(5000)
        assur = await page.inner_text("body")
        Path("/tmp/ca_deep_assurances.txt").write_text(assur)
        await page.screenshot(path="/tmp/ca_deep_assurances.png")
        print(f"  Assurances: {len(assur)} chars")
    except Exception as e:
        print(f"  Assurances error: {e}")

    data = {
        "scraped_at": datetime.now().isoformat(),
        "source": "credit_agricole",
        "credits": credits,
    }
    save("credit_agricole", data)
    return page


# ─── MAIN ────────────────────────────────────────────────────────
async def main():
    import sys
    from playwright.async_api import async_playwright

    target = sys.argv[1] if len(sys.argv) > 1 else "all"

    # Clean locks
    for lock in STATE_DIR.glob("Singleton*"):
        lock.unlink(missing_ok=True)

    pw = await async_playwright().start()
    context = await pw.chromium.launch_persistent_context(
        str(STATE_DIR),
        headless=False,
        viewport={"width": 1400, "height": 900},
        locale="fr-FR",
        args=["--remote-debugging-port=18800"],
    )

    print(f"🔍 Deep scraper — target: {target}")
    print(f"   {len(context.pages)} tabs open")
    print("=" * 50)

    # Open login pages in tabs so user can login manually
    urls_needed = {
        "tr": "https://app.traderepublic.com/portfolio",
        "bourso": "https://clients.boursobank.com/",
        "ibkr": "https://www.interactivebrokers.com/sso/Login",
        "ca": f"https://www.ca-{os.environ.get('CA_REGION','languedoc')}.fr",
    }

    existing_urls = [p.url for p in context.pages]
    for key, url in urls_needed.items():
        if target != "all" and target != key:
            continue
        # Check if tab already exists
        found = any(key_part in eu for eu in existing_urls for key_part in url.split("/")[2:3])
        if not found:
            page = await context.new_page()
            await page.goto(url, wait_until="domcontentloaded")
            print(f"  Opened tab: {url}")
            await page.wait_for_timeout(2000)

    print("\n⚠️  LOGIN MANUALLY in each browser tab now!")
    print("   Press ENTER here when all logins are done...")
    await asyncio.to_thread(input)
    print("   Starting deep scrape...\n")

    if target in ("tr", "all"):
        await deep_tr(context)
    if target in ("ibkr", "all"):
        await deep_ibkr(context)
    if target in ("bourso", "all"):
        await deep_bourso(context)
    if target in ("ca", "all"):
        await deep_ca(context)

    print("\n" + "=" * 50)
    print("🔍 DONE — browser stays open.")

    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass


if __name__ == "__main__":
    asyncio.run(main())
