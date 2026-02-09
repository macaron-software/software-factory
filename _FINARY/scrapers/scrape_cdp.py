#!/usr/bin/env python3
"""
Deep scraper that connects to an EXISTING browser via CDP (port 9222).
NEVER closes the browser. Extracts detailed financial data from all 4 banks.
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
    print(f"  💾 Saved {path}")
    return path


def parse_amount(text):
    """Parse French-formatted amounts like '1 234,56 €' → 1234.56"""
    if not text:
        return 0.0
    text = text.replace("\xa0", " ").replace("€", "").replace("$", "").replace("USD", "").replace("EUR", "").strip()
    text = re.sub(r"\s+", "", text)
    text = text.replace(",", ".")
    try:
        return float(text)
    except (ValueError, TypeError):
        return 0.0


# ─────────────────────────────────────────────
# TRADE REPUBLIC
# ─────────────────────────────────────────────
async def deep_trade_republic(page):
    print("\n🟢 TRADE REPUBLIC — Deep scraping...")
    result = {"bank": "trade_republic", "positions": [], "cash": 0, "transactions": []}

    # Get portfolio page content
    await page.goto("https://app.traderepublic.com/portfolio?timeframe=1d")
    await page.wait_for_timeout(3000)

    # Extract positions from portfolio list
    # TR uses data-testid or specific class patterns
    body_text = await page.inner_text("body")
    print(f"  Page length: {len(body_text)} chars")

    # Try to find all portfolio items - they appear as links in the portfolio
    position_links = await page.locator('a[href*="/asset/"]').all()
    print(f"  Found {len(position_links)} asset links")

    if not position_links:
        # Try alternative: look for portfolio item containers
        position_links = await page.locator('[data-testid*="portfolio"] a, [class*="portfolio"] a').all()
        print(f"  Alt: Found {len(position_links)} portfolio links")

    # If we found links, click each one to get details
    positions = []
    for i, link in enumerate(position_links):
        try:
            href = await link.get_attribute("href")
            if not href or "/asset/" not in href:
                continue
            name_text = (await link.inner_text()).strip()
            if not name_text:
                continue

            # Extract basic info from the link text
            lines = [l.strip() for l in name_text.split("\n") if l.strip()]
            pos_name = lines[0] if lines else "Unknown"
            print(f"  [{i+1}] {pos_name} → {href}")

            # Navigate to the asset detail page
            full_url = f"https://app.traderepublic.com{href}" if href.startswith("/") else href
            detail_page = page  # Reuse same tab

            await detail_page.goto(full_url)
            await detail_page.wait_for_timeout(2000)

            detail_text = await detail_page.inner_text("body")

            # Extract ISIN from URL or page
            isin_match = re.search(r'[A-Z]{2}[A-Z0-9]{9}\d', detail_text) or re.search(r'/asset/([A-Z]{2}[A-Z0-9]{9}\d)', full_url)
            isin = isin_match.group(0) if isin_match else (re.search(r'/asset/(\w+)', full_url).group(1) if re.search(r'/asset/(\w+)', full_url) else "")

            # Extract key details from detail page
            pos_data = {
                "name": pos_name,
                "isin": isin,
                "url": full_url,
            }

            # Look for specific fields
            for pattern, key in [
                (r'(\d+[.,]\d+)\s*(?:actions?|parts?|shares?|pcs)', 'shares'),
                (r'Prix\s*moyen[^\d]*(\d+[.,]\d+)', 'avg_price'),
                (r'Rendement[^\d]*([+-]?\d+[.,]\d+)', 'return_pct'),
                (r'P/L[^\d]*([+-]?\d+[.,]\d+)', 'pnl'),
                (r'Valeur[^\d]*(\d[\d\s.,]*\d)\s*€', 'value'),
                (r'Cours[^\d]*(\d[\d\s.,]*\d)', 'current_price'),
            ]:
                m = re.search(pattern, detail_text, re.IGNORECASE)
                if m:
                    pos_data[key] = m.group(1).replace(",", ".").replace(" ", "")

            positions.append(pos_data)

        except Exception as e:
            print(f"    ⚠ Error on position {i}: {e}")
            continue

    # If no links found, try to extract from page text directly
    if not positions:
        print("  Trying text-based extraction...")
        await page.goto("https://app.traderepublic.com/portfolio?timeframe=1d")
        await page.wait_for_timeout(3000)

        # Get all text and try to parse positions
        all_text = await page.inner_text("body")

        # TR shows positions as: Name \n Amount € \n +/-X.XX%
        # Let's get the full HTML to look for structured data
        html = await page.content()

        # Look for JSON data in the page (React state)
        json_matches = re.findall(r'\"positions\":\s*(\[.*?\])', html)
        if json_matches:
            try:
                positions = json.loads(json_matches[0])
                print(f"  Found {len(positions)} positions in React state")
            except:
                pass

        # Extract what we can from visible text
        print(f"  Portfolio text preview:\n{all_text[:2000]}")

    result["positions"] = positions

    # Get cash balance
    await page.goto("https://app.traderepublic.com/profile")
    await page.wait_for_timeout(2000)
    profile_text = await page.inner_text("body")
    cash_match = re.search(r'Espèces\s*\n?\s*(\d[\d\s.,]*\d)\s*€', profile_text)
    if cash_match:
        result["cash"] = parse_amount(cash_match.group(1))
        print(f"  Cash: {result['cash']}€")

    # Get transaction history
    await page.goto("https://app.traderepublic.com/profile/transactions")
    await page.wait_for_timeout(3000)
    tx_text = await page.inner_text("body")
    result["transactions_raw"] = tx_text[:5000]
    print(f"  Transactions text: {len(tx_text)} chars")

    # Go back to portfolio
    await page.goto("https://app.traderepublic.com/portfolio?timeframe=1d")
    await page.wait_for_timeout(1000)

    save("trade_republic_deep", result)
    return result


# ─────────────────────────────────────────────
# IBKR
# ─────────────────────────────────────────────
async def deep_ibkr(page):
    print("\n🟠 IBKR — Deep scraping...")
    result = {"bank": "ibkr", "positions": [], "trades": [], "summary": {}}

    # Make sure we're on the dashboard
    current_url = page.url
    print(f"  Current URL: {current_url}")

    if "dashboard" not in current_url:
        await page.goto("https://www.interactivebrokers.ie/portal/#/dashboard")
        await page.wait_for_timeout(3000)

    # Close any modal
    try:
        close_btn = page.locator('button:has-text("Close"), button:has-text("Fermer"), .modal-close')
        if await close_btn.count() > 0:
            await close_btn.first.click()
            await page.wait_for_timeout(500)
    except:
        pass

    # Get dashboard summary
    dash_text = await page.inner_text("body")
    print(f"  Dashboard: {len(dash_text)} chars")

    # Extract summary from dashboard
    for pattern, key in [
        (r'Net\s*(?:Liquidation|Asset)\s*(?:Value)?\s*[:\s]*(\$?[\d,]+\.?\d*)', 'net_value'),
        (r'Unrealized\s*P&L\s*[:\s]*([+-]?\$?[\d,]+\.?\d*)', 'unrealized_pnl'),
        (r'Cash\s*[:\s]*([+-]?\$?[\d,]+\.?\d*)', 'cash'),
        (r'Buying\s*Power\s*[:\s]*(\$?[\d,]+\.?\d*)', 'buying_power'),
    ]:
        m = re.search(pattern, dash_text, re.IGNORECASE)
        if m:
            result["summary"][key] = m.group(1)

    print(f"  Summary: {result['summary']}")

    # Navigate to Portfolio tab
    try:
        portfolio_tab = page.locator('a:has-text("Portefeuille"), a:has-text("Portfolio"), [data-cat="portfolio"]')
        if await portfolio_tab.count() > 0:
            await portfolio_tab.first.click()
            await page.wait_for_timeout(3000)
            portfolio_text = await page.inner_text("body")
            result["portfolio_raw"] = portfolio_text[:10000]
            print(f"  Portfolio page: {len(portfolio_text)} chars")

            # Extract positions from portfolio table
            rows = await page.locator('table tr, [class*="position"], [class*="row"]').all()
            print(f"  Found {len(rows)} table/position rows")

            for row in rows[:50]:
                try:
                    row_text = await row.inner_text()
                    if any(kw in row_text.upper() for kw in ['SPY', 'VOO', 'AAPL', 'AMZN', 'TSLA', 'META', 'BTC', 'ETH', 'SOL', 'LTC', 'BCH']):
                        lines = [l.strip() for l in row_text.split("\n") if l.strip()]
                        result["positions"].append({"raw": lines})
                except:
                    continue
    except Exception as e:
        print(f"  ⚠ Portfolio nav error: {e}")

    # Navigate to Transaction/Activity
    try:
        tx_tab = page.locator('a:has-text("Transaction"), a:has-text("Activité"), a:has-text("Activity")')
        if await tx_tab.count() > 0:
            await tx_tab.first.click()
            await page.wait_for_timeout(3000)
            tx_text = await page.inner_text("body")
            result["transactions_raw"] = tx_text[:10000]
            print(f"  Transactions: {len(tx_text)} chars")
    except Exception as e:
        print(f"  ⚠ Transaction nav error: {e}")

    # Navigate to Performance & Reports
    try:
        perf_tab = page.locator('a:has-text("Performance"), a:has-text("Rapports"), a:has-text("Reports")')
        if await perf_tab.count() > 0:
            await perf_tab.first.click()
            await page.wait_for_timeout(3000)
            perf_text = await page.inner_text("body")
            result["performance_raw"] = perf_text[:5000]
            print(f"  Performance: {len(perf_text)} chars")
    except Exception as e:
        print(f"  ⚠ Performance nav error: {e}")

    # Navigate to Statements
    try:
        stmt_tab = page.locator('a:has-text("Relevés"), a:has-text("Statements")')
        if await stmt_tab.count() > 0:
            await stmt_tab.first.click()
            await page.wait_for_timeout(3000)
            stmt_text = await page.inner_text("body")
            result["statements_raw"] = stmt_text[:5000]
            print(f"  Statements: {len(stmt_text)} chars")
    except Exception as e:
        print(f"  ⚠ Statements nav error: {e}")

    # Go back to dashboard
    await page.goto("https://www.interactivebrokers.ie/portal/#/dashboard")
    await page.wait_for_timeout(1000)

    save("ibkr_deep", result)
    return result


# ─────────────────────────────────────────────
# BOURSOBANK
# ─────────────────────────────────────────────
async def deep_bourso(page):
    print("\n🔵 BOURSOBANK — Deep scraping...")
    result = {"bank": "boursobank", "accounts": [], "pea": [], "loans": [], "savings": []}

    current_url = page.url
    print(f"  Current URL: {current_url}")

    # Get main dashboard
    if "clients.boursobank.com" not in current_url:
        await page.goto("https://clients.boursobank.com/")
        await page.wait_for_timeout(3000)

    dash_text = await page.inner_text("body")
    print(f"  Dashboard: {len(dash_text)} chars")
    result["dashboard_raw"] = dash_text[:5000]

    # Navigate to all accounts
    try:
        await page.goto("https://clients.boursobank.com/compte/")
        await page.wait_for_timeout(2000)
        accounts_text = await page.inner_text("body")
        result["accounts_raw"] = accounts_text[:5000]
        print(f"  Accounts page: {len(accounts_text)} chars")
    except Exception as e:
        print(f"  ⚠ Accounts error: {e}")

    # Navigate to PEA/Bourse
    for pea_url in [
        "https://clients.boursobank.com/bourse/",
        "https://clients.boursobank.com/patrimoine/",
    ]:
        try:
            await page.goto(pea_url)
            await page.wait_for_timeout(2000)
            pea_text = await page.inner_text("body")
            if len(pea_text) > 200:
                result["pea_raw"] = pea_text[:8000]
                print(f"  PEA/Bourse ({pea_url}): {len(pea_text)} chars")

                # Try to find position rows with ISIN
                position_links = await page.locator('a[href*="/cours/"], a[href*="/bourse/"]').all()
                for link in position_links[:20]:
                    try:
                        href = await link.get_attribute("href")
                        text = (await link.inner_text()).strip()
                        if text and href:
                            result["pea"].append({"name": text, "href": href})
                    except:
                        continue
                print(f"  Found {len(result['pea'])} PEA positions")
                break
        except:
            continue

    # Navigate to loans/credits
    for loan_url in [
        "https://clients.boursobank.com/credit/",
        "https://clients.boursobank.com/patrimoine/credit/",
    ]:
        try:
            await page.goto(loan_url)
            await page.wait_for_timeout(2000)
            loan_text = await page.inner_text("body")
            if len(loan_text) > 200 and "crédit" in loan_text.lower():
                result["loans_raw"] = loan_text[:8000]
                print(f"  Loans ({loan_url}): {len(loan_text)} chars")

                # Extract rate info
                for pattern, key in [
                    (r'Taux[^\d]*(\d+[.,]\d+)\s*%', 'taux'),
                    (r'TEG[^\d]*(\d+[.,]\d+)\s*%', 'teg'),
                    (r'TAEG[^\d]*(\d+[.,]\d+)\s*%', 'taeg'),
                    (r'Mensualité[^\d]*([\d\s.,]+)\s*€', 'mensualite'),
                    (r'Capital\s*restant[^\d]*([\d\s.,]+)\s*€', 'capital_restant'),
                    (r'Assurance[^\d]*([\d\s.,]+)\s*€', 'assurance'),
                ]:
                    m = re.search(pattern, loan_text, re.IGNORECASE)
                    if m:
                        result["loans"].append({key: m.group(1)})
                break
        except:
            continue

    # Navigate to savings
    try:
        await page.goto("https://clients.boursobank.com/epargne/")
        await page.wait_for_timeout(2000)
        savings_text = await page.inner_text("body")
        if len(savings_text) > 200:
            result["savings_raw"] = savings_text[:5000]
            print(f"  Savings: {len(savings_text)} chars")
    except:
        pass

    # Go back to main
    await page.goto("https://clients.boursobank.com/")
    await page.wait_for_timeout(1000)

    save("bourso_deep", result)
    return result


# ─────────────────────────────────────────────
# CREDIT AGRICOLE
# ─────────────────────────────────────────────
async def deep_ca(page):
    print("\n🟤 CRÉDIT AGRICOLE — Deep scraping...")
    result = {"bank": "credit_agricole", "accounts": [], "credits": [], "insurance": []}

    current_url = page.url
    print(f"  Current URL: {current_url}")

    # Get main synthese
    if "synthese" not in current_url:
        await page.goto("https://www.credit-agricole.fr/ca-languedoc/particulier/operations/synthese.html")
        await page.wait_for_timeout(3000)

    synth_text = await page.inner_text("body")
    print(f"  Synthese: {len(synth_text)} chars")
    result["synthese_raw"] = synth_text[:5000]

    # Expand credits section
    try:
        credit_btn = page.locator('text="Afficher mes crédits"')
        if await credit_btn.count() > 0:
            await credit_btn.click()
            await page.wait_for_timeout(2000)
            synth_text = await page.inner_text("body")
    except:
        pass

    # Navigate to credits page for detailed info
    try:
        await page.goto("https://www.credit-agricole.fr/ca-languedoc/particulier/operations/credits.html")
        await page.wait_for_timeout(3000)
        credits_text = await page.inner_text("body")
        result["credits_page_raw"] = credits_text[:8000]
        print(f"  Credits page: {len(credits_text)} chars")

        # Extract rate details
        for pattern, key in [
            (r'Taux[^\d]*(\d+[.,]\d+)\s*%', 'taux'),
            (r'TEG[^\d]*(\d+[.,]\d+)\s*%', 'teg'),
            (r'TAEG[^\d]*(\d+[.,]\d+)\s*%', 'taeg'),
            (r'[Éé]chéance[^\d]*([\d\s.,]+)\s*€', 'echeance'),
            (r'Montant\s*emprunt[éeè][^\d]*([\d\s.,]+)\s*€', 'montant_emprunte'),
            (r'Restant\s*d[ûu][^\d]*([\d\s.,]+)\s*€', 'restant_du'),
            (r'Assurance[^\d]*([\d\s.,]+)\s*€', 'assurance'),
            (r'Dur[ée]e[^\d]*(\d+)\s*(?:mois|ans)', 'duree'),
        ]:
            matches = re.findall(pattern, credits_text, re.IGNORECASE)
            if matches:
                result["credits"].append({key: matches})

        # Click on each credit for full detail
        credit_links = await page.locator('a[href*="credit"], a[href*="pret"]').all()
        for link in credit_links[:10]:
            try:
                href = await link.get_attribute("href")
                text = (await link.inner_text()).strip()
                if href and text and len(text) > 3:
                    print(f"    Credit link: {text} → {href}")
                    result["credits"].append({"name": text, "href": href})
            except:
                continue

    except Exception as e:
        print(f"  ⚠ Credits page error: {e}")

    # Navigate to insurance/assurances
    for ins_url in [
        "https://www.credit-agricole.fr/ca-languedoc/particulier/assurances.html",
        "https://www.credit-agricole.fr/ca-languedoc/particulier/operations/assurances.html",
    ]:
        try:
            await page.goto(ins_url)
            await page.wait_for_timeout(2000)
            ins_text = await page.inner_text("body")
            if len(ins_text) > 200:
                result["insurance_raw"] = ins_text[:5000]
                print(f"  Insurance ({ins_url}): {len(ins_text)} chars")

                # Extract insurance details
                for pattern, key in [
                    (r'Cotisation[^\d]*([\d\s.,]+)\s*€', 'cotisation'),
                    (r'Prime[^\d]*([\d\s.,]+)\s*€', 'prime'),
                ]:
                    matches = re.findall(pattern, ins_text, re.IGNORECASE)
                    if matches:
                        result["insurance"].append({key: matches})
                break
        except:
            continue

    # Try compte details
    try:
        await page.goto("https://www.credit-agricole.fr/ca-languedoc/particulier/operations/comptes.html")
        await page.wait_for_timeout(2000)
        comptes_text = await page.inner_text("body")
        result["comptes_raw"] = comptes_text[:5000]
        print(f"  Comptes page: {len(comptes_text)} chars")
    except:
        pass

    # Go back to synthese
    await page.goto("https://www.credit-agricole.fr/ca-languedoc/particulier/operations/synthese.html")
    await page.wait_for_timeout(1000)

    save("ca_deep", result)
    return result


# ─────────────────────────────────────────────
# MAIN — Connect via CDP, scrape all, NEVER close
# ─────────────────────────────────────────────
async def main():
    print("🔌 Connecting to browser via CDP on port 9222...")
    pw = await async_playwright().start()
    browser = await pw.chromium.connect_over_cdp(CDP_URL)

    contexts = browser.contexts
    print(f"  Found {len(contexts)} browser contexts")

    if not contexts:
        print("  ❌ No browser contexts found!")
        return

    ctx = contexts[0]
    pages = ctx.pages
    print(f"  Found {len(pages)} pages:")

    # Identify pages by URL
    tr_page = ibkr_page = bourso_page = ca_page = None
    for p in pages:
        url = p.url
        title = await p.title()
        print(f"    - {title[:50]} → {url[:80]}")
        if "traderepublic" in url:
            tr_page = p
        elif "interactivebrokers" in url:
            ibkr_page = p
        elif "boursobank" in url or "boursorama" in url:
            bourso_page = p
        elif "credit-agricole" in url:
            ca_page = p

    results = {}

    # Scrape each bank
    if tr_page:
        try:
            results["trade_republic"] = await deep_trade_republic(tr_page)
        except Exception as e:
            print(f"  ❌ TR error: {e}")
    else:
        print("  ⚠ No Trade Republic tab found")

    if ibkr_page:
        try:
            results["ibkr"] = await deep_ibkr(ibkr_page)
        except Exception as e:
            print(f"  ❌ IBKR error: {e}")
    else:
        print("  ⚠ No IBKR tab found")

    if bourso_page:
        try:
            results["boursobank"] = await deep_bourso(bourso_page)
        except Exception as e:
            print(f"  ❌ Bourso error: {e}")
    else:
        print("  ⚠ No Boursobank tab found")

    if ca_page:
        try:
            results["credit_agricole"] = await deep_ca(ca_page)
        except Exception as e:
            print(f"  ❌ CA error: {e}")
    else:
        print("  ⚠ No Crédit Agricole tab found")

    # Save combined results
    save("all_banks_deep", results)

    print("\n✅ Deep scraping complete! Browser left open.")
    print("   Run this script again anytime to re-scrape.")

    # DO NOT close browser or playwright
    # Just disconnect the CDP connection
    await browser.close()  # This only closes the CDP connection, not the browser
    await pw.stop()


if __name__ == "__main__":
    asyncio.run(main())
