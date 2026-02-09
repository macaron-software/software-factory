"""
Finary Clone — API Server
Serves real scraped patrimoine data to the Next.js frontend.
Reads from scrapers/data/patrimoine_complet_*.json
"""
import json
import math
import uuid
import random
from pathlib import Path
from datetime import date, timedelta
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Finary Clone API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Load Data ────────────────────────────────────────────────────────────────

DATA_DIR = Path(__file__).resolve().parent.parent / "scrapers" / "data"

def load_patrimoine():
    files = sorted(DATA_DIR.glob("patrimoine_complet_*.json"), reverse=True)
    if not files:
        raise FileNotFoundError("No patrimoine_complet_*.json found in scrapers/data/")
    with open(files[0]) as f:
        return json.load(f)

P = load_patrimoine()

# ─── Sector/Country mapping for diversification ──────────────────────────────

SECTOR_MAP = {
    "US0231351067": ("Technology", "US"),       # Amazon
    "NL0000226223": ("Semiconductors", "NL"),   # STMicro
    "FR0000120321": ("Consumer", "FR"),          # L'Oreal
    "CNE100000296": ("Automotive", "CN"),        # BYD
    "US60770K1079": ("Healthcare", "US"),        # Moderna
    "DE0008404005": ("Finance", "DE"),           # Allianz
    "US30231G1022": ("Energy", "US"),            # Exxon
    "FR0000121014": ("Luxury", "FR"),            # LVMH
    "US7561091049": ("Real Estate", "US"),       # Realty Income
    "US46120E6023": ("Healthcare", "US"),        # Intuitive Surgical
    "FR0000120271": ("Energy", "FR"),            # TotalEnergies
    "US4781601046": ("Healthcare", "US"),        # J&J
    "US29355A1079": ("Energy", "US"),            # Enphase
    "US72919P2020": ("Energy", "US"),            # Plug Power
    "FR0000120578": ("Healthcare", "FR"),        # Sanofi
    "IE00B3WJKG14": ("Technology", "IE"),        # S&P 500 IT ETF
    "US58733R1023": ("Technology", "BR"),        # MercadoLibre
    "FR0013227113": ("Semiconductors", "FR"),    # Soitec
    "CA1363751027": ("Industrials", "CA"),       # CN Railway
    "US81141R1005": ("Technology", "SG"),        # Sea
    "DE0007030009": ("Defense", "DE"),           # Rheinmetall
    "US4612021034": ("Technology", "US"),        # Intuit
    "US5949181045": ("Technology", "US"),        # MSFT
    "US02079K3059": ("Technology", "US"),        # GOOGL
    "US67066G1040": ("Semiconductors", "US"),    # NVDA
}

COUNTRY_NAMES = {
    "US": "États-Unis", "FR": "France", "DE": "Allemagne", "NL": "Pays-Bas",
    "CN": "Chine", "IE": "Irlande", "BR": "Brésil", "CA": "Canada", "SG": "Singapour",
}

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _id(prefix: str, i: int) -> str:
    return f"{prefix}-{i:04d}"

EUR_USD = 1.08  # approximate

# ─── Build accounts list ─────────────────────────────────────────────────────

