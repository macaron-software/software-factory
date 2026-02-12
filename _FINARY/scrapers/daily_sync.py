#!/usr/bin/env python3
"""daily_sync.py — Full daily pipeline: login → scrape → parse → rebuild.

Connects to Chrome CDP on port 18800, logs into all 4 banks using existing tabs,
scrapes portfolio/account data, downloads IBKR statement, parses transactions
into DuckDB, and rebuilds patrimoine_complet.

2FA: IBKR and TR require mobile app confirmation. A macOS notification is sent
when 2FA is needed. The script waits up to 120s for approval.

Schedule: launchd at 09:00 weekdays (Mon-Fri).

Usage:
    python3 daily_sync.py            # Full pipeline
    python3 daily_sync.py --scrape   # Skip login, scrape only (sessions alive)
    python3 daily_sync.py --rebuild  # Only rebuild from existing data
    python3 daily_sync.py --parse    # Only re-parse transactions → DuckDB
"""

import asyncio
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv

DIR = Path(__file__).parent
DATA_DIR = DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
sys.path.insert(0, str(DIR))
load_dotenv(DIR / ".env")

TODAY = date.today().isoformat()
LOG = []


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    LOG.append(line)


def notify(title, msg):
    """Send macOS notification."""
    try:
        subprocess.run([
            "osascript", "-e",
            f'display notification "{msg}" with title "{title}"'
        ], timeout=5)
    except Exception:
        pass


# ════════════════════════════════════════════════════════════════
# LOGIN
# ════════════════════════════════════════════════════════════════

