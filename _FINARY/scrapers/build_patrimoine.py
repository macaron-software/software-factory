#!/usr/bin/env python3
"""
Build patrimoine_complet JSON from individual scraped files.
Reads: extraction_complete, bourso_deep, ca_deep + SCA data (embedded).
Outputs: scrapers/data/patrimoine_complet_YYYY-MM-DD.json

Usage:
    python3 scrapers/build_patrimoine.py              # today's date
    python3 scrapers/build_patrimoine.py 2026-02-09   # specific date
"""
import json
import sys
from datetime import date, datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"

# ─── SCA La Désirade (stable data, updated manually) ──────────────────────
SCA = {
    "type": "sca",
    "name": "SCA La Désirade",
    "role": "Associé - Groupe 1",
    "parts": 352078,
    "total_parts": 695873,
    "ownership_pct": 50.595,
    "property": {
        "address": "40 chemin de la désirade, 34790 GRABELS",
        "type": "Maison",
        "rooms": 4,
        "surface_m2": 110,
        "terrain_value_book": 282000,
        "purchase_date": "08/2021",
        "dpe_score": "D",
        "bourso_estimate": 505254,
        "bourso_estimate_range": {"low": 445129, "high": 565380},
        "price_per_m2_estimate": 4593.22,
    },
    "financials": {
        "capital_souscrit": 352078,
        "capital_verse": 286711.09,
        "cca_avances": 31517.56,
        "total_verse": 318228.65,
        "total_charges_qp": 312694.10,
        "af_impayes": 11930.01,
        "solde_net": 5534.55,
        "bank_account_balance": 3002.11,
    },
    "co_associate": {
        "name": "Mme Françoise BEAUSSIER",
        "parts": 343795,
        "ownership_pct": 49.405,
    },
    "charges_breakdown": {
        "terrain_qp": 142678.33,
        "travaux_groupe1": 136738.65,
        "travaux_communs_qp": 667.86,
        "honoraires_total_qp": 19209.65,
        "taxes_total_qp": 6990.42,
        "frais_bancaires_qp": 511.25,
        "eau_qp": 5494.76,
        "electricite_qp": 264.30,
        "divers_qp": 138.88,
    },
}


def load_json(name: str, d: str) -> dict | None:
    path = DATA_DIR / f"{name}_{d}.json"
    if not path.exists():
        print(f"  ⚠️  Missing {path.name}")
        return None
    with open(path) as f:
        return json.load(f)