def build_accounts():
    accounts = []
    i = 0

    # Trade Republic
    tr = P["trade_republic"]
    i += 1
    accounts.append({
        "id": _id("acc", i), "institution_id": "trade_republic",
        "institution": "trade_republic", "institution_display_name": "Trade Republic",
        "external_id": None, "name": "CTO Trade Republic",
        "account_type": "cto", "currency": "EUR",
        "balance": tr["total_account_value"], "is_pro": False,
        "updated_at": P["date"],
    })

    # IBKR
    ibkr = P["ibkr"]
    i += 1
    accounts.append({
        "id": _id("acc", i), "institution_id": "ibkr",
        "institution": "ibkr", "institution_display_name": "Interactive Brokers",
        "external_id": ibkr["account_id"], "name": "CTO Margin IBKR",
        "account_type": "cto", "currency": "EUR",
        "balance": ibkr["net_liquidation_eur"], "is_pro": False,
        "updated_at": P["date"],
    })

    # Boursobank
    b = P["boursobank"]
    for key, acc_data in b["accounts"].items():
        i += 1
        accounts.append({
            "id": _id("acc", i), "institution_id": "boursobank",
            "institution": "boursobank", "institution_display_name": "Boursobank",
            "external_id": acc_data.get("account"), "name": acc_data["label"],
            "account_type": acc_data.get("type", "checking").lower(),
            "currency": "EUR", "balance": acc_data["balance"],
            "is_pro": False, "updated_at": P["date"],
        })
    for key, acc_data in b["children_accounts"].items():
        i += 1
        accounts.append({
            "id": _id("acc", i), "institution_id": "boursobank",
            "institution": "boursobank", "institution_display_name": "Boursobank",
            "external_id": None, "name": acc_data["label"],
            "account_type": "savings" if "livret" in key.lower() else "checking",
            "currency": "EUR", "balance": acc_data["balance"],
            "is_pro": False, "updated_at": P["date"],
        })
    for loan in b["loans"]:
        i += 1
        accounts.append({
            "id": _id("acc", i), "institution_id": "boursobank",
            "institution": "boursobank", "institution_display_name": "Boursobank",
            "external_id": None, "name": loan["name"],
            "account_type": "loan", "currency": "EUR",
            "balance": -loan["remaining"], "is_pro": False,
            "updated_at": P["date"],
        })

    # Crédit Agricole
    ca = P["credit_agricole"]
    ca_acc = ca["accounts"]["checking"]
    i += 1
    accounts.append({
        "id": _id("acc", i), "institution_id": "credit_agricole",
        "institution": "credit_agricole", "institution_display_name": "Crédit Agricole",
        "external_id": ca_acc.get("account"), "name": ca_acc["label"],
        "account_type": "checking", "currency": "EUR",
        "balance": ca_acc["balance"], "is_pro": False,
        "updated_at": P["date"],
    })
    for credit in ca["credits"]:
        i += 1
        accounts.append({
            "id": _id("acc", i), "institution_id": "credit_agricole",
            "institution": "credit_agricole", "institution_display_name": "Crédit Agricole",
            "external_id": credit.get("account"), "name": credit["name"],
            "account_type": "loan", "currency": "EUR",
            "balance": -credit["remaining"], "is_pro": False,
            "updated_at": P["date"],
            # Extra loan fields
            "loan_borrowed": credit["borrowed"],
            "loan_remaining": credit["remaining"],
            "loan_monthly": credit["monthly_payment"],
            "loan_rate": credit.get("rate"),
            "loan_type": credit.get("type"),
        })

    return accounts

ACCOUNTS = build_accounts()

# ─── Build positions ─────────────────────────────────────────────────────────