async def login_all(ctx):
    """Auto-login all 4 banks on their existing tabs (or create new ones)."""
    pages = {}
    for p in ctx.pages:
        u = p.url.lower()
        if "interactivebrokers" in u:
            pages["ibkr"] = p
        elif "bourso" in u:
            pages["bourso"] = p
        elif "traderepublic" in u:
            pages["tr"] = p
        elif "credit-agricole" in u or "ca-languedoc" in u:
            pages["ca"] = p

    log(f"🏦 Found tabs: {list(pages.keys())}")

    # Create missing bank tabs
    BANK_URLS = {
        "ibkr": "https://www.interactivebrokers.ie/portal/#/portfolio",
        "bourso": "https://clients.boursobank.com/connexion/",
        "tr": "https://app.traderepublic.com/login",
        "ca": f"https://www.credit-agricole.fr/ca-{os.environ.get('CA_REGION', 'languedoc')}/particulier/acceder-a-mes-comptes.html",
    }
    for bank, url in BANK_URLS.items():
        if bank not in pages:
            log(f"  [{bank.upper()}] No tab found — creating one")
            page = await ctx.new_page()
            await page.goto(url, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)
            pages[bank] = page

    logged = {}

    # ─── IBKR ───
    if "ibkr" in pages:
        page = pages["ibkr"]
        log("  [IBKR] Checking session...")
        await page.goto("https://www.interactivebrokers.ie/portal/#/portfolio", wait_until="domcontentloaded")
        await page.wait_for_timeout(5000)
        if "portal" in page.url and "Login" not in await page.title():
            log("  [IBKR] ✅ Already logged in")
            logged["ibkr"] = page
        else:
            log("  [IBKR] Session expired, logging in...")
            await page.goto("https://www.interactivebrokers.com/sso/Login", wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)
            username = os.environ.get("IBKR_USERNAME", "")
            password = os.environ.get("IBKR_PASSWORD", "")
            try:
                await page.fill('input[name="username"], #user_name', username, timeout=5000)
                await page.fill('input[name="password"], #password', password, timeout=5000)
                await page.click('button[type="submit"], #submitForm', timeout=5000)
                notify("Finary Sync", "IBKR 2FA — confirme sur IB Key")
                log("  [IBKR] ⏳ Waiting for 2FA (120s)...")
                for _ in range(24):
                    await page.wait_for_timeout(5000)
                    if "portal" in page.url:
                        log("  [IBKR] ✅ Logged in")
                        logged["ibkr"] = page
                        break
                else:
                    log("  [IBKR] ⚠️ 2FA timeout")
            except Exception as e:
                log(f"  [IBKR] ❌ Login failed: {e}")

    # ─── BOURSO ───
    if "bourso" in pages:
        page = pages["bourso"]
        log("  [Bourso] Checking session...")
        await page.goto("https://clients.boursobank.com/", wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        body = await page.inner_text("body")
        if "Total des avoirs" in body or "Mes comptes" in body:
            log("  [Bourso] ✅ Already logged in")
            logged["bourso"] = page
        else:
            log("  [Bourso] Session expired, logging in...")
            await page.add_init_script("""
                delete window.PublicKeyCredential;
                navigator.credentials = { get: () => Promise.reject('disabled'), create: () => Promise.reject('disabled') };
            """)
            await page.goto("https://clients.boursobank.com/connexion/", wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)
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
            # Username
            username = os.environ.get("BOURSO_USERNAME", "")
            password = os.environ.get("BOURSO_PASSWORD", "")
            try:
                inp = await page.query_selector('input[name="login"], input[type="text"]')
                if inp:
                    await inp.fill(username)
                await page.click('button[type="submit"]', timeout=5000)
                await page.wait_for_timeout(5000)
                # Virtual numpad
                buttons = await page.query_selector_all('.sasmap__key')
                if len(buttons) >= 10:
                    digit_map = {}
                    for i, btn in enumerate(buttons):
                        img = await btn.query_selector("img")
                        if img:
                            src = await img.get_attribute("src") or ""
                            h = hashlib.md5(src.encode()).hexdigest()
                            digit_map[h] = i
                    # Screenshot each to /tmp for debug
                    btn_hashes = {}
                    for i, btn in enumerate(buttons):
                        img = await btn.query_selector("img")
                        if img:
                            src = await img.get_attribute("src") or ""
                            btn_hashes[i] = hashlib.md5(src.encode()).hexdigest()
                    # Known SVG hashes → digit mapping (from previous sessions)
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
                    # Build index→digit
                    idx_to_digit = {}
                    for i, h in btn_hashes.items():
                        if h in SVG_TO_DIGIT:
                            idx_to_digit[i] = SVG_TO_DIGIT[h]
                    digit_to_idx = {v: k for k, v in idx_to_digit.items()}
                    for ch in password:
                        idx = digit_to_idx.get(ch)
                        if idx is not None:
                            await buttons[idx].click()
                            await page.wait_for_timeout(200)
                    await page.click('button[type="submit"]', timeout=5000)
                    await page.wait_for_timeout(5000)
                    if "connexion" not in page.url:
                        log("  [Bourso] ✅ Logged in")
                        logged["bourso"] = page
                    else:
                        log("  [Bourso] ⚠️ Login may have failed")
                else:
                    log(f"  [Bourso] ⚠️ Numpad not found ({len(buttons)} buttons)")
            except Exception as e:
                log(f"  [Bourso] ❌ Login failed: {e}")

    # ─── TR ───
    if "tr" in pages:
        page = pages["tr"]
        log("  [TR] Checking session...")
        await page.goto("https://app.traderepublic.com/portfolio", wait_until="domcontentloaded")
        await page.wait_for_timeout(5000)
        if "login" not in page.url:
            log("  [TR] ✅ Already logged in")
            logged["tr"] = page
        else:
            log("  [TR] Session expired, logging in...")
            phone = os.environ.get("TR_PHONE", "")
            pin = os.environ.get("TR_PIN", "")
            try:
                # Select France (+33)
                await page.click('button:has-text("+49"), button:has-text("+33")', timeout=5000)
                await page.wait_for_timeout(1000)
                await page.evaluate("""() => {
                    const items = document.querySelectorAll('[role="option"], li');
                    for (const item of items) {
                        if (item.textContent.includes('+33') || item.textContent.includes('France')) {
                            item.scrollIntoView(); item.click(); return;
                        }
                    }
                }""")
                await page.wait_for_timeout(500)
                phone_num = phone.replace("+33", "")
                await page.fill('#loginPhoneNumber__input', phone_num, timeout=5000)
                await page.click('button[type="submit"]', timeout=5000)
                await page.wait_for_timeout(3000)
                # PIN
                inputs = await page.query_selector_all('input[type="password"], input[type="tel"]')
                for i, ch in enumerate(pin[:4]):
                    if i < len(inputs):
                        await inputs[i].fill(ch)
                await page.wait_for_timeout(1000)
                await page.click('button[type="submit"]', timeout=5000)
                notify("Finary Sync", "TR 2FA — confirme sur l'app Trade Republic")
                log("  [TR] ⏳ Waiting for 2FA (120s)...")
                for _ in range(24):
                    await page.wait_for_timeout(5000)
                    if "login" not in page.url:
                        log("  [TR] ✅ Logged in")
                        logged["tr"] = page
                        break
                else:
                    log("  [TR] ⚠️ 2FA timeout")
            except Exception as e:
                log(f"  [TR] ❌ Login failed: {e}")

    # ─── CA ───
    if "ca" in pages:
        page = pages["ca"]
        log("  [CA] Checking session...")
        body = await page.inner_text("body")
        if "BONJOUR" in body or "synthese" in page.url:
            log("  [CA] ✅ Already logged in")
            logged["ca"] = page
        else:
            log("  [CA] Session expired, logging in...")
            region = os.environ.get("CA_REGION", "languedoc")
            username = os.environ.get("CA_USERNAME", "")
            pin = os.environ.get("CA_PIN", "")
            try:
                await page.goto(f"https://www.credit-agricole.fr/ca-{region}/particulier/acceder-a-mes-comptes.html", wait_until="domcontentloaded")
                await page.wait_for_timeout(3000)
                # Cookie consent
                for sel in ['button:has-text("Tout accepter")', 'button:has-text("Accepter")']:
                    try:
                        btn = await page.query_selector(sel)
                        if btn and await btn.is_visible():
                            await btn.click()
                            await page.wait_for_timeout(1000)
                            break
                    except Exception:
                        continue
                # Username
                await page.fill('#Login-account, input[name="CCPTE"]', username, timeout=5000)
                await page.click('text=Entrer mon code personnel', timeout=5000)
                await page.wait_for_timeout(3000)
                # Virtual keyboard (a.Login-key with digit text)
                for digit in pin:
                    await page.evaluate(f"""() => {{
                        const links = document.querySelectorAll('a.Login-key');
                        for (const a of links) {{
                            if (a.textContent.trim() === '{digit}') {{ a.click(); return; }}
                        }}
                    }}""")
                    await page.wait_for_timeout(300)
                await page.click('text=VALIDER', timeout=5000)
                await page.wait_for_timeout(5000)
                if "synthese" in page.url or "operations" in page.url:
                    log("  [CA] ✅ Logged in")
                    logged["ca"] = page
                else:
                    log(f"  [CA] ⚠️ Login unclear: {page.url[:50]}")
            except Exception as e:
                log(f"  [CA] ❌ Login failed: {e}")

    return logged


# ════════════════════════════════════════════════════════════════
# SCRAPE
# ════════════════════════════════════════════════════════════════

async def scrape_all(pages):
    """Scrape portfolio data from logged-in bank pages."""
    results = {}

    # ─── IBKR Portfolio ───
    if "ibkr" in pages:
        page = pages["ibkr"]
        log("  📊 [IBKR] Scraping portfolio...")
        try:
            await page.goto("https://www.interactivebrokers.ie/portal/#/portfolio", wait_until="domcontentloaded")
            await page.wait_for_timeout(5000)
            raw = await page.inner_text("body")

            # Parse positions
            pos_re = re.compile(
                r'([A-Z]{2,5})\s*\n'
                r'\t([\d.]+)\t([\d,.]+)\t([+-]?[\d.]+%)\t'
                r'([\d,.]+)\s*\n'
                r'([\d,.]+)\n'
                r'\t([\d,.]+)\t([+-]?[\d,.]+)\t([+-]?[\d,.]+)',
                re.MULTILINE)
            positions = []
            for m in pos_re.finditer(raw):
                positions.append({
                    "symbol": m.group(1),
                    "quantity": float(m.group(2)),
                    "last_price_usd": float(m.group(3).replace(",", "")),
                    "cost_basis_eur": float(m.group(5).replace(",", "")),
                    "market_value_eur": float(m.group(6).replace(",", "")),
                    "avg_price_usd": float(m.group(7).replace(",", "")),
                    "daily_pnl_eur": float(m.group(8).replace(",", "").replace("+", "")),
                    "unrealized_pnl_eur": float(m.group(9).replace(",", "").replace("+", "")),
                })

            summary = {}
            for pat, key in [
                (r"Net Liquidity\n([\d,.]+)", "net_liquidity"),
                (r"Buying Power\n([\d,.]+)", "buying_power"),
                (r"Unrealized P&L\n([+-]?[\d,.]+)", "unrealized_pnl"),
                (r"Excess Liquidity\n\n?([\d,.]+)", "excess_liquidity"),
            ]:
                m2 = re.search(pat, raw)
                if m2:
                    summary[key] = float(m2.group(1).replace(",", ""))

            cash = {}
            for pat, key in [
                (r"EUR \(base currency\)\t([−-]?[\d,.]+)", "EUR"),
                (r"USD\t([−-]?[\d,.]+)", "USD"),
                (r"Total Cash.*?\t([−-]?[\d,.]+)", "total_eur"),
            ]:
                m2 = re.search(pat, raw)
                if m2:
                    cash[key] = float(m2.group(1).replace(",", "").replace("−", "-"))

            data = {"scraped_at": datetime.now().isoformat(), "source": "ibkr",
                    "summary": summary, "positions": positions, "cash": cash}
            (DATA_DIR / f"ibkr_{TODAY}.json").write_text(json.dumps(data, indent=2))
            log(f"    ✅ {len(positions)} positions, NLV={summary.get('net_liquidity', 0):,.0f}€")
            results["ibkr"] = data

            # Download Activity Statement CSV
            log("    📄 Downloading Activity Statement...")
            await page.click('button:has-text("Statements")', timeout=5000)
            await page.wait_for_timeout(5000)
            selects = await page.query_selector_all("select")
            if selects:
                await selects[0].select_option(label="Annuel")
                await page.wait_for_timeout(2000)
                selects2 = await page.query_selector_all("select")
                for s in selects2:
                    opts = await s.evaluate("s => Array.from(s.options).map(o => o.text)")
                    if "2025" in opts:
                        await s.select_option(label="2025")
                        break
                await page.wait_for_timeout(2000)
                try:
                    async with page.expect_download(timeout=30000) as dl_info:
                        await page.click('[aria-label*="CSV"]', timeout=5000)
                    dl = await dl_info.value
                    await dl.save_as(str(DATA_DIR / "ibkr_activity_2025.csv"))
                    log("    ✅ Activity Statement 2025 CSV downloaded")
                except Exception as e:
                    log(f"    ⚠️ Statement download failed: {e}")
        except Exception as e:
            log(f"    ❌ IBKR scrape failed: {e}")

    # ─── Bourso ───
    if "bourso" in pages:
        page = pages["bourso"]
        log("  📊 [Bourso] Scraping accounts...")
        try:
            await page.goto("https://clients.boursobank.com/", wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)
            body = await page.inner_text("body")
            bourso_data = {"scraped_at": datetime.now().isoformat(), "source": "boursobank",
                           "accounts": [], "loans": [], "children": []}
            lines = [l.strip() for l in body.split("\n") if l.strip()]
            section = None
            for i, l in enumerate(lines):
                if "Mes comptes bancaires" in l: section = "accounts"
                elif "Mes crédits" in l: section = "loans"
                elif "Comptes de mes enfants" in l: section = "children"
                m = re.match(r"^[−-]?\s*([\d\s]+,\d{2})\s*€$", l.replace("\xa0", " "))
                if m and i > 0:
                    amt = l.replace("\xa0", " ").replace(" ", "").replace("−", "-").replace(",", ".").replace("€", "").strip()
                    try:
                        amount = float(amt)
                    except ValueError:
                        continue
                    name = lines[i - 1][:60]
                    entry = {"name": name, "balance": amount, "currency": "EUR"}
                    if section == "loans" or amount < -100:
                        bourso_data["loans"].append(entry)
                    elif section == "children":
                        bourso_data["children"].append(entry)
                    else:
                        bourso_data["accounts"].append(entry)
            (DATA_DIR / f"boursobank_{TODAY}.json").write_text(
                json.dumps(bourso_data, indent=2, ensure_ascii=False))
            log(f"    ✅ {len(bourso_data['accounts'])} accounts, {len(bourso_data['loans'])} loans")
            results["bourso"] = bourso_data

            # CSV export
            uuid = "fab68d213d98fe597b6cbf7e08d8dd4a"
            await page.goto(f"https://clients.boursobank.com/compte/cav/{uuid}/mouvements", wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)
            try:
                resp = await page.request.get(f"https://clients.boursobank.com/operations/generate/{uuid}")
                csv_text = await resp.text()
                if resp.status == 200 and not csv_text.startswith("<!DOCTYPE"):
                    (DATA_DIR / f"bourso_export.csv").write_text(csv_text)
                    log(f"    ✅ CSV export: {csv_text.count(chr(10))} lines")
            except Exception as e:
                log(f"    ⚠️ CSV export failed: {e}")
        except Exception as e:
            log(f"    ❌ Bourso scrape failed: {e}")

    # ─── TR ───
    if "tr" in pages:
        page = pages["tr"]
        log("  📊 [TR] Scraping portfolio...")
        try:
            await page.goto("https://app.traderepublic.com/portfolio", wait_until="domcontentloaded")
            await page.wait_for_timeout(6000)
            raw = await page.inner_text("body")
            lines = [l.strip() for l in raw.split("\n") if l.strip()]
            positions = []
            in_inv = False
            i = 0
            while i < len(lines):
                l = lines[i]
                if l in ("Investments", "Investissements"):
                    in_inv = True
                    if i + 1 < len(lines) and lines[i + 1] in ("Since buy", "Depuis achat"):
                        i += 2
                    else:
                        i += 1
                    continue
                if l in ("Following", "Favorites", "Discover", "Mes favoris", "Close"):
                    break
                if in_inv and not re.match(r"^[\d.]+$", l) and "€" not in l and "%" not in l \
                        and l not in ("Open your PEA", "To access your PEA account, please use your app."):
                    if i + 3 < len(lines) and re.match(r"^[\d.]+$", lines[i + 1]) \
                            and "€" in lines[i + 2] and "%" in lines[i + 3]:
                        val = float(lines[i + 2].replace("\xa0", "").replace(" ", "").replace(",", ".").replace("€", ""))
                        pct = float(lines[i + 3].replace("\xa0", "").replace(" ", "").replace(",", ".").replace("%", ""))
                        positions.append({"name": l, "shares": float(lines[i + 1]),
                                          "value": val, "return_pct": pct})
                        i += 4
                        continue
                i += 1

            tr_data = {"scraped_at": datetime.now().isoformat(), "source": "trade_republic",
                       "portfolio_value": sum(p["value"] for p in positions),
                       "positions": positions}
            (DATA_DIR / f"trade_republic_{TODAY}.json").write_text(
                json.dumps(tr_data, indent=2, ensure_ascii=False))
            log(f"    ✅ {len(positions)} positions, total={tr_data['portfolio_value']:,.2f}€")
            results["tr"] = tr_data

            # Activities
            log("    📜 Scraping TR activities...")
            await page.goto("https://app.traderepublic.com/profile/transactions", wait_until="domcontentloaded")
            await page.wait_for_timeout(5000)
            for _ in range(10):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(1500)
            activities = await page.inner_text("body")
            (DATA_DIR / f"tr_activities_{TODAY}.txt").write_text(activities)
            log(f"    ✅ Activities: {len(activities)} chars")
        except Exception as e:
            log(f"    ❌ TR scrape failed: {e}")

    # ─── CA ───
    if "ca" in pages:
        page = pages["ca"]
        log("  📊 [CA] Scraping accounts & credits...")
        try:
            await page.goto("https://www.credit-agricole.fr/ca-languedoc/particulier/operations/synthese.html",
                            wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)
            body = await page.inner_text("body")

            ca_data = {"scraped_at": datetime.now().isoformat(), "source": "credit_agricole",
                       "region": "languedoc", "accounts": [], "credits": [], "recent_transactions": []}

            # Main balance
            m = re.search(r"MON COMPTE PRINCIPAL.*?([\d\s,]+)\s*€", body, re.DOTALL)
            if m:
                bal = float(m.group(1).replace("\xa0", "").replace(" ", "").replace(",", "."))
                ca_data["accounts"].append({"name": "Compte Principal", "type": "checking", "balance": bal})

            # Transactions
            lines = [l.strip() for l in body.split("\n") if l.strip()]
            for i, l in enumerate(lines):
                if re.match(r"^\d{2}/\d{2}$", l) and i + 2 < len(lines):
                    desc_idx = i + 2
                    if desc_idx + 1 < len(lines):
                        desc = lines[desc_idx]
                        amt = lines[desc_idx + 1].replace("\xa0", " ")
                        if re.match(r"^-?[\d\s,]+€$", amt.replace(" ", "")):
                            ca_data["recent_transactions"].append(
                                {"date": l, "description": desc, "amount": amt})

            # Credits
            try:
                await page.click("text=Afficher mes crédits", timeout=5000)
                await page.wait_for_timeout(3000)
                credit_body = await page.inner_text("body")
                credit_lines = [l.strip() for l in credit_body.split("\n") if l.strip()]
                current = None
                ci = 0
                while ci < len(credit_lines):
                    cl = credit_lines[ci]
                    if "Prêt à 0%" in cl:
                        current = {"name": "PTZ", "type": "ptz"}
                    elif "Prêt d'Accession Social" in cl:
                        current = {"name": "PAS", "type": "pas"}
                    elif "Prêt à Consommer" in cl:
                        current = {"name": "Prêt Conso", "type": "conso"}
                    if "Restant dû" in cl and current and ci + 1 < len(credit_lines):
                        nm = credit_lines[ci + 1].replace("\xa0", " ")
                        rm = re.match(r"^([\d\s]+,\d{2})\s*€$", nm)
                        if rm:
                            current["remaining"] = float(rm.group(1).replace(" ", "").replace(",", "."))
                            ca_data["credits"].append(current)
                            current = None
                    if current and "Echéance" in cl and ci + 1 < len(credit_lines):
                        nm = credit_lines[ci + 1].replace("\xa0", " ")
                        rm = re.match(r"^([\d\s]+,\d{2})\s*€$", nm)
                        if rm:
                            current["monthly"] = float(rm.group(1).replace(" ", "").replace(",", "."))
                    if current and "Montant emprunté" in cl and ci + 1 < len(credit_lines):
                        nm = credit_lines[ci + 1].replace("\xa0", " ")
                        rm = re.match(r"^([\d\s]+,\d{2})\s*€$", nm)
                        if rm:
                            current["borrowed"] = float(rm.group(1).replace(" ", "").replace(",", "."))
                    ci += 1
            except Exception as e:
                log(f"    ⚠️ CA credits: {e}")

            (DATA_DIR / f"credit_agricole_{TODAY}.json").write_text(
                json.dumps(ca_data, indent=2, ensure_ascii=False))
            log(f"    ✅ {len(ca_data['accounts'])} accounts, {len(ca_data['credits'])} credits")
            results["ca"] = ca_data
        except Exception as e:
            log(f"    ❌ CA scrape failed: {e}")

    return results


# ════════════════════════════════════════════════════════════════
# BUILD EXTRACTION + PATRIMOINE
# ════════════════════════════════════════════════════════════════

def build_extraction(scrape_results):
    """Build extraction_complete from scrape results, merging with previous data."""
    # Load previous extraction for ISINs and deep data
    prev = None
    for f in sorted(DATA_DIR.glob("extraction_complete_*.json"), reverse=True):
        try:
            prev = json.loads(f.read_text())
            break
        except Exception:
            continue

    prev_ibkr = {p["symbol"]: p for p in (prev or {}).get("ibkr_positions", [])}
    prev_tr = {p["name"]: p for p in (prev or {}).get("tr_positions", [])}

    # IBKR positions
    ibkr_data = scrape_results.get("ibkr", {})
    ibkr_positions = []
    for p in ibkr_data.get("positions", []):
        old = prev_ibkr.get(p["symbol"], {})
        ibkr_positions.append({
            "symbol": p["symbol"], "isin": old.get("isin", ""),
            "quantity": p["quantity"], "last_price_usd": p["last_price_usd"],
            "avg_price_usd": p["avg_price_usd"], "cost_basis_usd": p["cost_basis_eur"],
            "market_value_usd": p["market_value_eur"], "unrealized_pnl_usd": p["unrealized_pnl_eur"],
            "currency": "USD", "dividend": old.get("dividend"),
            "dividend_yield_pct": old.get("dividend_yield_pct"),
            "ex_dividend_date": old.get("ex_dividend_date"),
        })

    # TR positions
    tr_data = scrape_results.get("tr", {})
    tr_total = tr_data.get("portfolio_value", 0) or 1
    tr_positions = []
    for p in tr_data.get("positions", []):
        old = prev_tr.get(p["name"], {})
        val = p["value"]
        pct = p["return_pct"]
        perf = round(val * pct / (100 + pct), 2) if pct else 0
        tr_positions.append({
            "name": p["name"], "isin": old.get("isin", ""),
            "shares": p["shares"], "avg_price": old.get("avg_price"),
            "total_value": val, "performance_eur": perf, "performance_pct": pct,
            "portfolio_pct": round(val / tr_total * 100, 2),
            "pe_ratio": old.get("pe_ratio"), "beta": old.get("beta"),
        })

    summary = ibkr_data.get("summary", {})
    cash = ibkr_data.get("cash", {})
    extraction = {
        "tr_positions": tr_positions,
        "ibkr_positions": ibkr_positions,
        "ibkr_extras": {
            "net_liquidation_eur": summary.get("net_liquidity", 0),
            "buying_power_eur": summary.get("buying_power", 0),
            "unrealized_pnl_eur": summary.get("unrealized_pnl", 0),
            "total_cash_eur": cash.get("total_eur", 0),
            "cash_eur": cash.get("EUR", 0),
            "excess_liquidity": summary.get("excess_liquidity", 0),
            "maintenance_margin": 0,
        },
    }
    (DATA_DIR / f"extraction_complete_{TODAY}.json").write_text(json.dumps(extraction, indent=2))
    log(f"  ✅ extraction_complete: {len(ibkr_positions)} IBKR + {len(tr_positions)} TR")

    # Also create deep files from previous + updates
    for kind in ["bourso_deep", "ca_deep", "trade_republic_deep"]:
        prev_f = sorted(DATA_DIR.glob(f"{kind}_*.json"), reverse=True)
        if prev_f:
            new_f = DATA_DIR / f"{kind}_{TODAY}.json"
            if not new_f.exists():
                data = json.loads(prev_f[0].read_text())
                if "bourso" in kind and "bourso" in scrape_results:
                    for acc in data.get("accounts", []):
                        for na in scrape_results["bourso"].get("accounts", []):
                            if na["name"][:15] in acc.get("name", ""):
                                acc["balance"] = na["balance"]
                if "ca" in kind and "ca" in scrape_results:
                    data["accounts"] = scrape_results["ca"]["accounts"]
                    data["credits"] = scrape_results["ca"]["credits"]
                if "trade_republic" in kind and "tr" in scrape_results:
                    data["portfolio_value"] = tr_data.get("portfolio_value")
                new_f.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def rebuild_patrimoine():
    """Rebuild patrimoine_complet from latest data."""
    try:
        from build_patrimoine import build
        build(TODAY)
        log("  ✅ patrimoine_complet rebuilt")
    except Exception as e:
        log(f"  ❌ patrimoine rebuild failed: {e}")


def parse_transactions():
    """Re-parse all transaction data into DuckDB."""
    try:
        import parse_transactions
        parse_transactions.main()
        log("  ✅ transactions.duckdb updated")
    except Exception as e:
        log(f"  ❌ transaction parse failed: {e}")


# ════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════

async def main():
    skip_login = "--scrape" in sys.argv
    rebuild_only = "--rebuild" in sys.argv
    parse_only = "--parse" in sys.argv

    if rebuild_only:
        log(f"🔨 Rebuild only — {TODAY}")
        rebuild_patrimoine()
        return

    if parse_only:
        log(f"📊 Parse only — {TODAY}")
        parse_transactions()
        return

    log(f"🔄 Daily sync — {TODAY}")

    # Connect to Chrome
    try:
        from playwright.async_api import async_playwright
        pw = await async_playwright().start()
        browser = await pw.chromium.connect_over_cdp("http://127.0.0.1:18800")
        ctx = browser.contexts[0]
        log(f"📡 Chrome CDP connected — {len(ctx.pages)} tabs")
    except Exception as e:
        log(f"❌ Cannot connect to Chrome: {e}")
        return

    try:
        # Phase 1: Login
        if skip_login:
            log("⏭️  Skipping login (--scrape mode)")
            pages = {}
            for p in ctx.pages:
                u = p.url.lower()
                if "interactivebrokers" in u: pages["ibkr"] = p
                elif "bourso" in u: pages["bourso"] = p
                elif "traderepublic" in u: pages["tr"] = p
                elif "credit-agricole" in u: pages["ca"] = p
        else:
            log("\n🔑 Phase 1: Login")
            notify("Finary Sync", "Début du scraping quotidien — 2FA possible")
            pages = await login_all(ctx)

        # Phase 2: Scrape
        log(f"\n📊 Phase 2: Scrape ({len(pages)} banks)")
        scrape_results = await scrape_all(pages)

        # Phase 3: Build extraction + patrimoine
        log("\n🔨 Phase 3: Build")
        if scrape_results:
            build_extraction(scrape_results)
            rebuild_patrimoine()
        else:
            log("  ⚠️ No scrape results — skipping build")

        # Phase 4: Parse transactions
        log("\n📄 Phase 4: Parse transactions")
        parse_transactions()

        # Summary
        log(f"\n{'='*50}")
        log(f"✅ Daily sync complete — {datetime.now().strftime('%H:%M:%S')}")
        log(f"   Banks scraped: {list(scrape_results.keys())}")
        notify("Finary Sync ✅", f"Sync terminé — {len(scrape_results)} banques")

    finally:
        await browser.close()
        await pw.stop()

    # Save log
    (DATA_DIR / f"sync_log_{TODAY}.txt").write_text("\n".join(LOG))


if __name__ == "__main__":
    asyncio.run(main())
