"""
Scrape real loan details (rates, insurance, dates, amortization) from bank sites.
Requires active CDP sessions on port 9222.

Usage:
    python3 scrapers/scrape_loan_details.py

Outputs:
    scrapers/data/loan_details_YYYY-MM-DD.json
"""
import asyncio
import json
import re
from datetime import date
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"


async def scrape_ca_loan_details(page) -> dict:
    """Navigate to CA credits detail page and extract rates/insurance/dates."""
    result = {"bank": "credit_agricole", "loans": []}

    # Go to credits overview
    await page.goto(
        "https://www.credit-agricole.fr/ca-languedoc/particulier/operations/credits.html"
    )
    await page.wait_for_timeout(5000)
    text = await page.inner_text("body")

    if "connexion" in text.lower()[:300] or len(text) < 200:
        print("  ⚠ CA session expired — need re-login")
        result["error"] = "session_expired"
        return result

    print(f"  CA Credits page: {len(text)} chars")

    # Extract rates from main page text
    patterns = {
        "taux_nominal": r"Taux\s*(?:nominal|fixe|variable)?[^\d]*(\d+[.,]\d+)\s*%",
        "taeg": r"TAEG[^\d]*(\d+[.,]\d+)\s*%",
        "teg": r"TEG[^\d]*(\d+[.,]\d+)\s*%",
        "assurance": r"[Aa]ssurance[^\d]*([\d.,]+)\s*€",
        "duree": r"[Dd]ur[ée]e[^\d]*(\d+)\s*(mois|ans)",
        "date_debut": r"[Dd]ate\s*(?:de\s*)?(?:d[ée]but|souscription)[^\d]*(\d{2}/\d{2}/\d{4})",
        "echeance": r"[ÉéEe]ch[ée]ance[^\d]*([\d.,]+)\s*€",
        "capital_restant": r"[Cc]apital\s*restant[^\d]*([\d\s.,]+)\s*€",
    }

    for key, pattern in patterns.items():
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            result[f"global_{key}"] = matches
            print(f"    {key}: {matches}")

    # Try to click on each credit link for detail view
    credit_links = page.locator('a[href*="credit"]')
    count = await credit_links.count()
    print(f"  Found {count} credit links")

    for i in range(min(count, 10)):
        try:
            href = await credit_links.nth(i).get_attribute("href")
            link_text = (await credit_links.nth(i).inner_text()).strip()
            if not link_text or len(link_text) > 100:
                continue
            print(f"    Link {i}: {link_text[:50]} → {href}")
        except Exception:
            continue

    # Try the amortization table
    try:
        amort_url = "https://www.credit-agricole.fr/ca-languedoc/particulier/operations/credits/tableau-amortissement.html"
        await page.goto(amort_url)
        await page.wait_for_timeout(4000)
        amort_text = await page.inner_text("body")
        if len(amort_text) > 300 and "connexion" not in amort_text.lower()[:200]:
            result["amortisation_raw"] = amort_text[:10000]
            print(f"  Amortization table: {len(amort_text)} chars")

            # Extract rate from amortization table
            for key, pattern in patterns.items():
                matches = re.findall(pattern, amort_text, re.IGNORECASE)
                if matches:
                    result[f"amort_{key}"] = matches
                    print(f"    amort_{key}: {matches}")
    except Exception as e:
        print(f"  ⚠ Amortization: {e}")

    return result


async def scrape_bourso_loan_details(page) -> dict:
    """Navigate to Boursobank loan detail pages."""
    result = {"bank": "boursobank", "loans": []}

    # Try credit overview
    for url in [
        "https://clients.boursobank.com/patrimoine/credit/",
        "https://clients.boursobank.com/credit/",
    ]:
        await page.goto(url)
        await page.wait_for_timeout(4000)
        text = await page.inner_text("body")
        if "n'existe plus" not in text and "connecter" not in text.lower()[:300] and len(text) > 300:
            result["credit_overview"] = text[:5000]
            print(f"  Bourso credits: {len(text)} chars from {url}")
            break
    else:
        # Try patrimoine page which has "Voir détails" links
        await page.goto("https://clients.boursobank.com/patrimoine/immobilier/")
        await page.wait_for_timeout(4000)
        text = await page.inner_text("body")
        if "connecter" in text.lower()[:300]:
            print("  ⚠ Bourso session expired — need re-login")
            result["error"] = "session_expired"
            return result

    # Click "Voir détails" links for each credit
    detail_links = page.locator('a:has-text("Voir détails")')
    count = await detail_links.count()
    print(f"  Found {count} 'Voir détails' links")

    for i in range(count):
        try:
            href = await detail_links.nth(i).get_attribute("href")
            print(f"    Detail link {i}: {href}")
            await detail_links.nth(i).click()
            await page.wait_for_timeout(3000)
            detail_text = await page.inner_text("body")

            loan_detail = {"href": href, "raw": detail_text[:5000]}

            # Extract structured data
            for key, pattern in [
                ("taux", r"[Tt]aux[^\d]*(\d+[.,]\d+)\s*%"),
                ("taeg", r"TAEG[^\d]*(\d+[.,]\d+)\s*%"),
                ("mensualite", r"[Mm]ensualit[ée][^\d]*([\d\s.,]+)\s*€"),
                ("assurance", r"[Aa]ssurance[^\d]*([\d.,]+)\s*€"),
                ("duree", r"[Dd]ur[ée]e[^\d]*(\d+)\s*(mois|ans)"),
                ("date_debut", r"(\d{2}/\d{2}/\d{4})"),
                ("capital_initial", r"[Cc]apital\s*(?:initial|emprunt[ée])[^\d]*([\d\s.,]+)\s*€"),
            ]:
                matches = re.findall(pattern, detail_text, re.IGNORECASE)
                if matches:
                    loan_detail[key] = matches
                    print(f"      {key}: {matches}")

            result["loans"].append(loan_detail)
            await page.go_back()
            await page.wait_for_timeout(2000)
        except Exception as e:
            print(f"    ⚠ Detail {i}: {e}")

    return result


async def main():
    from playwright.async_api import async_playwright

    pw = await async_playwright().start()
    browser = await pw.chromium.connect_over_cdp("http://localhost:9222")
    ctx = browser.contexts[0]

    results = {}

    # Find pages by URL
    ca_page = None
    bourso_page = None
    for page in ctx.pages:
        url = page.url.lower()
        if "credit-agricole" in url:
            ca_page = page
        elif "bourso" in url:
            bourso_page = page

    if ca_page:
        print("=== Crédit Agricole ===")
        results["credit_agricole"] = await scrape_ca_loan_details(ca_page)
    else:
        print("⚠ No CA page found — open CA tab first")

    if bourso_page:
        print("\n=== Boursobank ===")
        results["boursobank"] = await scrape_bourso_loan_details(bourso_page)
    else:
        print("⚠ No Bourso page found — open Bourso tab first")

    # Save
    out = DATA_DIR / f"loan_details_{date.today()}.json"
    with open(out, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n✅ Saved → {out}")

    await pw.stop()


if __name__ == "__main__":
    asyncio.run(main())