def build_positions():
    positions = []
    total_value = 0

    # TR positions
    for i, pos in enumerate(P["trade_republic"]["positions"]):
        val = pos["current_value_eur"]
        cost = pos["shares"] * pos["avg_price_eur"] if pos["shares"] and pos["avg_price_eur"] else 0
        pnl = pos["unrealized_pnl_eur"]
        pnl_pct = pos["unrealized_pnl_pct"]
        total_value += val
        isin = pos["isin"]
        sector, country = SECTOR_MAP.get(isin, ("Other", "??"))

        positions.append({
            "id": _id("pos", i + 1),
            "account_id": "acc-0001",  # TR
            "ticker": isin[:6] if not pos["name"] else pos["name"].split()[0][:6].upper(),
            "isin": isin,
            "name": pos["name"],
            "quantity": pos["shares"],
            "avg_cost": pos["avg_price_eur"],
            "current_price": round(val / pos["shares"], 2) if pos["shares"] else None,
            "currency": "EUR",
            "asset_type": "stock",
            "sector": sector,
            "country": country,
            "value_native": val,
            "value_eur": val,
            "pnl_native": pnl,
            "pnl_eur": pnl,
            "pnl_pct": pnl_pct,
            "weight_pct": 0,  # computed after
            "pe_ratio": pos.get("pe_ratio"),
            "beta": pos.get("beta"),
            "source": "Trade Republic",
        })

    # IBKR positions
    for j, pos in enumerate(P["ibkr"]["positions"]):
        val_usd = pos["market_value_usd"]
        val_eur = round(val_usd / EUR_USD, 2)
        cost_usd = pos["cost_basis_usd"]
        pnl_usd = pos["unrealized_pnl_usd"]
        pnl_eur = round(pnl_usd / EUR_USD, 2)
        pnl_pct = round(pnl_usd / cost_usd * 100, 2) if cost_usd else 0
        total_value += val_eur
        isin = pos["isin"]
        sector, country = SECTOR_MAP.get(isin, ("Other", "US"))

        positions.append({
            "id": _id("pos", 100 + j),
            "account_id": "acc-0002",  # IBKR
            "ticker": pos["symbol"],
            "isin": isin,
            "name": pos["symbol"],
            "quantity": pos["quantity"],
            "avg_cost": pos["avg_price_usd"],
            "current_price": pos["last_price_usd"],
            "currency": "USD",
            "asset_type": "stock",
            "sector": sector,
            "country": country,
            "value_native": val_usd,
            "value_eur": val_eur,
            "pnl_native": pnl_usd,
            "pnl_eur": pnl_eur,
            "pnl_pct": pnl_pct,
            "weight_pct": 0,
            "dividend_yield_pct": pos.get("dividend_yield_pct"),
            "ex_dividend_date": pos.get("ex_dividend_date"),
            "source": "Interactive Brokers",
        })

    # Compute weights
    for pos in positions:
        pos["weight_pct"] = round(pos["value_eur"] / total_value * 100, 2) if total_value else 0

    # Sort by value descending
    positions.sort(key=lambda x: x["value_eur"], reverse=True)
    return positions

POSITIONS = build_positions()

# ─── API Routes ───────────────────────────────────────────────────────────────

@app.get("/api/v1/networth")
def get_networth():
    t = P["totals"]
    tr_val = P["trade_republic"]["total_account_value"]
    ibkr_val = P["ibkr"]["net_liquidation_eur"]

    return {
        "net_worth": t["net_worth"],
        "total_assets": t["total_assets"],
        "total_liabilities": t["total_debt"],
        "breakdown": {
            "cash": t["total_bank_liquid"],
            "savings": P["boursobank"]["total_savings"],
            "investments": t["total_investments"],
            "real_estate": t["total_real_estate"],
        },
        "by_institution": [
            {"name": "ibkr", "display_name": "Interactive Brokers", "total": ibkr_val},
            {"name": "credit_agricole", "display_name": "Crédit Agricole", "total": round(P["credit_agricole"]["accounts"]["checking"]["balance"] + P["credit_agricole"]["total_debt"], 2)},
            {"name": "boursobank", "display_name": "Boursobank", "total": round(P["boursobank"]["total_liquid"] + P["boursobank"]["total_savings"] + P["boursobank"]["total_loans"], 2)},
            {"name": "trade_republic", "display_name": "Trade Republic", "total": tr_val},
            {"name": "sca", "display_name": "SCA La Désirade", "total": P["sca_la_desirade"]["your_share_property_value"]},
        ],
        "variation_day": None,
        "variation_month": None,
    }


@app.get("/api/v1/networth/history")
def get_networth_history(limit: int = Query(365)):
    """Generate realistic net worth history seeded from real current values."""
    today = date.today()
    t = P["totals"]
    history = []

    # Current values
    investments_now = t["total_investments"]
    cash_now = t["total_bank_liquid"]
    re_now = t["total_real_estate"]
    debt_now = t["total_debt"]

    # Walk backward from today
    random.seed(42)  # deterministic
    inv = investments_now
    cash = cash_now
    re = re_now

    points = []
    for i in range(limit):
        d = today - timedelta(days=i)

        # Go backward: subtract growth
        if i > 0:
            inv *= 1 - (random.random() - 0.47) * 0.008
            cash += (random.random() - 0.5) * 50
            if d.day == 1:
                cash -= 3000  # salary removal going back
                cash += 2000  # expenses removal going back

        total_assets = inv + cash + re
        net = total_assets - debt_now

        points.append({
            "date": d.isoformat(),
            "total_assets": round(total_assets, 2),
            "total_liabilities": round(debt_now, 2),
            "net_worth": round(net, 2),
            "breakdown": {
                "investments": round(inv, 2),
                "cash": round(cash, 2),
                "real_estate": round(re, 2),
            },
        })

    points.reverse()
    return points[:limit]


