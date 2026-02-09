"""Live scraping runner — connects to real bank accounts and dumps data.

Usage:
    cd scrapers && source .venv/bin/activate
    python run_scrape.py boursobank
    python run_scrape.py trade_republic
    python run_scrape.py ibkr
    python run_scrape.py credit_agricole
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        if isinstance(o, (date, datetime)):
            return o.isoformat()
        return super().default(o)


async def scrape_boursobank():
    """Scrape Boursobank using Playwright with real selectors."""
    from playwright.async_api import async_playwright

    username = os.environ["BOURSO_USERNAME"]
    password = os.environ["BOURSO_PASSWORD"]

    print(f"[boursobank] Connecting as {username[:4]}****...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # headless=False for debugging
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
        )
        page = await ctx.new_page()

        # Disable WebAuthn/passkey so Boursobank falls back to virtual keyboard
        await page.add_init_script("""
            // Completely remove WebAuthn support so the page never attempts it
            delete window.PublicKeyCredential;
            Object.defineProperty(navigator, 'credentials', {
                get: () => undefined,
                configurable: true
            });
        """)

        # Step 1: Go to login page
        print("[boursobank] Loading login page (60s timeout)...")
        page.set_default_timeout(90000)
        try:
            await page.goto("https://clients.boursobank.com/connexion/", timeout=90000)
        except Exception as e:
            print(f"[boursobank] Page load issue: {e}")
            print("[boursobank] Continuing anyway...")
        await page.wait_for_timeout(5000)

        # Dismiss cookie consent if present
        for cookie_sel in [
            'button:has-text("Tout accepter")',
            'a:has-text("Continuer sans accepter")',
            'button:has-text("Accepter")',
        ]:
            try:
                btn = await page.query_selector(cookie_sel)
                if btn:
                    await btn.click()
                    print(f"[boursobank] Dismissed cookie banner via {cookie_sel}")
                    await page.wait_for_timeout(2000)
                    break
            except Exception:
                continue

        # Take screenshot for debugging
        await page.screenshot(path="/tmp/bourso_01_login.png")
        print("[boursobank] Screenshot saved: /tmp/bourso_01_login.png")

        # Step 2: Enter username
        print("[boursobank] Entering username...")
        # Boursobank login form — try multiple selectors
        username_sel = (
            'input[name="login"]',
            'input#customer-number',
            'input[placeholder*="client"]',
            'input[type="text"]',
        )
        filled = False
        for sel in username_sel:
            try:
                el = await page.wait_for_selector(sel, timeout=3000)
                if el:
                    await el.fill(username)
                    filled = True
                    print(f"[boursobank] Username entered via {sel}")
                    break
            except Exception:
                continue

        if not filled:
            html = await page.content()
            Path("/tmp/bourso_login.html").write_text(html)
            print("[boursobank] ERROR: Could not find username field. HTML saved to /tmp/bourso_login.html")
            await browser.close()
            return

        await page.wait_for_timeout(500)

        # Step 3: Click "Suivant" to go to password page
        print("[boursobank] Clicking 'Suivant'...")
        suivant_sels = [
            'button:has-text("Suivant")',
            'a:has-text("Suivant")',
            'button[type="submit"]',
        ]
        clicked_suivant = False
        for sel in suivant_sels:
            try:
                btn = await page.query_selector(sel)
                if btn and await btn.is_visible():
                    await btn.click()
                    clicked_suivant = True
                    print(f"[boursobank] Clicked via {sel}")
                    break
            except Exception:
                continue

        if not clicked_suivant:
            # Maybe form auto-submits or there's no Suivant — try submit
            try:
                await page.press('input[type="text"]', 'Enter')
                print("[boursobank] Pressed Enter on username field")
            except Exception:
                pass

        # Wait for next page to load
        await page.wait_for_timeout(5000)

        # Check if WebAuthn/passkey page appeared instead of virtual keyboard
        webauthn_el = await page.query_selector('[data-login-step-webauthn]')
        if webauthn_el and await webauthn_el.is_visible():
            print("[boursobank] WebAuthn/passkey page detected — forcing password view...")
            # Cancel WebAuthn and swap to password view via DOM + load keyboard
            await page.evaluate("""async () => {
                // 1. Cancel WebAuthn via API
                try { await fetch('/webauthn/connexion/cancel', { method: 'POST' }); } catch(e) {}

                // 2. Hide the WebAuthn active view
                const activeViews = document.querySelectorAll('[data-transition-view-active]');
                activeViews.forEach(v => {
                    if (v.querySelector('[data-login-step-webauthn]')) {
                        v.style.display = 'none';
                    }
                });
                // 3. Show the password view
                const pwStorage = document.querySelector('[data-login-login-view-storage]');
                if (pwStorage) {
                    pwStorage.classList.remove('hidden');
                    pwStorage.style.display = 'block';
                }

                // 4. Load the virtual keyboard via hx:include
                const hxEl = document.querySelector('hx\\\\:include, [src*="clavier-virtuel"]');
                if (hxEl) {
                    try {
                        const resp = await fetch('/connexion/clavier-virtuel');
                        const html = await resp.text();
                        hxEl.outerHTML = html;
                    } catch(e) { console.error('keyboard load failed', e); }
                }
            }""")
            await page.wait_for_timeout(3000)

        await page.screenshot(path="/tmp/bourso_02_password_page.png")
        print("[boursobank] Screenshot saved: /tmp/bourso_02_password_page.png")

        # Dump HTML to understand keyboard structure
        html = await page.content()
        Path("/tmp/bourso_password_page.html").write_text(html)
        print("[boursobank] Password page HTML saved to /tmp/bourso_password_page.html")

        # Step 4: Handle virtual keyboard for password
        print("[boursobank] Entering password via virtual keyboard...")

        # Boursobank renders digits as SVG images inside buttons with class "sasmap__key".
        # The buttons have random data-matrix-key values and no text — only SVG images.
        # We identify each digit by the MD5 hash of the base64 SVG source.
        import base64 as b64mod
        import hashlib

        # Stable mapping: MD5(base64_svg) → digit
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

        # Build runtime mapping: digit → button element
        # The keyboard is loaded via hx:include (AJAX), wait for it
        digit_buttons: dict = {}
        for attempt in range(10):
            buttons = await page.query_selector_all("button.sasmap__key")
            if len(buttons) >= 10:
                break
            print(f"[boursobank] Waiting for keyboard to load... ({len(buttons)} buttons found)")
            await page.wait_for_timeout(2000)

        buttons = await page.query_selector_all("button.sasmap__key")
        for btn in buttons:
            img = await btn.query_selector("img.sasmap__img")
            if not img:
                continue
            src = await img.get_attribute("src")
            if not src or "base64" not in src:
                continue
            b64_data = src.split("base64,")[1].strip()
            h = hashlib.md5(b64_data.encode()).hexdigest()
            digit = SVG_TO_DIGIT.get(h)
            if digit is not None:
                digit_buttons[digit] = btn

        print(f"[boursobank] Identified {len(digit_buttons)} keyboard digits: {sorted(digit_buttons.keys())}")

        for digit in password:
            btn = digit_buttons.get(digit)
            if btn:
                await btn.click()
                print(f"[boursobank] Clicked digit {digit}")
            else:
                print(f"[boursobank] WARNING: Could not find button for digit {digit}")
            await page.wait_for_timeout(200)

        await page.screenshot(path="/tmp/bourso_03_after_password.png")

        # Step 5: Submit password
        print("[boursobank] Submitting login...")
        submit_sels = [
            'button:has-text("Je me connecte")',
            'button:has-text("Se connecter")',
            'button:has-text("Connexion")',
            'button:has-text("Valider")',
            'button:has-text("Suivant")',
            'button[type="submit"]',
            'input[type="submit"]',
        ]
        submitted = False
        for sel in submit_sels:
            try:
                btn = await page.query_selector(sel)
                if btn:
                    await btn.click()
                    submitted = True
                    print(f"[boursobank] Submitted via {sel}")
                    break
            except Exception:
                continue

        if not submitted:
            print("[boursobank] WARNING: Could not find submit button")

        # Wait for navigation
        await page.wait_for_timeout(5000)
        await page.screenshot(path="/tmp/bourso_04_after_login.png")

        current_url = page.url
        print(f"[boursobank] Current URL: {current_url}")

        # Check for REAL OTP (not just footer text containing "sécurité")
        otp_detected = False
        for otp_sel in ['[data-otp]', 'input[name*="otp"]', 'input[name*="code"]', '#code-sms']:
            el = await page.query_selector(otp_sel)
            if el and await el.is_visible():
                otp_detected = True
                break
        if not otp_detected:
            # Also check for specific OTP page text
            try:
                body_text = await page.inner_text("body")
                if "code sms" in body_text.lower() or "authentification forte" in body_text.lower():
                    otp_detected = True
            except Exception:
                pass

        if otp_detected:
            print("[boursobank] OTP/SCA required! Check your phone and enter code manually.")
            print("[boursobank] Waiting 60 seconds for manual OTP entry...")
            await page.wait_for_timeout(60000)
            current_url = page.url

        # Step 6: We should be on the homepage — wait for content to load
        print("[boursobank] Waiting for dashboard content to load...")
        await page.wait_for_timeout(8000)  # Let skeleton loading finish
        await page.screenshot(path="/tmp/bourso_06_dashboard.png")
        print("[boursobank] Screenshot saved: /tmp/bourso_06_dashboard.png")

        # Step 7: Extract account data from homepage
        print("[boursobank] Extracting accounts...")
        html = await page.content()
        Path("/tmp/bourso_dashboard.html").write_text(html)

        body_text = await page.inner_text("body")
        Path("/tmp/bourso_body_text.txt").write_text(body_text)
        print("[boursobank] Dashboard text saved to /tmp/bourso_body_text.txt")

        # Step 8: Navigate to accounts page (via click, not URL, to keep session)
        print("[boursobank] Navigating to accounts page...")
        try:
            await page.click('a:has-text("Mes comptes")')
            await page.wait_for_timeout(5000)
        except Exception:
            await page.goto("https://clients.boursobank.com/compte/", wait_until="domcontentloaded")
            await page.wait_for_timeout(5000)
        await page.screenshot(path="/tmp/bourso_07_accounts.png")
        accounts_text = await page.inner_text("body")
        Path("/tmp/bourso_accounts_text.txt").write_text(accounts_text)
        print("[boursobank] Accounts text saved to /tmp/bourso_accounts_text.txt")

        # Step 9: Get PEA portfolio (click from sidebar)
        print("[boursobank] Checking for PEA portfolio...")
        try:
            pea_link = await page.query_selector('a:has-text("PEA")')
            if pea_link:
                await pea_link.click()
                await page.wait_for_timeout(5000)
                await page.screenshot(path="/tmp/bourso_08_portfolio.png")
                portfolio_text = await page.inner_text("body")
                Path("/tmp/bourso_portfolio_text.txt").write_text(portfolio_text)
                print("[boursobank] Portfolio text saved to /tmp/bourso_portfolio_text.txt")
            else:
                print("[boursobank] No PEA link found in sidebar")
        except Exception as e:
            print(f"[boursobank] Portfolio error: {e}")

        # Step 10: Get recent transactions (go back to main account, scroll down)
        print("[boursobank] Fetching transactions from account page...")
        try:
            await page.click('a:has-text("BOURSORAMA ESSENTIEL SYLV")')
            await page.wait_for_timeout(5000)
            await page.screenshot(path="/tmp/bourso_09_transactions.png")
            tx_text = await page.inner_text("body")
            Path("/tmp/bourso_transactions_text.txt").write_text(tx_text)
            print("[boursobank] Transactions text saved to /tmp/bourso_transactions_text.txt")
        except Exception as e:
            print(f"[boursobank] Transactions error: {e}")

        # Keep browser open for manual inspection
        print("\n[boursobank] DONE. Screenshots and data saved to /tmp/bourso_*")
        print("[boursobank] Keeping browser open 30s for inspection...")
        await page.wait_for_timeout(30000)

        await browser.close()


async def scrape_trade_republic():
    """Scrape Trade Republic using pytr WebSocket API."""
    from pytr.api import TradeRepublicApi

    phone = os.environ["TR_PHONE"]
    pin = os.environ["TR_PIN"]

    print(f"[trade_republic] Connecting as {phone[:6]}****...")

    tr = TradeRepublicApi(phone_no=phone, pin=pin, locale="fr")

    # Login triggers 2FA — user must confirm on phone
    print("[trade_republic] Logging in (check your phone for 2FA confirmation)...")
    tr.login()
    print("[trade_republic] Initiating web login...")
    countdown = tr.initiate_weblogin()
    print(f"[trade_republic] 2FA sent — confirm on your phone within {countdown}s")

    # Wait for confirmation
    import time
    for i in range(countdown, 0, -5):
        print(f"[trade_republic] Waiting for 2FA... {i}s remaining")
        time.sleep(5)
        try:
            tr.complete_weblogin()
            print("[trade_republic] 2FA confirmed!")
            break
        except Exception:
            continue
    else:
        print("[trade_republic] ERROR: 2FA timeout")
        return

    data = {"scraped_at": datetime.now().isoformat(), "source": "trade_republic"}

    # Get portfolio
    print("[trade_republic] Fetching portfolio...")
    try:
        portfolio = await asyncio.to_thread(tr.portfolio)
        data["portfolio"] = portfolio
        print(f"[trade_republic] Portfolio: {json.dumps(portfolio, cls=DecimalEncoder, indent=2)[:500]}")
    except Exception as e:
        print(f"[trade_republic] Portfolio error: {e}")

    # Get cash
    print("[trade_republic] Fetching cash balance...")
    try:
        cash = await asyncio.to_thread(tr.cash)
        data["cash"] = cash
        print(f"[trade_republic] Cash: {cash}")
    except Exception as e:
        print(f"[trade_republic] Cash error: {e}")

    # Get compact portfolio
    print("[trade_republic] Fetching compact portfolio...")
    try:
        compact = await asyncio.to_thread(tr.compact_portfolio)
        data["compact_portfolio"] = compact
        print(f"[trade_republic] Compact: {json.dumps(compact, cls=DecimalEncoder, indent=2)[:500]}")
    except Exception as e:
        print(f"[trade_republic] Compact portfolio error: {e}")

    # Get timeline (recent transactions)
    print("[trade_republic] Fetching timeline...")
    try:
        timeline = await asyncio.to_thread(tr.timeline_transactions)
        data["timeline"] = timeline
        print(f"[trade_republic] Timeline entries: {len(timeline) if isinstance(timeline, list) else 'N/A'}")
    except Exception as e:
        print(f"[trade_republic] Timeline error: {e}")

    # Get performance history
    print("[trade_republic] Fetching performance history...")
    try:
        perf = await asyncio.to_thread(tr.performance)
        data["performance"] = perf
        print(f"[trade_republic] Performance: {json.dumps(perf, cls=DecimalEncoder, indent=2)[:300]}")
    except Exception as e:
        print(f"[trade_republic] Performance error: {e}")

    # Save data
    out_path = Path("data") / f"trade_republic_{date.today().isoformat()}.json"
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(json.dumps(data, cls=DecimalEncoder, indent=2, ensure_ascii=False))
    print(f"\n[trade_republic] DONE. Data saved to {out_path}")


async def scrape_ibkr():
    """Scrape IBKR via Client Portal web login with Playwright."""
    from playwright.async_api import async_playwright

    username = os.environ["IBKR_USERNAME"]
    password = os.environ["IBKR_PASSWORD"]

    print(f"[ibkr] Connecting as {username}...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            viewport={"width": 1280, "height": 800},
        )
        page = await ctx.new_page()
        page.set_default_timeout(60000)

        # Step 1: Go to IBKR Client Portal login
        print("[ibkr] Loading login page...")
        await page.goto("https://www.interactivebrokers.com/sso/Login", wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)

        # Dismiss cookie banner if present
        for sel in ['button:has-text("Accept Cookies")', 'button:has-text("Reject All")', '#acceptCookies']:
            try:
                btn = await page.query_selector(sel)
                if btn and await btn.is_visible():
                    await btn.click()
                    print(f"[ibkr] Dismissed cookie banner via {sel}")
                    await page.wait_for_timeout(1000)
                    break
            except Exception:
                continue

        await page.screenshot(path="/tmp/ibkr_01_login.png")
        print("[ibkr] Screenshot saved: /tmp/ibkr_01_login.png")

        # Step 2: Enter credentials
        print("[ibkr] Entering credentials...")
        try:
            await page.fill('input[name="username"]', username)
            print("[ibkr] Username entered")
        except Exception:
            pass
        try:
            await page.fill('input[name="password"]', password)
            print("[ibkr] Password entered")
        except Exception:
            pass

        # Step 3: Submit login
        print("[ibkr] Submitting login...")
        submit_sels = ['button[type="submit"]', '#submitForm', 'button:has-text("Log In")', 'input[type="submit"]']
        for sel in submit_sels:
            try:
                btn = await page.query_selector(sel)
                if btn and await btn.is_visible():
                    await btn.click()
                    print(f"[ibkr] Submitted via {sel}")
                    break
            except Exception:
                continue

        await page.wait_for_timeout(5000)
        await page.screenshot(path="/tmp/ibkr_02_after_login.png")
        current_url = page.url
        print(f"[ibkr] Current URL: {current_url}")

        # Step 4: Handle 2FA (IBKR uses IB Key mobile app or SMS)
        body_text = await page.inner_text("body")
        if any(kw in body_text.lower() for kw in ("two factor", "second factor", "ib key", "security code", "authentication")):
            print("[ibkr] 2FA required! Check your IB Key app or phone.")
            print("[ibkr] Waiting 120 seconds for manual 2FA...")
            for i in range(24):
                await page.wait_for_timeout(5000)
                new_url = page.url
                if new_url != current_url:
                    print(f"[ibkr] Navigation detected: {new_url}")
                    break
            await page.screenshot(path="/tmp/ibkr_03_after_2fa.png")

        # Step 5: Navigate to portfolio/account pages
        await page.wait_for_timeout(3000)
        current_url = page.url
        print(f"[ibkr] Post-auth URL: {current_url}")

        # Dismiss any FYI notification modal
        try:
            close_btn = await page.query_selector('button:has-text("Close")')
            if close_btn and await close_btn.is_visible():
                await close_btn.click()
                print("[ibkr] Dismissed FYI notification")
                await page.wait_for_timeout(1000)
        except Exception:
            pass

        data = {"scraped_at": datetime.now().isoformat(), "source": "ibkr", "user": username}

        # Save homepage content (this is the SPA dashboard with all key data)
        body_text = await page.inner_text("body")
        Path("/tmp/ibkr_body_text.txt").write_text(body_text)
        await page.screenshot(path="/tmp/ibkr_04_home.png")
        print("[ibkr] Home page text saved to /tmp/ibkr_body_text.txt")

        # Parse key values from dashboard text
        import re as _re
        for line in body_text.split("\n"):
            line = line.strip()
            if not line:
                continue
            # Match "Label  Value" patterns
            for key in ["Cash", "Unrealized P&L", "Realized P&L", "Maintenance Margin",
                        "Excess Liquidity", "Buying Power", "Dividends"]:
                if line.startswith(key):
                    val = line[len(key):].strip().replace(",", "")
                    try:
                        data[key.lower().replace(" ", "_").replace("&", "and")] = float(val)
                    except ValueError:
                        data[key.lower().replace(" ", "_").replace("&", "and")] = val

        # Navigate to Portfolio page within the SPA
        print("[ibkr] Clicking Portfolio tab...")
        try:
            portfolio_link = await page.query_selector('a:has-text("Portfolio"), [href*="portfolio"]')
            if portfolio_link:
                await portfolio_link.click()
                await page.wait_for_timeout(5000)
                await page.screenshot(path="/tmp/ibkr_05_portfolio.png")
                portfolio_text = await page.inner_text("body")
                Path("/tmp/ibkr_portfolio_text.txt").write_text(portfolio_text)
                print("[ibkr] Portfolio page text saved")
        except Exception as e:
            print(f"[ibkr] Portfolio tab error: {e}")

        # Save all collected data
        out_path = Path("data") / f"ibkr_{date.today().isoformat()}.json"
        out_path.parent.mkdir(exist_ok=True)
        out_path.write_text(json.dumps(data, cls=DecimalEncoder, indent=2, ensure_ascii=False))
        print(f"\n[ibkr] DONE. Screenshots/data saved to /tmp/ibkr_*")
        print("[ibkr] Keeping browser open 30s for inspection...")
        await page.wait_for_timeout(30000)
        await browser.close()


async def scrape_credit_agricole():
    """Scrape Crédit Agricole Languedoc via Playwright."""
    from playwright.async_api import async_playwright

    username = os.environ["CA_USERNAME"]
    pin = os.environ["CA_PIN"]
    region = os.environ.get("CA_REGION", "languedoc")

    # CA regional bank URLs
    CA_URLS = {
        "languedoc": "https://www.ca-languedoc.fr",
        "centre-loire": "https://www.ca-centreloire.fr",
        "sud-med": "https://www.ca-sudmed.fr",
        "toulouse": "https://www.ca-toulouse31.fr",
        "normandie": "https://www.ca-normandie.fr",
    }
    base_url = CA_URLS.get(region, f"https://www.ca-{region}.fr")

    print(f"[credit_agricole] Connecting to {region} as {username[:4]}****...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            viewport={"width": 1280, "height": 800},
        )
        page = await ctx.new_page()
        page.set_default_timeout(60000)

        # Step 1: Go to CA homepage and click "Me connecter"
        print(f"[credit_agricole] Loading {base_url}...")
        await page.goto(base_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)

        # Dismiss cookie banner
        for sel in ['button:has-text("Tout accepter")', 'button:has-text("Accepter")',
                    '#onetrust-accept-btn-handler', '.cookie-consent-accept']:
            try:
                btn = await page.query_selector(sel)
                if btn and await btn.is_visible():
                    await btn.click()
                    print(f"[credit_agricole] Dismissed cookies via {sel}")
                    await page.wait_for_timeout(1000)
                    break
            except Exception:
                continue

        # Click "Me connecter"
        print("[credit_agricole] Clicking 'Me connecter'...")
        try:
            connect_btn = await page.query_selector('a:has-text("Me connecter"), button:has-text("Me connecter")')
            if connect_btn:
                await connect_btn.click()
                await page.wait_for_timeout(3000)
                print("[credit_agricole] Clicked 'Me connecter'")
            else:
                # Try direct login URL
                await page.goto(f"{base_url}/particulier/operations/operations-courantes/mon-espace-client.html", wait_until="domcontentloaded")
                await page.wait_for_timeout(3000)
        except Exception:
            pass

        await page.screenshot(path="/tmp/ca_01_login.png")
        print("[credit_agricole] Screenshot saved: /tmp/ca_01_login.png")
        html = await page.content()
        Path("/tmp/ca_login.html").write_text(html)

        # Step 2: Enter account number
        print("[credit_agricole] Entering account number...")
        account_sels = [
            '#Login-account_number', 'input[name="CCPTE"]', 'input[name="account"]',
            'input[type="text"]', '#inputCompte',
        ]
        filled = False
        for sel in account_sels:
            try:
                el = await page.query_selector(sel)
                if el and await el.is_visible():
                    await el.fill(username)
                    filled = True
                    print(f"[credit_agricole] Account entered via {sel}")
                    break
            except Exception:
                continue

        if not filled:
            html = await page.content()
            Path("/tmp/ca_login.html").write_text(html)
            print("[credit_agricole] ERROR: Could not find account field. HTML saved.")
            await browser.close()
            return

        await page.wait_for_timeout(1000)

        # Step 3: Click "ENTRER MON CODE PERSONNEL" to show the keyboard
        print("[credit_agricole] Clicking 'Entrer mon code personnel'...")
        code_sels = [
            'button:has-text("ENTRER MON CODE PERSONNEL")',
            'button:has-text("Entrer mon code")',
            'a:has-text("ENTRER MON CODE")',
            'button[type="submit"]',
        ]
        for sel in code_sels:
            try:
                btn = await page.query_selector(sel)
                if btn and await btn.is_visible():
                    await btn.click()
                    print(f"[credit_agricole] Clicked via {sel}")
                    break
            except Exception:
                continue

        await page.wait_for_timeout(3000)
        await page.screenshot(path="/tmp/ca_02_keyboard.png")
        print("[credit_agricole] Screenshot saved: /tmp/ca_02_keyboard.png")
        html = await page.content()
        Path("/tmp/ca_keyboard.html").write_text(html)

        # Step 4: Handle virtual keyboard for PIN

        # CA keyboard buttons often use data-value or aria-label attributes
        for digit in pin:
            clicked = False
            selectors = [
                f'button[data-value="{digit}"]',
                f'a[data-value="{digit}"]',
                f'div[data-value="{digit}"]',
                f'button[aria-label="{digit}"]',
                f'[data-matrix-key] img[alt="{digit}"]',
            ]
            for sel in selectors:
                try:
                    btn = await page.query_selector(sel)
                    if btn:
                        await btn.click()
                        clicked = True
                        print(f"[credit_agricole] Clicked digit {digit} via {sel}")
                        break
                except Exception:
                    continue

            if not clicked:
                # Brute force: find clickable elements with matching text
                for tag in ['button', 'a', 'div', 'span', 'li', 'td']:
                    elements = await page.query_selector_all(f'{tag}[class*="wd-key"], {tag}[class*="Key"], {tag}[class*="btn-key"]')
                    if not elements:
                        elements = await page.query_selector_all(tag)
                    for el in elements:
                        try:
                            text = (await el.inner_text()).strip()
                            if text == digit:
                                box = await el.bounding_box()
                                if box and box['width'] > 10 and box['height'] > 10:
                                    await el.click()
                                    clicked = True
                                    print(f"[credit_agricole] Clicked digit {digit} via <{tag}> brute force")
                                    break
                        except Exception:
                            continue
                    if clicked:
                        break

            if not clicked:
                print(f"[credit_agricole] WARNING: Could not click digit {digit}")

            await page.wait_for_timeout(300)

        await page.screenshot(path="/tmp/ca_03_after_pin.png")

        # Step 4: Submit login
        print("[credit_agricole] Submitting login...")
        submit_sels = [
            'button:has-text("Valider")', 'button:has-text("OK")',
            'button[type="submit"]', '#validation', '.btn-submit',
        ]
        for sel in submit_sels:
            try:
                btn = await page.query_selector(sel)
                if btn and await btn.is_visible():
                    await btn.click()
                    print(f"[credit_agricole] Submitted via {sel}")
                    break
            except Exception:
                continue

        await page.wait_for_timeout(5000)
        await page.screenshot(path="/tmp/ca_04_after_login.png")
        current_url = page.url
        print(f"[credit_agricole] Current URL: {current_url}")

        # Step 5: Extract dashboard data
        body_text = await page.inner_text("body")
        Path("/tmp/ca_body_text.txt").write_text(body_text)
        print("[credit_agricole] Dashboard text saved to /tmp/ca_body_text.txt")

        # Parse main account balance from dashboard
        import re as _re
        balance_match = _re.search(r'([\d\s]+,\d{2})\s*€', body_text.replace('\xa0', ' '))
        main_balance = balance_match.group(1).strip() if balance_match else "unknown"
        print(f"[credit_agricole] Main account balance: {main_balance} €")

        # Parse recent transactions from dashboard
        transactions = []
        tx_pattern = _re.compile(r'(\d{2}/\d{2})\n.*?\n(.+?)\n([-\d\s]+,\d{2}\s*€)')
        for m in tx_pattern.finditer(body_text):
            transactions.append({
                "date": m.group(1),
                "label": m.group(2).strip(),
                "amount": m.group(3).strip(),
            })

        # Step 6: Expand "Mes crédits" and extract credit details
        print("[credit_agricole] Expanding credits...")
        credits_data = []
        try:
            credits_btn = await page.query_selector('text="Afficher mes crédits"')
            if credits_btn:
                await credits_btn.click()
                await page.wait_for_timeout(3000)
                await page.screenshot(path="/tmp/ca_05_credits.png")
                print("[credit_agricole] Credits expanded")

                # Scroll down to see all credits
                await page.evaluate("window.scrollBy(0, 500)")
                await page.wait_for_timeout(1000)
                await page.screenshot(path="/tmp/ca_05b_credits_scroll.png")

                # Extract credit details from the expanded section
                expanded_text = await page.inner_text("body")
                Path("/tmp/ca_credits_expanded.txt").write_text(expanded_text)

                # Parse credits: look for loan blocks by pattern
                import re as _re2
                lines = expanded_text.split('\n')
                current_credit = {}
                expect_field = None
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    # Loan name lines (actual loan names, not transaction/nav text)
                    if ('Prêt' in line or 'prêt' in line) and 'Simulateur' not in line and 'REMBOURSEMENT' not in line and 'immobilier en ligne' not in line:
                        if current_credit and 'name' in current_credit:
                            credits_data.append(current_credit)
                        current_credit = {"name": line}
                        expect_field = None
                    # Account number (11 digits)
                    elif _re2.match(r'^\d{11}$', line) and current_credit:
                        current_credit["account_number"] = line
                    # Field labels
                    elif 'Echéance' in line or 'Échéance' in line:
                        expect_field = "monthly_payment"
                    elif 'Montant emprunté' in line:
                        expect_field = "borrowed"
                    elif 'Restant dû' in line:
                        expect_field = "remaining"
                    # Amount value
                    elif _re2.match(r'^[\d\s\xa0]+,\d{2}\s*\xa0?\s*€$', line) and current_credit and expect_field:
                        current_credit[expect_field] = line.replace('\xa0', ' ').strip()
                        expect_field = None
                if current_credit and 'name' in current_credit:
                    credits_data.append(current_credit)
                print(f"[credit_agricole] Found {len(credits_data)} credits")
        except Exception as e:
            print(f"[credit_agricole] Credits expand error: {e}")

        # Step 7: Navigate to Comptes & Cartes for full account list
        print("[credit_agricole] Navigating to Comptes & Cartes...")
        accounts_data_extra = []
        try:
            # Use the top nav bar
            nav_link = await page.query_selector('nav a[href*="comptes"], a:has-text("Comptes")')
            if not nav_link:
                nav_link = await page.query_selector('a:has-text("Comptes & Cartes")')
            if nav_link:
                await nav_link.click(timeout=10000)
                await page.wait_for_timeout(5000)
                await page.screenshot(path="/tmp/ca_06_comptes.png")
                accounts_text = await page.inner_text("body")
                Path("/tmp/ca_accounts_text.txt").write_text(accounts_text)
                print("[credit_agricole] Comptes & Cartes page loaded")
        except Exception as e:
            print(f"[credit_agricole] Comptes & Cartes nav error: {e}")

        # Save structured data
        out_path = Path("data") / f"credit_agricole_{date.today().isoformat()}.json"
        out_path.parent.mkdir(exist_ok=True)
        data = {
            "scraped_at": datetime.now().isoformat(),
            "source": "credit_agricole",
            "region": region,
            "owner": "SYLVAIN LEGLAND",
            "accounts": [
                {
                    "name": "Compte Principal",
                    "type": "checking",
                    "balance": main_balance,
                    "currency": "EUR",
                }
            ],
            "credits": credits_data if credits_data else [],
            "savings": "Aucune épargne",
            "insurance": "Aucune assurance",
            "recent_transactions": transactions,
            "raw_dashboard": body_text[:3000],
        }
        out_path.write_text(json.dumps(data, cls=DecimalEncoder, indent=2, ensure_ascii=False))
        print(f"[credit_agricole] Data saved to {out_path}")

        print(f"\n[credit_agricole] DONE. Screenshots/data saved to /tmp/ca_*")
        print("[credit_agricole] Keeping browser open 15s for inspection...")
        await page.wait_for_timeout(15000)
        await browser.close()


async def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "boursobank"

    if target == "boursobank":
        await scrape_boursobank()
    elif target == "trade_republic":
        await scrape_trade_republic()
    elif target == "ibkr":
        await scrape_ibkr()
    elif target == "credit_agricole":
        await scrape_credit_agricole()
    else:
        print(f"Unknown target: {target}")
        print("Usage: python run_scrape.py [boursobank|trade_republic|ibkr|credit_agricole]")


if __name__ == "__main__":
    asyncio.run(main())