def build(d: str) -> dict:
    """Build patrimoine complet for date string YYYY-MM-DD."""
    print(f"🔨 Building patrimoine for {d}")

    ext = load_json("extraction_complete", d)
    bourso = load_json("bourso_deep", d)
    ca = load_json("ca_deep", d)
    tr_deep = load_json("trade_republic_deep", d)

    if not ext:
        raise FileNotFoundError(f"extraction_complete_{d}.json required")

    # ─── Trade Republic ───────────────────────────────────────────
    # Load previous patrimoine as fallback for incomplete scrapes
    prev = None
    prev_files = sorted(DATA_DIR.glob("patrimoine_complet_*.json"), reverse=True)
    for pf in prev_files:
        if pf.stem != f"patrimoine_complet_{d}":
            with open(pf) as f:
                prev = json.load(f)
            break
    # Also try same-day file as fallback
    if not prev:
        same_day = DATA_DIR / f"patrimoine_complet_{d}.json"
        if same_day.exists():
            with open(same_day) as f:
                prev = json.load(f)

    # Index previous TR positions by ISIN
    prev_tr = {}
    if prev and "trade_republic" in prev:
        for p in prev["trade_republic"].get("positions", []):
            prev_tr[p["isin"]] = p

    tr_positions = []
    for p in ext["tr_positions"]:
        if "isin" not in p or "total_value" not in p:
            # Incomplete scrape — use previous data if available
            fb = prev_tr.get(p.get("isin", ""))
            if not fb:
                # Try to find by name in previous
                for pp in prev_tr.values():
                    if pp["name"] == p.get("name"):
                        fb = pp
                        break
            if fb:
                tr_positions.append(fb)
            continue

        invested = p["total_value"] - p["performance_eur"]
        avg_price = round(invested / p["shares"], 2) if p["shares"] else 0
        tr_positions.append({
            "name": p["name"],
            "isin": p["isin"],
            "shares": p["shares"],
            "avg_price_eur": avg_price,
            "current_value_eur": p["total_value"],
            "unrealized_pnl_eur": p["performance_eur"],
            "unrealized_pnl_pct": p["performance_pct"],
            "portfolio_weight_pct": p["portfolio_pct"],
            "pe_ratio": p.get("pe_ratio"),
            "beta": p.get("beta"),
            "dividend_yield_pct": p.get("dividend_yield_pct"),
        })

    tr_portfolio = sum(p["current_value_eur"] for p in tr_positions)
    tr_cash = tr_deep["cash"] if tr_deep else 0
    tr_invested = sum(p["shares"] * p["avg_price_eur"] for p in tr_positions if p["shares"] and p["avg_price_eur"])
    tr_pnl = sum(p["unrealized_pnl_eur"] for p in tr_positions)

    trade_republic = {
        "type": "cto",
        "currency": "EUR",
        "cash": tr_cash,
        "portfolio_value": round(tr_portfolio, 2),
        "total_invested": round(tr_invested, 2),
        "unrealized_pnl": round(tr_pnl, 2),
        "total_account_value": round(tr_portfolio + tr_cash, 2),
        "fees_per_trade": 1.0,
        "positions": tr_positions,
    }

    # ─── IBKR ─────────────────────────────────────────────────────
    ibkr_extras = ext.get("ibkr_extras", {})
    ibkr_positions = []
    for p in ext["ibkr_positions"]:
        ibkr_positions.append({
            "symbol": p["symbol"],
            "isin": p["isin"],
            "quantity": p["quantity"],
            "last_price_usd": p["last_price_usd"],
            "avg_price_usd": p["avg_price_usd"],
            "cost_basis_usd": p["cost_basis_usd"],
            "market_value_usd": p["market_value_usd"],
            "unrealized_pnl_usd": p["unrealized_pnl_usd"],
            "dividend_yield_pct": p.get("dividend_yield_pct"),
            "ex_dividend_date": p.get("ex_dividend_date"),
        })

    ibkr = {
        "type": "cto_margin",
        "account_id": "U13393818",
        "currency_base": "EUR",
        "net_liquidation_eur": ibkr_extras.get("net_liquidation_eur", 0),
        "buying_power_eur": ibkr_extras.get("buying_power_eur", 0),
        "maintenance_margin_eur": ibkr_extras.get("maintenance_margin", 0),
        "excess_liquidity_eur": ibkr_extras.get("excess_liquidity", 0),
        "cash": {
            "total_eur": ibkr_extras.get("total_cash_eur", 0),
            "eur": ibkr_extras.get("cash_eur", 0),
            "usd": ibkr_extras.get("cash_usd", 0),
        },
        "margin_loan_usd": abs(ibkr_extras.get("cash_usd", 0)),
        "margin_interest_rate": ibkr_extras.get("margin_interest_rate", "5.83%"),
        "positions": ibkr_positions,
    }

    # ─── Boursobank ───────────────────────────────────────────────
    # Parse bourso accounts
    checking_balance = 19.33
    pea_balance = 100.0
    children_checking = 351.74
    livret_a = 7726.18
    bourso_loans = []

    if bourso:
        for acc in bourso.get("accounts", []):
            if isinstance(acc, dict):
                if "pea_total" in acc: pea_balance = acc["pea_total"]
                if "livret_a" in acc: livret_a = acc["livret_a"]

        for loan in bourso.get("loans", []):
            bourso_loans.append({
                "name": loan.get("name", "Prêt personnel"),
                "remaining": loan.get("remaining", 0),
                "monthly_payment": loan.get("monthly_payment", 0),
                "rate": loan.get("rate"),
            })

    # Fallback to known values if no loans in deep scrape
    if not bourso_loans:
        bourso_loans = [
            {"name": "PRÊT PERSONNEL 1", "remaining": 1448.78, "monthly_payment": 0, "rate": None},
            {"name": "PRÊT PERSONNEL 2", "remaining": 6284.35, "monthly_payment": 0, "rate": None},
        ]

    total_liquid = round(checking_balance + children_checking, 2)
    total_savings = round(pea_balance + livret_a, 2)
    total_loans = -round(sum(l["remaining"] for l in bourso_loans), 2)

    boursobank = {
        "type": "bank",
        "accounts": {
            "checking": {"label": "BOURSORAMA ESSENTIEL SYLVAIN", "balance": checking_balance, "type": "checking"},
            "pea": {"label": "PEA LEGLAND", "balance": pea_balance, "type": "PEA"},
        },
        "children_accounts": {
            "checking_nathael": {"label": "BOURSORAMA ESSENTIEL NATHAEL", "balance": children_checking},
            "livret_a_nathael": {"label": "LIVRET A NATHAEL", "balance": livret_a},
        },
        "loans": bourso_loans,
        "total_liquid": total_liquid,
        "total_savings": total_savings,
        "total_loans": total_loans,
    }

    # ─── Crédit Agricole ──────────────────────────────────────────
    ca_checking = 2.34
    ca_credits = []

    if ca:
        for acc in ca.get("accounts", []):
            if isinstance(acc, dict) and "balance" in acc:
                ca_checking = acc["balance"]

        for c in ca.get("credits", []):
            if not isinstance(c, dict) or "name" not in c:
                continue
            if c["name"].startswith("©"):
                continue
            ca_credits.append({
                "name": c["name"],
                "account": c.get("account_number", ""),
                "type": "PTZ" if "0%" in c["name"] else "PAS" if "Accession" in c["name"] else "consumer",
                "borrowed": c.get("borrowed", 0),
                "remaining": c.get("remaining", 0),
                "monthly_payment": c.get("monthly_payment", 0),
                "rate": c.get("rate"),
                "insurance_monthly": c.get("insurance_monthly", 0),
                "start_date": c.get("start_date"),
                "status": c.get("status"),
            })

    if not ca_credits:
        # Fallback
        ca_credits = [
            {"name": "PTZ Ministère du Logement", "account": "00004690214", "type": "PTZ",
             "borrowed": 102000, "remaining": 102000, "monthly_payment": 0, "rate": "0%",
             "insurance_monthly": 0, "start_date": "08/2021", "status": "Différé total"},
            {"name": "Prêt d'Accession Sociale 1", "account": "00004690213", "type": "PAS",
             "borrowed": 10000, "remaining": 10000, "monthly_payment": 0,
             "rate": "variable (indexé Euribor)", "insurance_monthly": 0, "start_date": "08/2021"},
            {"name": "Prêt d'Accession Sociale 2", "account": "00004690212", "type": "PAS",
             "borrowed": 138290, "remaining": 110594.85, "monthly_payment": 90.32,
             "rate": "variable (indexé Euribor)", "insurance_monthly": 0, "start_date": "08/2021"},
            {"name": "Prêt Conso Personnel (PACP)", "account": "73140424333", "type": "consumer",
             "borrowed": 5000, "remaining": 1803.50, "monthly_payment": 73.69,
             "rate": None, "insurance_monthly": 0},
        ]

    ca_total_debt = -sum(c["remaining"] for c in ca_credits)
    ca_monthly = sum(c["monthly_payment"] for c in ca_credits)

    credit_agricole = {
        "type": "bank",
        "region": "Languedoc",
        "accounts": {
            "checking": {"label": "COMPTE CHEQUE", "balance": ca_checking, "account": "00040636024"},
        },
        "credits": ca_credits,
        "total_debt": ca_total_debt,
        "monthly_payments": ca_monthly,
    }

    # ─── SCA ──────────────────────────────────────────────────────
    sca = dict(SCA)
    sca["your_share_property_value"] = round(
        sca["property"]["bourso_estimate"] * sca["ownership_pct"] / 100, 2
    )

    # ─── Totals ───────────────────────────────────────────────────
    total_investments = trade_republic["total_account_value"] + ibkr["net_liquidation_eur"]
    total_bank_liquid = boursobank["total_liquid"] + boursobank["total_savings"] + ca_checking
    total_real_estate = sca["your_share_property_value"]
    total_assets = total_investments + total_bank_liquid + total_real_estate
    total_debt = abs(ca_total_debt) + abs(total_loans)
    ibkr_margin_monthly = round(abs(ibkr["cash"]["usd"]) * 0.0583 / 12 / 1.08, 2)

    totals = {
        "total_investments": round(total_investments, 2),
        "total_bank_liquid": round(total_bank_liquid, 2),
        "total_real_estate": round(total_real_estate, 2),
        "total_assets": round(total_assets, 2),
        "total_debt": round(total_debt, 2),
        "net_worth": round(total_assets - total_debt, 2),
        "monthly_loan_payments": round(ca_monthly, 2),
        "monthly_margin_cost": ibkr_margin_monthly,
    }

    patrimoine = {
        "date": d,
        "timestamp": datetime.now().isoformat(),
        "trade_republic": trade_republic,
        "ibkr": ibkr,
        "boursobank": boursobank,
        "credit_agricole": credit_agricole,
        "sca_la_desirade": sca,
        "totals": totals,
    }

    # Save
    out_path = DATA_DIR / f"patrimoine_complet_{d}.json"
    out_path.write_text(json.dumps(patrimoine, indent=2, ensure_ascii=False))
    print(f"✅ Saved {out_path.name}")
    print(f"   Net worth: {totals['net_worth']:,.2f}€")
    print(f"   Assets: {totals['total_assets']:,.2f}€  |  Debt: {totals['total_debt']:,.2f}€")
    print(f"   Positions: {len(tr_positions)} TR + {len(ibkr_positions)} IBKR")
    return patrimoine


if __name__ == "__main__":
    target_date = sys.argv[1] if len(sys.argv) > 1 else date.today().isoformat()
    build(target_date)