@app.get("/api/v1/accounts")
def get_accounts():
    return ACCOUNTS


@app.get("/api/v1/accounts/{account_id}")
def get_account(account_id: str):
    for a in ACCOUNTS:
        if a["id"] == account_id:
            return a
    return {"error": "not found"}


@app.get("/api/v1/portfolio")
def get_portfolio():
    return POSITIONS


@app.get("/api/v1/portfolio/allocation")
def get_allocation():
    # By sector
    sectors: dict[str, float] = {}
    countries: dict[str, float] = {}
    currencies: dict[str, float] = {}
    asset_types: dict[str, float] = {}

    total = sum(p["value_eur"] for p in POSITIONS)

    for p in POSITIONS:
        s = p.get("sector", "Other")
        sectors[s] = sectors.get(s, 0) + p["value_eur"]

        c = COUNTRY_NAMES.get(p.get("country", ""), p.get("country", "Other"))
        countries[c] = countries.get(c, 0) + p["value_eur"]

        cur = p["currency"]
        currencies[cur] = currencies.get(cur, 0) + p["value_eur"]

        at = p.get("asset_type", "stock")
        asset_types[at] = asset_types.get(at, 0) + p["value_eur"]

    def to_items(d):
        return sorted(
            [{"label": k, "value_eur": round(v, 2), "percentage": round(v / total * 100, 1)} for k, v in d.items()],
            key=lambda x: -x["value_eur"]
        )

    return {
        "by_sector": to_items(sectors),
        "by_country": to_items(countries),
        "by_currency": to_items(currencies),
        "by_asset_type": to_items(asset_types),
    }


@app.get("/api/v1/portfolio/dividends")
def get_dividends():
    divs = []
    for p in POSITIONS:
        dy = p.get("dividend_yield_pct")
        if dy and dy != "?":
            try:
                rate = float(dy) / 100
            except (ValueError, TypeError):
                continue
            divs.append({
                "id": f"div-{p['id']}",
                "position_id": p["id"],
                "ex_date": p.get("ex_dividend_date"),
                "pay_date": None,
                "amount_per_share": round(p["current_price"] * rate, 4) if p["current_price"] else 0,
                "total_amount": round(p["value_eur"] * rate, 2),
                "currency": p["currency"],
            })
    return divs


@app.get("/api/v1/analytics/diversification")
def get_diversification():
    sectors = set()
    countries = set()
    max_w = 0
    max_t = ""
    for p in POSITIONS:
        sectors.add(p.get("sector", "Other"))
        countries.add(p.get("country", "??"))
        if p["weight_pct"] > max_w:
            max_w = p["weight_pct"]
            max_t = p["ticker"]

    # Score: max 100
    n_pos = len(POSITIONS)
    n_sec = len(sectors)
    n_cou = len(countries)
    score = min(100, n_pos * 2 + n_sec * 5 + n_cou * 5 + max(0, 30 - max_w))

    return {
        "score": round(score),
        "max_score": 100,
        "details": {
            "num_positions": n_pos,
            "num_sectors": n_sec,
            "num_countries": n_cou,
            "max_weight_pct": round(max_w, 1),
            "max_weight_ticker": max_t,
        },
    }


@app.get("/api/v1/transactions")
def get_transactions(limit: int = Query(50)):
    return []  # No transaction data scraped yet


@app.get("/api/v1/accounts/{account_id}/transactions")
def get_account_transactions(account_id: str, limit: int = Query(50)):
    return []


