#!/usr/bin/env python3
"""
Scrape all banks in a single persistent browser.
One tab per bank. Browser stays open — no 2FA needed on re-runs.
"""
import asyncio
import json
import os
import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

STATE_DIR = Path("data/.browser_state")
STATE_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)


class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return super().default(o)


def save_json(name, data):
    path = DATA_DIR / f"{name}_{date.today().isoformat()}.json"
    path.write_text(json.dumps(data, cls=DecimalEncoder, indent=2, ensure_ascii=False))
    print(f"  ✅ Saved {path}")
    return path


# ─── TRADE REPUBLIC ──────────────────────────────────────────────
async def scrape_tr_details(context):
    """Scrape Trade Republic: positions with ISIN, shares, avg price, P&L + activity history."""
    page = await context.new_page()
    print("\n═══ TRADE REPUBLIC ═══")

    await page.goto("https://app.traderepublic.com/portfolio", wait_until="domcontentloaded")
    await page.wait_for_timeout(8000)  # TR SPA needs time to render positions

    if "login" in page.url:
        print("  ⚠️  Not logged in — enter credentials in the browser, then re-run.")
        return page

    print(f"  Logged in: {page.url}")
    body = await page.inner_text("body")

    # Parse portfolio total
    total_match = re.search(r'([\d\s\xa0,.]+)\s*€', body[:300])
    total = total_match.group(1).replace('\xa0', ' ').strip() if total_match else "?"

    # Parse position names from portfolio page
    lines = body.split('\n')
    positions = []
    idx = 0
    in_inv = False
    while idx < len(lines):
        l = lines[idx].strip()
        if l == "Investissements":
            in_inv = True
            idx += 1
            continue
        if l in ("Mes favoris", "Découvrez"):
            break
        if in_inv and l and not l.startswith(('1J', '1S', '1M', '1A', 'Max', 'Aujourd')):
            if idx + 2 < len(lines):
                val = lines[idx + 1].strip()
                pct = lines[idx + 2].strip()
                if re.match(r'^[\d\s\xa0,.]+\s*€$', val) and re.match(r'^[\d,.]+\s*%$', pct):
                    positions.append({
                        "name": l,
                        "current_value": val.replace('\xa0', ' '),
                        "daily_pct": pct.replace('\xa0', ' '),
                    })
                    idx += 3
                    continue
        idx += 1

    print(f"  Portfolio: {total} € — {len(positions)} positions")

    # Click each position to get ISIN, shares, avg price, P&L
    print("  Fetching position details...")
    for pos in positions:
        try:
            # Find clickable element by matching text content
            els = await page.query_selector_all(f'a, button, div[role="button"], [class*="instrument"], [class*="asset"]')
            clicked = False
            for el in els:
                try:
                    txt = await el.inner_text()
                    if pos["name"] in txt and await el.is_visible():
                        await el.click(timeout=5000)
                        clicked = True
                        break
                except Exception:
                    continue

            if not clicked:
                # Try Playwright's text selector with exact=False
                try:
                    await page.click(f'text="{pos["name"]}"', timeout=5000)
                    clicked = True
                except Exception:
                    pass

            if not clicked:
                print(f"    ⏭  {pos['name']}: can't click")
                continue

            await page.wait_for_timeout(2500)
            detail = await page.inner_text("body")

            # ISIN
            isin_match = re.search(r'\b([A-Z]{2}[A-Z0-9]{9}\d)\b', detail)
            if isin_match:
                pos["isin"] = isin_match.group(1)

            # Shares/quantity
            shares_match = re.search(r'([\d,.]+)\s*(?:parts?|actions?|shares?|pcs|Stk)', detail, re.IGNORECASE)
            if shares_match:
                pos["shares"] = shares_match.group(1)

            # Average price / prix moyen
            avg_match = re.search(r'(?:Prix moyen|Avg\. price|Durchschnitt)[:\s]*([\d\s,.]+\s*€)', detail, re.IGNORECASE)
            if avg_match:
                pos["avg_price"] = avg_match.group(1).replace('\xa0', ' ').strip()

            # P&L
            pnl_match = re.search(r'([\+\-][\d\s\xa0,.]+)\s*€.*?([\+\-]?[\d,.]+\s*%)', detail)
            if pnl_match:
                pos["pnl"] = pnl_match.group(1).replace('\xa0', ' ').strip() + " €"
                pos["pnl_pct"] = pnl_match.group(2).strip()

            # Currency
            if 'USD' in detail:
                pos["currency"] = "USD"
            elif 'EUR' in detail:
                pos["currency"] = "EUR"

            # Save raw detail
            safe = pos["name"].replace(" ", "_")[:25]
            Path(f"/tmp/tr_{safe}.txt").write_text(detail[:3000])

            print(f"    ✓ {pos['name']}: ISIN={pos.get('isin','?')} shares={pos.get('shares','?')} avg={pos.get('avg_price','?')}")

            await page.go_back()
            await page.wait_for_timeout(2000)
        except Exception as e:
            print(f"    ✗ {pos['name']}: {e}")
            await page.goto("https://app.traderepublic.com/portfolio", wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)

    # Activity / transaction history
    print("  Fetching activity history...")
    activity = []
    try:
        await page.goto("https://app.traderepublic.com/profile/transactions", wait_until="domcontentloaded")
        await page.wait_for_timeout(5000)

        # If that URL doesn't work, try clicking through profile
        if "transactions" not in page.url:
            await page.goto("https://app.traderepublic.com/profile", wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)
            for sel in ['text="Activité"', 'text="Activity"', 'text="Transactions"']:
                try:
                    await page.click(sel, timeout=3000)
                    await page.wait_for_timeout(3000)
                    break
                except Exception:
                    continue

        # Scroll to load history
        for _ in range(8):
            await page.evaluate("window.scrollBy(0, 1000)")
            await page.wait_for_timeout(600)

        await page.screenshot(path="/tmp/tr_activity.png")
        activity_text = await page.inner_text("body")
        Path("/tmp/tr_activity.txt").write_text(activity_text)
        print(f"  Activity text saved ({len(activity_text)} chars)")
    except Exception as e:
        print(f"  Activity error: {e}")

    # Cash balance
    cash = ""
    try:
        await page.goto("https://app.traderepublic.com/profile", wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        prof_text = await page.inner_text("body")
        cash_match = re.search(r'Espèces\s*([\d\s\xa0,.]+)\s*€', prof_text)
        if cash_match:
            cash = cash_match.group(1).replace('\xa0', ' ').strip()
            print(f"  Cash: {cash} €")
    except Exception:
        pass

    data = {
        "scraped_at": datetime.now().isoformat(),
        "source": "trade_republic",
        "total_value": total,
        "cash": cash,
        "currency": "EUR",
        "positions": positions,
    }
    save_json("trade_republic", data)
    return page


# ─── BOURSOBANK ──────────────────────────────────────────────────
async def scrape_bourso_details(context):
    """Scrape Boursobank: accounts, PEA positions with ISIN, fees, loans with rates."""
    import hashlib
    SVG_TO_DIGIT = {
        "4b50f14556c316b2d7e3a7d70f13cbe5": "2",
        "e69fe4547b16b1ad18e1001bc4301327": "1",
        "d5a8a106000b1de7fe06a39f3a631e14": "8",
        "60214108971f817e369edadc5455fda0": "5",
        "55bcf3184501f8f5821e858bd96e6eee": "6",
        "0721b3af55284721d8a947c96bd141de": "9",
        "d65e88cc5ca55f4fe4d276e1d7138c69": "3",
        "cb4b1d541bc9cc6ca899631da9b17e2c": "0",
        "4a3206b8d51ab80653b66d6943ecf5d3": "4",
        "484047df455f02161c57e1eb41afb30f": "7",
    }

    page = await context.new_page()
    print("\n═══ BOURSOBANK ═══")

    username = os.environ["BOURSO_USERNAME"]
    password = os.environ["BOURSO_PASSWORD"]

    # WebAuthn bypass
    await page.add_init_script("""
        delete window.PublicKeyCredential;
        navigator.credentials = { get: () => Promise.reject('disabled'), create: () => Promise.reject('disabled') };
    """)

    await page.goto("https://clients.boursobank.com/connexion/", wait_until="domcontentloaded")
    await page.wait_for_timeout(3000)

    # Check if already logged in
    if "connexion" not in page.url:
        print(f"  Already logged in: {page.url}")
    else:
        # Cookie consent
        for sel in ['button:has-text("Tout accepter")', '#didomi-notice-agree-button']:
            try:
                btn = await page.query_selector(sel)
                if btn and await btn.is_visible():
                    await btn.click()
                    await page.wait_for_timeout(1000)
                    break
            except Exception:
                continue

        # Enter username
        for sel in ['input[name="login"]', '#customer-number', 'input[type="text"]']:
            inp = await page.query_selector(sel)
            if inp and await inp.is_visible():
                await inp.fill(username)
                print(f"  Username entered")
                break

        # Click Suivant
        for sel in ['button:has-text("Suivant")', 'button[type="submit"]']:
            try:
                btn = await page.query_selector(sel)
                if btn and await btn.is_visible():
                    await btn.click()
                    break
            except Exception:
                continue

        await page.wait_for_timeout(3000)

        # Handle WebAuthn bypass if needed
        webauthn_el = await page.query_selector('[data-login-step-webauthn]')
        if webauthn_el and await webauthn_el.is_visible():
            print("  Bypassing WebAuthn...")
            await page.evaluate("fetch('/webauthn/connexion/cancel', {method:'POST'})")
            await page.wait_for_timeout(1000)
            await page.evaluate("""
                document.querySelector('[data-login-step-webauthn]')?.style.setProperty('display','none');
                document.querySelector('[data-login-login-view-storage]')?.style.setProperty('display','block');
            """)
            # Fetch virtual keyboard
            resp = await page.evaluate("fetch('/connexion/clavier-virtuel').then(r=>r.text())")
            await page.evaluate(f"""
                var container = document.querySelector('[data-login-login-view-storage]') || document.querySelector('.password-container');
                if(container) container.innerHTML += `{resp.replace('`', '\\`')}`;
            """)
            await page.wait_for_timeout(1000)

        # Enter password via virtual keyboard
        print("  Entering password via virtual keyboard...")
        for digit in password:
            keys = await page.query_selector_all('button.sasmap__key, .pad-button, [data-matrix-key]')
            for key in keys:
                try:
                    img = await key.query_selector('img')
                    if img:
                        src = await img.get_attribute('src')
                        if src and 'base64' in src:
                            b64 = src.split('base64,')[1]
                            h = hashlib.md5(b64.encode()).hexdigest()
                            if SVG_TO_DIGIT.get(h) == digit:
                                await key.click()
                                break
                except Exception:
                    continue

        await page.wait_for_timeout(1000)

        # Submit
        for sel in ['button:has-text("Se connecter")', 'button[type="submit"]', '#submitPassword']:
            try:
                btn = await page.query_selector(sel)
                if btn and await btn.is_visible():
                    await btn.click()
                    break
            except Exception:
                continue

        await page.wait_for_timeout(8000)
        print(f"  Login result: {page.url}")

    await page.screenshot(path="/tmp/bourso_dashboard.png")
    body = await page.inner_text("body")
    Path("/tmp/bourso_body.txt").write_text(body)

    # ── Navigate to accounts ──
    print("  Loading accounts...")
    accounts = []
    try:
        await page.click('a:has-text("Mes comptes")', timeout=5000)
        await page.wait_for_timeout(5000)
        accounts_text = await page.inner_text("body")
        Path("/tmp/bourso_accounts.txt").write_text(accounts_text)
        await page.screenshot(path="/tmp/bourso_accounts.png")
    except Exception as e:
        print(f"  Accounts nav error: {e}")

    # ── Navigate to PEA / Portfolio ──
    print("  Loading portfolio/PEA...")
    positions = []
    try:
        for sel in ['a:has-text("Bourse")', 'a:has-text("PEA")', 'a:has-text("Portefeuille")']:
            try:
                await page.click(sel, timeout=3000)
                await page.wait_for_timeout(5000)
                break
            except Exception:
                continue

        await page.screenshot(path="/tmp/bourso_portfolio.png")
        portfolio_text = await page.inner_text("body")
        Path("/tmp/bourso_portfolio.txt").write_text(portfolio_text)

        # Try to find position rows with ISIN links
        rows = await page.query_selector_all('tr, [class*="line"], [class*="position"]')
        for row in rows:
            try:
                txt = await row.inner_text()
                isin_match = re.search(r'\b([A-Z]{2}[A-Z0-9]{9}\d)\b', txt)
                if isin_match:
                    positions.append({"raw": txt.strip()[:200], "isin": isin_match.group(1)})
            except Exception:
                continue
        print(f"  Found {len(positions)} positions with ISIN")
    except Exception as e:
        print(f"  Portfolio error: {e}")

    # ── Loans / Credits ──
    print("  Loading loans...")
    loans = []
    try:
        await page.goto("https://clients.boursobank.com/credit/index.phtml", wait_until="domcontentloaded")
        await page.wait_for_timeout(5000)
        await page.screenshot(path="/tmp/bourso_loans.png")
        loans_text = await page.inner_text("body")
        Path("/tmp/bourso_loans.txt").write_text(loans_text)

        # Parse loan details: rate, TEG, monthly payment, remaining
        loan_blocks = re.split(r'(?=Prêt|Crédit|PRET)', loans_text)
        for block in loan_blocks:
            if len(block) < 20:
                continue
            loan = {"raw": block[:300]}
            rate_match = re.search(r'Taux\s*[:\s]*([\d,.]+)\s*%', block, re.IGNORECASE)
            if rate_match:
                loan["rate"] = rate_match.group(1) + "%"
            teg_match = re.search(r'TEG\s*[:\s]*([\d,.]+)\s*%', block, re.IGNORECASE)
            if teg_match:
                loan["teg"] = teg_match.group(1) + "%"
            taeg_match = re.search(r'TAEG\s*[:\s]*([\d,.]+)\s*%', block, re.IGNORECASE)
            if taeg_match:
                loan["taeg"] = taeg_match.group(1) + "%"
            mensualite_match = re.search(r'(?:mensualit|échéance)[^\d]*([\d\s,.]+)\s*€', block, re.IGNORECASE)
            if mensualite_match:
                loan["monthly"] = mensualite_match.group(1).strip() + " €"
            if rate_match or teg_match or taeg_match:
                loans.append(loan)
        print(f"  Found {len(loans)} loans with rates")
    except Exception as e:
        print(f"  Loans error: {e}")

    data = {
        "scraped_at": datetime.now().isoformat(),
        "source": "boursobank",
        "accounts_raw": Path("/tmp/bourso_accounts.txt").read_text()[:5000] if Path("/tmp/bourso_accounts.txt").exists() else "",
        "positions": positions,
        "loans": loans,
    }
    save_json("boursobank", data)
    return page


# ─── IBKR ────────────────────────────────────────────────────────
async def scrape_ibkr_details(context):
    """Scrape IBKR: positions, trades history, fees, margin details."""
    page = await context.new_page()
    print("\n═══ IBKR ═══")

    username = os.environ["IBKR_USERNAME"]
    password = os.environ["IBKR_PASSWORD"]

    await page.goto("https://www.interactivebrokers.com/sso/Login", wait_until="domcontentloaded")
    await page.wait_for_timeout(3000)

    # Check if redirected to portal (already logged in)
    if "portal" in page.url or "dashboard" in page.url:
        print(f"  Already logged in: {page.url}")
    else:
        # Dismiss cookies
        for sel in ['button:has-text("Accept")', 'button:has-text("Reject All")', '#onetrust-accept-btn-handler']:
            try:
                btn = await page.query_selector(sel)
                if btn and await btn.is_visible():
                    await btn.click()
                    await page.wait_for_timeout(1000)
                    break
            except Exception:
                continue

        # Login
        user_field = await page.query_selector('input[name="username"], #user_name')
        pass_field = await page.query_selector('input[name="password"], #password')
        if user_field:
            await user_field.fill(username)
        if pass_field:
            await pass_field.fill(password)

        for sel in ['button:has-text("Log In")', 'button:has-text("Login")', '#submitForm', 'button[type="submit"]']:
            try:
                btn = await page.query_selector(sel)
                if btn and await btn.is_visible():
                    await btn.click()
                    break
            except Exception:
                continue

        print("  ⚠️  IBKR 2FA: Confirm on IB Key mobile app!")

        # Wait for 2FA (up to 120s)
        for i in range(24):
            await page.wait_for_timeout(5000)
            if "portal" in page.url or "dashboard" in page.url:
                print(f"  2FA confirmed! URL: {page.url}")
                break
            print(f"  Waiting for 2FA... {120-(i+1)*5}s")
        else:
            print("  2FA timeout")

    await page.wait_for_timeout(5000)

    # Dismiss FYI modal
    try:
        close_btn = await page.query_selector('button:has-text("Close")')
        if close_btn and await close_btn.is_visible():
            await close_btn.click()
            await page.wait_for_timeout(1000)
    except Exception:
        pass

    await page.screenshot(path="/tmp/ibkr_dashboard.png")
    body = await page.inner_text("body")
    Path("/tmp/ibkr_body.txt").write_text(body)
    print(f"  Dashboard loaded: {page.url}")

    # Parse dashboard values
    total_match = re.search(r'(?:Net Liquidation|Total)[:\s]*([\d,.\s]+)', body)
    total = total_match.group(1).strip() if total_match else "?"
    print(f"  Total: {total}")

    # ── Try Portfolio tab ──
    print("  Loading portfolio...")
    positions = []
    try:
        for sel in ['text="Portfolio"', 'a[href*="portfolio"]', '[data-tab="portfolio"]']:
            try:
                await page.click(sel, timeout=5000)
                await page.wait_for_timeout(5000)
                break
            except Exception:
                continue

        await page.screenshot(path="/tmp/ibkr_portfolio.png")
        portfolio_text = await page.inner_text("body")
        Path("/tmp/ibkr_portfolio.txt").write_text(portfolio_text)

        # Parse positions with contract IDs
        rows = await page.query_selector_all('tr, [class*="position"], [class*="row"]')
        for row in rows:
            try:
                txt = await row.inner_text()
                if any(kw in txt for kw in ['STK', 'OPT', 'FUT', 'ETF', 'CASH']):
                    positions.append({"raw": txt.strip()[:300]})
            except Exception:
                continue
        print(f"  Found {len(positions)} positions")
    except Exception as e:
        print(f"  Portfolio error: {e}")

    # ── Trades / Activity ──
    print("  Loading trade history...")
    trades = []
    try:
        for sel in ['text="Activity"', 'text="Trades"', 'a[href*="activity"]', 'a[href*="trades"]']:
            try:
                await page.click(sel, timeout=3000)
                await page.wait_for_timeout(5000)
                break
            except Exception:
                continue

        await page.screenshot(path="/tmp/ibkr_activity.png")
        activity_text = await page.inner_text("body")
        Path("/tmp/ibkr_activity.txt").write_text(activity_text)
        print(f"  Activity text saved ({len(activity_text)} chars)")
    except Exception as e:
        print(f"  Activity error: {e}")

    # ── Account statements for fees ──
    print("  Looking for statements/reports...")
    try:
        for sel in ['text="Reports"', 'text="Statements"', 'a[href*="report"]', 'a[href*="statement"]']:
            try:
                await page.click(sel, timeout=3000)
                await page.wait_for_timeout(5000)
                break
            except Exception:
                continue

        await page.screenshot(path="/tmp/ibkr_reports.png")
        reports_text = await page.inner_text("body")
        Path("/tmp/ibkr_reports.txt").write_text(reports_text)
    except Exception as e:
        print(f"  Reports error: {e}")

    data = {
        "scraped_at": datetime.now().isoformat(),
        "source": "ibkr",
        "total_value": total,
        "positions": positions,
        "dashboard_raw": body[:5000],
    }
    save_json("ibkr", data)
    return page


# ─── CREDIT AGRICOLE ─────────────────────────────────────────────
async def scrape_ca_details(context):
    """Scrape Crédit Agricole: accounts, loans with rates/TEG/TAEG, insurance."""
    page = await context.new_page()
    print("\n═══ CRÉDIT AGRICOLE ═══")

    username = os.environ["CA_USERNAME"]
    pin = os.environ["CA_PIN"]
    region = os.environ.get("CA_REGION", "languedoc")
    base_url = f"https://www.ca-{region}.fr"

    await page.goto(base_url, wait_until="domcontentloaded")
    await page.wait_for_timeout(3000)

    # Check if already on authenticated page
    if "synthese" in page.url or "operations" in page.url:
        print(f"  Already logged in: {page.url}")
    else:
        # Cookies
        for sel in ['button:has-text("Tout accepter")', 'button:has-text("Accepter")']:
            try:
                btn = await page.query_selector(sel)
                if btn and await btn.is_visible():
                    await btn.click()
                    await page.wait_for_timeout(1000)
                    break
            except Exception:
                continue

        # Click "Me connecter"
        try:
            conn = await page.query_selector('a:has-text("Me connecter"), button:has-text("Me connecter")')
            if conn:
                await conn.click()
                await page.wait_for_timeout(3000)
        except Exception:
            pass

        # Enter account number
        for sel in ['input[name="CCPTE"]', 'input[name="account"]', 'input[type="text"]']:
            inp = await page.query_selector(sel)
            if inp and await inp.is_visible():
                await inp.fill(username)
                print(f"  Account number entered")
                break

        # Click "ENTRER MON CODE PERSONNEL"
        try:
            await page.click('button:has-text("ENTRER MON CODE PERSONNEL")', timeout=5000)
            await page.wait_for_timeout(3000)
        except Exception:
            pass

        # Virtual keyboard for PIN
        for digit in pin:
            links = await page.query_selector_all('a[onclick], a.sasmap__key, .pad-button a, a')
            for link in links:
                try:
                    txt = (await link.inner_text()).strip()
                    if txt == digit and await link.is_visible():
                        await link.click()
                        break
                except Exception:
                    continue

        # Submit
        for sel in ['#validation', 'button[type="submit"]', 'button:has-text("Valider")']:
            try:
                btn = await page.query_selector(sel)
                if btn and await btn.is_visible():
                    await btn.click()
                    break
            except Exception:
                continue

        await page.wait_for_timeout(5000)
        print(f"  Login result: {page.url}")

    await page.screenshot(path="/tmp/ca_dashboard.png")

    # ── Dashboard data ──
    body = await page.inner_text("body")
    Path("/tmp/ca_body.txt").write_text(body)
    balance_match = re.search(r'([\d\s]+,\d{2})\s*€', body.replace('\xa0', ' '))
    balance = balance_match.group(1).strip() if balance_match else "?"
    print(f"  Main balance: {balance} €")

    # ── Expand credits on dashboard ──
    credits = []
    try:
        btn = await page.query_selector('text="Afficher mes crédits"')
        if btn:
            await btn.click()
            await page.wait_for_timeout(3000)

        expanded = await page.inner_text("body")
        Path("/tmp/ca_credits.txt").write_text(expanded)

        # Parse: name → account → Echéance → amount → Montant emprunté → amount → Restant dû → amount
        lines = expanded.split('\n')
        current = {}
        expect = None
        for line in lines:
            l = line.strip()
            if not l:
                continue
            if ('Prêt' in l or 'prêt' in l) and 'Simulateur' not in l and 'REMBOURSEMENT' not in l and 'immobilier en ligne' not in l:
                if current and 'name' in current:
                    credits.append(current)
                current = {"name": l}
                expect = None
            elif re.match(r'^\d{11}$', l) and current:
                current["account_number"] = l
            elif 'Echéance' in l or 'Échéance' in l:
                expect = "monthly_payment"
            elif 'Montant emprunté' in l:
                expect = "borrowed"
            elif 'Restant dû' in l:
                expect = "remaining"
            elif re.match(r'^[\d\s\xa0]+,\d{2}\s*\xa0?\s*€$', l) and current and expect:
                current[expect] = l.replace('\xa0', ' ').strip()
                expect = None
        if current and 'name' in current:
            credits.append(current)
        print(f"  Found {len(credits)} loans")
    except Exception as e:
        print(f"  Credits error: {e}")

    # ── Navigate to Crédits page for rates/TEG ──
    print("  Loading Crédits page for rates...")
    try:
        await page.goto(f"https://www.credit-agricole.fr/ca-{region}/particulier/operations/credits.html", wait_until="domcontentloaded")
        await page.wait_for_timeout(5000)
        await page.screenshot(path="/tmp/ca_credits_page.png")
        credits_page = await page.inner_text("body")
        Path("/tmp/ca_credits_page.txt").write_text(credits_page)

        # Parse rates
        for credit in credits:
            if "account_number" in credit:
                acct = credit["account_number"]
                # Find block related to this account
                if acct in credits_page:
                    idx = credits_page.index(acct)
                    block = credits_page[max(0, idx-200):idx+500]
                    rate_match = re.search(r'Taux\s*[:\s]*([\d,.]+)\s*%', block, re.IGNORECASE)
                    if rate_match:
                        credit["rate"] = rate_match.group(1) + "%"
                    teg_match = re.search(r'TEG\s*[:\s]*([\d,.]+)\s*%', block, re.IGNORECASE)
                    if teg_match:
                        credit["teg"] = teg_match.group(1) + "%"
                    taeg_match = re.search(r'TAEG\s*[:\s]*([\d,.]+)\s*%', block, re.IGNORECASE)
                    if taeg_match:
                        credit["taeg"] = taeg_match.group(1) + "%"
                    duree_match = re.search(r'(?:Durée|durée)\s*[:\s]*([\d]+)\s*(?:mois|ans)', block, re.IGNORECASE)
                    if duree_match:
                        credit["duration"] = duree_match.group(0).strip()

        # Try clicking each credit for detail
        for credit in credits:
            if "account_number" in credit:
                try:
                    link = await page.query_selector(f'text="{credit["account_number"]}"')
                    if link:
                        await link.click()
                        await page.wait_for_timeout(3000)
                        detail = await page.inner_text("body")
                        rate_match = re.search(r'Taux\s*[:\s]*([\d,.]+)\s*%', detail, re.IGNORECASE)
                        if rate_match:
                            credit["rate"] = rate_match.group(1) + "%"
                        teg_match = re.search(r'(?:TEG|TAEG)\s*[:\s]*([\d,.]+)\s*%', detail, re.IGNORECASE)
                        if teg_match:
                            credit["teg"] = teg_match.group(1) + "%"
                        assurance_match = re.search(r'assurance\s*[:\s]*([\d,.]+)\s*€', detail, re.IGNORECASE)
                        if assurance_match:
                            credit["insurance_cost"] = assurance_match.group(1) + " €"
                        Path(f"/tmp/ca_credit_{credit['account_number']}.txt").write_text(detail[:3000])
                        print(f"    {credit['name']}: rate={credit.get('rate','?')} teg={credit.get('teg','?')}")
                        await page.go_back()
                        await page.wait_for_timeout(2000)
                except Exception:
                    pass
    except Exception as e:
        print(f"  Credits page error: {e}")

    data = {
        "scraped_at": datetime.now().isoformat(),
        "source": "credit_agricole",
        "region": region,
        "owner": "SYLVAIN LEGLAND",
        "main_balance": balance + " €",
        "credits": credits,
        "savings": "Aucune épargne",
        "insurance": "Aucune assurance",
    }
    save_json("credit_agricole", data)
    return page


# ─── MAIN ────────────────────────────────────────────────────────
async def main():
    from playwright.async_api import async_playwright

    # Clean stale locks
    for lock in STATE_DIR.glob("Singleton*"):
        lock.unlink(missing_ok=True)

    pw = await async_playwright().start()
    context = await pw.chromium.launch_persistent_context(
        str(STATE_DIR),
        headless=False,
        viewport={"width": 1400, "height": 900},
        locale="fr-FR",
    )

    print("🏦 Multi-bank scraper — single browser, multiple tabs")
    print("=" * 55)

    pages = []

    # TR first (already has session potentially)
    p = await scrape_tr_details(context)
    if p: pages.append(p)

    # Boursobank
    p = await scrape_bourso_details(context)
    if p: pages.append(p)

    # IBKR
    p = await scrape_ibkr_details(context)
    if p: pages.append(p)

    # Crédit Agricole
    p = await scrape_ca_details(context)
    if p: pages.append(p)

    print("\n" + "=" * 55)
    print("🏦 ALL DONE — browser stays open for inspection.")
    print("   Close the browser manually when finished.")
    print("   Re-run this script to scrape again without re-login.")

    # Auto-build patrimoine_complet from scraped data
    try:
        from build_patrimoine import build
        build()
        print("✅ patrimoine_complet rebuilt from fresh scrape data")
    except Exception as e:
        print(f"⚠️  Failed to rebuild patrimoine: {e}")

    # Keep alive — don't close!
    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass


if __name__ == "__main__":
    asyncio.run(main())