@app.get("/api/v1/budget/monthly")
def get_monthly_budget(limit: int = Query(12)):
    # Placeholder with monthly loan payments as expenses
    monthly_costs = P["totals"]["total_monthly_costs"]
    months = []
    today = date.today()
    for i in range(limit - 1, -1, -1):
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        months.append({
            "month": f"{y}-{m:02d}",
            "income": 0,
            "expenses": round(monthly_costs, 2),
            "savings_rate": 0,
        })
    return months


@app.get("/api/v1/budget/categories")
def get_category_spending(limit: int = Query(3)):
    ca_credits = P["credit_agricole"]["monthly_payments"]
    margin = P["ibkr"]["margin_loan"]["monthly_cost_estimate_eur"]
    bourso_loans = round((P["boursobank"]["loans"][0]["remaining"] + P["boursobank"]["loans"][1]["remaining"]) / 24, 2)
    return [
        {"category": "credits_immobilier", "total": round(ca_credits * limit, 2), "count": 2},
        {"category": "marge_ibkr", "total": round(margin * limit, 2), "count": limit},
        {"category": "prets_perso", "total": round(bourso_loans * limit, 2), "count": 2},
    ]


@app.get("/api/v1/market/fx")
def get_fx_rates():
    return [
        {"date": date.today().isoformat(), "base_currency": "EUR", "quote_currency": "USD", "rate": EUR_USD},
    ]


@app.get("/api/v1/market/quote/{ticker}")
def get_quote(ticker: str):
    return []


@app.get("/api/v1/market/history/{ticker}")
def get_history(ticker: str, limit: int = Query(365)):
    return []


@app.get("/api/v1/alerts")
def get_alerts():
    return []


# ─── Extra: Patrimoine & Loans detail endpoints ──────────────────────────────

@app.get("/api/v1/patrimoine")
def get_patrimoine():
    """Full patrimoine data including SCA, property, loans."""
    return P


@app.get("/api/v1/loans")
def get_loans():
    """All loans across institutions."""
    loans = []
    for credit in P["credit_agricole"]["credits"]:
        loans.append({
            "institution": "Crédit Agricole",
            "name": credit["name"],
            "type": credit.get("type", "unknown"),
            "borrowed": credit["borrowed"],
            "remaining": credit["remaining"],
            "monthly_payment": credit["monthly_payment"],
            "rate": credit.get("rate"),
            "start_date": credit.get("start_date"),
            "status": credit.get("status"),
        })
    for loan in P["boursobank"]["loans"]:
        loans.append({
            "institution": "Boursobank",
            "name": loan["name"],
            "type": loan.get("type", "consumer"),
            "borrowed": None,
            "remaining": loan["remaining"],
            "monthly_payment": None,
            "rate": None,
        })
    # IBKR margin
    ml = P["ibkr"]["margin_loan"]
    loans.append({
        "institution": "Interactive Brokers",
        "name": "Prêt sur marge",
        "type": "margin",
        "borrowed": None,
        "remaining": ml["amount_eur"],
        "monthly_payment": ml["monthly_cost_estimate_eur"],
        "rate": ml["interest_rate_usd"],
    })
    return loans


@app.get("/api/v1/sca")
def get_sca():
    """SCA La Désirade data."""
    return P["sca_la_desirade"]


@app.get("/api/v1/costs")
def get_costs():
    """Monthly recurring costs breakdown."""
    ml = P["ibkr"]["margin_loan"]
    ca = P["credit_agricole"]
    return {
        "monthly_total": P["totals"]["total_monthly_costs"],
        "breakdown": [
            {"name": "PAS 2 (immo)", "amount": 90.32, "type": "credit"},
            {"name": "PACP (conso)", "amount": 73.69, "type": "credit"},
            {"name": "Marge IBKR (~5.83%)", "amount": ml["monthly_cost_estimate_eur"], "type": "margin"},
        ],
        "annual_fees": {
            "tr_trading": round(len(P["trade_republic"]["positions"]) * 1.0, 2),
            "ibkr_commissions_est": 12.0,
            "margin_interest_annual": round(ml["amount_eur"] * 0.0583, 2),
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
